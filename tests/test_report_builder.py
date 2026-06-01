import pandas as pd

from src.dcf_engine.intelligence.models import CompanySnapshot, SourceFact
from src.dcf_engine.intelligence.report_builder import build_public_report


def _snapshot():
    fact = SourceFact(
        ticker="AAPL",
        cik="0000320193",
        company_name="Apple Inc.",
        account="Revenue",
        concept="Revenues",
        value=100.0,
        unit="USD",
        form="10-K",
        filed="2026-01-30",
        period_end="2025-12-31",
        source_url="https://www.sec.gov/",
    )
    return CompanySnapshot(
        ticker="AAPL",
        cik="0000320193",
        company_name="Apple Inc.",
        latest_period="2025-12-31",
        financials=pd.DataFrame(),
        facts=[fact],
        key_metrics={"revenue": 100.0},
        warnings=[],
    )


def test_public_report_shapes_source_linked_data(monkeypatch):
    monkeypatch.setattr(
        "src.dcf_engine.intelligence.report_builder.fetch_company_snapshot",
        lambda ticker, years=5: _snapshot(),
    )
    monkeypatch.setattr(
        "src.dcf_engine.intelligence.report_builder.build_valuation_preview",
        lambda ticker, years=5: {
            "blended_equity_value": 120.0,
            "wacc": 0.1,
            "terminal_growth_rate": 0.03,
            "source_map": [],
            "warnings": [],
            "metadata_checked": False,
        },
    )
    monkeypatch.setattr(
        "src.dcf_engine.intelligence.report_builder.detect_filing_changes",
        lambda snapshot: {
            "numeric_changes": [{
                "account": "Revenue",
                "severity": "medium",
                "valuation_impact": "Review forecast CAGR.",
            }],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "src.dcf_engine.intelligence.report_builder.detect_red_flags",
        lambda snapshot, filing_changes, submissions=None: [],
    )
    monkeypatch.setattr(
        "src.dcf_engine.intelligence.report_builder.build_valuation_impacts",
        lambda changes, flags: [{"title": "Revenue moved", "detail": "Review growth."}],
    )

    report = build_public_report("aapl")

    assert report["ticker"] == "AAPL"
    assert report["company_name"] == "Apple Inc."
    assert report["latest_filing_date"] == "2026-01-30"
    assert report["numeric_changes"][0]["account"] == "Revenue"
    assert report["source_map"][0]["source_url"] == "https://www.sec.gov/"
    assert any("metadata" in warning.lower() for warning in report["warnings"])
