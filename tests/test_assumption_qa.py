import pytest
from src.dcf_engine.intelligence.assumption_qa import evaluate_assumption_quality

# Helper to generate a baseline healthy payload
def get_clean_payload():
    return {
        "company_name": "Test Co",
        "ticker": "TEST",
        "base_year_revenue": 100000000.0,
        "base_cash": 20000000.0,
        "base_ppe": 40000000.0,
        "base_nwc": 15000000.0,
        "base_common_stock": 0.0,
        "base_retained_earnings": 10000000.0,
        "base_intangibles": 5000000.0,
        "forecast": {
            "projection_years": 5,
            "revenue_cagr": 0.08,
            "cogs_pct_revenue": 0.45,
            "sga_pct_revenue": 0.20,
            "other_opex_pct_revenue": 0.05,
            "depreciation_rate": 0.10,
            "amortisation_pct_revenue": 0.005,
            "capex_pct_revenue": 0.04,
            "tax_rate": 0.25,
        },
        "wacc": {
            "risk_free_rate": 0.042,
            "equity_risk_premium": 0.055,
            "beta": 1.1,
            "size_premium": 0.0,
            "country_risk_premium": 0.0,
            "target_debt_weight": 0.30,
            "target_equity_weight": 0.70,
            "interest_coverage_ratio": 5.0,
            "tax_rate": 0.25,
        },
        "valuation": {
            "terminal_growth_rate": 0.025,
            "exit_ev_ebitda_multiple": 10.0,
            "cash": 20000000.0,
            "debt": 10000000.0,
            "fully_diluted_shares": 50000000.0,
        }
    }

def test_qa_clean_sourced_assumptions():
    """Verify that a clean, fully-supported payload scores 100 and Grade A."""
    payload = get_clean_payload()
    result = evaluate_assumption_quality(payload, warnings=[])
    
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert len(result["warnings"]) == 0
    assert "Excellent" in result["summary"]

def test_qa_fallback_heavy():
    """Verify that moderate and heavy fallback lists correctly degrade the score and grade."""
    payload = get_clean_payload()
    
    # 1. Moderate fallback warnings (4 warnings)
    res_mod = evaluate_assumption_quality(payload, warnings=["w1", "w2", "w3", "w4"])
    assert res_mod["score"] == 90  # -10
    assert res_mod["grade"] == "A"
    assert any(w["code"] == "fallback_moderate" for w in res_mod["warnings"])

    # 2. Heavy fallback warnings (8 warnings)
    res_heavy = evaluate_assumption_quality(payload, warnings=["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8"])
    assert res_heavy["score"] == 80  # -20
    assert res_heavy["grade"] == "B"
    assert any(w["code"] == "fallback_heavy" for w in res_heavy["warnings"])

def test_qa_missing_base_revenue_and_default_shares():
    """Verify that missing base revenue and default shares outstanding are caught and scored."""
    payload = get_clean_payload()
    payload["base_year_revenue"] = 0.0
    payload["valuation"]["fully_diluted_shares"] = 1000000.0  # default shares

    result = evaluate_assumption_quality(payload)
    # base_rev <= 0 (-20 high), default_shares (-10 medium) -> score 70 (Grade B)
    assert result["score"] == 70
    assert result["grade"] == "B"
    assert any(w["code"] == "missing_base_revenue" for w in result["warnings"])
    assert any(w["code"] == "default_shares" for w in result["warnings"])

def test_qa_extreme_growth_and_high_terminal_growth():
    """Verify that extreme growth and high terminal growth are flagged."""
    payload = get_clean_payload()
    payload["forecast"]["revenue_cagr"] = 0.35  # extreme cagr (> 25%)
    payload["valuation"]["terminal_growth_rate"] = 0.04  # high terminal growth (> 3.5%)

    result = evaluate_assumption_quality(payload)
    # rev_cagr > 25% (-20 high), terminal_growth > 3.5% (-10 medium) -> score 70 (Grade B)
    assert result["score"] == 70
    assert any(w["code"] == "revenue_growth_extreme" for w in result["warnings"])
    assert any(w["code"] == "terminal_growth_high" for w in result["warnings"])

