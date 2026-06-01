import pytest
import math
from unittest.mock import patch, MagicMock
import pandas as pd

from src.dcf_engine.intelligence import build_valuation_preview
from dashboard_api import app


@pytest.fixture(autouse=True)
def mock_ingest_edgar_client_submissions():
    with patch("src.dcf_engine.ingestion.edgar_client.EdgarClient") as mock:
        mock_instance = MagicMock()
        mock_instance.fetch_submissions.return_value = None
        mock.return_value = mock_instance
        yield mock


# Realistic mock facts for a fully populated company (reused from test_assumption_builder.py)
MOCK_FACTS_JSON_2Y = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "end": "2022-09-30",
                            "val": 300000000000.0,
                            "accn": "0000320193-22-000106",
                            "fy": 2022,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2022-10-28",
                            "frame": "CY2022"
                        },
                        {
                            "end": "2023-09-30",
                            "val": 330000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "CostOfGoodsAndServicesSold": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 165000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "SellingGeneralAndAdministrativeExpense": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 49500000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "ResearchAndDevelopmentExpense": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 16500000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "CashAndCashEquivalentsAtCarryingValue": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 20000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "PropertyPlantAndEquipmentNet": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 40000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "AccountsReceivableNetCurrent": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 50000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "InventoryNet": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 10000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "AccountsPayableCurrent": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 30000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {
                    "shares": [
                        {
                            "end": "2023-09-30",
                            "val": 10000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "LongTermDebt": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 80000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "ShortTermBorrowings": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 20000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 115500000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "InterestExpense": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 5500000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "IncomeTaxExpenseBenefit": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 22000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 88000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "RetainedEarningsAccumulatedDeficit": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 15000000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            },
            "PaymentsToAcquirePropertyPlantAndEquipment": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 9900000000.0,
                            "accn": "0000320193-23-000106",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                            "frame": "CY2023"
                        }
                    ]
                }
            }
        }
    }
}

def test_valuation_preview_import_safety():
    """Verify that build_valuation_preview can be imported and executed without circular crashes."""
    assert build_valuation_preview is not None

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_success(MockEdgarClient):
    """Test successful preview generation from realistic mocked SEC facts."""
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    result = build_valuation_preview("AAPL", years=2)

    assert result["ticker"] == "AAPL"
    assert result["blended_equity_value"] > 0.0
    assert result["blended_enterprise_value"] > 0.0
    assert result["implied_share_price"] > 0.0
    assert result["wacc"] > 0.0
    assert result["terminal_growth"] == 0.025
    assert result["exit_multiple"] == 10.0
    assert result["revenue_cagr"] == pytest.approx(0.10, abs=1e-3)
    # COGS 50%, SGA 15%, R&D 5% -> EBITDA margin = 30%
    assert result["ebitda_margin"] == pytest.approx(0.30, abs=1e-3)
    assert result["tv_pct_of_ev"] > 0.0
    assert isinstance(result["warnings"], list)
    assert isinstance(result["source_map"], list)
    assert len(result["source_map"]) > 0
    assert "revenue_cagr" in result["key_assumptions"]
    assert "forecast" in result["payload"]
    assert "assumption_quality" in result
    assert "score" in result["assumption_quality"]
    assert "grade" in result["assumption_quality"]

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_sparse_fallbacks(MockEdgarClient):
    """Verify that a sparse snapshot returns fallback warnings and runs successfully."""
    sparse_json = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-09-30",
                                "val": 383285000000.0,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "frame": "CY2023"
                            }
                        ]
                    }
                }
            }
        }
    }

    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = sparse_json
    MockEdgarClient.return_value = mock_instance

    result = build_valuation_preview("AAPL", years=5)

    assert result["ticker"] == "AAPL"
    assert result["blended_equity_value"] > 0.0
    assert result["wacc"] > 0.0
    
    # Sparse fallbacks should populate warnings
    w = result["warnings"]
    assert any("Cash not found" in msg for msg in w)
    assert any("Debt not found" in msg for msg in w)
    assert any("Shares not found" in msg for msg in w)

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_overrides_and_validation(MockEdgarClient):
    """Test whitelisted overrides, bad keys ignored, and strict value checks."""
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    overrides = {
        "forecast.revenue_cagr": 0.06,  # whitelisted & valid
        "forecast.cogs_pct_revenue": 0.40,  # whitelisted & valid
        "valuation.exit_ev_ebitda_multiple": 12.0,  # whitelisted & valid
        "scenarios.Bull.revenue_multiplier": 1.5,  # not whitelisted (ignored)
        "wacc.beta": "invalid_string",  # non-numeric (ignored)
        "wacc.risk_free_rate": -0.05,  # negative rate (ignored)
        "wacc.target_debt_weight": 1.5,  # weight outside [0, 1] (ignored)
        "wacc.equity_risk_premium": True,  # boolean (ignored)
    }

    result = build_valuation_preview("AAPL", years=2, overrides=overrides)

    assert result["revenue_cagr"] == 0.06
    assert result["exit_multiple"] == 12.0
    # COGS overridden to 40%, SGA 15%, R&D 5% -> EBITDA margin = 40%
    assert result["ebitda_margin"] == pytest.approx(0.40, abs=1e-3)
    
    # Check that yoy was updated
    assert result["payload"]["forecast"]["revenue_yoy"] == [0.06] * 5

    # Check warnings for invalid overrides
    w = result["warnings"]
    assert any("Override 'scenarios.Bull.revenue_multiplier' is not allowed and was ignored." in msg for msg in w)
    assert any("Override 'wacc.beta' has invalid non-numeric value 'invalid_string' and was ignored." in msg for msg in w)
    assert any("Override 'wacc.risk_free_rate' value -0.05 cannot be negative and was ignored." in msg for msg in w)
    assert any("Override 'wacc.target_debt_weight' value 1.5 is outside allowed range [0.0, 1.0] and was ignored." in msg for msg in w)
    assert any("Override 'wacc.equity_risk_premium' has invalid non-numeric value 'True' and was ignored." in msg for msg in w)

