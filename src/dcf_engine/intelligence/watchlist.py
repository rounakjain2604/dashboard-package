"""
Stateless Watchlist Digest MVP — Phase 9

Accepts up to 10 tickers, runs filing change detection and numeric red flags
for each, and returns a severity-sorted digest.

No database, no auth, no email alerts, no scheduling.
Metadata red flags are skipped to minimize SEC API calls; only numeric red
flags are computed. This is explicitly stated in the response.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from src.dcf_engine.intelligence.sec_snapshot import fetch_company_snapshot
from src.dcf_engine.intelligence.filing_changes import detect_filing_changes
from src.dcf_engine.intelligence.red_flags import detect_red_flags
from src.dcf_engine.intelligence.valuation_impacts import build_valuation_impacts

logger = logging.getLogger(__name__)

MAX_TICKERS = 10

_SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def _max_severity(items: list[dict], key: str = "severity") -> str:
    """Return the highest severity from a list of dicts."""
    max_sev = "low"
    for item in items:
        sev = item.get(key, "low")
        if _SEVERITY_ORDER.get(sev, 0) > _SEVERITY_ORDER.get(max_sev, 0):
            max_sev = sev
    return max_sev


def refresh_watchlist(tickers: list[str], years: int = 5) -> dict:
    """
    Refresh a watchlist of tickers with filing change and red flag analysis.

    Args:
        tickers: list of ticker strings (max 10)
        years: number of historical years to analyze

    Returns:
        dict with:
          results: list of per-ticker summary dicts
          warnings: list of global warnings

    Errors for individual tickers do not fail the entire watchlist.
    Metadata red flags are NOT checked to minimize SEC API calls.
    """
    warnings = []

    if not tickers:
        return {
            "results": [],
            "warnings": ["No tickers provided."],
        }

    if len(tickers) > MAX_TICKERS:
        warnings.append(
            f"Ticker list truncated from {len(tickers)} to {MAX_TICKERS}. "
            f"Maximum {MAX_TICKERS} tickers allowed per request."
        )
        tickers = tickers[:MAX_TICKERS]

    results = []

    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        if not ticker or len(ticker) > 12:
            results.append({
                "ticker": raw_ticker,
                "status": "error",
                "error": f"Invalid ticker: '{raw_ticker}'",
                "latest_period": None,
                "change_count": 0,
                "red_flag_count": 0,
                "top_impacts": [],
                "max_severity": "low",
                "source_quality_weak": False,
                "metadata_checked": False,
            })
            continue

        try:
            # Fetch snapshot
            snapshot = fetch_company_snapshot(ticker, years=years)

            # Detect filing changes
            change_result = detect_filing_changes(snapshot)
            numeric_changes = change_result.get("numeric_changes", [])

            # Detect numeric red flags only (no submissions to save SEC calls)
            red_flags = detect_red_flags(
                snapshot=snapshot,
                filing_changes=numeric_changes,
                submissions=None,  # Skip metadata to avoid extra SEC calls
            )

            # Build valuation impacts
            impacts = build_valuation_impacts(numeric_changes, red_flags)

            # Determine source quality
            source_quality_weak = len(snapshot.warnings) >= 8

            # Top impacts (limit to 3)
            top_impacts = impacts[:3]

            # Compute max severity across changes and flags
            all_severities = [c.get("severity", "low") for c in numeric_changes] + \
                             [f.get("severity", "low") for f in red_flags]
            max_sev = _max_severity([{"severity": s} for s in all_severities]) if all_severities else "low"

            results.append({
                "ticker": ticker,
                "status": "ok",
                "latest_period": change_result.get("latest_period"),
                "change_count": len(numeric_changes),
                "red_flag_count": len(red_flags),
                "top_impacts": top_impacts,
                "max_severity": max_sev,
                "source_quality_weak": source_quality_weak,
                "metadata_checked": False,
            })

        except Exception as exc:
            logger.warning("Watchlist error for %s: %s", ticker, exc)
            results.append({
                "ticker": ticker,
                "status": "error",
                "error": str(exc),
                "latest_period": None,
                "change_count": 0,
                "red_flag_count": 0,
                "top_impacts": [],
                "max_severity": "low",
                "source_quality_weak": False,
                "metadata_checked": False,
            })

    # Sort by severity (high first), then by change_count descending
    results.sort(
        key=lambda x: (
            _SEVERITY_ORDER.get(x.get("max_severity", "low"), 0),
            x.get("red_flag_count", 0),
            x.get("change_count", 0),
        ),
        reverse=True,
    )

    return {
        "results": results,
        "warnings": warnings,
    }
