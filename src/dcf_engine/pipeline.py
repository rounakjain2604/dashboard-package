"""
Pipeline orchestrator — full DCF model run.

Ingestion → 3-Statement Build → Valuation → Comps → Output.
Each step feeds into the next with full error collection and audit logging.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

from .config import DCFEngineConfig, ScenarioOverrides
from .statements.income_statement import build_income_statement, IncomeStatementResult
from .statements.balance_sheet import build_balance_sheet, BalanceSheetResult
from .statements.cash_flow import build_cash_flow_statement, CashFlowResult
from .schedules.working_capital import build_working_capital, WorkingCapitalResult
from .schedules.capex_depreciation import build_capex_da, CapexDAResult
from .schedules.debt_schedule import build_debt_schedule, DebtScheduleResult
from .valuation.wacc import compute_wacc, WACCResult
from .valuation.dcf_engine import run_dcf, DCFResult
from .valuation.scenarios import (
    ScenarioResult, ScenarioComparisonResult, build_scenario_comparison,
)
from .valuation.monte_carlo import run_monte_carlo, MonteCarloResult
from .valuation.sensitivity import build_sensitivity_tables, SensitivityResult
from .valuation.tornado import build_tornado, TornadoResult
from .comps.comps import build_comps, CompsResult
# Lazy-import heavy output modules to avoid import failures if optional
# dependencies (reportlab, etc.) are not installed
_build_excel = None
_build_pdf_memo = None

def _get_build_excel():
    global _build_excel
    if _build_excel is None:
        from .output.excel_builder import build_excel as _be
        _build_excel = _be
    return _build_excel

def _get_build_pdf_memo():
    global _build_pdf_memo
    if _build_pdf_memo is None:
        from .output.pdf_memo import build_pdf_memo as _bpm
        _build_pdf_memo = _bpm
    return _build_pdf_memo

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Full pipeline output container."""
    # 3-Statement Model
    income_statement: Optional[IncomeStatementResult] = None
    balance_sheet: Optional[BalanceSheetResult] = None
    cash_flow: Optional[CashFlowResult] = None
    # Schedules
    working_capital: Optional[WorkingCapitalResult] = None
    capex_da: Optional[CapexDAResult] = None
    debt_schedule: Optional[DebtScheduleResult] = None
    # Valuation
    wacc: Optional[WACCResult] = None
    dcf: Optional[DCFResult] = None
    scenario_comparison: Optional[ScenarioComparisonResult] = None
    monte_carlo: Optional[MonteCarloResult] = None
    sensitivity: Optional[SensitivityResult] = None
    tornado: Optional[TornadoResult] = None
    # Comps
    comps: Optional[CompsResult] = None
    # Output paths
    excel_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    # Audit
    errors: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)


def _run_step(name: str, func, result: PipelineResult, *args, **kwargs):
    """Execute a pipeline step with timing and error capture."""
    t0 = time.time()
    try:
        logger.info("Starting: %s", name)
        out = func(*args, **kwargs)
        result.timings[name] = time.time() - t0
        logger.info("Completed: %s (%.2fs)", name, result.timings[name])
        return out
    except Exception as e:
        result.timings[name] = time.time() - t0
        err_msg = f"{name}: {type(e).__name__}: {e}"
        result.errors.append(err_msg)
        logger.error(err_msg, exc_info=True)
        return None


