"""
Cash Flow Statement builder.

Constructs the CFS from the Income Statement, Working Capital changes,
Capex/D&A schedule, and Debt schedule.  CFO + CFI + CFF = Change in Cash.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import numpy as np


@dataclass
class CashFlowResult:
    """Projected Cash Flow Statement."""
    table: pd.DataFrame
    fcf_table: pd.DataFrame  # Unlevered and Levered FCF


def build_cash_flow_statement(
    income_stmt: pd.DataFrame,
    working_capital: pd.DataFrame,
    capex_da: pd.DataFrame,
    debt_schedule: pd.DataFrame,
    tax_rate: float = 0.25,
    beginning_cash: float = 0.0,
    dividend_payout_ratio: float = 0.0,
) -> CashFlowResult:
    """
    Build multi-year Cash Flow Statement.

    Parameters
    ----------
    income_stmt : DataFrame with year_index, Net Income, D&A, Interest Expense, etc.
    working_capital : DataFrame with year_index, Delta NWC.
    capex_da : DataFrame with year_index, Capex, Depreciation.
    debt_schedule : DataFrame with year_index, New Issuance, Principal Repayment, Interest.
    """
    rows = []
    fcf_rows = []
    cash = beginning_cash

    for idx in range(1, len(income_stmt) + 1):
        is_row = income_stmt[income_stmt["year_index"] == idx].iloc[0]
        wc_row = working_capital[working_capital["year_index"] == idx].iloc[0]
        cd_row = capex_da[capex_da["year_index"] == idx].iloc[0]

        net_income = is_row.get("Net Income", 0.0)
        depreciation = cd_row.get("Depreciation", 0.0)
        amortisation = is_row.get("Amortisation", 0.0)
        total_da = depreciation + amortisation
        delta_nwc = wc_row.get("Delta NWC", 0.0)

        # ── CFO ──────────────────────────────────────────────────────
        # Start with Net Income, add back non-cash, subtract WC increase
        cfo = net_income + total_da - delta_nwc

        # ── CFI ──────────────────────────────────────────────────────
        capex = cd_row.get("Capex", 0.0)
        cfi = -abs(capex)  # Capex is always a cash outflow

        # ── CFF ──────────────────────────────────────────────────────
        if not debt_schedule.empty and idx in debt_schedule["year_index"].values:
            ds_row = debt_schedule[debt_schedule["year_index"] == idx].iloc[0]
            new_debt = ds_row.get("New Issuance", 0.0)
            repayment = ds_row.get("Principal Repayment", 0.0)
            interest = ds_row.get("Interest Expense", 0.0)
        else:
            new_debt = 0.0
            repayment = 0.0
            interest = 0.0

        dividends = net_income * dividend_payout_ratio
        # Interest is NOT included in CFF because it already flows through
        # Net Income → CFO (indirect method).  Including it here would
        # double-count the cash outflow.  This matches the Excel model
        # where Interest Paid = 0 in the CFF section.
        cff = new_debt - repayment - dividends

        # ── Net Change & Ending Cash ─────────────────────────────────
        net_change = cfo + cfi + cff
        ending_cash = cash + net_change

        rows.append({
            "year_index": idx,
            # CFO
            "Net Income": net_income,
            "Depreciation": depreciation,
            "Amortisation": amortisation,
            "Total D&A": total_da,
            "Change in NWC": -delta_nwc,  # decrease in NWC = cash inflow
            "CFO": cfo,
            # CFI
            "Capex": -abs(capex),
            "CFI": cfi,
            # CFF
            "New Debt Issuance": new_debt,
            "Debt Repayment": -repayment,
            "Interest Paid": 0,  # Flows through NI in CFO; see Income Statement
            "Dividends Paid": -dividends,
            "CFF": cff,
            # Summary
            "Net Change in Cash": net_change,
            "Beginning Cash": cash,
            "Ending Cash": ending_cash,
        })

        # ── Unlevered & Levered FCF ──────────────────────────────────
        ebit = is_row.get("EBIT", 0.0)
        nopat = ebit * (1 - tax_rate)
        ufcf = nopat + total_da - abs(capex) - delta_nwc
        lfcf = ufcf - interest * (1 - tax_rate) - repayment + new_debt

        fcf_rows.append({
            "year_index": idx,
            "EBIT": ebit,
            "NOPAT": nopat,
            "D&A": total_da,
            "Capex": -abs(capex),
            "Delta NWC": -delta_nwc,
            "Unlevered FCF": ufcf,
            "Interest (after-tax)": -interest * (1 - tax_rate),
            "Debt Repayment": -repayment,
            "New Issuance": new_debt,
            "Levered FCF": lfcf,
        })

        cash = ending_cash

    return CashFlowResult(
        table=pd.DataFrame(rows),
        fcf_table=pd.DataFrame(fcf_rows),
    )
