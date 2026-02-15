"""
Debt schedule with interest calculations.

Supports multiple tranches, mandatory amortisation, optional prepayments,
cash sweeps, and automatic interest-expense linkage to the Income Statement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd
import numpy as np

from ..config import DebtTranche


@dataclass
class DebtScheduleResult:
    table: pd.DataFrame         # Consolidated: year_index, Beginning, Interest, Repayment, Ending
    tranche_tables: dict[str, pd.DataFrame]   # Per-tranche detail
    total_interest_by_year: dict[int, float]
    total_debt_by_year: dict[int, float]


def build_debt_schedule(
    tranches: List[DebtTranche],
    projection_years: int = 5,
    excess_cash_flow_by_year: dict[int, float] | None = None,
) -> DebtScheduleResult:
    """
    Build a multi-tranche debt schedule.

    Parameters
    ----------
    tranches : list of DebtTranche configs.
    projection_years : number of forecast years.
    excess_cash_flow_by_year : optional dict {year_index: excess_cf} for cash sweeps.
    """
    if not tranches:
        # Return empty schedule if no debt
        empty_df = pd.DataFrame({
            "year_index": range(1, projection_years + 1),
            "Beginning Balance": 0.0,
            "New Issuance": 0.0,
            "Interest Expense": 0.0,
            "Principal Repayment": 0.0,
            "Ending Balance": 0.0,
            "Current Portion": 0.0,
        })
        return DebtScheduleResult(
            table=empty_df,
            tranche_tables={},
            total_interest_by_year={i: 0.0 for i in range(1, projection_years + 1)},
            total_debt_by_year={i: 0.0 for i in range(1, projection_years + 1)},
        )

    excess_cf = excess_cash_flow_by_year or {}
    tranche_tables = {}

    for tranche in tranches:
        rows = []
        balance = tranche.beginning_balance

        for yr in range(1, projection_years + 1):
            beginning = balance

            # Interest on beginning balance
            interest = beginning * tranche.interest_rate

            # Mandatory amortisation
            mandatory = min(tranche.annual_amortisation, beginning)

            # Optional prepayment
            optional = min(tranche.optional_prepayment, beginning - mandatory)

            # Cash sweep
            ecf = excess_cf.get(yr, 0.0)
            sweep = min(ecf * tranche.cash_sweep_pct, max(beginning - mandatory - optional, 0))

            total_repayment = mandatory + optional + sweep

            # Bullet maturity
            if yr == tranche.maturity_year:
                bullet = max(beginning - total_repayment, 0)
                total_repayment += bullet
            else:
                bullet = 0.0

            ending = max(beginning - total_repayment, 0)

            # Current portion = next year's mandatory amortisation (if applicable)
            if yr < tranche.maturity_year:
                current_portion = min(tranche.annual_amortisation, ending)
            elif yr == tranche.maturity_year:
                current_portion = ending  # All remaining is current
            else:
                current_portion = 0.0

            rows.append({
                "year_index": yr,
                "Tranche": tranche.name,
                "Beginning Balance": beginning,
                "Interest Rate": tranche.interest_rate,
                "Interest Expense": interest,
                "Mandatory Amort": mandatory,
                "Optional Prepay": optional,
                "Cash Sweep": sweep,
                "Bullet Payment": bullet,
                "Principal Repayment": total_repayment,
                "Ending Balance": ending,
                "Current Portion": current_portion,
            })

            balance = ending

        tranche_tables[tranche.name] = pd.DataFrame(rows)

    # ── Consolidate across tranches ──────────────────────────────────
    consolidated_rows = []
    total_interest = {}
    total_debt = {}

    for yr in range(1, projection_years + 1):
        yr_beginning = 0.0
        yr_interest = 0.0
        yr_repayment = 0.0
        yr_ending = 0.0
        yr_current = 0.0
        yr_new = 0.0

        for tname, tdf in tranche_tables.items():
            t_row = tdf[tdf["year_index"] == yr].iloc[0]
            yr_beginning += t_row["Beginning Balance"]
            yr_interest += t_row["Interest Expense"]
            yr_repayment += t_row["Principal Repayment"]
            yr_ending += t_row["Ending Balance"]
            yr_current += t_row["Current Portion"]

        consolidated_rows.append({
            "year_index": yr,
            "Beginning Balance": yr_beginning,
            "New Issuance": yr_new,
            "Interest Expense": yr_interest,
            "Principal Repayment": yr_repayment,
            "Ending Balance": yr_ending,
            "Current Portion": yr_current,
        })

        total_interest[yr] = yr_interest
        total_debt[yr] = yr_ending

    return DebtScheduleResult(
        table=pd.DataFrame(consolidated_rows),
        tranche_tables=tranche_tables,
        total_interest_by_year=total_interest,
        total_debt_by_year=total_debt,
    )
