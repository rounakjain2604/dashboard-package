"""
Live market-data helpers.

Pulls risk-free rate, equity risk premium, beta, and comparable
company fundamentals from free public APIs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

import pandas as pd
import requests

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed. Market data features disabled.")

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    risk_free_rate: Optional[float] = None
    equity_risk_premium: Optional[float] = None
    beta: Optional[float] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    trailing_revenue: Optional[float] = None
    trailing_ebitda: Optional[float] = None
    trailing_net_income: Optional[float] = None
    current_price: Optional[float] = None
    shares_outstanding: Optional[float] = None


# ── Risk-Free Rate (FRED: 10-Year Treasury) ──────────────────────────
def fetch_risk_free_rate() -> Optional[float]:
    """Pull the latest 10-Year Treasury yield from FRED (no key needed for observations)."""
    try:
        if yf is None:
            return None
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1]) / 100.0
            logger.info("Risk-free rate (^TNX): %.4f", rate)
            return rate
    except Exception as exc:
        logger.warning("Failed to fetch risk-free rate: %s", exc)
    return None


# ── Beta ─────────────────────────────────────────────────────────────
def fetch_beta(ticker: str) -> Optional[float]:
    """Pull beta for a given ticker via yfinance."""
    try:
        if yf is None:
            return None
        info = yf.Ticker(ticker).info
        beta = info.get("beta")
        if beta is not None:
            logger.info("Beta for %s: %.2f", ticker, beta)
            return float(beta)
    except Exception as exc:
        logger.warning("Failed to fetch beta for %s: %s", ticker, exc)
    return None


# ── Company Fundamentals (for comps) ─────────────────────────────────
def fetch_company_snapshot(ticker: str) -> MarketSnapshot:
    """Pull key fundamentals for a single ticker via yfinance."""
    snap = MarketSnapshot()
    try:
        if yf is None:
            return snap
        t = yf.Ticker(ticker)
        info = t.info

        snap.market_cap = info.get("marketCap")
        snap.enterprise_value = info.get("enterpriseValue")
        snap.trailing_revenue = info.get("totalRevenue")
        snap.trailing_ebitda = info.get("ebitda")
        snap.trailing_net_income = info.get("netIncomeToCommon")
        snap.current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        snap.shares_outstanding = info.get("sharesOutstanding")
        snap.beta = info.get("beta")
    except Exception as exc:
        logger.warning("Failed to fetch snapshot for %s: %s", ticker, exc)
    return snap


def fetch_peer_snapshots(tickers: List[str]) -> Dict[str, MarketSnapshot]:
    """Pull snapshots for a list of peer tickers."""
    results = {}
    for t in tickers:
        results[t] = fetch_company_snapshot(t)
    return results


# ── Equity Risk Premium ──────────────────────────────────────────────
def fetch_equity_risk_premium() -> Optional[float]:
    """
    Attempt to pull Damodaran's implied ERP.
    Falls back to a reasonable default of 5.5%.
    """
    try:
        url = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html"
        resp = requests.get(url, timeout=10)
        if resp.ok:
            # Parse the page for US ERP — this is fragile, so we fall back
            tables = pd.read_html(resp.text, match="United States")
            if tables:
                for tbl in tables:
                    for col in tbl.columns:
                        if "equity" in str(col).lower() and "premium" in str(col).lower():
                            us_row = tbl[tbl.iloc[:, 0].astype(str).str.contains("United States", case=False, na=False)]
                            if not us_row.empty:
                                val = pd.to_numeric(us_row[col].iloc[0], errors="coerce")
                                if pd.notna(val):
                                    erp = float(val) / 100 if val > 1 else float(val)
                                    logger.info("Equity risk premium (Damodaran): %.4f", erp)
                                    return erp
    except Exception as exc:
        logger.warning("Failed to fetch ERP: %s", exc)

    logger.info("Using default ERP: 0.055")
    return 0.055
