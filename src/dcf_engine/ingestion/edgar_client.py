"""
SEC EDGAR API client for automated financial data ingestion.

Uses the free EDGAR REST API (https://data.sec.gov/api/xbrl/).
No API key required — only a valid User-Agent per SEC policy.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# SEC mandates ≤10 requests/sec and a descriptive User-Agent
_BASE_URL = "https://data.sec.gov"
_COMPANY_FACTS = f"{_BASE_URL}/api/xbrl/companyfacts/CIK{{cik}}.json"
_COMPANY_CONCEPT = f"{_BASE_URL}/api/xbrl/companyconcept/CIK{{cik}}/us-gaap/{{concept}}.json"
_TICKER_TO_CIK = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&enddt=2025-12-31&forms=10-K"
_CIK_LOOKUP = "https://www.sec.gov/files/company_tickers.json"

_DEFAULT_USER_AGENT = "Trinsic/1.0 (support@trinsic.space)"
_RATE_LIMIT_DELAY = 0.12  # ~8 req/sec to stay under 10

# ── Standard XBRL concepts → friendly names ─────────────────────────
XBRL_CONCEPT_MAP: Dict[str, str] = {
    # Income Statement
    "Revenues": "Revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "SalesRevenueNet": "Revenue",
    "CostOfGoodsAndServicesSold": "COGS",
    "CostOfRevenue": "COGS",
    "CostOfGoodsSold": "COGS",
    "SellingGeneralAndAdministrativeExpense": "SGA",
    "ResearchAndDevelopmentExpense": "R&D",
    "DepreciationAndAmortization": "D&A",
    "DepreciationDepletionAndAmortization": "D&A",
    "Depreciation": "Depreciation",
    "OperatingIncomeLoss": "EBIT",
    "InterestExpense": "Interest Expense",
    "IncomeTaxExpenseBenefit": "Tax Expense",
    "NetIncomeLoss": "Net Income",
    "EarningsPerShareBasic": "EPS Basic",
    "EarningsPerShareDiluted": "EPS Diluted",
    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted": "Shares Outstanding",
    "WeightedAverageNumberOfDilutedSharesOutstanding": "Shares Diluted",
    # Balance Sheet
    "Assets": "Total Assets",
    "AssetsCurrent": "Current Assets",
    "CashAndCashEquivalentsAtCarryingValue": "Cash",
    "AccountsReceivableNetCurrent": "Accounts Receivable",
    "InventoryNet": "Inventory",
    "PrepaidExpenseAndOtherAssetsCurrent": "Prepaid & Other Current",
    "PropertyPlantAndEquipmentNet": "PP&E Net",
    "Goodwill": "Goodwill",
    "IntangibleAssetsNetExcludingGoodwill": "Intangibles",
    "Liabilities": "Total Liabilities",
    "LiabilitiesCurrent": "Current Liabilities",
    "AccountsPayableCurrent": "Accounts Payable",
    "AccruedLiabilitiesCurrent": "Accrued Liabilities",
    "LongTermDebt": "Long-Term Debt",
    "LongTermDebtNoncurrent": "Long-Term Debt",
    "ShortTermBorrowings": "Short-Term Debt",
    "StockholdersEquity": "Total Equity",
    "RetainedEarningsAccumulatedDeficit": "Retained Earnings",
    "CommonStockSharesOutstanding": "Shares Outstanding (BS)",
    # Cash Flow
    "NetCashProvidedByUsedInOperatingActivities": "CFO",
    "PaymentsToAcquirePropertyPlantAndEquipment": "Capex",
    "NetCashProvidedByUsedInInvestingActivities": "CFI",
    "NetCashProvidedByUsedInFinancingActivities": "CFF",
}

# Concepts we always try to pull (annual 10-K filings)
PRIORITY_CONCEPTS = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold",
    "SellingGeneralAndAdministrativeExpense",
    "ResearchAndDevelopmentExpense",
    "DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
    "OperatingIncomeLoss",
    "InterestExpense",
    "IncomeTaxExpenseBenefit",
    "NetIncomeLoss",
    "Assets", "AssetsCurrent",
    "CashAndCashEquivalentsAtCarryingValue",
    "AccountsReceivableNetCurrent",
    "InventoryNet",
    "PropertyPlantAndEquipmentNet",
    "Liabilities", "LiabilitiesCurrent",
    "AccountsPayableCurrent",
    "AccruedLiabilitiesCurrent",
    "LongTermDebt", "LongTermDebtNoncurrent",
    "ShortTermBorrowings",
    "StockholdersEquity",
    "RetainedEarningsAccumulatedDeficit",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "EarningsPerShareDiluted",
]


@dataclass
class EdgarFiling:
    """Structured result from an EDGAR data pull."""
    cik: str
    company_name: str
    financials: pd.DataFrame          # columns: period, account, amount, statement
    raw_facts: Dict[str, list] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class EdgarClient:
    """Pulls structured financial data from SEC EDGAR XBRL API."""

    def __init__(self, user_agent: str = _DEFAULT_USER_AGENT):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })
        self._last_request_time = 0.0

    # ── Public API ───────────────────────────────────────────────────
    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Resolve a ticker symbol to a 10-digit CIK string."""
        data = self._get(_CIK_LOOKUP)
        if data is None:
            return None
        for entry in data.values():
            if str(entry.get("ticker", "")).upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
        return None

    def fetch_financials(
        self,
        ticker: Optional[str] = None,
        cik: Optional[str] = None,
        years: int = 5,
    ) -> EdgarFiling:
        """
        Pull historical financials from EDGAR for the given company.

        Provide either ``ticker`` or ``cik``.  Returns an EdgarFiling
        with a tidy DataFrame ready for the 3-statement builder.
        """
        if cik is None:
            if ticker is None:
                raise ValueError("Provide either ticker or cik")
            cik = self.ticker_to_cik(ticker)
            if cik is None:
                raise ValueError(f"Could not resolve ticker '{ticker}' to CIK")

        cik_padded = cik.zfill(10)

        # Pull the company facts endpoint (all XBRL facts at once)
        url = _COMPANY_FACTS.format(cik=cik_padded)
        data = self._get(url)
        if data is None:
            return EdgarFiling(
                cik=cik_padded,
                company_name="Unknown",
                financials=pd.DataFrame(),
                errors=["Failed to fetch company facts"],
            )

        company_name = data.get("entityName", "Unknown")
        us_gaap = data.get("facts", {}).get("us-gaap", {})

        rows: List[dict] = []
        errors: List[str] = []

        for concept in PRIORITY_CONCEPTS:
            friendly = XBRL_CONCEPT_MAP.get(concept, concept)
            concept_data = us_gaap.get(concept)

            if concept_data is None:
                continue

            units = concept_data.get("units", {})
            # Prefer USD, then "shares", then "pure"
            unit_data = units.get("USD") or units.get("shares") or units.get("USD/shares") or units.get("pure")
            if not unit_data:
                continue

            # Filter to 10-K annual filings only, no segments
            for fact in unit_data:
                form = fact.get("form", "")
                if form not in ("10-K", "10-K/A"):
                    continue
                # Skip segment-level data
                if fact.get("frame") is None and fact.get("end") is None:
                    continue

                end_date = fact.get("end")
                if end_date is None:
                    continue

                # Deduplicate: keep only facts that span ~1 year (instant BS vs duration IS)
                start_date = fact.get("start")
                is_instant = start_date is None

                rows.append({
                    "period": end_date,
                    "account": friendly,
                    "amount": float(fact.get("val", 0)),
                    "concept": concept,
                    "is_instant": is_instant,
                    "form": form,
                    "filed": fact.get("filed", ""),
                })

        if not rows:
            errors.append("No parseable XBRL facts found")
            return EdgarFiling(
                cik=cik_padded,
                company_name=company_name,
                financials=pd.DataFrame(),
                errors=errors,
            )

        df = pd.DataFrame(rows)
        df["period"] = pd.to_datetime(df["period"], errors="coerce")

        # Keep only the most recent N years
        unique_periods = sorted(df["period"].dropna().unique(), reverse=True)
        cutoff_periods = unique_periods[:years]
        df = df[df["period"].isin(cutoff_periods)].copy()

        # Deduplicate: for the same (period, account), keep the latest filing
        df = df.sort_values("filed", ascending=False)
        df = df.drop_duplicates(subset=["period", "account"], keep="first")

        # Infer statement type
        is_items = {"Revenue", "COGS", "SGA", "R&D", "D&A", "Depreciation",
                    "EBIT", "Interest Expense", "Tax Expense", "Net Income",
                    "EPS Basic", "EPS Diluted"}
        bs_items = {"Total Assets", "Current Assets", "Cash", "Accounts Receivable",
                    "Inventory", "Prepaid & Other Current", "PP&E Net",
                    "Goodwill", "Intangibles", "Total Liabilities", "Current Liabilities",
                    "Accounts Payable", "Accrued Liabilities", "Long-Term Debt",
                    "Short-Term Debt", "Total Equity", "Retained Earnings",
                    "Shares Outstanding (BS)"}
        cf_items = {"CFO", "Capex", "CFI", "CFF"}

        def _stmt(acct: str) -> str:
            if acct in is_items:
                return "IS"
            if acct in bs_items:
                return "BS"
            if acct in cf_items:
                return "CF"
            return "IS"

        df["statement"] = df["account"].apply(_stmt)
        df = df[["period", "account", "amount", "statement"]].sort_values(
            ["period", "statement", "account"]
        ).reset_index(drop=True)

        return EdgarFiling(
            cik=cik_padded,
            company_name=company_name,
            financials=df,
            errors=errors,
        )

    # ── Internal ─────────────────────────────────────────────────────
    def fetch_submissions(self, cik: str) -> Optional[dict]:
        """Fetch SEC filing submissions metadata for a company.

        Returns the raw JSON from the submissions endpoint, or None on failure.
        Used by red flag detection to check for late filings, amendments, and 8-K events.
        """
        cik_padded = cik.zfill(10)
        url = f"{_BASE_URL}/submissions/CIK{cik_padded}.json"
        return self._get(url)

    def _get(self, url: str) -> Optional[dict]:
        """Rate-limited GET with error handling."""
        elapsed = time.time() - self._last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)

        try:
            resp = self.session.get(url, timeout=30)
            self._last_request_time = time.time()
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("EDGAR request failed: %s → %s", url, exc)
            return None
