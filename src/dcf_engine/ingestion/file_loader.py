"""
File loader for CSV / XLSX financial data.

Accepts flexible column layouts and normalises them into the standard
(period, account, amount, statement) format used across the engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class LoadResult:
    """Result of loading and normalising a file."""
    financials: pd.DataFrame      # columns: period, account, amount, statement
    source_path: str
    errors: list[str]


# ── Column-name synonyms ────────────────────────────────────────────
_PERIOD_SYNONYMS = {"period", "date", "year", "fiscal_year", "fiscal year", "fy", "end_date"}
_ACCOUNT_SYNONYMS = {"account", "item", "line_item", "line item", "metric", "description"}
_AMOUNT_SYNONYMS = {"amount", "value", "balance", "total"}
_STATEMENT_SYNONYMS = {"statement", "stmt", "type", "fs_type"}

# ── Standard chart-of-accounts mapping ───────────────────────────────
_ACCOUNT_MAP = {
    "revenue": "Revenue", "sales": "Revenue", "net sales": "Revenue",
    "total revenue": "Revenue", "net revenue": "Revenue",
    "cost of goods sold": "COGS", "cogs": "COGS", "cost of revenue": "COGS",
    "cost of sales": "COGS",
    "gross profit": "Gross Profit",
    "selling general and administrative": "SGA", "sg&a": "SGA", "sga": "SGA",
    "selling general & administrative": "SGA",
    "research and development": "R&D", "r&d": "R&D",
    "depreciation": "Depreciation", "depreciation and amortization": "D&A",
    "d&a": "D&A", "amortization": "Amortization",
    "operating income": "EBIT", "ebit": "EBIT",
    "ebitda": "EBITDA",
    "interest expense": "Interest Expense", "interest": "Interest Expense",
    "income tax": "Tax Expense", "tax expense": "Tax Expense",
    "provision for income taxes": "Tax Expense",
    "net income": "Net Income",
    # Balance Sheet
    "total assets": "Total Assets", "assets": "Total Assets",
    "current assets": "Current Assets",
    "cash": "Cash", "cash and equivalents": "Cash",
    "cash and cash equivalents": "Cash",
    "accounts receivable": "Accounts Receivable", "ar": "Accounts Receivable",
    "trade receivables": "Accounts Receivable",
    "inventory": "Inventory", "inventories": "Inventory",
    "prepaid expenses": "Prepaid & Other Current", "prepaid": "Prepaid & Other Current",
    "property plant and equipment": "PP&E Net", "pp&e": "PP&E Net", "ppe": "PP&E Net",
    "property plant & equipment net": "PP&E Net",
    "goodwill": "Goodwill",
    "intangible assets": "Intangibles", "intangibles": "Intangibles",
    "total liabilities": "Total Liabilities", "liabilities": "Total Liabilities",
    "current liabilities": "Current Liabilities",
    "accounts payable": "Accounts Payable", "ap": "Accounts Payable",
    "trade payables": "Accounts Payable",
    "accrued liabilities": "Accrued Liabilities", "accrued expenses": "Accrued Liabilities",
    "long-term debt": "Long-Term Debt", "long term debt": "Long-Term Debt",
    "short-term debt": "Short-Term Debt", "short term debt": "Short-Term Debt",
    "current portion of long-term debt": "Short-Term Debt",
    "total equity": "Total Equity", "stockholders equity": "Total Equity",
    "shareholders equity": "Total Equity", "equity": "Total Equity",
    "retained earnings": "Retained Earnings",
    "common stock": "Common Stock",
    # Cash Flow
    "capital expenditures": "Capex", "capex": "Capex",
    "dividends paid": "Dividends Paid",
    "shares outstanding": "Shares Outstanding",
}

_IS_ACCOUNTS = {"Revenue", "COGS", "Gross Profit", "SGA", "R&D", "D&A",
                "Depreciation", "Amortization", "EBIT", "EBITDA",
                "Interest Expense", "Tax Expense", "Net Income"}
_BS_ACCOUNTS = {"Total Assets", "Current Assets", "Cash", "Accounts Receivable",
                "Inventory", "Prepaid & Other Current", "PP&E Net", "Goodwill",
                "Intangibles", "Total Liabilities", "Current Liabilities",
                "Accounts Payable", "Accrued Liabilities", "Long-Term Debt",
                "Short-Term Debt", "Total Equity", "Retained Earnings", "Common Stock"}
_CF_ACCOUNTS = {"Capex", "Dividends Paid"}


def load_financial_file(path: str | Path) -> LoadResult:
    """
    Load a CSV or Excel file and normalise it into the standard format.

    The loader is deliberately flexible: it tries to auto-detect which
    columns map to period / account / amount by scanning column-name
    synonyms.  Also supports "wide" layouts where years are column
    headers and accounts are row labels.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    errors: list[str] = []

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")

    df.columns = [str(c).strip() for c in df.columns]

    # ── Try tidy (long) format first ─────────────────────────────────
    period_col = _find_column(df, _PERIOD_SYNONYMS)
    account_col = _find_column(df, _ACCOUNT_SYNONYMS)
    amount_col = _find_column(df, _AMOUNT_SYNONYMS)

    if period_col and account_col and amount_col:
        tidy = _build_tidy(df, period_col, account_col, amount_col)
        stmt_col = _find_column(df, _STATEMENT_SYNONYMS)
        if stmt_col:
            tidy["statement"] = df[stmt_col].astype(str).str.upper()
        else:
            tidy["statement"] = tidy["account"].apply(_infer_statement)
        return LoadResult(financials=tidy, source_path=str(path), errors=errors)

    # ── Fall back to wide format (years as columns) ──────────────────
    tidy = _try_wide_format(df)
    if tidy is not None and not tidy.empty:
        tidy["statement"] = tidy["account"].apply(_infer_statement)
        return LoadResult(financials=tidy, source_path=str(path), errors=errors)

    errors.append("Could not auto-detect column mapping. "
                   "Expected columns: period, account, amount (or wide format with years as headers)")
    return LoadResult(financials=pd.DataFrame(), source_path=str(path), errors=errors)


