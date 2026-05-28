import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from src.dcf_engine.intelligence.filing_changes import detect_filing_changes
from src.dcf_engine.intelligence.models import CompanySnapshot, SourceFact
from dashboard_api import app


def _make_two_period_snapshot(
    rev_latest=330e9, rev_prior=300e9,
    cogs_latest=165e9, cogs_prior=150e9,
    ebit_latest=115e9, ebit_prior=100e9,
    ni_latest=88e9, ni_prior=80e9,
    cfo_latest=100e9, cfo_prior=90e9,
    capex_latest=-10e9, capex_prior=-8e9,
    cash_latest=20e9, cash_prior=25e9,
    lt_debt_latest=80e9, lt_debt_prior=60e9,
    st_debt_latest=20e9, st_debt_prior=15e9,
    shares_latest=10e9, shares_prior=9.6e9,
    ppe_latest=40e9, ppe_prior=38e9,
    ar_latest=50e9, ar_prior=45e9,
    inv_latest=10e9, inv_prior=9e9,
    ap_latest=30e9, ap_prior=28e9,
):
    """Build a CompanySnapshot with two periods for testing."""
    rows = []
    latest = "2023-09-30"
    prior = "2022-09-30"

    metric_map = {
        "Revenue": (rev_latest, rev_prior),
        "COGS": (cogs_latest, cogs_prior),
        "EBIT": (ebit_latest, ebit_prior),
        "Net Income": (ni_latest, ni_prior),
        "CFO": (cfo_latest, cfo_prior),
        "Capex": (capex_latest, capex_prior),
        "Cash": (cash_latest, cash_prior),
        "Long-Term Debt": (lt_debt_latest, lt_debt_prior),
        "Short-Term Debt": (st_debt_latest, st_debt_prior),
        "Shares Diluted": (shares_latest, shares_prior),
        "PP&E Net": (ppe_latest, ppe_prior),
        "Accounts Receivable": (ar_latest, ar_prior),
        "Inventory": (inv_latest, inv_prior),
        "Accounts Payable": (ap_latest, ap_prior),
    }

    for account, (lv, pv) in metric_map.items():
        rows.append({"period": latest, "account": account, "amount": lv, "statement": "IS"})
        rows.append({"period": prior, "account": account, "amount": pv, "statement": "IS"})

    df = pd.DataFrame(rows)

    facts = [
        SourceFact(
            ticker="TEST", cik="0000000001", company_name="Test Corp",
            account=account, concept="TestConcept", value=lv, unit="USD",
            form="10-K", filed="2023-11-01", period_end=latest,
        )
        for account, (lv, _) in metric_map.items()
    ]

    return CompanySnapshot(
        ticker="TEST",
        cik="0000000001",
        company_name="Test Corp",
        latest_period=latest,
        financials=df,
        facts=facts,
        key_metrics={},
        warnings=[],
    )


def test_revenue_increase_severity():
    """12% revenue increase should be classified as medium."""
    snap = _make_two_period_snapshot(rev_latest=336e9, rev_prior=300e9)  # 12%
    result = detect_filing_changes(snap)
    changes = result["numeric_changes"]
    rev_change = [c for c in changes if c["account"] == "Revenue"][0]
    assert rev_change["severity"] == "medium"
    assert rev_change["percent_change"] == pytest.approx(0.12, abs=0.01)
    assert result["latest_period"] == "2023-09-30"
    assert result["prior_period"] == "2022-09-30"


def test_debt_increase_high():
    """35% debt increase should be classified as high."""
    snap = _make_two_period_snapshot(
        lt_debt_latest=100e9, lt_debt_prior=60e9,
        st_debt_latest=20e9, st_debt_prior=20e9,
    )  # (120-80)/80 = 50%
    result = detect_filing_changes(snap)
    debt_change = [c for c in result["numeric_changes"] if c["account"] == "Total Debt"][0]
    assert debt_change["severity"] == "high"


