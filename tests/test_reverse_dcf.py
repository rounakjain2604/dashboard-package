import pytest
from unittest.mock import patch, MagicMock

from src.dcf_engine.intelligence.reverse_dcf import (
    solve_implied_revenue_cagr,
    solve_implied_ebitda_margin,
    solve_implied_metrics,
    _quick_dcf,
)


def _make_base_payload():
    """Build a realistic base payload for reverse DCF testing."""
    return {
        "ticker": "TEST",
        "company_name": "Test Corp",
        "base_year_revenue": 100_000_000_000,  # 100B
        "base_cash": 20_000_000_000,
        "base_ppe": 40_000_000_000,
        "base_nwc": 30_000_000_000,
        "forecast": {
            "revenue_cagr": 0.10,
            "revenue_yoy": [0.10] * 5,
            "cogs_pct_revenue": 0.50,
            "sga_pct_revenue": 0.15,
            "other_opex_pct_revenue": 0.05,
            "capex_pct_revenue": 0.03,
            "tax_rate": 0.21,
            "depreciation_rate": 0.10,
            "projection_years": 5,
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
            "gordon_weight": 0.50,
            "cash": 20_000_000_000,
            "debt": 80_000_000_000,
            "fully_diluted_shares": 10_000_000_000,
        },
    }


def test_quick_dcf_basic():
    """Verify the lightweight DCF helper returns a reasonable positive price."""
    price = _quick_dcf(
        base_revenue=100e9,
        revenue_cagr=0.10,
        ebitda_margin=0.30,
        tax_rate=0.21,
        capex_pct_revenue=0.03,
        depreciation_rate=0.10,
        base_ppe=40e9,
        wacc=0.10,
        terminal_growth=0.025,
        exit_multiple=10.0,
        gordon_weight=0.50,
        projection_years=5,
        cash=20e9,
        debt=80e9,
        shares=10e9,
    )
    assert price is not None
    assert price > 0


def test_quick_dcf_degenerate_inputs():
    """Verify _quick_dcf returns None for degenerate inputs."""
    # Zero shares
    assert _quick_dcf(100e9, 0.10, 0.30, 0.21, 0.03, 0.10, 40e9, 0.10, 0.025, 10.0, 0.5, 5, 20e9, 80e9, 0) is None
    # Zero WACC
    assert _quick_dcf(100e9, 0.10, 0.30, 0.21, 0.03, 0.10, 40e9, 0.0, 0.025, 10.0, 0.5, 5, 20e9, 80e9, 10e9) is None
    # WACC <= terminal growth
    assert _quick_dcf(100e9, 0.10, 0.30, 0.21, 0.03, 0.10, 40e9, 0.02, 0.025, 10.0, 0.5, 5, 20e9, 80e9, 10e9) is None


def test_implied_cagr_bracketed():
    """Target price within bisection range should converge."""
    payload = _make_base_payload()
    # Get the base case price first
    base_price = _quick_dcf(
        base_revenue=100e9, revenue_cagr=0.10, ebitda_margin=0.30,
        tax_rate=0.21, capex_pct_revenue=0.03, depreciation_rate=0.10,
        base_ppe=40e9, wacc=0.10, terminal_growth=0.025, exit_multiple=10.0,
        gordon_weight=0.50, projection_years=5, cash=20e9, debt=80e9, shares=10e9,
    )
    assert base_price is not None
    # Use a target slightly above base
    target = base_price * 1.3
    result = solve_implied_revenue_cagr(payload, target_price=target)
    assert result["implied_revenue_cagr"] is not None
    assert result["converged"] is True
    assert result["implied_revenue_cagr"] > 0.10  # Must be higher than base CAGR
    assert result["target_price"] == target
    assert result["base_case_price"] is not None


