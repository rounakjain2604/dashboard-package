"""
IB-Grade Excel workbook generator — fully formula-linked.

Core model tabs (IS, BS, CF, WC, CapexDA, WACC, DCF) use Excel formulas
referencing the Assumptions sheet. Analytics tabs (MC, Sensitivity, Tornado,
Comps, Scenarios) use computed values from Python simulations.

All cells use Verdana font. Sheets are set to fit-to-width for printing.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def build_excel(
    output_path: str | Path,
    cfg: "DCFEngineConfig",
    # Base year values for Assumptions sheet
    base_revenue: float = 0,
    base_cash: float = 0,
    base_ppe: float = 0,
    base_nwc: float = 0,
    base_retained_earnings: float = 0,
    base_common_stock: float = 0,
    # Computed results (for value-based tabs only)
    debt_schedule_table: Optional[pd.DataFrame] = None,
    scenario_comparison=None,
    sensitivity_result=None,
    monte_carlo_result=None,
    tornado_result=None,
    comps_result=None,
    credit_spread: float = 0.02,
    **kwargs,  # Accept and ignore legacy parameters
) -> Path:
    """Build the fully formula-linked IB-grade Excel workbook."""
    from openpyxl import Workbook
    from .sheets_core import (
        build_cover, build_assumptions, build_is,
        build_wc, build_capex_da, build_debt_schedule,
    )
    from .sheets_valuation import build_bs, build_cf, build_wacc, build_dcf
    from .sheets_analytics import (
        build_scenarios, build_sensitivity, build_monte_carlo,
        build_tornado, build_comps, build_checks, build_audit,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n = cfg.forecast.projection_years

    wb = Workbook()
    wb.remove(wb.active)

    # ── Formula-Linked Core Model ────────────────────────────────────
    build_cover(wb, cfg)
    build_assumptions(wb, cfg, base_revenue, base_cash, base_ppe,
                      base_nwc, base_retained_earnings, base_common_stock,
                      credit_spread)
    build_is(wb, n)
    build_wc(wb, n)
    build_capex_da(wb, n)
    build_debt_schedule(wb, n, debt_schedule_table)
    build_bs(wb, n)
    build_cf(wb, n)
    build_wacc(wb, credit_spread)
    build_dcf(wb, n)

    # ── Value-Based Analytics ────────────────────────────────────────
    build_scenarios(wb, scenario_comparison)
    build_sensitivity(wb, sensitivity_result)
    build_monte_carlo(wb, monte_carlo_result, cfg.monte_carlo)
    build_tornado(wb, tornado_result)
    build_comps(wb, comps_result)
    build_checks(wb, n)
    build_audit(wb, cfg)

    wb.save(str(output_path))
    logger.info("Excel workbook saved to %s", output_path)
    return output_path