def test_share_dilution():
    """4% share increase should be classified as high."""
    snap = _make_two_period_snapshot(
        shares_latest=10.4e9, shares_prior=10e9,
    )  # 4%
    result = detect_filing_changes(snap)
    share_change = [c for c in result["numeric_changes"] if c["account"] == "Diluted Shares"][0]
    assert share_change["severity"] == "high"


def test_fcf_sign_flip():
    """FCF from positive to negative should be high severity."""
    snap = _make_two_period_snapshot(
        cfo_latest=5e9, cfo_prior=90e9,
        capex_latest=-10e9, capex_prior=-8e9,
    )  # FCF: 5-10=-5 vs 90-8=82
    result = detect_filing_changes(snap)
    fcf_change = [c for c in result["numeric_changes"] if c["account"] == "FCF"][0]
    assert fcf_change["severity"] == "high"
    assert fcf_change["latest_value"] < 0
    assert fcf_change["prior_value"] > 0


def test_single_period_no_changes():
    """Only one period should return empty changes with warning."""
    rows = [{"period": "2023-09-30", "account": "Revenue", "amount": 100e9, "statement": "IS"}]
    df = pd.DataFrame(rows)
    snap = CompanySnapshot(
        ticker="TEST", cik="0000000001", company_name="Test Corp",
        latest_period="2023-09-30", financials=df, facts=[], key_metrics={}, warnings=[],
    )
    result = detect_filing_changes(snap)
    assert result["numeric_changes"] == []
    assert any("one period" in w.lower() or "cannot compare" in w.lower() for w in result["warnings"])


def test_empty_financials():
    """Empty DataFrame should return no changes with warning."""
    snap = CompanySnapshot(
        ticker="TEST", cik="0000000001", company_name="Test Corp",
        latest_period=None, financials=pd.DataFrame(), facts=[], key_metrics={}, warnings=[],
    )
    result = detect_filing_changes(snap)
    assert result["numeric_changes"] == []
    assert len(result["warnings"]) > 0


def test_composite_sources_use_components():
    """Composite metrics (Gross Margin, FCF, etc.) should use source_components, not single source_fact."""
    snap = _make_two_period_snapshot()
    result = detect_filing_changes(snap)
    fcf_change = [c for c in result["numeric_changes"] if c["account"] == "FCF"]
    if fcf_change:
        assert fcf_change[0]["source_fact_latest"] is None
        assert fcf_change[0]["source_fact_prior"] is None
        # source_components should contain CFO and Capex facts
        assert fcf_change[0]["source_components"] is not None or fcf_change[0]["source_components"] == []


def test_capex_sign_normalization():
    """Capex should be reported as absolute value."""
    snap = _make_two_period_snapshot(
        capex_latest=-15e9, capex_prior=-10e9,
    )
    result = detect_filing_changes(snap)
    capex_change = [c for c in result["numeric_changes"] if c["account"] == "Capex"]
    if capex_change:
        assert capex_change[0]["latest_value"] == 15e9
        assert capex_change[0]["prior_value"] == 10e9


def test_dict_return_shape():
    """Result should have consistent dict shape."""
    snap = _make_two_period_snapshot()
    result = detect_filing_changes(snap)
    assert "ticker" in result
    assert "latest_period" in result
    assert "prior_period" in result
    assert "numeric_changes" in result
    assert "warnings" in result
    assert isinstance(result["numeric_changes"], list)


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_api_route(MockEdgarClient):
    """Test /api/filing-changes route with mocked data."""
    from tests.test_valuation_preview import MOCK_FACTS_JSON_2Y
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    client = app.test_client()
    resp = client.post("/api/filing-changes", json={"ticker": "AAPL", "years": 2})
    data = resp.get_json()
    assert data["success"] is True
    assert "numeric_changes" in data
    assert "red_flags" in data
    assert "valuation_impacts" in data
    assert "request_id" in data
