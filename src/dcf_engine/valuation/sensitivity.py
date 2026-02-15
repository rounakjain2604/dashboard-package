"""
2D sensitivity tables.

Generates data tables for:
1. WACC vs Terminal Growth Rate → Equity Value
2. Revenue Growth vs EBITDA Margin → Equity Value
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from ..config import SensitivityConfig


@dataclass
class SensitivityResult:
    wacc_vs_growth: pd.DataFrame   # rows=terminal_growth, cols=wacc
    revenue_vs_margin: pd.DataFrame   # rows=margin, cols=revenue_growth
    wacc_values: List[float]
    growth_values: List[float]
    rev_growth_values: List[float]
    margin_values: List[float]


def build_sensitivity_tables(
    base_equity: float,
    base_wacc: float,
    base_terminal_growth: float,
    base_revenue_growth: float,
    base_ebitda_margin: float,
    base_revenue: float,
    projection_years: int,
    cfg: SensitivityConfig,
    tax_rate: float = 0.25,
    capex_pct: float = 0.04,
    da_pct: float = 0.04,
    cash: float = 0.0,
    debt: float = 0.0,
    exit_mult: float = 10.0,
    gordon_weight: float = 0.50,
) -> SensitivityResult:
    """
    Build two 2D sensitivity tables.

    Each cell runs a simplified DCF to compute equity value under
    the changed assumptions.
    """
    # ── Table 1: WACC vs Terminal Growth ─────────────────────────────
    wacc_vals = [base_wacc + d for d in cfg.wacc_range]
    growth_vals = [base_terminal_growth + d for d in cfg.terminal_growth_range]

    wacc_vals = [max(w, 0.03) for w in wacc_vals]
    growth_vals = [max(g, 0.0) for g in growth_vals]

    tbl1 = pd.DataFrame(
        index=[f"{g:.1%}" for g in growth_vals],
        columns=[f"{w:.1%}" for w in wacc_vals],
        dtype=float,
    )

    for gi, g in enumerate(growth_vals):
        for wi, w in enumerate(wacc_vals):
            ev = _quick_dcf(base_revenue, base_ebitda_margin, w, g,
                            projection_years, tax_rate, capex_pct, da_pct,
                            base_revenue_growth, cash, debt, exit_mult,
                            gordon_weight)
            tbl1.iloc[gi, wi] = ev

    tbl1.index.name = "Terminal Growth ↓ / WACC →"

    # ── Table 2: Revenue Growth vs EBITDA Margin ─────────────────────
    rev_vals = [base_revenue_growth + d for d in cfg.revenue_growth_range]
    margin_vals = [base_ebitda_margin + d for d in cfg.ebitda_margin_range]
    rev_vals = [max(r, -0.10) for r in rev_vals]
    margin_vals = [max(m, 0.01) for m in margin_vals]

    tbl2 = pd.DataFrame(
        index=[f"{m:.1%}" for m in margin_vals],
        columns=[f"{r:.1%}" for r in rev_vals],
        dtype=float,
    )

    for mi, m in enumerate(margin_vals):
        for ri, r in enumerate(rev_vals):
            ev = _quick_dcf(base_revenue, m, base_wacc, base_terminal_growth,
                            projection_years, tax_rate, capex_pct, da_pct,
                            r, cash, debt, exit_mult, gordon_weight)
            tbl2.iloc[mi, ri] = ev

    tbl2.index.name = "EBITDA Margin ↓ / Rev Growth →"

    return SensitivityResult(
        wacc_vs_growth=tbl1,
        revenue_vs_margin=tbl2,
        wacc_values=wacc_vals,
        growth_values=growth_vals,
        rev_growth_values=rev_vals,
        margin_values=margin_vals,
    )


def _quick_dcf(
    base_rev: float,
    margin: float,
    wacc: float,
    tg: float,
    years: int,
    tax: float,
    capex_pct: float,
    da_pct: float,
    rev_growth: float,
    cash: float,
    debt: float,
    exit_mult: float = 10.0,
    gordon_weight: float = 0.50,
) -> float:
    """Simplified DCF for sensitivity table cells."""
    wacc = max(wacc, tg + 0.005)
    revenue = base_rev
    pv_sum = 0.0
    last_fcf = 0.0
    last_ebitda = 0.0

    for yr in range(1, years + 1):
        revenue *= (1 + rev_growth)
        ebitda = revenue * margin
        da = revenue * da_pct
        ebit = ebitda - da
        nopat = ebit * (1 - tax)
        capex = revenue * capex_pct
        fcf = nopat + da - capex
        df = 1.0 / ((1 + wacc) ** (yr - 0.5))
        pv_sum += fcf * df
        last_fcf = fcf
        last_ebitda = ebitda

    gordon_tv = last_fcf * (1 + tg) / (wacc - tg)
    exit_tv = last_ebitda * exit_mult
    tv = gordon_tv * gordon_weight + exit_tv * (1 - gordon_weight)
    pv_tv = tv / ((1 + wacc) ** (years - 0.5))  # mid-year consistency

    ev = pv_sum + pv_tv
    return ev + cash - debt