# ── Helpers ──────────────────────────────────────────────────────────
def _find_column(df: pd.DataFrame, synonyms: set[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for syn in synonyms:
        if syn in lower_map:
            return lower_map[syn]
    return None


def _build_tidy(df: pd.DataFrame, period_col: str, account_col: str, amount_col: str) -> pd.DataFrame:
    out = df[[period_col, account_col, amount_col]].copy()
    out.columns = ["period", "account", "amount"]
    out["period"] = pd.to_datetime(out["period"], errors="coerce")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0.0)
    out["account"] = out["account"].astype(str).str.strip()
    out["account"] = out["account"].apply(_map_account)
    return out


def _try_wide_format(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Detect wide format where first column is account names and remaining columns are years."""
    if len(df.columns) < 3:
        return None

    first_col = df.columns[0]
    year_cols = []
    for col in df.columns[1:]:
        try:
            year = int(str(col).strip())
            if 1990 <= year <= 2040:
                year_cols.append(col)
        except (ValueError, TypeError):
            # Try to parse as date
            try:
                pd.to_datetime(col)
                year_cols.append(col)
            except Exception:
                continue

    if not year_cols:
        return None

    rows = []
    for _, row in df.iterrows():
        account = _map_account(str(row[first_col]).strip())
        for yc in year_cols:
            try:
                period = pd.to_datetime(str(yc).strip(), format="%Y") + pd.offsets.YearEnd(0)
            except Exception:
                period = pd.to_datetime(str(yc).strip(), errors="coerce")
            amount = pd.to_numeric(row[yc], errors="coerce")
            if pd.notna(amount):
                rows.append({
                    "period": period,
                    "account": account,
                    "amount": float(amount),
                })

    return pd.DataFrame(rows) if rows else None


def _map_account(raw: str) -> str:
    key = raw.lower().strip()
    for phrase, standard in _ACCOUNT_MAP.items():
        if phrase == key or phrase in key:
            return standard
    return raw  # keep original if no match


def _infer_statement(account: str) -> str:
    if account in _IS_ACCOUNTS:
        return "IS"
    if account in _BS_ACCOUNTS:
        return "BS"
    if account in _CF_ACCOUNTS:
        return "CF"
    return "IS"