def test_api_valuation_preview_route_validation():
    """Verify Flask server endpoint parameter validation."""
    client = app.test_client()

    # 1. Missing ticker
    resp = client.post("/api/valuation-preview", json={"years": 5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Ticker is required"

    # 2. Out of range years
    resp = client.post("/api/valuation-preview", json={"ticker": "AAPL", "years": 11})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "between 1 and 10" in data["error"]

    # 3. Invalid years type
    resp = client.post("/api/valuation-preview", json={"ticker": "AAPL", "years": "invalid"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "integer" in data["error"]

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_api_valuation_preview_success_integration(MockEdgarClient):
    """Verify full integration run via client POST request."""
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    client = app.test_client()
    resp = client.post("/api/valuation-preview", json={
        "ticker": "AAPL",
        "years": 2,
        "overrides": {
            "forecast.revenue_cagr": 0.08
        }
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "request_id" in data
    assert data["ticker"] == "AAPL"
    assert data["blended_equity_value"] > 0.0
    assert data["revenue_cagr"] == 0.08
    assert data["key_assumptions"]["revenue_cagr"] == 0.08
    assert "assumption_quality" in data
    assert "score" in data["assumption_quality"]
    assert "grade" in data["assumption_quality"]

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_missing_revenue(MockEdgarClient):
    """Verify that a snapshot with missing/zero revenue cleanly aborts without falling back to sample CSV."""
    empty_json = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {}
    }
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = empty_json
    MockEdgarClient.return_value = mock_instance

    # Should cleanly return None metrics and failure/aborted warnings
    result = build_valuation_preview("AAPL", years=5)

    assert result["ticker"] == "AAPL"
    assert result["blended_equity_value"] is None
    assert result["blended_enterprise_value"] is None
    assert result["implied_share_price"] is None
    assert result["wacc"] is None
    assert any("Valuation preview aborted: SEC-derived base year revenue is missing or zero." in w for w in result["warnings"])
    assert "assumption_quality" in result
    assert "score" in result["assumption_quality"]

    # Now verify via endpoint that it returns 400
    client = app.test_client()
    resp = client.post("/api/valuation-preview", json={"ticker": "AAPL", "years": 5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "Critical valuation" in data["error"]
    assert "assumption_quality" in data
    assert "score" in data["assumption_quality"]

def test_valuation_preview_invalid_overrides_type():
    """Verify that passing non-dict override container types raises ValueError or returns 400."""
    # 1. Direct call raises ValueError
    with pytest.raises(ValueError, match="overrides parameter must be a dictionary"):
        build_valuation_preview("AAPL", years=5, overrides="invalid_string")

    with pytest.raises(ValueError, match="overrides parameter must be a dictionary"):
        build_valuation_preview("AAPL", years=5, overrides=[1, 2, 3])

    with pytest.raises(ValueError, match="overrides parameter must be a dictionary"):
        build_valuation_preview("AAPL", years=5, overrides=True)

    # 2. API endpoint returns 400
    client = app.test_client()
    resp = client.post("/api/valuation-preview", json={
        "ticker": "AAPL",
        "years": 5,
        "overrides": "invalid_string"
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "overrides parameter must be a dictionary" in data["error"]

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_custom_data_file_path(MockEdgarClient):
    """Verify that the payload's data_file is explicitly set inside the data directory to avoid fallbacks."""
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    result = build_valuation_preview("AAPL", years=2)
    assert result["payload"]["data_file"] == "data/nonexistent_sec_preview_file.csv"


@patch("src.dcf_engine.ingestion.edgar_client.EdgarClient")
@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_metadata_red_flags(MockSecEdgarClient, MockIngestEdgarClient):
    """Verify that metadata red flags flow into valuation impacts and metadata_checked is True."""
    from datetime import date
    
    mock_sec = MagicMock()
    mock_sec.ticker_to_cik.return_value = "0000320193"
    mock_sec._get.return_value = MOCK_FACTS_JSON_2Y
    MockSecEdgarClient.return_value = mock_sec

    mock_submissions = {
        "filings": {
            "recent": {
                "form": ["NT 10-K", "10-K/A", "8-K", "10-K"],
                "filingDate": [date.today().isoformat()] * 4
            }
        }
    }
    mock_ingest = MagicMock()
    mock_ingest.fetch_submissions.return_value = mock_submissions
    MockIngestEdgarClient.return_value = mock_ingest

    result = build_valuation_preview("AAPL", years=2)
    assert result["metadata_checked"] is True
    
    # Assert metadata red flags flow into valuation impacts
    impacts = result["valuation_impacts"]
    categories = [imp.get("category") for imp in impacts]
    titles = [imp.get("title") for imp in impacts]
    
    assert "red_flag" in categories
    assert any("Late filing detected" in t for t in titles)
    assert any("Filing amendment detected" in t for t in titles)
    assert any("filing(s) in the last 30 days" in t for t in titles)


@patch("src.dcf_engine.ingestion.edgar_client.EdgarClient")
@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_submissions_fail_warning(MockSecEdgarClient, MockIngestEdgarClient):
    """Verify that fetch_submissions returning None gives metadata_checked: False and the warnings."""
    mock_sec = MagicMock()
    mock_sec.ticker_to_cik.return_value = "0000320193"
    mock_sec._get.return_value = MOCK_FACTS_JSON_2Y
    MockSecEdgarClient.return_value = mock_sec

    mock_ingest = MagicMock()
    mock_ingest.fetch_submissions.return_value = None
    MockIngestEdgarClient.return_value = mock_ingest

    result = build_valuation_preview("AAPL", years=2)
    assert result["metadata_checked"] is False
    assert any("metadata unavailable" in w for w in result["warnings"])


@patch("src.dcf_engine.ingestion.edgar_client.EdgarClient")
@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_api_route_valuation_preview_metadata_success(MockSecEdgarClient, MockIngestEdgarClient):
    """Verify metadata_checked is included in successful /api/valuation-preview responses."""
    mock_sec = MagicMock()
    mock_sec.ticker_to_cik.return_value = "0000320193"
    mock_sec._get.return_value = MOCK_FACTS_JSON_2Y
    MockSecEdgarClient.return_value = mock_sec

    mock_ingest = MagicMock()
    mock_ingest.fetch_submissions.return_value = {"filings": {"recent": {"form": ["10-K"], "filingDate": ["2023-11-03"]}}}
    MockIngestEdgarClient.return_value = mock_ingest

    client = app.test_client()
    resp = client.post("/api/valuation-preview", json={"ticker": "AAPL", "years": 2})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["metadata_checked"] is True


@patch("src.dcf_engine.ingestion.edgar_client.EdgarClient")
@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_api_route_valuation_preview_missing_revenue_metadata(MockSecEdgarClient, MockIngestEdgarClient):
    """Verify metadata_checked is included in 400 missing revenue responses."""
    mock_sec = MagicMock()
    mock_sec.ticker_to_cik.return_value = "0000320193"
    mock_sec._get.return_value = {"cik": 320193, "entityName": "Apple Inc.", "facts": {}}  # empty -> missing revenue
    MockSecEdgarClient.return_value = mock_sec

    mock_ingest = MagicMock()
    mock_ingest.fetch_submissions.return_value = None
    MockIngestEdgarClient.return_value = mock_ingest

    client = app.test_client()
    resp = client.post("/api/valuation-preview", json={"ticker": "AAPL", "years": 2})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["metadata_checked"] is False


@patch("src.dcf_engine.ingestion.edgar_client.EdgarClient")
@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_valuation_preview_single_period_metadata_red_flags(MockSecEdgarClient, MockIngestEdgarClient):
    """Verify metadata red flags are captured for single-period/sparse companies even when numeric_changes is empty."""
    from datetime import date
    
    single_period_json = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-09-30",
                                "val": 330000000000.0,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "frame": "CY2023"
                            }
                        ]
                    }
                }
            }
        }
    }
    
    mock_sec = MagicMock()
    mock_sec.ticker_to_cik.return_value = "0000320193"
    mock_sec._get.return_value = single_period_json
    MockSecEdgarClient.return_value = mock_sec

    mock_submissions = {
        "filings": {
            "recent": {
                "form": ["NT 10-K", "10-K/A", "8-K", "10-K"],
                "filingDate": [date.today().isoformat()] * 4
            }
        }
    }
    mock_ingest = MagicMock()
    mock_ingest.fetch_submissions.return_value = mock_submissions
    MockIngestEdgarClient.return_value = mock_ingest

    result = build_valuation_preview("AAPL", years=2)
    
    assert result["metadata_checked"] is True
    
    impacts = result["valuation_impacts"]
    categories = [imp.get("category") for imp in impacts]
    titles = [imp.get("title") for imp in impacts]
    
    assert "red_flag" in categories
    assert any("Late filing detected" in t for t in titles)
    assert any("Filing amendment detected" in t for t in titles)
    assert any("filing(s) in the last 30 days" in t for t in titles)
    
    w = result["warnings"]
    assert any("Fewer than two filing periods available; numeric filing changes were not computed." in msg for msg in w)
    assert not any("valuation impacts not computed" in msg for msg in w)