def test_qa_terminal_growth_near_wacc():
    """Verify that terminal growth too close to estimated WACC is flagged."""
    payload = get_clean_payload()
    # Estimated WACC for clean payload:
    # rf = 4.2%, beta = 1.1, erp = 5.5% -> Cost of Equity = 4.2 + 6.05 = 10.25%
    # cost of debt pre-tax = 4.2 + 2.0 = 6.2% -> cost of debt post-tax = 6.2% * (1 - 25%) = 4.65%
    # wacc_estimated = 10.25% * 0.7 + 4.65% * 0.3 = 7.175% + 1.395% = 8.57%
    # Set terminal growth to 8.4% (within 0.5% of estimated WACC)
    payload["valuation"]["terminal_growth_rate"] = 0.084

    result = evaluate_assumption_quality(payload)
    assert any(w["code"] == "terminal_growth_near_wacc" for w in result["warnings"])
    assert any(w["severity"] == "high" for w in result["warnings"] if w["code"] == "terminal_growth_near_wacc")

def test_qa_margins():
    """Verify operational operational margins are checked correctly."""
    # 1. Negative margin
    payload_neg = get_clean_payload()
    payload_neg["forecast"]["cogs_pct_revenue"] = 0.80
    payload_neg["forecast"]["sga_pct_revenue"] = 0.25  # cogs + sga = 105% -> margin -5%
    res_neg = evaluate_assumption_quality(payload_neg)
    assert any(w["code"] == "margin_negative" for w in res_neg["warnings"])

    # 2. Excessive margin
    payload_exc = get_clean_payload()
    payload_exc["forecast"]["cogs_pct_revenue"] = 0.15
    payload_exc["forecast"]["sga_pct_revenue"] = 0.10  # margin = 70%
    res_exc = evaluate_assumption_quality(payload_exc)
    assert any(w["code"] == "margin_excessive" for w in res_exc["warnings"])

def test_qa_capex_and_tax_rate():
    """Verify Capex and Tax rate checks."""
    payload = get_clean_payload()
    payload["forecast"]["capex_pct_revenue"] = 0.002  # 0.2% (unusually low)
    payload["forecast"]["tax_rate"] = 0.40  # extreme (> 35%)

    result = evaluate_assumption_quality(payload)
    assert any(w["code"] == "capex_unusually_low" for w in result["warnings"])
    assert any(w["code"] == "tax_rate_extreme" for w in result["warnings"])

def test_qa_heavy_debt_burden():
    """Verify that a heavy debt leverage scenario is flagged."""
    payload = get_clean_payload()
    payload["valuation"]["debt"] = 60000000.0  # 60M (materially > cash 20M, and is 60% of base revenue 100M)
    payload["valuation"]["cash"] = 20000000.0

    result = evaluate_assumption_quality(payload)
    assert any(w["code"] == "heavy_debt_burden" for w in result["warnings"])

def test_qa_malformed_payload_safety():
    """Verify that a totally empty or malformed payload does not crash the system, and defaults map safely."""
    # Complete empty dictionary
    res_empty = evaluate_assumption_quality({})
    assert isinstance(res_empty["score"], int)
    assert res_empty["grade"] in ("A", "B", "C", "D", "F")
    assert isinstance(res_empty["warnings"], list)
    assert isinstance(res_empty["summary"], str)

    # Malformed datatypes
    res_malformed = evaluate_assumption_quality({
        "base_year_revenue": "not_a_number",
        "wacc": "not_a_dict",
        "valuation": {
            "fully_diluted_shares": [1, 2, 3]
        }
    })
    assert isinstance(res_malformed["score"], int)
    assert res_malformed["grade"] in ("A", "B", "C", "D", "F")
