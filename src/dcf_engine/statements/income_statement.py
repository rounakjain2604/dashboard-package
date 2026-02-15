"""
Income Statement builder.

Takes historical financials + forecast assumptions and produces a fully
linked projected Income Statement for the specified number of years.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from ..config import ForecastConfig, ScenarioOverrides


@dataclass
class IncomeStatementResult:
    """Projected Income Statement rows for all forecast years."""
    table: pd.DataFrame  # columns: year_index, period, Revenue … Net Income
    historical: Optional[pd.DataFrame] = None


def build_income_statement(
    historical: pd.DataFrame,
    cfg: ForecastConfig,
    scenario: ScenarioOverrides,
    base_year_revenue: float,
) -> IncomeStatementResult:
    """
    Build a multi-year projected Income Statement.

    Parameters
    ----------
    historical : DataFrame
        Tidy historical data (period, account, amount, statement).
    cfg : ForecastConfig
        Base forecast assumptions.
    scenario : ScenarioOverrides
        Scenario-specific tweaks.
    base_year_revenue : float
        The last historical year's revenue (starting point).

    Returns
    -------
    IncomeStatementResult
        A DataFrame with one row per projection year.
    """
    hist_summary = _summarise_historical(historical)
    rows: List[dict] = []
    revenue = base_year_revenue

    # Compute base COGS/SGA ratios from history for overlay
    hist_cogs_pct = _hist_ratio(hist_summary, "COGS", "Revenue", default=cfg.cogs_pct_revenue)
    hist_sga_pct = _hist_ratio(hist_summary, "SGA", "Revenue", default=cfg.sga_pct_revenue)

    # Apply revenue_multiplier once to the base (not compounded each year)
    revenue = revenue * scenario.revenue_multiplier

    for idx in range(1, cfg.projection_years + 1):
        # ── Revenue ──────────────────────────────────────────────────
        growth = _revenue_growth(cfg, scenario, idx)
        revenue = revenue * (1 + growth)

        # ── COGS ─────────────────────────────────────────────────────
        cogs_pct = cfg.cogs_pct_revenue
        if cfg.cogs_yoy and idx <= len(cfg.cogs_yoy):
            cogs_pct = cfg.cogs_yoy[idx - 1]

        # Apply margin shift to COGS (lower COGS = higher margin)
        margin_shift = scenario.margin_delta_bps / 10_000
        cogs = revenue * cogs_pct * (1 - margin_shift)

        gross_profit = revenue - cogs
        gross_margin = gross_profit / revenue if revenue else 0

        # ── SGA ──────────────────────────────────────────────────────
        sga = revenue * cfg.sga_pct_revenue

        # ── Other OpEx ───────────────────────────────────────────────
        other_opex = revenue * cfg.other_opex_pct_revenue

        # ── EBITDA ───────────────────────────────────────────────────
        ebitda = gross_profit - sga - other_opex
        if scenario.ebitda_margin_override is not None:
            ebitda = revenue * scenario.ebitda_margin_override

        ebitda_margin = ebitda / revenue if revenue else 0

        # ── D&A (placeholder — real values come from capex schedule) ─
        depreciation = 0.0  # Will be overwritten by capex_depreciation schedule
        amortisation = revenue * cfg.amortisation_pct_revenue
        total_da = depreciation + amortisation

        # ── EBIT ─────────────────────────────────────────────────────
        ebit = ebitda - total_da

        # ── Interest (placeholder — comes from debt schedule) ────────
        interest_expense = 0.0  # Will be overwritten by debt schedule

        # ── EBT ──────────────────────────────────────────────────────
        ebt = ebit - interest_expense

        # ── Tax ──────────────────────────────────────────────────────
        tax = max(ebt * cfg.tax_rate, 0)

        # ── Net Income ───────────────────────────────────────────────
        net_income = ebt - tax

        rows.append({
            "year_index": idx,
            "Revenue": revenue,
            "Revenue Growth": growth,
            "COGS": cogs,
            "Gross Profit": gross_profit,
            "Gross Margin": gross_margin,
            "SGA": sga,
            "Other OpEx": other_opex,
            "EBITDA": ebitda,
            "EBITDA Margin": ebitda_margin,
            "Depreciation": depreciation,
            "Amortisation": amortisation,
            "Total D&A": total_da,
            "EBIT": ebit,
            "Interest Expense": interest_expense,
            "EBT": ebt,
            "Tax Expense": tax,
            "Net Income": net_income,
        })

    table = pd.DataFrame(rows)
    return IncomeStatementResult(table=table, historical=hist_summary)


# ── Helpers ──────────────────────────────────────────────────────────
def _revenue_growth(cfg: ForecastConfig, scenario: ScenarioOverrides, year_idx: int) -> float:
    """Determine revenue growth rate for a given year."""
    if scenario.revenue_growth_override is not None:
        return scenario.revenue_growth_override

    if cfg.revenue_method == "cagr":
        return cfg.revenue_cagr
    if cfg.revenue_method == "yoy":
        if year_idx <= len(cfg.revenue_yoy):
            return cfg.revenue_yoy[year_idx - 1]
        return cfg.revenue_yoy[-1] if cfg.revenue_yoy else cfg.revenue_cagr
    if cfg.revenue_method == "manual":
        return cfg.revenue_manual.get(year_idx, cfg.revenue_cagr)
    return cfg.revenue_cagr


def _summarise_historical(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Pivot historical data into a summary table."""
    if df is None or df.empty:
        return None
    try:
        pivot = (
            df.groupby(["period", "account"])["amount"]
            .sum()
            .reset_index()
            .pivot(index="period", columns="account", values="amount")
            .fillna(0)
            .reset_index()
            .sort_values("period")
        )
        return pivot
    except Exception:
        return None


def _hist_ratio(summary: Optional[pd.DataFrame], numerator: str, denominator: str, default: float) -> float:
    if summary is None or numerator not in summary.columns or denominator not in summary.columns:
        return default
    num = summary[numerator].iloc[-1]
    den = summary[denominator].iloc[-1]
    return float(num / den) if den else default
