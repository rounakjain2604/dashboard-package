"""
Working Capital schedule.

Calculates AR, Inventory, AP, and other current items based on
DSO / DIO / DPO assumptions.  Outputs year-over-year changes for
the Cash Flow Statement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import numpy as np

from ..config import ForecastConfig, ScenarioOverrides


@dataclass
class WorkingCapitalResult:
    table: pd.DataFrame   # year_index, AR, Inventory, AP, NWC, Delta NWC, etc.


def build_working_capital(
    revenue_by_year: list[float],
    cogs_by_year: list[float],
    cfg: ForecastConfig,
    scenario: ScenarioOverrides,
    base_nwc: float = 0.0,
    base_cash: float = 0.0,
) -> WorkingCapitalResult:
    """
    Build a multi-year working capital schedule.

    Parameters
    ----------
    revenue_by_year : Revenue for each projection year (list indexed from 0).
    cogs_by_year : COGS for each projection year.
    cfg : ForecastConfig with DSO, DIO, DPO, etc.
    scenario : ScenarioOverrides with working_capital_days_delta.
    base_nwc : Prior-year NWC to compute delta for year 1.
    """
    rows = []
    prev_nwc = base_nwc

    adj_dso = max(cfg.dso + scenario.working_capital_days_delta, 0)
    adj_dio = max(cfg.dio + scenario.working_capital_days_delta, 0)
    adj_dpo = max(cfg.dpo + scenario.working_capital_days_delta, 0)

    for idx, (rev, cogs) in enumerate(zip(revenue_by_year, cogs_by_year), start=1):
        # Current Assets
        ar = rev * adj_dso / 365
        inventory = cogs * adj_dio / 365
        prepaid = rev * cfg.prepaid_pct_revenue
        other_ca = rev * cfg.other_current_assets_pct_revenue
        cash = base_cash  # Placeholder; BS builder uses cash as plug

        # Current Liabilities
        ap = cogs * adj_dpo / 365
        accrued = rev * cfg.accrued_pct_revenue
        other_cl = rev * cfg.other_current_liabilities_pct_revenue

        # NWC = current assets (excl. cash) - current liabilities (excl. debt)
        nwc = ar + inventory + prepaid + other_ca - ap - accrued - other_cl
        delta_nwc = nwc - prev_nwc

        rows.append({
            "year_index": idx,
            "Accounts Receivable": ar,
            "DSO": adj_dso,
            "Inventory": inventory,
            "DIO": adj_dio,
            "Prepaid": prepaid,
            "Other Current Assets": other_ca,
            "Accounts Payable": ap,
            "DPO": adj_dpo,
            "Accrued Liabilities": accrued,
            "Other Current Liabilities": other_cl,
            "Cash": cash,
            "NWC": nwc,
            "Delta NWC": delta_nwc,
            "Revenue": rev,
            "COGS": cogs,
        })
        prev_nwc = nwc

    return WorkingCapitalResult(table=pd.DataFrame(rows))
