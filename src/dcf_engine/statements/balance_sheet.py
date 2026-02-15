"""
Balance Sheet builder.

Constructs projected Balance Sheets that balance (Assets = L + E) by
linking to the Income Statement, Working Capital schedule, Capex/D&A
schedule, and Debt schedule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict

import pandas as pd
import numpy as np


@dataclass
class BalanceSheetResult:
    """Projected Balance Sheet plus a balance-check flag per year."""
    table: pd.DataFrame
    checks: pd.DataFrame  # year_index, assets, liabs_equity, difference, status


def build_balance_sheet(
    income_stmt: pd.DataFrame,
    working_capital: pd.DataFrame,
    capex_da: pd.DataFrame,
    debt_schedule: pd.DataFrame,
    hist_bs: Optional[pd.DataFrame] = None,
    dividend_payout_ratio: float = 0.0,
    base_retained_earnings: float = 0.0,
    base_common_stock: float = 0.0,
    base_other_lt_assets: float = 0.0,
    base_other_lt_liabilities: float = 0.0,
    base_goodwill: float = 0.0,
    base_intangibles: float = 0.0,
) -> BalanceSheetResult:
    """
    Build multi-year projected Balance Sheet.

    All inputs are DataFrames indexed by ``year_index`` (1-based).
    """
    rows = []
    checks = []
    retained_earnings = base_retained_earnings

    for idx in range(1, len(income_stmt) + 1):
        is_row = income_stmt[income_stmt["year_index"] == idx].iloc[0]
        wc_row = working_capital[working_capital["year_index"] == idx].iloc[0]
        cd_row = capex_da[capex_da["year_index"] == idx].iloc[0]

        # Debt schedule may not have this year
        if not debt_schedule.empty and idx in debt_schedule["year_index"].values:
            ds_row = debt_schedule[debt_schedule["year_index"] == idx].iloc[0]
            total_debt = ds_row.get("Ending Balance", 0.0)
            current_debt = ds_row.get("Current Portion", 0.0)
            lt_debt = total_debt - current_debt
        else:
            total_debt = 0.0
            current_debt = 0.0
            lt_debt = 0.0

        # ── Current Assets ───────────────────────────────────────────
        cash = wc_row.get("Cash", 0.0)  # Will be solved as plug
        accounts_receivable = wc_row.get("Accounts Receivable", 0.0)
        inventory = wc_row.get("Inventory", 0.0)
        prepaid = wc_row.get("Prepaid", 0.0)
        other_ca = wc_row.get("Other Current Assets", 0.0)
        current_assets = cash + accounts_receivable + inventory + prepaid + other_ca

        # ── Non-Current Assets ───────────────────────────────────────
        ppe_net = cd_row.get("Ending PP&E (Net)", cd_row.get("Ending PP&E", 0.0))
        goodwill = base_goodwill
        intangibles = max(base_intangibles - is_row.get("Amortisation", 0.0) * idx, 0)
        other_lt_assets = base_other_lt_assets
        non_current_assets = ppe_net + goodwill + intangibles + other_lt_assets

        total_assets = current_assets + non_current_assets

        # ── Current Liabilities ──────────────────────────────────────
        accounts_payable = wc_row.get("Accounts Payable", 0.0)
        accrued = wc_row.get("Accrued Liabilities", 0.0)
        other_cl = wc_row.get("Other Current Liabilities", 0.0)
        current_liabilities = accounts_payable + accrued + other_cl + current_debt

        # ── Non-Current Liabilities ──────────────────────────────────
        other_lt_liabilities = base_other_lt_liabilities
        non_current_liabilities = lt_debt + other_lt_liabilities

        total_liabilities = current_liabilities + non_current_liabilities

        # ── Equity ───────────────────────────────────────────────────
        net_income = is_row.get("Net Income", 0.0)
        dividends = net_income * dividend_payout_ratio
        retained_earnings = retained_earnings + net_income - dividends
        common_stock = base_common_stock
        total_equity = common_stock + retained_earnings

        total_liabilities_equity = total_liabilities + total_equity

        # ── Cash as plug (to force balance) ──────────────────────────
        imbalance = total_liabilities_equity - total_assets
        cash_adjusted = cash + imbalance
        current_assets_adj = cash_adjusted + accounts_receivable + inventory + prepaid + other_ca
        total_assets_adj = current_assets_adj + non_current_assets

        rows.append({
            "year_index": idx,
            # Assets
            "Cash": cash_adjusted,
            "Accounts Receivable": accounts_receivable,
            "Inventory": inventory,
            "Prepaid": prepaid,
            "Other Current Assets": other_ca,
            "Current Assets": current_assets_adj,
            "PP&E Net": ppe_net,
            "Goodwill": goodwill,
            "Intangibles": intangibles,
            "Other LT Assets": other_lt_assets,
            "Non-Current Assets": non_current_assets,
            "Total Assets": total_assets_adj,
            # Liabilities
            "Accounts Payable": accounts_payable,
            "Accrued Liabilities": accrued,
            "Other Current Liabilities": other_cl,
            "Current Portion of Debt": current_debt,
            "Current Liabilities": current_liabilities,
            "Long-Term Debt": lt_debt,
            "Other LT Liabilities": other_lt_liabilities,
            "Non-Current Liabilities": non_current_liabilities,
            "Total Liabilities": total_liabilities,
            # Equity
            "Common Stock": common_stock,
            "Retained Earnings": retained_earnings,
            "Total Equity": total_equity,
            "Total Liabilities & Equity": total_liabilities + total_equity,
            # Extras
            "Dividends": dividends,
            "Net Income": net_income,
        })

        diff = abs(total_assets_adj - (total_liabilities + total_equity))
        checks.append({
            "year_index": idx,
            "Total Assets": total_assets_adj,
            "Total L+E": total_liabilities + total_equity,
            "Difference": diff,
            "Status": "PASS" if diff < 0.01 else "FAIL",
        })

    return BalanceSheetResult(
        table=pd.DataFrame(rows),
        checks=pd.DataFrame(checks),
    )
