"""
Dashboard API — Flask backend that wraps the IB-Grade DCF Engine pipeline
and returns full model results as JSON for the interactive dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import csv
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file, redirect

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
from src.dcf_engine import __version__ as ENGINE_VERSION
from src.dcf_engine.pipeline import run_pipeline
from src.dcf_engine.sample_models import get_sample, get_sample_payload, list_samples
from src.dcf_engine.intelligence import (
    fetch_company_snapshot, build_assumptions_from_snapshot, build_valuation_preview,
    detect_filing_changes, detect_red_flags, build_valuation_impacts, refresh_watchlist,
    build_public_report,
)
from src.dcf_engine.ingestion.edgar_client import EdgarClient
from src.dcf_engine.saas import identify_user, check_export_access, consume_export_credit

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(_BASE_DIR / "static"),
    template_folder=str(_BASE_DIR / "templates"),
)
app.json.sort_keys = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 1_000_000))

# ── Environment configuration ──
IS_PRODUCTION = os.environ.get("APP_ENV", "development").lower() == "production"
MAX_MC_ITERATIONS = int(os.environ.get("MAX_MONTE_CARLO_ITERATIONS", 2000 if IS_PRODUCTION else 50_000))
WACC_LIVE_DATA = os.environ.get("WACC_LIVE_DATA_ENABLED", "false").lower() == "true"
BRAND_NAME = os.environ.get("BRAND_NAME", "Trinsic")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@trinsic.space")
CUSTOM_MODEL_CHECKOUT_URL = os.environ.get("CUSTOM_MODEL_CHECKOUT_URL", "")
BUNDLE_CHECKOUT_URL = os.environ.get("BUNDLE_CHECKOUT_URL", "")
REQUESTS_FILE = _BASE_DIR / "data" / "model_requests.csv"


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


def _public_context(**extra):
    """Shared template context for public launch pages."""
    ctx = {
        "brand_name": BRAND_NAME,
        "support_email": SUPPORT_EMAIL,
        "custom_model_checkout_url": CUSTOM_MODEL_CHECKOUT_URL,
        "bundle_checkout_url": BUNDLE_CHECKOUT_URL,
        "samples": list_samples(),
    }
    ctx.update(extra)
    return ctx


def _api_error(message: str, status: int = 500, request_id: str | None = None):
    """Return a public-safe API error without stack traces."""
    return jsonify({
        "success": False,
        "error": message,
        "request_id": request_id or uuid.uuid4().hex[:10],
    }), status


@app.context_processor
def _template_formatters():
    def fmt_number(value):
        try:
            if value is None:
                return "N/A"
            value = float(value)
            if abs(value) >= 1_000_000_000:
                return f"{value / 1_000_000_000:,.1f}B"
            if abs(value) >= 1_000_000:
                return f"{value / 1_000_000:,.1f}M"
            return f"{value:,.0f}"
        except (TypeError, ValueError):
            return "N/A"

    def fmt_money(value):
        formatted = fmt_number(value)
        return formatted if formatted == "N/A" else f"${formatted}"

    def fmt_pct(value):
        try:
            if value is None:
                return "N/A"
            return f"{float(value) * 100:.1f}%"
        except (TypeError, ValueError):
            return "N/A"

    return {"fmt_number": fmt_number, "fmt_money": fmt_money, "fmt_pct": fmt_pct}


def _validate_years(years_val, request_id):
    """Strict validation for years parameter, reusing validation from /api/valuation-preview."""
    if years_val is None:
        return 5, None
    if isinstance(years_val, bool) or not isinstance(years_val, (int, str)):
        return None, (jsonify({
            "success": False,
            "error": "Invalid years parameter: must be an integer",
            "request_id": request_id,
            "warnings": []
        }), 400)
    try:
        if isinstance(years_val, str):
            if not years_val.strip().isdigit():
                raise ValueError("Non-integer string")
        years = int(years_val)
    except (ValueError, TypeError):
        return None, (jsonify({
            "success": False,
            "error": "Invalid years parameter: must be an integer",
            "request_id": request_id,
            "warnings": []
        }), 400)

    if years < 1 or years > 10:
        return None, (jsonify({
            "success": False,
            "error": "Years must be between 1 and 10",
            "request_id": request_id,
            "warnings": []
        }), 400)

    return years, None


def _safe_project_path(filename: str, allowed_dir: Path, allowed_suffixes: tuple[str, ...]) -> Path | None:
    """Resolve a user path inside an approved directory only."""
    try:
        candidate = (allowed_dir / filename).resolve()
        root = allowed_dir.resolve()
        if root not in candidate.parents and candidate != root:
            return None
        if candidate.suffix.lower() not in allowed_suffixes:
            return None
        return candidate
    except (OSError, ValueError):
        return None


def _load_historical_and_base_values(data: dict):
    """Load historical CSV and derive base-year values from payload/defaults."""
    data_file = data.get("data_file", "data/asian_street_financials.csv")
    hist_path = (_BASE_DIR / data_file).resolve()
    data_root = (_BASE_DIR / "data").resolve()
    if data_root not in hist_path.parents and hist_path != data_root:
        hist_path = data_root / "asian_street_financials.csv"

    hist = pd.read_csv(hist_path) if hist_path.exists() else pd.DataFrame()

    base_year_revenue = float(data.get("base_year_revenue", 0))
    base_cash = float(data.get("base_cash", 0))
    base_ppe = float(data.get("base_ppe", 0))
    base_nwc = float(data.get("base_nwc", 0))
    base_retained_earnings = float(data.get("base_retained_earnings", 0))
    base_common_stock = float(data.get("base_common_stock", 0))
    base_intangibles = float(data.get("base_intangibles", 0))

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

    return hist, {
        "base_year_revenue": base_year_revenue,
        "base_cash": base_cash,
        "base_ppe": base_ppe,
        "base_nwc": base_nwc,
        "base_retained_earnings": base_retained_earnings,
        "base_common_stock": base_common_stock,
        "base_intangibles": base_intangibles,
    }


def _run_payload(data: dict, output_excel: str | None = None, protect_sheets: bool = False):
    """Build config and run the valuation pipeline from a dashboard payload."""
    cfg = _build_config_from_payload(data)
    cfg.monte_carlo.iterations = min(cfg.monte_carlo.iterations, MAX_MC_ITERATIONS)
    if not WACC_LIVE_DATA:
        cfg.wacc.use_live_data = False

    hist, base = _load_historical_and_base_values(data)
    return run_pipeline(cfg=cfg, historical=hist, output_excel=output_excel, protect_sheets=protect_sheets, **base)


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
    # Parse revenue_manual (string keys from JSON → int keys)
    rev_manual_raw = fc.get("revenue_manual", {})
    revenue_manual = {int(k): float(v) for k, v in rev_manual_raw.items()} if rev_manual_raw else {}

    # Parse capex_manual (string keys from JSON → int keys)
    capex_manual_raw = fc.get("capex_manual", {})
    capex_manual = {int(k): float(v) for k, v in capex_manual_raw.items()} if capex_manual_raw else {}

    forecast = ForecastConfig(
        projection_years=int(fc.get("projection_years", 5)),
        revenue_method=fc.get("revenue_method", "cagr"),
        revenue_cagr=float(fc.get("revenue_cagr", 0.08)),
        revenue_yoy=[float(x) for x in fc.get("revenue_yoy", [0.08, 0.07, 0.06, 0.05, 0.05])],
        revenue_manual=revenue_manual,
        cogs_pct_revenue=float(fc.get("cogs_pct_revenue", 0.45)),
        sga_pct_revenue=float(fc.get("sga_pct_revenue", 0.20)),
        other_opex_pct_revenue=float(fc.get("other_opex_pct_revenue", 0.05)),
        depreciation_rate=float(fc.get("depreciation_rate", 0.10)),
        amortisation_pct_revenue=float(fc.get("amortisation_pct_revenue", 0.005)),
        capex_method=fc.get("capex_method", "pct_revenue"),
        capex_pct_revenue=float(fc.get("capex_pct_revenue", 0.04)),
        capex_fixed=float(fc.get("capex_fixed", 0.0)),
        capex_manual=capex_manual,
        dso=float(fc.get("dso", 45)),
        dio=float(fc.get("dio", 50)),
        dpo=float(fc.get("dpo", 40)),
        prepaid_pct_revenue=float(fc.get("prepaid_pct_revenue", 0.005)),
        accrued_pct_revenue=float(fc.get("accrued_pct_revenue", 0.01)),
        other_current_assets_pct_revenue=float(fc.get("other_current_assets_pct_revenue", 0.005)),
        other_current_liabilities_pct_revenue=float(fc.get("other_current_liabilities_pct_revenue", 0.005)),
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
    mc_seed_raw = mc.get("seed", None)
    mc_seed = int(mc_seed_raw) if mc_seed_raw is not None else None
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
        seed=mc_seed,
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

@app.after_request
def add_cache_headers(response):
    """Prevent aggressive caching of dynamic HTML and API responses."""
    if response.content_type and ('text/html' in response.content_type or 'application/json' in response.content_type):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.route("/")
def index():
    return render_template("landing.html", **_public_context())


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/research")
def research():
    return render_template("research.html", **_public_context())


@app.route("/watchlist")
def watchlist():
    return render_template("watchlist.html", **_public_context())


@app.route("/samples/<ticker>")
def sample_page(ticker: str):
    sample = get_sample(ticker)
    if sample is None:
        return render_template("landing.html", **_public_context(error="Sample model not found.")), 404
    return render_template("sample.html", **_public_context(sample={
        "ticker": ticker.upper(),
        "name": sample["name"],
        "industry": sample["industry"],
        "tagline": sample["tagline"],
        "summary": sample["summary"],
    }))


@app.route("/reports/<ticker>")
def report_page(ticker: str):
    request_id = uuid.uuid4().hex[:10]
    try:
        report = build_public_report(ticker, years=5)
        return render_template("report.html", **_public_context(report=report))
    except ValueError as exc:
        return render_template("landing.html", **_public_context(error=str(exc))), 400
    except Exception:
        logger.error("Public report error [%s]: %s", request_id, traceback.format_exc())
        return render_template("landing.html", **_public_context(
            error="Report is temporarily unavailable. Try another ticker."
        )), 503


@app.route("/reports/<ticker>/print")
def printable_report(ticker: str):
    request_id = uuid.uuid4().hex[:10]
    try:
        report = build_public_report(ticker, years=5)
        return render_template("report.html", **_public_context(report=report, printable=True))
    except ValueError as exc:
        return render_template("landing.html", **_public_context(error=str(exc))), 400
    except Exception:
        logger.error("Printable report error [%s]: %s", request_id, traceback.format_exc())
        return render_template("landing.html", **_public_context(
            error="Printable report is temporarily unavailable."
        )), 503


@app.route("/checkout/custom")
def checkout_custom():
    if CUSTOM_MODEL_CHECKOUT_URL:
        return redirect(CUSTOM_MODEL_CHECKOUT_URL, code=302)
    return render_template("landing.html", **_public_context(
        error="Custom model orders are temporarily paused while our LemonSqueezy payment gateway completes verification. Please check back shortly, or email support at " + SUPPORT_EMAIL + " to order directly!"
    )), 503


@app.route("/api/company-snapshot", methods=["POST"])
def api_company_snapshot():
    request_id = uuid.uuid4().hex[:10]
    try:
        data = request.get_json(force=True) or {}
        ticker = str(data.get("ticker", "")).strip().upper()
        if not ticker:
            return jsonify({
                "success": False,
                "error": "Ticker is required",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        if len(ticker) > 12:
            return jsonify({
                "success": False,
                "error": "Ticker too long",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        years_val = data.get("years")
        years, err_resp = _validate_years(years_val, request_id)
        if err_resp:
            return err_resp[0], err_resp[1]
        
        snapshot = fetch_company_snapshot(ticker=ticker, years=years)
        
        # Serialize snapshot facts
        facts_serialized = []
        for f in snapshot.facts:
            facts_serialized.append({
                "ticker": f.ticker,
                "cik": f.cik,
                "company_name": f.company_name,
                "account": f.account,
                "concept": f.concept,
                "value": f.value,
                "unit": f.unit,
                "form": f.form,
                "filed": f.filed,
                "period_end": f.period_end,
                "fiscal_year": f.fiscal_year,
                "fiscal_period": f.fiscal_period,
                "accession": f.accession,
                "frame": f.frame,
                "source_url": f.source_url
            })
            
        return jsonify({
            "success": True,
            "request_id": request_id,
            "ticker": snapshot.ticker,
            "cik": snapshot.cik,
            "company_name": snapshot.company_name,
            "latest_period": snapshot.latest_period,
            "key_metrics": snapshot.key_metrics,
            "financials": _df_to_records(snapshot.financials),
            "source_map": facts_serialized,
            "warnings": snapshot.warnings
        })
    except Exception as exc:
        logger.error("Snapshot error [%s]: %s", request_id, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "Failed to fetch company snapshot",
            "request_id": request_id,
            "warnings": []
        }), 500


@app.route("/api/ticker-assumptions", methods=["POST"])
def api_ticker_assumptions():
    request_id = uuid.uuid4().hex[:10]
    try:
        data = request.get_json(force=True) or {}
        ticker = str(data.get("ticker", "")).strip().upper()
        if not ticker:
            return jsonify({
                "success": False,
                "error": "Ticker is required",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        if len(ticker) > 12:
            return jsonify({
                "success": False,
                "error": "Ticker too long",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        years_val = data.get("years")
        years, err_resp = _validate_years(years_val, request_id)
        if err_resp:
            return err_resp[0], err_resp[1]
            
        snapshot = fetch_company_snapshot(ticker=ticker, years=years)
        result = build_assumptions_from_snapshot(snapshot)
        
        # Serialize underlying source facts to list of dictionaries
        source_map_serialized = []
        for f in result.source_map:
            source_map_serialized.append({
                "ticker": f.ticker,
                "cik": f.cik,
                "company_name": f.company_name,
                "account": f.account,
                "concept": f.concept,
                "value": f.value,
                "unit": f.unit,
                "form": f.form,
                "filed": f.filed,
                "period_end": f.period_end,
                "fiscal_year": f.fiscal_year,
                "fiscal_period": f.fiscal_period,
                "accession": f.accession,
                "frame": f.frame,
                "source_url": f.source_url
            })
            
        return jsonify({
            "success": True,
            "request_id": request_id,
            "ticker": snapshot.ticker,
            "payload": result.payload,
            "source_map": source_map_serialized,
            "warnings": result.warnings
        })
    except Exception as exc:
        logger.error("Ticker assumptions error [%s]: %s", request_id, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "Failed to build company assumptions",
            "request_id": request_id,
            "warnings": []
        }), 500


@app.route("/api/valuation-preview", methods=["POST"])
def api_valuation_preview():
    request_id = uuid.uuid4().hex[:10]
    try:
        data = request.get_json(force=True) or {}
        ticker = str(data.get("ticker", "")).strip().upper()
        if not ticker:
            return jsonify({
                "success": False,
                "error": "Ticker is required",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        if len(ticker) > 12:
            return jsonify({
                "success": False,
                "error": "Ticker too long",
                "request_id": request_id,
                "warnings": []
            }), 400
            
        years_val = data.get("years")
        years, err_resp = _validate_years(years_val, request_id)
        if err_resp:
            return err_resp[0], err_resp[1]

        overrides = data.get("overrides")
        
        result = build_valuation_preview(ticker=ticker, years=years, overrides=overrides)
        
        # If result.dcf or result.wacc is missing, return success: false with a clean JSON error
        if result.get("blended_equity_value") is None or result.get("wacc") is None:
            return jsonify({
                "success": False,
                "error": "Critical valuation or WACC result missing from preview calculation.",
                "request_id": request_id,
                "warnings": result.get("warnings", []),
                "assumption_quality": result.get("assumption_quality"),
                "reverse_dcf": result.get("reverse_dcf"),
                "valuation_impacts": result.get("valuation_impacts", []),
                "metadata_checked": result.get("metadata_checked", False),
            }), 400
            
        response = {
            "success": True,
            "request_id": request_id,
        }
        response.update(result)
        return jsonify(response)
        
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "request_id": request_id,
            "warnings": []
        }), 400
    except Exception as exc:
        logger.error("Valuation preview error [%s]: %s", request_id, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": f"Failed to build valuation preview: {str(exc)}",
            "request_id": request_id,
            "warnings": []
        }), 500


@app.route("/api/filing-changes", methods=["POST"])
def api_filing_changes():
    """Detect numeric changes between latest and prior filing periods."""
    request_id = uuid.uuid4().hex[:10]
    try:
        data = request.get_json(force=True) or {}
        ticker = str(data.get("ticker", "")).strip().upper()
        if not ticker:
            return jsonify({
                "success": False,
                "error": "Ticker is required",
                "request_id": request_id,
                "warnings": []
            }), 400

        if len(ticker) > 12:
            return jsonify({
                "success": False,
                "error": "Ticker too long",
                "request_id": request_id,
                "warnings": []
            }), 400

        years_val = data.get("years")
        years, err_resp = _validate_years(years_val, request_id)
        if err_resp:
            return err_resp[0], err_resp[1]

        snapshot = fetch_company_snapshot(ticker, years=years)
        change_result = detect_filing_changes(snapshot)

        numeric_changes = change_result.get("numeric_changes", [])
        warnings = list(change_result.get("warnings", []))

        submissions = None
        metadata_checked = False
        if snapshot.cik:
            try:
                client = EdgarClient()
                submissions = client.fetch_submissions(snapshot.cik)
                if submissions is not None:
                    metadata_checked = True
                else:
                    warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")
            except Exception as e:
                logger.warning("Submissions fetch failed for CIK %s: %s", snapshot.cik, e)
                warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")
        else:
            warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")

        red_flags = detect_red_flags(
            snapshot=snapshot,
            filing_changes=numeric_changes,
            submissions=submissions,
        )

        impacts = build_valuation_impacts(numeric_changes, red_flags)

        return jsonify({
            "success": True,
            "request_id": request_id,
            "ticker": ticker,
            "latest_period": change_result.get("latest_period"),
            "prior_period": change_result.get("prior_period"),
            "numeric_changes": numeric_changes,
            "red_flags": red_flags,
            "valuation_impacts": impacts,
            "warnings": warnings,
            "metadata_checked": metadata_checked,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "request_id": request_id,
            "warnings": []
        }), 400
    except Exception as exc:
        logger.error("Filing changes error [%s]: %s", request_id, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": f"Failed to detect filing changes: {str(exc)}",
            "request_id": request_id,
            "warnings": []
        }), 500


@app.route("/api/watchlist/refresh", methods=["POST"])
def api_watchlist_refresh():
    """Refresh a watchlist of tickers with filing change and red flag analysis."""
    request_id = uuid.uuid4().hex[:10]
    try:
        data = request.get_json(force=True) or {}
        tickers = data.get("tickers")

        if not tickers or not isinstance(tickers, list):
            return jsonify({
                "success": False,
                "error": "tickers must be a non-empty list",
                "request_id": request_id,
                "warnings": []
            }), 400

        if len(tickers) > 10:
            return jsonify({
                "success": False,
                "error": "Maximum 10 tickers allowed per request",
                "request_id": request_id,
                "warnings": []
            }), 400

        years_val = data.get("years")
        years, err_resp = _validate_years(years_val, request_id)
        if err_resp:
            return err_resp[0], err_resp[1]
        result = refresh_watchlist(tickers=tickers, years=years)

        return jsonify({
            "success": True,
            "request_id": request_id,
            "results": result.get("results", []),
            "warnings": result.get("warnings", []),
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "request_id": request_id,
            "warnings": []
        }), 400
    except Exception as exc:
        logger.error("Watchlist refresh error [%s]: %s", request_id, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": f"Failed to refresh watchlist: {str(exc)}",
            "request_id": request_id,
            "warnings": []
        }), 500


@app.route("/api/version", methods=["GET"])
def api_version():
    """Return backend engine version for UI badge display."""
    major = str(ENGINE_VERSION).split(".")[0] if ENGINE_VERSION else "0"
    return jsonify({"version": ENGINE_VERSION, "badge": f"V{major}"})


@app.route("/api/run", methods=["POST"])
def api_run():
    """Run full DCF pipeline and return JSON results."""
    try:
        data = request.get_json(force=True)
        cfg = _build_config_from_payload(data)

        # Cap Monte Carlo iterations in production to avoid timeouts
        cfg.monte_carlo.iterations = min(cfg.monte_carlo.iterations, MAX_MC_ITERATIONS)
        if not WACC_LIVE_DATA:
            cfg.wacc.use_live_data = False

        # Load historical data — resolve relative to project root
        data_file = data.get("data_file", "data/asian_street_financials.csv")
        hist_path = _safe_project_path(data_file.replace("data/", "", 1), _BASE_DIR / "data", (".csv", ".xlsx"))
        if hist_path is None:
            hist_path = _BASE_DIR / "data" / "asian_street_financials.csv"
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
        base_intangibles = float(data.get("base_intangibles", 0))

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
            base_intangibles=base_intangibles,
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

    except Exception:
        request_id = uuid.uuid4().hex[:10]
        logger.error("API error [%s]: %s", request_id, traceback.format_exc())
        return _api_error("Model run failed. Please check assumptions or try again.", request_id=request_id)


@app.route("/api/export-excel", methods=["POST"])
def api_export_excel():
    """Run pipeline and return the fully formula-linked Excel workbook."""
    try:
        data = request.get_json(force=True)
        checkout_url = BUNDLE_CHECKOUT_URL or CUSTOM_MODEL_CHECKOUT_URL or "/checkout/custom"
        user = identify_user(request.headers, data)
        access = check_export_access(user, checkout_url=checkout_url)
        if not access.allowed:
            return jsonify({
                "success": False,
                "error": "Export requires a paid plan or export credit.",
                "checkout_url": access.checkout_url,
            }), 402

        cfg = _build_config_from_payload(data)

        cfg.monte_carlo.iterations = min(cfg.monte_carlo.iterations, MAX_MC_ITERATIONS)
        if not WACC_LIVE_DATA:
            cfg.wacc.use_live_data = False

        # Load historical data
        data_file = data.get("data_file", "data/asian_street_financials.csv")
        hist_path = _safe_project_path(data_file.replace("data/", "", 1), _BASE_DIR / "data", (".csv", ".xlsx"))
        if hist_path is None:
            hist_path = _BASE_DIR / "data" / "asian_street_financials.csv"
        hist = pd.read_csv(hist_path) if hist_path.exists() else pd.DataFrame()

        # Base-year values
        base_year_revenue = float(data.get("base_year_revenue", 0))
        base_cash = float(data.get("base_cash", 0))
        base_ppe = float(data.get("base_ppe", 0))
        base_nwc = float(data.get("base_nwc", 0))
        base_retained_earnings = float(data.get("base_retained_earnings", 0))
        base_common_stock = float(data.get("base_common_stock", 0))
        base_intangibles = float(data.get("base_intangibles", 0))

        # Auto-detect from historical
        if base_year_revenue == 0 and not hist.empty:
            try:
                base_year_revenue = float(hist[hist["account"] == "Revenue"].sort_values("period").iloc[-1]["amount"])
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

        # Generate Excel to a temp file
        tmp_dir = tempfile.mkdtemp()
        company_name = data.get("company_name", "DCF_Model").replace(" ", "_")
        excel_filename = f"{company_name}_Trinsic_DCF_Model.xlsx"
        excel_path = os.path.join(tmp_dir, excel_filename)

        result = run_pipeline(
            cfg=cfg,
            historical=hist,
            base_year_revenue=base_year_revenue,
            base_cash=base_cash,
            base_ppe=base_ppe,
            base_nwc=base_nwc,
            base_retained_earnings=base_retained_earnings,
            base_common_stock=base_common_stock,
            base_intangibles=base_intangibles,
            output_excel=excel_path,
            source_facts=data.get("source_map"),
            warnings=data.get("warnings"),
            filing_changes=data.get("filing_changes") or data.get("numeric_changes"),
            valuation_impacts=data.get("valuation_impacts"),
        )

        if result.excel_path and Path(result.excel_path).exists():
            if access.consume_credit:
                consume_export_credit(access.email, cfg.company.ticker or cfg.company.name, result.errors)
            return send_file(
                str(result.excel_path),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=excel_filename,
            )
        else:
            errors = result.errors or ["Excel generation failed"]
            return jsonify({"success": False, "error": "; ".join(errors)}), 500

    except Exception:
        request_id = uuid.uuid4().hex[:10]
        logger.error("Excel export error [%s]: %s", request_id, traceback.format_exc())
        return _api_error("Excel export failed. Please try again.", request_id=request_id)


@app.route("/download/sample/<ticker>", methods=["GET"])
def download_sample_model(ticker: str):
    """Generate and download a public sample Excel model."""
    payload = get_sample_payload(ticker)
    if payload is None:
        return render_template("landing.html", **_public_context(error="Sample model not found.")), 404

    try:
        tmp_dir = tempfile.mkdtemp()
        safe_ticker = ticker.upper()
        excel_filename = f"Trinsic_{safe_ticker}_DCF_Sample.xlsx"
        excel_path = os.path.join(tmp_dir, excel_filename)
        result = _run_payload(payload, output_excel=excel_path, protect_sheets=True)
        if result.excel_path and Path(result.excel_path).exists():
            return send_file(
                str(result.excel_path),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=excel_filename,
            )
        return _api_error("Sample model generation failed.", 500)
    except Exception:
        request_id = uuid.uuid4().hex[:10]
        logger.error("Sample export error [%s]: %s", request_id, traceback.format_exc())
        return _api_error("Sample model generation failed. Please try again.", request_id=request_id)


@app.route("/api/request-model", methods=["POST"])
def api_request_model():
    """Capture early custom model requests for the productized-service MVP."""
    try:
        data = request.get_json(force=True) or {}
        email = str(data.get("email", "")).strip()[:160]
        ticker = str(data.get("ticker", "")).strip().upper()[:16]
        notes = str(data.get("notes", "")).strip()[:1000]

        if "@" not in email or "." not in email:
            return _api_error("Please enter a valid email.", 400)
        if not ticker:
            return _api_error("Please enter a ticker.", 400)

        REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_exists = REQUESTS_FILE.exists()
        with REQUESTS_FILE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["created_at", "email", "ticker", "notes"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "created_at": datetime.now(timezone.utc).isoformat(),
                "email": email,
                "ticker": ticker,
                "notes": notes,
            })

        return jsonify({
            "success": True,
            "message": "Request captured.",
            "checkout_url": CUSTOM_MODEL_CHECKOUT_URL or "/checkout/custom",
            "support_email": SUPPORT_EMAIL,
        })
    except Exception:
        request_id = uuid.uuid4().hex[:10]
        logger.error("Request capture error [%s]: %s", request_id, traceback.format_exc())
        return _api_error("Could not capture request. Please email support.", request_id=request_id)


@app.route("/api/configs", methods=["GET"])
def api_list_configs():
    """List available config files (searches root and configs/ folder)."""
    configs = []
    for p in _BASE_DIR.glob("config.*.json"):
        configs.append({"filename": p.name, "name": p.stem.replace("config.", "").replace("_", " ").title()})
    configs_dir = _BASE_DIR / "configs"
    if configs_dir.exists():
        for p in configs_dir.glob("config.*.json"):
            configs.append({"filename": f"configs/{p.name}", "name": p.stem.replace("config.", "").replace("_", " ").title()})
    return jsonify(configs)


@app.route("/api/config/<path:filename>", methods=["GET"])
def api_load_config(filename: str):
    """Load a config file."""
    if filename.startswith("config."):
        path = _safe_project_path(filename, _BASE_DIR, (".json",))
    else:
        path = _safe_project_path(filename.replace("config/", "", 1), _BASE_DIR / "config", (".json",))
    if path is None:
        return jsonify({"error": "Not found"}), 404
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


@app.route("/api/data-file-base-values/<path:filename>", methods=["GET"])
def api_data_file_base_values(filename: str):
    """Extract latest-period base-year values from a historical data CSV."""
    try:
        hist_path = _safe_project_path(filename.replace("data/", "", 1), _BASE_DIR / "data", (".csv", ".xlsx"))
        if hist_path is None:
            return jsonify({"error": "File not found"}), 404
        if not hist_path.exists():
            return jsonify({"error": "File not found"}), 404

        hist = pd.read_csv(hist_path)
        if hist.empty:
            return jsonify({"error": "Empty file"}), 400

        latest_period = hist["period"].max()
        latest = hist[hist["period"] == latest_period]

        def _get(account):
            rows = latest[latest["account"] == account]
            return float(rows.iloc[0]["amount"]) if len(rows) else 0

        rev = _get("Revenue")
        cash = _get("Cash")
        ar = _get("Accounts Receivable")
        inv = _get("Inventory")
        ap = _get("Accounts Payable")
        nwc = ar + inv - ap

        return jsonify({
            "base_year_revenue": rev,
            "base_cash": cash,
            "base_nwc": nwc,
            "base_ppe": 0,
            "latest_period": latest_period,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
