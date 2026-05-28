import pytest
from datetime import date

from src.dcf_engine.intelligence.red_flags import detect_red_flags, _check_numeric_flags, _check_metadata_flags
from src.dcf_engine.intelligence.models import CompanySnapshot
import pandas as pd


def _make_empty_snapshot():
    return CompanySnapshot(
        ticker="TEST", cik="0000000001", company_name="Test Corp",
        latest_period=None, financials=pd.DataFrame(), facts=[], key_metrics={}, warnings=[],
    )


def test_revenue_decline_flag():
    """Revenue decline > 20% should trigger high severity flag."""
    changes = [{
        "account": "Revenue",
        "percent_change": -0.25,
        "latest_value": 75e9,
        "prior_value": 100e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "revenue_decline_severe"
    assert flags[0]["severity"] == "high"
    assert flags[0]["affected_assumptions"] is not None
    assert "base_year_revenue" in flags[0]["affected_assumptions"]


def test_fcf_negative_flag():
    """FCF turning negative should trigger high severity flag."""
    changes = [{
        "account": "FCF",
        "percent_change": -1.5,
        "latest_value": -10e9,
        "prior_value": 20e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "fcf_turned_negative"
    assert flags[0]["severity"] == "high"


def test_debt_surge_flag():
    """Debt increase > 30% should trigger high severity flag."""
    changes = [{
        "account": "Total Debt",
        "percent_change": 0.35,
        "latest_value": 135e9,
        "prior_value": 100e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "debt_surge"
    assert flags[0]["severity"] == "high"


def test_dilution_high_flag():
    """Share increase > 5% should trigger high severity flag."""
    changes = [{
        "account": "Diluted Shares",
        "percent_change": 0.06,
        "latest_value": 10.6e9,
        "prior_value": 10e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "dilution_high"


def test_cash_decline_flag():
    """Cash decline > 30% should trigger high severity flag."""
    changes = [{
        "account": "Cash",
        "percent_change": -0.35,
        "latest_value": 13e9,
        "prior_value": 20e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "cash_decline_severe"


def test_income_turned_negative_flag():
    """Net income positive to negative should trigger high severity flag."""
    changes = [{
        "account": "Net Income",
        "percent_change": -1.2,
        "latest_value": -5e9,
        "prior_value": 25e9,
    }]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 1
    assert flags[0]["code"] == "income_turned_negative"


def test_late_filing_flag():
    """NT 10-K in submissions should trigger late filing flag."""
    submissions = {
        "filings": {
            "recent": {
                "form": ["NT 10-K", "10-K", "10-Q"],
                "filingDate": ["2023-12-01", "2023-11-01", "2023-08-01"],
            }
        }
    }
    flags = _check_metadata_flags(submissions, as_of_date=date(2023, 12, 15))
    late_flags = [f for f in flags if f["code"] == "late_filing"]
    assert len(late_flags) == 1
    assert late_flags[0]["severity"] == "high"
    assert late_flags[0]["source_type"] == "metadata"


def test_amendment_flag():
    """10-K/A in submissions should trigger amendment flag."""
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-K/A", "10-K"],
                "filingDate": ["2023-12-01", "2023-11-01"],
            }
        }
    }
    flags = _check_metadata_flags(submissions, as_of_date=date(2023, 12, 15))
    amend_flags = [f for f in flags if f["code"] == "filing_amendment"]
    assert len(amend_flags) == 1
    assert amend_flags[0]["severity"] == "medium"


def test_recent_8k_flag():
    """8-K within 30 days should trigger recent_8k flag."""
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K", "10-K"],
                "filingDate": ["2023-12-10", "2023-12-05", "2023-11-01"],
            }
        }
    }
    flags = _check_metadata_flags(submissions, as_of_date=date(2023, 12, 15))
    _8k_flags = [f for f in flags if f["code"] == "recent_8k"]
    assert len(_8k_flags) == 1
    assert "2" in _8k_flags[0]["detail"]  # Should mention 2 filings


def test_no_flags_clean_company():
    """No changes above thresholds should produce no flags."""
    changes = [
        {"account": "Revenue", "percent_change": 0.05, "latest_value": 105e9, "prior_value": 100e9},
        {"account": "Cash", "percent_change": -0.05, "latest_value": 19e9, "prior_value": 20e9},
    ]
    flags = _check_numeric_flags(changes)
    assert len(flags) == 0


def test_missing_submissions_no_crash():
    """None submissions should produce no metadata flags and not crash."""
    snap = _make_empty_snapshot()
    flags = detect_red_flags(snap, filing_changes=[], submissions=None)
    assert flags == []


def test_as_of_date_determinism():
    """Same data with fixed as_of_date should produce same result."""
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K"],
                "filingDate": ["2023-12-10"],
            }
        }
    }
    ref = date(2023, 12, 15)
    flags1 = _check_metadata_flags(submissions, as_of_date=ref)
    flags2 = _check_metadata_flags(submissions, as_of_date=ref)
    assert flags1 == flags2


def test_8k_outside_30_days():
    """8-K more than 30 days ago should NOT trigger recent_8k."""
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K"],
                "filingDate": ["2023-11-01"],
            }
        }
    }
    flags = _check_metadata_flags(submissions, as_of_date=date(2023, 12, 15))
    _8k_flags = [f for f in flags if f["code"] == "recent_8k"]
    assert len(_8k_flags) == 0


def test_red_flag_has_affected_assumptions():
    """Every red flag should have the affected_assumptions field."""
    changes = [
        {"account": "Revenue", "percent_change": -0.25, "latest_value": 75e9, "prior_value": 100e9},
        {"account": "Total Debt", "percent_change": 0.35, "latest_value": 135e9, "prior_value": 100e9},
    ]
    flags = _check_numeric_flags(changes)
    for flag in flags:
        assert "affected_assumptions" in flag
