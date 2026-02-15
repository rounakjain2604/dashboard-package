"""
Capex & Depreciation schedule.

Models PP&E rollforward: Beginning PP&E → + Capex → − Depreciation → Ending PP&E.
Tracks existing and new-vintage depreciation separately.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import numpy as np

from ..config import ForecastConfig, ScenarioOverrides


@dataclass
class CapexDAResult:
    table: pd.DataFrame   # year_index, Beginning PP&E, Capex, Depreciation, Ending PP&E, etc.


def build_capex_da(
    revenue_by_year: list[float],
    cfg: ForecastConfig,
    scenario: ScenarioOverrides,
    base_ppe: float = 0.0,
    base_accumulated_dep: float = 0.0,
) -> CapexDAResult:
    """
    Build multi-year Capex & Depreciation schedule.

    Parameters
    ----------
    revenue_by_year : Revenue per projection year.
    cfg : ForecastConfig with capex_pct_revenue, depreciation_rate, etc.
    scenario : ScenarioOverrides with capex_multiplier.
    base_ppe : Prior-year gross PP&E.
    base_accumulated_dep : Prior-year accumulated depreciation.
    """
    rows = []
    gross_ppe = base_ppe
    accum_dep = base_accumulated_dep
    net_ppe = gross_ppe - accum_dep

    for idx, rev in enumerate(revenue_by_year, start=1):
        beginning_net = net_ppe

        # Capex
        if cfg.capex_method == "pct_revenue":
            capex = rev * cfg.capex_pct_revenue
        elif cfg.capex_method == "fixed":
            capex = getattr(cfg, 'capex_fixed', 0.0) or cfg.capex_manual.get(idx, 0.0)
        else:
            capex = cfg.capex_manual.get(idx, 0.0)
        capex *= scenario.capex_multiplier

        # Depreciation: on beginning net PP&E + half of new capex
        dep_existing = beginning_net * cfg.depreciation_rate
        dep_new = capex * cfg.depreciation_rate * 0.5  # half-year convention for new
        total_depreciation = dep_existing + dep_new

        # Rollforward
        gross_ppe = gross_ppe + capex
        accum_dep = accum_dep + total_depreciation
        ending_net = gross_ppe - accum_dep
        net_ppe = ending_net

        rows.append({
            "year_index": idx,
            "Beginning PP&E (Net)": beginning_net,
            "Capex": capex,
            "Capex % Revenue": capex / rev if rev else 0,
            "Dep on Existing": dep_existing,
            "Dep on New": dep_new,
            "Depreciation": total_depreciation,
            "Dep % Beg PP&E": total_depreciation / beginning_net if beginning_net else 0,
            "Ending PP&E (Net)": ending_net,
            "Gross PP&E": gross_ppe,
            "Accumulated Dep": accum_dep,
        })

    return CapexDAResult(table=pd.DataFrame(rows))
