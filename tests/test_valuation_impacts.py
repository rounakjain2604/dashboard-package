import pytest

from src.dcf_engine.intelligence.valuation_impacts import build_valuation_impacts


def test_revenue_impact():
    """Medium+ revenue change should generate a revenue_growth impact."""
    changes = [{
        "account": "Revenue",
        "category": "revenue",
        "severity": "medium",
        "percent_change": 0.12,
        "absolute_change": 36e9,
        "latest_value": 336e9,
        "prior_value": 300e9,
        "valuation_impact": "Review revenue growth.",
    }]
    impacts = build_valuation_impacts(changes, red_flags=[])
    assert len(impacts) >= 1
    rev_impact = [i for i in impacts if i["category"] == "revenue_growth"]
    assert len(rev_impact) == 1
    assert "base_year_revenue" in rev_impact[0]["affected_assumptions"]
    assert "forecast.revenue_cagr" in rev_impact[0]["affected_assumptions"]


def test_debt_impact():
    """High debt change should generate a debt_wacc impact."""
    changes = [{
        "account": "Total Debt",
        "category": "debt",
        "severity": "high",
        "percent_change": 0.50,
        "absolute_change": 40e9,
        "latest_value": 120e9,
        "prior_value": 80e9,
        "valuation_impact": "Review debt.",
    }]
    impacts = build_valuation_impacts(changes, red_flags=[])
    debt_impacts = [i for i in impacts if i["category"] == "debt_wacc"]
    assert len(debt_impacts) == 1
    assert "valuation.debt" in debt_impacts[0]["affected_assumptions"]


def test_share_dilution_impact():
    """High share dilution should generate share_count impact."""
    changes = [{
        "account": "Diluted Shares",
        "category": "shares",
        "severity": "high",
        "percent_change": 0.04,
        "absolute_change": 0.4e9,
        "latest_value": 10.4e9,
        "prior_value": 10e9,
        "valuation_impact": "Review dilution.",
    }]
    impacts = build_valuation_impacts(changes, red_flags=[])
    share_impacts = [i for i in impacts if i["category"] == "share_count"]
    assert len(share_impacts) == 1
    assert "valuation.fully_diluted_shares" in share_impacts[0]["affected_assumptions"]


def test_red_flag_impact():
    """Red flags should generate red_flag category impacts."""
    red_flags = [{
        "code": "revenue_decline_severe",
        "severity": "high",
        "title": "Revenue declined more than 20%",
        "detail": "Revenue fell 25%.",
        "source_type": "xbrl",
        "affected_assumptions": ["base_year_revenue", "forecast.revenue_cagr"],
    }]
    impacts = build_valuation_impacts(changes=[], red_flags=red_flags)
    assert len(impacts) == 1
    assert impacts[0]["category"] == "red_flag"
    assert impacts[0]["severity"] == "high"
    assert "base_year_revenue" in impacts[0]["affected_assumptions"]


def test_no_changes_no_impacts():
    """No changes and no red flags should produce no impacts."""
    impacts = build_valuation_impacts(changes=[], red_flags=[])
    assert impacts == []


def test_low_severity_excluded():
    """Low severity changes should not produce impacts (min_severity is medium)."""
    changes = [{
        "account": "Revenue",
        "category": "revenue",
        "severity": "low",
        "percent_change": 0.02,
        "absolute_change": 6e9,
        "latest_value": 306e9,
        "prior_value": 300e9,
        "valuation_impact": "Modest.",
    }]
    impacts = build_valuation_impacts(changes, red_flags=[])
    rev_impacts = [i for i in impacts if i["category"] == "revenue_growth"]
    assert len(rev_impacts) == 0


def test_multiple_impacts_sorted():
    """Multiple impacts should be sorted by severity (high first)."""
    changes = [
        {
            "account": "Revenue",
            "category": "revenue",
            "severity": "medium",
            "percent_change": 0.12,
            "absolute_change": 36e9,
            "latest_value": 336e9,
            "prior_value": 300e9,
            "valuation_impact": "Review.",
        },
        {
            "account": "Total Debt",
            "category": "debt",
            "severity": "high",
            "percent_change": 0.50,
            "absolute_change": 40e9,
            "latest_value": 120e9,
            "prior_value": 80e9,
            "valuation_impact": "Review.",
        },
    ]
    impacts = build_valuation_impacts(changes, red_flags=[])
    assert len(impacts) >= 2
    # High severity should come first
    assert impacts[0]["severity"] == "high"


def test_no_forbidden_wording():
    """Impact output must not contain investment advice language."""
    changes = [
        {
            "account": "Revenue",
            "category": "revenue",
            "severity": "high",
            "percent_change": 0.25,
            "absolute_change": 75e9,
            "latest_value": 375e9,
            "prior_value": 300e9,
            "valuation_impact": "Review.",
        },
        {
            "account": "Total Debt",
            "category": "debt",
            "severity": "high",
            "percent_change": 0.50,
            "absolute_change": 40e9,
            "latest_value": 120e9,
            "prior_value": 80e9,
            "valuation_impact": "Review.",
        },
    ]
    red_flags = [{
        "code": "debt_surge",
        "severity": "high",
        "title": "Debt increased more than 30%",
        "detail": "Total debt increased 50%.",
        "source_type": "xbrl",
        "affected_assumptions": ["valuation.debt"],
    }]
    impacts = build_valuation_impacts(changes, red_flags)
    forbidden_words = ["buy", "sell", "guaranteed", "overvalued", "undervalued",
                       "financial advice", "investment advice"]
    all_text = " ".join(
        f"{i.get('title', '')} {i.get('detail', '')}" for i in impacts
    ).lower()
    for word in forbidden_words:
        assert word not in all_text, f"Forbidden wording found: '{word}'"


def test_impact_has_affected_assumptions():
    """Every impact should have an affected_assumptions list."""
    changes = [{
        "account": "Revenue",
        "category": "revenue",
        "severity": "high",
        "percent_change": 0.20,
        "absolute_change": 60e9,
        "latest_value": 360e9,
        "prior_value": 300e9,
        "valuation_impact": "Review.",
    }]
    impacts = build_valuation_impacts(changes, red_flags=[])
    for impact in impacts:
        assert "affected_assumptions" in impact
        assert isinstance(impact["affected_assumptions"], list)