def test_implied_margin_bracketed():
    """Target price within margin bisection range should converge."""
    payload = _make_base_payload()
    base_price = _quick_dcf(
        base_revenue=100e9, revenue_cagr=0.10, ebitda_margin=0.30,
        tax_rate=0.21, capex_pct_revenue=0.03, depreciation_rate=0.10,
        base_ppe=40e9, wacc=0.10, terminal_growth=0.025, exit_multiple=10.0,
        gordon_weight=0.50, projection_years=5, cash=20e9, debt=80e9, shares=10e9,
    )
    target = base_price * 1.2
    result = solve_implied_ebitda_margin(payload, target_price=target)
    assert result["implied_ebitda_margin"] is not None
    assert result["converged"] is True
    assert result["implied_ebitda_margin"] > 0.30  # Higher than base margin
    assert result["implied_cogs_pct"] is not None
    assert result["implied_cogs_pct"] >= 0.0  # COGS must not be negative


def test_unbracketed_returns_warning():
    """Target price far outside range should return boundary + warning."""
    payload = _make_base_payload()
    result = solve_implied_revenue_cagr(payload, target_price=999999.0)
    assert result["converged"] is False
    assert len(result["warnings"]) > 0
    assert "outside" in result["warnings"][0].lower() or "boundary" in result["warnings"][0].lower()


def test_missing_price_returns_warning():
    """None target_price should skip reverse DCF with warning."""
    payload = _make_base_payload()
    result = solve_implied_metrics(payload, target_price=None)
    assert result["implied_revenue_cagr"] is None
    assert result["implied_ebitda_margin"] is None
    assert any("unavailable" in w.lower() for w in result["warnings"])


def test_missing_shares_returns_warning():
    """Zero shares should return warning."""
    payload = _make_base_payload()
    payload["valuation"]["fully_diluted_shares"] = 0
    result = solve_implied_revenue_cagr(payload, target_price=50.0)
    assert result["implied_revenue_cagr"] is None
    assert result["converged"] is False
    assert any("shares" in w.lower() for w in result["warnings"])


def test_missing_revenue_returns_warning():
    """Zero base revenue should return warning."""
    payload = _make_base_payload()
    payload["base_year_revenue"] = 0
    result = solve_implied_revenue_cagr(payload, target_price=50.0)
    assert result["implied_revenue_cagr"] is None
    assert result["converged"] is False
    assert any("revenue" in w.lower() for w in result["warnings"])


def test_margin_solver_negative_cogs_guard():
    """Margin solver should clamp upper bound to avoid negative COGS."""
    payload = _make_base_payload()
    # Set SGA + other to 90% of revenue, leaving only 10% for margin
    payload["forecast"]["sga_pct_revenue"] = 0.70
    payload["forecast"]["other_opex_pct_revenue"] = 0.20
    result = solve_implied_ebitda_margin(payload, target_price=50.0)
    # Should clamp or warn about the upper bound
    if result["implied_ebitda_margin"] is not None:
        implied_cogs = 1.0 - result["implied_ebitda_margin"] - 0.70 - 0.20
        assert implied_cogs >= -0.01  # Allow tiny float tolerance


def test_solve_implied_metrics_with_market_cap():
    """solve_implied_metrics should derive target_price from market_cap / shares."""
    payload = _make_base_payload()
    shares = payload["valuation"]["fully_diluted_shares"]
    target_price = 50.0
    result = solve_implied_metrics(payload, target_price=None, market_cap=target_price * shares)
    assert result["target_price"] == pytest.approx(target_price, abs=0.01)
    assert result["target_equity_value"] is not None


def test_payload_not_mutated():
    """Ensure solvers do not mutate the original payload."""
    payload = _make_base_payload()
    import copy
    original = copy.deepcopy(payload)
    solve_implied_revenue_cagr(payload, target_price=50.0)
    solve_implied_ebitda_margin(payload, target_price=50.0)
    assert payload == original


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_reverse_dcf_in_preview(MockEdgarClient):
    """Verify valuation preview includes reverse_dcf key."""
    from tests.test_valuation_preview import MOCK_FACTS_JSON_2Y
    from src.dcf_engine.intelligence import build_valuation_preview

    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    with patch("src.dcf_engine.intelligence.valuation_preview._try_get_market_price", return_value=None):
        result = build_valuation_preview("AAPL", years=2)

    assert "reverse_dcf" in result
    assert isinstance(result["reverse_dcf"], dict)
    assert "warnings" in result["reverse_dcf"]
    # Since market price is None, should have unavailable warning
    assert any("unavailable" in w.lower() for w in result["reverse_dcf"]["warnings"])
