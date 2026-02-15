"""
Tornado chart — key value driver analysis.

Identifies the top value drivers by swinging each ±20% while holding
all others at base. Outputs ranked impact data for horizontal bar charts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import pandas as pd


@dataclass
class TornadoResult:
    """Ranked value-driver impacts for tornado chart rendering."""
    drivers: pd.DataFrame   # driver_name, low_value, high_value, base_value, impact
    base_equity: float


def build_tornado(
    base_equity: float,
    base_revenue: float,
    base_ebitda_margin: float,
    base_wacc: float,
    base_terminal_growth: float,
    base_exit_multiple: float,
    base_revenue_growth: float,
    base_tax_rate: float,
    base_capex_pct: float,
    projection_years: int = 5,
    swing_pct: float = 0.20,
    cash: float = 0.0,
    debt: float = 0.0,
) -> TornadoResult:
    """
    Build tornado chart data by swinging each driver ±swing_pct.

    Returns a DataFrame sorted by absolute impact (largest first).
    """
    drivers = {
        "Revenue Growth": base_revenue_growth,
        "EBITDA Margin": base_ebitda_margin,
        "WACC": base_wacc,
        "Terminal Growth": base_terminal_growth,
        "Exit Multiple": base_exit_multiple,
        "Tax Rate": base_tax_rate,
        "Capex % Revenue": base_capex_pct,
    }

    results = []

    for driver_name, base_val in drivers.items():
        low_input = base_val * (1 - swing_pct)
        high_input = base_val * (1 + swing_pct)

        # Clamp
        if driver_name == "WACC":
            low_input = max(low_input, 0.03)
            high_input = min(high_input, 0.30)
        elif driver_name == "Terminal Growth":
            low_input = max(low_input, 0.0)
            high_input = min(high_input, 0.05)
        elif driver_name in ("EBITDA Margin", "Tax Rate", "Capex % Revenue"):
            low_input = max(low_input, 0.01)
            high_input = min(high_input, 0.60)

        low_eq = _compute_equity(
            base_revenue, base_ebitda_margin, base_wacc, base_terminal_growth,
            base_exit_multiple, base_revenue_growth, base_tax_rate, base_capex_pct,
            projection_years, cash, debt,
            override={driver_name: low_input}
        )

        high_eq = _compute_equity(
            base_revenue, base_ebitda_margin, base_wacc, base_terminal_growth,
            base_exit_multiple, base_revenue_growth, base_tax_rate, base_capex_pct,
            projection_years, cash, debt,
            override={driver_name: high_input}
        )

        # For WACC and Tax Rate, higher input → lower equity
        results.append({
            "Driver": driver_name,
            "Base Input": base_val,
            "Low Input": low_input,
            "High Input": high_input,
            "Equity at Low": low_eq,
            "Equity at High": high_eq,
            "Impact": abs(high_eq - low_eq),
        })

    df = pd.DataFrame(results).sort_values("Impact", ascending=True).reset_index(drop=True)

    return TornadoResult(drivers=df, base_equity=base_equity)


def _compute_equity(
    base_revenue: float,
    margin: float,
    wacc: float,
    tg: float,
    exit_mult: float,
    rev_growth: float,
    tax_rate: float,
    capex_pct: float,
    years: int,
    cash: float,
    debt: float,
    override: Dict[str, float] | None = None,
) -> float:
    """Quick DCF with one driver overridden."""
    o = override or {}
    margin = o.get("EBITDA Margin", margin)
    wacc = o.get("WACC", wacc)
    tg = o.get("Terminal Growth", tg)
    exit_mult = o.get("Exit Multiple", exit_mult)
    rev_growth = o.get("Revenue Growth", rev_growth)
    tax_rate = o.get("Tax Rate", tax_rate)
    capex_pct = o.get("Capex % Revenue", capex_pct)

    wacc = max(wacc, tg + 0.005)

    revenue = base_revenue
    pv_sum = 0.0
    last_fcf = 0.0
    last_ebitda = 0.0

    for yr in range(1, years + 1):
        revenue *= (1 + rev_growth)
        ebitda = revenue * margin
        da = revenue * 0.04
        ebit = ebitda - da
        nopat = ebit * (1 - tax_rate)
        capex = revenue * capex_pct
        fcf = nopat + da - capex
        df = 1.0 / ((1 + wacc) ** (yr - 0.5))
        pv_sum += fcf * df
        last_fcf = fcf
        last_ebitda = ebitda

    gordon_tv = last_fcf * (1 + tg) / (wacc - tg)
    exit_tv = last_ebitda * exit_mult
    tv = (gordon_tv + exit_tv) / 2.0
    pv_tv = tv / ((1 + wacc) ** (years - 0.5))

    return pv_sum + pv_tv + cash - debt