def run_pipeline(
    cfg: DCFEngineConfig,
    historical: Optional[pd.DataFrame] = None,
    base_year_revenue: float = 0.0,
    base_cash: float = 0.0,
    base_ppe: float = 0.0,
    base_nwc: float = 0.0,
    base_retained_earnings: float = 0.0,
    base_common_stock: float = 0.0,
    output_excel: Optional[str] = None,
    output_pdf: Optional[str] = None,
) -> PipelineResult:
    """
    Run the full DCF pipeline.

    Parameters
    ----------
    cfg : DCFEngineConfig — master config.
    historical : Optional historical financial data (tidy format).
    base_year_revenue : Last year's revenue.
    output_excel : Path for Excel output.
    output_pdf : Path for PDF output.
    """
    result = PipelineResult()
    hist = historical if historical is not None else pd.DataFrame()
    base_scenario = cfg.scenarios.get("Base", ScenarioOverrides(name="Base"))

    # ── Step 1: Income Statement ─────────────────────────────────────
    is_result = _run_step("Income Statement", build_income_statement,
                          result, hist, cfg.forecast, base_scenario, base_year_revenue)
    result.income_statement = is_result
    if is_result is None:
        logger.error("Income Statement failed. Aborting pipeline.")
        return result

    is_table = is_result.table
    revenue_list = is_table["Revenue"].tolist()
    cogs_list = is_table["COGS"].tolist()

    # ── Step 2: Working Capital ──────────────────────────────────────
    wc_result = _run_step("Working Capital", build_working_capital,
                          result, revenue_list, cogs_list, cfg.forecast,
                          base_scenario, base_nwc, base_cash)
    result.working_capital = wc_result

    # ── Step 3: Capex & D&A ──────────────────────────────────────────
    cd_result = _run_step("Capex & DA", build_capex_da,
                          result, revenue_list, cfg.forecast, base_scenario, base_ppe)
    result.capex_da = cd_result

    # ── Step 3b: Auto-create debt tranche from valuation.debt ────────
    # The Excel Assumptions sheet populates Debt Beginning Balance (B51)
    # from valuation.debt when no explicit tranches exist.  Mirror that
    # logic here so the Python debt schedule produces the same interest
    # figures the formula-linked Excel model does.
    if not cfg.debt_tranches and cfg.valuation.debt > 0:
        from .config import DebtTranche as _DT
        from .valuation.wacc import synthetic_credit_spread
        # Derive interest rate from WACC config (risk-free + synthetic spread)
        # instead of hardcoding, so Interest Expense is consistent with WACC.
        _rating, _spread = synthetic_credit_spread(cfg.wacc.interest_coverage_ratio)
        _auto_rate = cfg.wacc.risk_free_rate + _spread
        cfg.debt_tranches.append(_DT(
            name="Auto (from Equity Bridge)",
            beginning_balance=cfg.valuation.debt,
            interest_rate=_auto_rate,
            annual_amortisation=0.0,
            maturity_year=cfg.forecast.projection_years,
        ))
        logger.info("Auto-created debt tranche from valuation.debt: %.0f @ %.2f%%",
                    cfg.valuation.debt, _auto_rate * 100)

    # ── Step 4: Debt Schedule ────────────────────────────────────────
    ds_result = _run_step("Debt Schedule", build_debt_schedule,
                          result, cfg.debt_tranches, cfg.forecast.projection_years)
    result.debt_schedule = ds_result

    # ── Step 5: Link D&A and Interest back to IS ─────────────────────
    if cd_result and ds_result:
        for idx in range(len(is_table)):
            yr = is_table.loc[idx, "year_index"]
            # Depreciation from capex schedule
            cd_row = cd_result.table[cd_result.table["year_index"] == yr]
            if not cd_row.empty:
                dep = float(cd_row.iloc[0].get("Depreciation", 0))
                is_table.loc[idx, "Depreciation"] = dep
                is_table.loc[idx, "Total D&A"] = dep + is_table.loc[idx, "Amortisation"]
            # Interest from debt schedule
            ds_row = ds_result.table[ds_result.table["year_index"] == yr]
            if not ds_row.empty:
                interest = float(ds_row.iloc[0].get("Interest Expense", 0))
                is_table.loc[idx, "Interest Expense"] = interest

            # Recalculate downstream
            is_table.loc[idx, "EBIT"] = is_table.loc[idx, "EBITDA"] - is_table.loc[idx, "Total D&A"]
            is_table.loc[idx, "EBT"] = is_table.loc[idx, "EBIT"] - is_table.loc[idx, "Interest Expense"]
            is_table.loc[idx, "Tax Expense"] = max(is_table.loc[idx, "EBT"] * cfg.forecast.tax_rate, 0)
            is_table.loc[idx, "Net Income"] = is_table.loc[idx, "EBT"] - is_table.loc[idx, "Tax Expense"]

    # ── Step 6: Balance Sheet ────────────────────────────────────────
    bs_result = _run_step(
        "Balance Sheet", build_balance_sheet, result,
        is_table,
        wc_result.table if wc_result else pd.DataFrame(),
        cd_result.table if cd_result else pd.DataFrame(),
        ds_result.table if ds_result else pd.DataFrame(),
        dividend_payout_ratio=cfg.forecast.dividend_payout_ratio,
        base_retained_earnings=base_retained_earnings,
        base_common_stock=base_common_stock,
    )
    result.balance_sheet = bs_result

    # ── Step 7: Cash Flow Statement ──────────────────────────────────
    cf_result = _run_step(
        "Cash Flow Statement", build_cash_flow_statement, result,
        is_table,
        wc_result.table if wc_result else pd.DataFrame(),
        cd_result.table if cd_result else pd.DataFrame(),
        ds_result.table if ds_result else pd.DataFrame(),
        tax_rate=cfg.forecast.tax_rate,
        beginning_cash=base_cash,
        dividend_payout_ratio=cfg.forecast.dividend_payout_ratio,
    )
    result.cash_flow = cf_result

    # ── Step 7b: WACC capital-structure weights ───────────────────────
    # Respect the user's explicit WACC weight inputs.  The target
    # capital structure is an assumption about the *optimal* structure,
    # not necessarily what the model carries today.  IB-grade models
    # let the analyst set D/E weights independently of model debt.
    logger.info(
        "WACC weights (user-set): D=%.1f%% E=%.1f%%",
        cfg.wacc.target_debt_weight * 100,
        cfg.wacc.target_equity_weight * 100,
    )

    # ── Step 8: WACC ─────────────────────────────────────────────────
    wacc_result = _run_step("WACC", compute_wacc, result, cfg.wacc, cfg.company.ticker)
    result.wacc = wacc_result

    # ── Step 9: DCF ──────────────────────────────────────────────────
    if cf_result and wacc_result:
        # Add EBITDA to FCF table for terminal value
        fcf = cf_result.fcf_table.copy()
        if "EBITDA" not in fcf.columns:
            fcf["EBITDA"] = is_table["EBITDA"].values[:len(fcf)]

        dcf_result = _run_step("DCF", run_dcf, result, fcf, wacc_result, cfg.valuation)
        result.dcf = dcf_result

    # ── Step 10: Scenarios ───────────────────────────────────────────
    scenarios_dict = {}
    for name, overrides in cfg.scenarios.items():
        s_is = _run_step(f"Scenario IS ({name})", build_income_statement,
                         result, hist, cfg.forecast, overrides, base_year_revenue)
        if s_is is None:
            continue
        s_rev = s_is.table["Revenue"].tolist()
        s_cogs = s_is.table["COGS"].tolist()
        s_wc = build_working_capital(s_rev, s_cogs, cfg.forecast, overrides, base_nwc, base_cash)
        s_cd = build_capex_da(s_rev, cfg.forecast, overrides, base_ppe)
        s_cf = build_cash_flow_statement(
            s_is.table, s_wc.table, s_cd.table,
            ds_result.table if ds_result else pd.DataFrame(),
            cfg.forecast.tax_rate, base_cash, cfg.forecast.dividend_payout_ratio,
        )
        s_fcf = s_cf.fcf_table.copy()
        if "EBITDA" not in s_fcf.columns:
            s_fcf["EBITDA"] = s_is.table["EBITDA"].values[:len(s_fcf)]

        s_dcf = run_dcf(s_fcf, wacc_result, cfg.valuation) if wacc_result else None
        dcf_summary = {}
        if s_dcf:
            dcf_summary = {
                "WACC": wacc_result.wacc,
                "Terminal Growth": cfg.valuation.terminal_growth_rate,
                "Exit Multiple": cfg.valuation.exit_ev_ebitda_multiple,
                "EV (Gordon)": s_dcf.ev_gordon, "EV (Exit)": s_dcf.ev_exit,
                "EV (Blended)": s_dcf.ev_blended,
                "Equity (Gordon)": s_dcf.equity_gordon, "Equity (Exit)": s_dcf.equity_exit,
                "Equity (Blended)": s_dcf.equity_blended,
                "Price (Gordon)": s_dcf.price_gordon, "Price (Exit)": s_dcf.price_exit,
                "Price (Blended)": s_dcf.price_blended,
                "Revenue Yr5": float(s_is.table.iloc[-1]["Revenue"]),
                "EBITDA Yr5": float(s_is.table.iloc[-1]["EBITDA"]),
                "EBITDA Margin Yr5": float(s_is.table.iloc[-1]["EBITDA Margin"]),
                "Total FCF (5yr)": float(s_fcf["Unlevered FCF"].sum()),
                "TV % of EV": s_dcf.tv_pct_of_ev,
            }
        scenarios_dict[name] = ScenarioResult(
            name=name, income_statement=s_is.table,
            balance_sheet=pd.DataFrame(), cash_flow=s_cf.table,
            fcf_table=s_fcf, dcf_summary=dcf_summary,
        )

    scen_comp = _run_step("Scenario Comparison", build_scenario_comparison, result, scenarios_dict)
    result.scenario_comparison = scen_comp

    # ── Step 11: Monte Carlo ─────────────────────────────────────────
    if result.dcf:
        mc_result = _run_step(
            "Monte Carlo", run_monte_carlo, result,
            base_year_revenue,
            cfg.forecast.cogs_pct_revenue,  # approximate EBITDA margin
            wacc_result.wacc if wacc_result else 0.10,
            cfg.valuation.terminal_growth_rate,
            cfg.valuation.exit_ev_ebitda_multiple,
            cfg.forecast.projection_years,
            cfg.monte_carlo,
            cfg.forecast.tax_rate,
            cfg.forecast.capex_pct_revenue,
            cfg.forecast.depreciation_rate,
            cfg.valuation.cash, cfg.valuation.debt,
            cfg.valuation.fully_diluted_shares,
        )
        result.monte_carlo = mc_result

    # ── Step 12: Sensitivity ─────────────────────────────────────────
    if result.dcf and wacc_result:
        sens = _run_step(
            "Sensitivity", build_sensitivity_tables, result,
            result.dcf.equity_blended, wacc_result.wacc,
            cfg.valuation.terminal_growth_rate,
            cfg.forecast.revenue_cagr,
            1.0 - cfg.forecast.cogs_pct_revenue - cfg.forecast.sga_pct_revenue - cfg.forecast.other_opex_pct_revenue,
            base_year_revenue, cfg.forecast.projection_years,
            cfg.sensitivity, cfg.forecast.tax_rate,
            cfg.forecast.capex_pct_revenue,
            cfg.forecast.depreciation_rate,
            cfg.valuation.cash, cfg.valuation.debt,
            cfg.valuation.exit_ev_ebitda_multiple,
        )
        result.sensitivity = sens

    # ── Step 13: Tornado ─────────────────────────────────────────────
    if result.dcf and wacc_result:
        ebitda_margin = 1.0 - cfg.forecast.cogs_pct_revenue - cfg.forecast.sga_pct_revenue - cfg.forecast.other_opex_pct_revenue
        tornado = _run_step(
            "Tornado", build_tornado, result,
            result.dcf.equity_blended, base_year_revenue,
            ebitda_margin, wacc_result.wacc,
            cfg.valuation.terminal_growth_rate,
            cfg.valuation.exit_ev_ebitda_multiple,
            cfg.forecast.revenue_cagr,
            cfg.forecast.tax_rate,
            cfg.forecast.capex_pct_revenue,
            cfg.forecast.projection_years,
            0.20, cfg.valuation.cash, cfg.valuation.debt,
        )
        result.tornado = tornado

    # ── Step 14: Comps ───────────────────────────────────────────────
    if cfg.comps.peer_tickers:
        target_rev = float(is_table.iloc[-1]["Revenue"]) if len(is_table) else 0
        target_ebitda = float(is_table.iloc[-1]["EBITDA"]) if len(is_table) else 0
        target_ni = float(is_table.iloc[-1]["Net Income"]) if len(is_table) else 0
        comps = _run_step(
            "Comps", build_comps, result, cfg.comps,
            target_rev, target_ebitda, target_ni,
            cfg.valuation.cash, cfg.valuation.debt,
        )
        result.comps = comps

    # ── Step 15: Excel Output ────────────────────────────────────────
    if output_excel:
        # Extract credit spread from WACC result
        _credit_spread = 0.02
        if wacc_result and hasattr(wacc_result, 'credit_spread'):
            _credit_spread = wacc_result.credit_spread
        elif wacc_result:
            _credit_spread = getattr(wacc_result, 'pre_tax_kd', 0.06) - (wacc_result.risk_free_rate if hasattr(wacc_result, 'risk_free_rate') else 0.04)

        excel_path = _run_step(
            "Excel Output", _get_build_excel(), result,
            output_excel, cfg,
            base_revenue=base_year_revenue,
            base_cash=base_cash,
            base_ppe=base_ppe,
            base_nwc=base_nwc,
            base_retained_earnings=base_retained_earnings,
            base_common_stock=base_common_stock,
            debt_schedule_table=ds_result.table if ds_result else None,
            scenario_comparison=scen_comp,
            sensitivity_result=result.sensitivity,
            monte_carlo_result=result.monte_carlo,
            tornado_result=result.tornado,
            comps_result=result.comps,
            credit_spread=_credit_spread,
        )
        result.excel_path = excel_path

    # ── Step 16: PDF Output ──────────────────────────────────────────
    if output_pdf:
        pdf_path = _run_step(
            "PDF Output", _get_build_pdf_memo(), result,
            output_pdf, cfg,
            income_stmt=is_table,
            balance_sheet_table=bs_result.table if bs_result else None,
            cash_flow_table=cf_result.table if cf_result else None,
            fcf_table=cf_result.fcf_table if cf_result else None,
            wacc_result=wacc_result,
            dcf_result=result.dcf,
            scenario_comparison=scen_comp,
            sensitivity_result=result.sensitivity,
            monte_carlo_result=result.monte_carlo,
            tornado_result=result.tornado,
            comps_result=result.comps,
        )
        result.pdf_path = pdf_path

    # ── Summary ──────────────────────────────────────────────────────
    total_time = sum(result.timings.values())
    logger.info("Pipeline complete in %.2fs (%d errors)", total_time, len(result.errors))
    if result.errors:
        for err in result.errors:
            logger.warning("  ERROR: %s", err)

    return result
