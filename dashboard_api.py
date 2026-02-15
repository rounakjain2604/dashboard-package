"""
Dashboard API — Flask backend that wraps the IB-Grade DCF Engine pipeline
and returns full model results as JSON for the interactive dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory

from src.dcf_engine.config import (
    DCFEngineConfig,
    CompanyInfo,
    ForecastConfig,
    WACCConfig,
    ValuationConfig,
    MonteCarloConfig,
    SensitivityConfig,
    CompsConfig,
    DebtTranche,
    ScenarioOverrides,
)
from src.dcf_engine.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# Resolve paths relative to this file so it works both locally and on Vercel
_BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(_BASE_DIR / "static"),
    template_folder=str(_BASE_DIR / "templates"),
)

# Detect Vercel environment
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


# ── Helpers ──────────────────────────────────────────────────────────

def _safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _df_to_records(df: pd.DataFrame | None) -> list[dict]:
    """Convert DataFrame → list of dicts, replacing NaN/Inf with None."""
    if df is None or df.empty:
        return []
    df = df.copy()
    for col in df.columns:
        if df[col].dtype.kind == 'f':
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
    return json.loads(df.to_json(orient="records", double_precision=2))


def _build_config_from_payload(data: dict) -> DCFEngineConfig:
    """Build DCFEngineConfig from the front-end JSON payload."""
    company = CompanyInfo(
        name=data.get("company_name", "Target Company"),
        ticker=data.get("ticker") or None,
        industry=data.get("industry", ""),
        currency=data.get("currency", "USD"),
        analyst_name=data.get("analyst_name", "Dashboard User"),
    )

    fc = data.get("forecast", {})
    forecast = ForecastConfig(
        projection_years=int(fc.get("projection_years", 5)),
        revenue_method=fc.get("revenue_method", "cagr"),
        revenue_cagr=float(fc.get("revenue_cagr", 0.08)),
        revenue_yoy=[float(x) for x in fc.get("revenue_yoy", [0.08, 0.07, 0.06, 0.05, 0.05])],
        cogs_pct_revenue=float(fc.get("cogs_pct_revenue", 0.45)),
        sga_pct_revenue=float(fc.get("sga_pct_revenue", 0.20)),
        other_opex_pct_revenue=float(fc.get("other_opex_pct_revenue", 0.05)),
        depreciation_rate=float(fc.get("depreciation_rate", 0.10)),
        amortisation_pct_revenue=float(fc.get("amortisation_pct_revenue", 0.005)),
        capex_method=fc.get("capex_method", "pct_revenue"),
        capex_pct_revenue=float(fc.get("capex_pct_revenue", 0.04)),
        dso=float(fc.get("dso", 45)),
        dio=float(fc.get("dio", 50)),
        dpo=float(fc.get("dpo", 40)),
        prepaid_pct_revenue=float(fc.get("prepaid_pct_revenue", 0.005)),
        accrued_pct_revenue=float(fc.get("accrued_pct_revenue", 0.01)),
        tax_rate=float(fc.get("tax_rate", 0.25)),
        dividend_payout_ratio=float(fc.get("dividend_payout_ratio", 0.0)),
    )

    wc = data.get("wacc", {})
    wacc = WACCConfig(
        risk_free_rate=float(wc.get("risk_free_rate", 0.042)),
        equity_risk_premium=float(wc.get("equity_risk_premium", 0.055)),
        beta=float(wc.get("beta", 1.1)),
        size_premium=float(wc.get("size_premium", 0.0)),
        country_risk_premium=float(wc.get("country_risk_premium", 0.0)),
        target_debt_weight=float(wc.get("target_debt_weight", 0.30)),
        target_equity_weight=float(wc.get("target_equity_weight", 0.70)),
        interest_coverage_ratio=float(wc.get("interest_coverage_ratio", 5.0)),
        tax_rate=float(wc.get("tax_rate", 0.25)),
        use_live_data=bool(wc.get("use_live_data", False)),
    )

    vc = data.get("valuation", {})
    valuation = ValuationConfig(
        terminal_growth_rate=float(vc.get("terminal_growth_rate", 0.025)),
        exit_ev_ebitda_multiple=float(vc.get("exit_ev_ebitda_multiple", 10.0)),
        discount_convention=vc.get("discount_convention", "mid_year"),
        gordon_weight=float(vc.get("gordon_weight", 0.50)),
        cash=float(vc.get("cash", 0)),
        debt=float(vc.get("debt", 0)),
        minority_interest=float(vc.get("minority_interest", 0)),
        preferred_stock=float(vc.get("preferred_stock", 0)),
        fully_diluted_shares=float(vc.get("fully_diluted_shares", 1_000_000)),
        gdp_growth_cap=float(vc.get("gdp_growth_cap", 0.035)),
        terminal_spread_floor_bps=float(vc.get("terminal_spread_floor_bps", 50.0)),
    )

    mc = data.get("monte_carlo", {})
    monte_carlo = MonteCarloConfig(
        iterations=int(mc.get("iterations", 10_000)),
        revenue_growth_mean=float(mc.get("revenue_growth_mean", 0.08)),
        revenue_growth_std=float(mc.get("revenue_growth_std", 0.03)),
        ebitda_margin_mean=float(mc.get("ebitda_margin_mean", 0.20)),
        ebitda_margin_std=float(mc.get("ebitda_margin_std", 0.05)),
        wacc_mean=float(mc.get("wacc_mean", 0.10)),
        wacc_std=float(mc.get("wacc_std", 0.02)),
        terminal_growth_mean=float(mc.get("terminal_growth_mean", 0.025)),
        terminal_growth_std=float(mc.get("terminal_growth_std", 0.01)),
        exit_multiple_mean=float(mc.get("exit_multiple_mean", 10.0)),
        exit_multiple_std=float(mc.get("exit_multiple_std", 2.0)),
        seed=int(mc.get("seed", 42)),
    )

    sc = data.get("sensitivity", {})
    sensitivity = SensitivityConfig(
        wacc_range=[float(x) for x in sc.get("wacc_range", [-0.02, -0.01, 0, 0.01, 0.02])],
        terminal_growth_range=[float(x) for x in sc.get("terminal_growth_range", [-0.01, -0.005, 0, 0.005, 0.01])],
        revenue_growth_range=[float(x) for x in sc.get("revenue_growth_range", [-0.03, -0.015, 0, 0.015, 0.03])],
        ebitda_margin_range=[float(x) for x in sc.get("ebitda_margin_range", [-0.05, -0.025, 0, 0.025, 0.05])],
    )

    comps = CompsConfig(
        peer_tickers=data.get("peer_tickers", []),
        multiples=data.get("multiples", ["EV/Revenue", "EV/EBITDA", "P/E"]),
    )

    tranches_raw = data.get("debt_tranches", [])
    debt_tranches = []
    for t in tranches_raw:
        debt_tranches.append(DebtTranche(
            name=t.get("name", "Term Loan"),
            beginning_balance=float(t.get("beginning_balance", 0)),
            interest_rate=float(t.get("interest_rate", 0.06)),
            annual_amortisation=float(t.get("annual_amortisation", 0)),
            maturity_year=int(t.get("maturity_year", 5)),
            optional_prepayment=float(t.get("optional_prepayment", 0)),
            cash_sweep_pct=float(t.get("cash_sweep_pct", 0)),
        ))

    scenarios_raw = data.get("scenarios", {})
    scenarios = {}
    for k, v in scenarios_raw.items():
        scenarios[k] = ScenarioOverrides(
            name=v.get("name", k),
            revenue_growth_override=v.get("revenue_growth_override"),
            revenue_multiplier=float(v.get("revenue_multiplier", 1.0)),
            ebitda_margin_override=v.get("ebitda_margin_override"),
            margin_delta_bps=float(v.get("margin_delta_bps", 0)),
            wacc_override=v.get("wacc_override"),
            terminal_growth_override=v.get("terminal_growth_override"),
            exit_multiple_override=v.get("exit_multiple_override"),
            working_capital_days_delta=float(v.get("working_capital_days_delta", 0)),
            capex_multiplier=float(v.get("capex_multiplier", 1.0)),
        )
    if not scenarios:
        scenarios = {
            "Base": ScenarioOverrides(name="Base"),
            "Bull": ScenarioOverrides(name="Bull", revenue_multiplier=1.10, margin_delta_bps=200, working_capital_days_delta=-3),
            "Bear": ScenarioOverrides(name="Bear", revenue_multiplier=0.90, margin_delta_bps=-200, working_capital_days_delta=4),
        }

    return DCFEngineConfig(
        company=company,
        forecast=forecast,
        wacc=wacc,
        valuation=valuation,
        monte_carlo=monte_carlo,
        sensitivity=sensitivity,
        comps=comps,
        debt_tranches=debt_tranches,
        scenarios=scenarios,
    )


# ── Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/run", methods=["POST"])
def api_run():
    """Run full DCF pipeline and return JSON results."""
    try:
        data = request.get_json(force=True)
        cfg = _build_config_from_payload(data)

        # Cap Monte Carlo iterations on Vercel to avoid timeouts
        if IS_VERCEL:
            cfg.monte_carlo.iterations = min(cfg.monte_carlo.iterations, 2000)
            cfg.wacc.use_live_data = False  # No external API calls on Vercel

        # Load historical data — resolve relative to project root
        data_file = data.get("data_file", "data/asian_street_financials.csv")
        hist_path = _BASE_DIR / data_file
        if not hist_path.exists():
            hist_path = Path(data_file)  # fallback to CWD-relative
        if hist_path.exists():
            hist = pd.read_csv(hist_path)
        else:
            hist = pd.DataFrame()

        # Base-year values
        base_year_revenue = float(data.get("base_year_revenue", 0))
        base_cash = float(data.get("base_cash", 0))
        base_ppe = float(data.get("base_ppe", 0))
        base_nwc = float(data.get("base_nwc", 0))
        base_retained_earnings = float(data.get("base_retained_earnings", 0))
        base_common_stock = float(data.get("base_common_stock", 0))

        # Auto-detect base year values from historical data if not provided
        if base_year_revenue == 0 and not hist.empty:
            try:
                latest_rev = hist[hist["account"] == "Revenue"].sort_values("period").iloc[-1]["amount"]
                base_year_revenue = float(latest_rev)
            except Exception:
                pass
        if base_cash == 0 and not hist.empty:
            try:
                base_cash = float(hist[hist["account"] == "Cash"].sort_values("period").iloc[-1]["amount"])
            except Exception:
                pass
        if base_nwc == 0 and not hist.empty:
            try:
                ar = float(hist[hist["account"].isin(["Accounts Receivable"])].sort_values("period").iloc[-1]["amount"]) if len(hist[hist["account"] == "Accounts Receivable"]) else 0
                inv = float(hist[hist["account"] == "Inventory"].sort_values("period").iloc[-1]["amount"]) if len(hist[hist["account"] == "Inventory"]) else 0
                ap = float(hist[hist["account"] == "Accounts Payable"].sort_values("period").iloc[-1]["amount"]) if len(hist[hist["account"] == "Accounts Payable"]) else 0
                base_nwc = ar + inv - ap
            except Exception:
                pass

        result = run_pipeline(
            cfg=cfg,
            historical=hist,
            base_year_revenue=base_year_revenue,
            base_cash=base_cash,
            base_ppe=base_ppe,
            base_nwc=base_nwc,
            base_retained_earnings=base_retained_earnings,
            base_common_stock=base_common_stock,
        )

        # ── Serialize results ────────────────────────────────────
        response = {
            "success": True,
            "errors": result.errors,
            "timings": {k: round(v, 3) for k, v in result.timings.items()},
        }

        # Income Statement
        if result.income_statement:
            response["income_statement"] = _df_to_records(result.income_statement.table)

        # Working Capital
        if result.working_capital:
            response["working_capital"] = _df_to_records(result.working_capital.table)

        # Capex & DA
        if result.capex_da:
            response["capex_da"] = _df_to_records(result.capex_da.table)

        # Debt Schedule
        if result.debt_schedule:
            response["debt_schedule"] = _df_to_records(result.debt_schedule.table)

        # Balance Sheet
        if result.balance_sheet:
            response["balance_sheet"] = _df_to_records(result.balance_sheet.table)

        # Cash Flow
        if result.cash_flow:
            response["cash_flow"] = _df_to_records(result.cash_flow.table)
            response["fcf_table"] = _df_to_records(result.cash_flow.fcf_table)

        # WACC
        if result.wacc:
            w = result.wacc
            response["wacc"] = {
                "cost_of_equity": _safe_float(w.cost_of_equity),
                "cost_of_debt_pre_tax": _safe_float(w.cost_of_debt_pre_tax),
                "cost_of_debt_after_tax": _safe_float(w.cost_of_debt_after_tax),
                "wacc": _safe_float(w.wacc),
                "synthetic_rating": getattr(w, "synthetic_rating", "N/A"),
                "risk_free_rate": _safe_float(w.risk_free_rate),
                "beta": _safe_float(w.beta),
                "equity_risk_premium": _safe_float(w.equity_risk_premium),
                "debt_weight": _safe_float(w.debt_weight),
                "equity_weight": _safe_float(w.equity_weight),
            }

        # DCF
        if result.dcf:
            d = result.dcf
            response["dcf"] = {
                "valuation_table": _df_to_records(d.valuation_table),
                "terminal_fcf": _safe_float(d.terminal_fcf),
                "terminal_ebitda": _safe_float(d.terminal_ebitda),
                "gordon_tv": _safe_float(d.gordon_tv),
                "exit_tv": _safe_float(d.exit_tv),
                "blended_tv": _safe_float(d.blended_tv),
                "pv_gordon": _safe_float(d.pv_gordon_tv),
                "pv_exit": _safe_float(d.pv_exit_tv),
                "pv_blended": _safe_float(d.pv_blended_tv),
                "pv_fcf_sum": _safe_float(d.pv_fcf_sum),
                "ev_gordon": _safe_float(d.ev_gordon),
                "ev_exit": _safe_float(d.ev_exit),
                "ev_blended": _safe_float(d.ev_blended),
                "equity_gordon": _safe_float(d.equity_gordon),
                "equity_exit": _safe_float(d.equity_exit),
                "equity_blended": _safe_float(d.equity_blended),
                "price_gordon": _safe_float(d.price_gordon),
                "price_exit": _safe_float(d.price_exit),
                "price_blended": _safe_float(d.price_blended),
                "tv_pct_of_ev": _safe_float(d.tv_pct_of_ev),
                "implied_exit_multiple_from_gordon": _safe_float(d.implied_exit_multiple_from_gordon),
                "implied_growth_from_exit": _safe_float(d.implied_growth_from_exit),
                "effective_terminal_growth": _safe_float(d.effective_terminal_growth),
                "terminal_wacc_spread": _safe_float(d.terminal_wacc_spread),
            }

        # Scenario Comparison
        if result.scenario_comparison:
            comp_df = result.scenario_comparison.comparison.reset_index()
            response["scenarios"] = _df_to_records(comp_df)

        # Monte Carlo
        if result.monte_carlo:
            mc = result.monte_carlo
            hist_data = mc.histogram_data if isinstance(mc.histogram_data, dict) else {}
            # Convert numpy arrays to lists for JSON serialization
            stats = {}
            if isinstance(mc.statistics, dict):
                for k, v in mc.statistics.items():
                    stats[k] = _safe_float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v
            response["monte_carlo"] = {
                "statistics": stats,
                "histogram": {
                    "bins": [float(x) for x in hist_data.get("bin_edges", hist_data.get("bins", []))],
                    "counts": [int(x) for x in hist_data.get("counts", [])],
                    "centers": [float(x) for x in hist_data.get("bin_centers", hist_data.get("centers", []))],
                },
            }

        # Sensitivity
        if result.sensitivity:
            s = result.sensitivity
            # wacc_vs_growth and revenue_vs_margin are DataFrames with index
            wacc_tg_df = s.wacc_vs_growth.reset_index() if hasattr(s.wacc_vs_growth, 'reset_index') else s.wacc_vs_growth
            rev_mar_df = s.revenue_vs_margin.reset_index() if hasattr(s.revenue_vs_margin, 'reset_index') else s.revenue_vs_margin
            response["sensitivity"] = {
                "wacc_tg": _df_to_records(wacc_tg_df),
                "rev_margin": _df_to_records(rev_mar_df),
            }

        # Tornado
        if result.tornado:
            response["tornado"] = _df_to_records(result.tornado.drivers)

        # Comps
        if result.comps:
            response["comps"] = {
                "peer_table": _df_to_records(result.comps.peer_table),
                "summary_stats": _df_to_records(result.comps.summary_stats),
                "implied_valuation": _df_to_records(result.comps.implied_valuation),
            }

        return jsonify(response)

    except Exception as e:
        logger.error("API error: %s", traceback.format_exc())
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/configs", methods=["GET"])
def api_list_configs():
    """List available config files."""
    configs = []
    for p in _BASE_DIR.glob("config.*.json"):
        configs.append({"filename": p.name, "name": p.stem.replace("config.", "").replace("_", " ").title()})
    return jsonify(configs)


@app.route("/api/config/<filename>", methods=["GET"])
def api_load_config(filename: str):
    """Load a config file."""
    path = _BASE_DIR / filename
    if not path.exists():
        return jsonify({"error": "Not found"}), 404
    return jsonify(json.loads(path.read_text()))


@app.route("/api/data-files", methods=["GET"])
def api_list_data_files():
    """List available CSV/XLSX data files."""
    files = []
    data_dir = _BASE_DIR / "data"
    if data_dir.exists():
        for p in data_dir.glob("*"):
            if p.suffix in (".csv", ".xlsx"):
                files.append({"filename": f"data/{p.name}", "name": p.stem.replace("_", " ").title()})
    return jsonify(files)


if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
