"""Public report data shaping for source-linked ticker pages."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

from src.dcf_engine.intelligence.sec_snapshot import fetch_company_snapshot
from src.dcf_engine.intelligence.valuation_preview import build_valuation_preview
from src.dcf_engine.intelligence.filing_changes import detect_filing_changes
from src.dcf_engine.intelligence.red_flags import detect_red_flags
from src.dcf_engine.intelligence.valuation_impacts import build_valuation_impacts


SAMPLE_REPORT_TICKERS = {"AAPL", "MSFT", "NVDA", "TSLA", "AMZN"}


def _record(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    return value


def _fact_to_dict(fact) -> dict:
    return {
        "ticker": fact.ticker,
        "cik": fact.cik,
        "company_name": fact.company_name,
        "account": fact.account,
        "concept": fact.concept,
        "value": fact.value,
        "unit": fact.unit,
        "form": fact.form,
        "filed": fact.filed,
        "period_end": fact.period_end,
        "fiscal_year": fact.fiscal_year,
        "fiscal_period": fact.fiscal_period,
        "accession": fact.accession,
        "frame": fact.frame,
        "source_url": fact.source_url,
    }


def build_public_report(ticker: str, years: int = 5) -> dict:
    """Build a compact, template-ready public report payload."""
    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise ValueError("Ticker is required")
    if len(clean_ticker) > 12:
        raise ValueError("Ticker too long")

    snapshot = fetch_company_snapshot(clean_ticker, years=years)
    preview = build_valuation_preview(clean_ticker, years=years)
    change_result = detect_filing_changes(snapshot)
    numeric_changes = [_record(item) for item in change_result.get("numeric_changes", [])]
    red_flags = [_record(item) for item in detect_red_flags(snapshot, numeric_changes, submissions=None)]
    impacts = build_valuation_impacts(numeric_changes, red_flags)

    warnings = []
    for source in (
        snapshot.warnings,
        preview.get("warnings", []),
        change_result.get("warnings", []),
    ):
        for warning in source or []:
            if warning not in warnings:
                warnings.append(warning)
    if not preview.get("metadata_checked", False):
        msg = "SEC metadata checks may be incomplete; use source filings for final diligence."
        if msg not in warnings:
            warnings.append(msg)

    source_map = preview.get("source_map") or [_fact_to_dict(fact) for fact in snapshot.facts[:25]]

    return {
        "ticker": clean_ticker,
        "company_name": snapshot.company_name or clean_ticker,
        "cik": snapshot.cik,
        "latest_period": snapshot.latest_period,
        "latest_filing_date": _latest_filing_date(snapshot.facts),
        "key_metrics": snapshot.key_metrics,
        "valuation_preview": preview,
        "numeric_changes": numeric_changes,
        "valuation_impacts": impacts,
        "reverse_dcf": preview.get("reverse_dcf"),
        "red_flags": red_flags,
        "source_map": source_map[:25],
        "warnings": warnings,
        "sample_tickers": sorted(SAMPLE_REPORT_TICKERS),
        "methodology": (
            "Trinsic maps SEC XBRL facts into valuation assumptions, flags material filing "
            "changes, and runs deterministic DCF checks. Outputs are research tooling, not "
            "investment advice."
        ),
    }


def _latest_filing_date(facts) -> str | None:
    dates = sorted({getattr(fact, "filed", None) for fact in facts if getattr(fact, "filed", None)})
    return dates[-1] if dates else None
