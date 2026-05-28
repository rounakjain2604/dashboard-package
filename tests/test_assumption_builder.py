import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.dcf_engine.intelligence.models import CompanySnapshot, SourceFact
from src.dcf_engine.intelligence.sec_snapshot import fetch_company_snapshot
from src.dcf_engine.intelligence.assumption_builder import build_assumptions_from_snapshot
from dashboard_api import app, _build_config_from_payload

# Mock multi-year facts JSON for a fully populated company
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


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_build_assumptions_success(MockEdgarClient):
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    snapshot = fetch_company_snapshot("AAPL", years=5)
    result = build_assumptions_from_snapshot(snapshot)

    # 1. Base levels checks
    assert result.base_values["base_year_revenue"] == 330000000000.0
    assert result.base_values["base_cash"] == 20000000000.0
    assert result.base_values["base_ppe"] == 40000000000.0
    assert result.base_values["base_nwc"] == 50000000000.0 + 10000000000.0 - 30000000000.0
    assert result.base_values["base_retained_earnings"] == 15000000000.0

    # 2. Payload root checks
    p = result.payload
    assert p["base_year_revenue"] == 330000000000.0
    assert p["base_cash"] == 20000000000.0
    assert p["base_ppe"] == 40000000000.0
    assert p["base_nwc"] == 30000000000.0
    assert p["base_retained_earnings"] == 15000000000.0

    # 3. Forecast derivation checks
    fc = p["forecast"]
    assert fc["revenue_cagr"] == pytest.approx(0.10, abs=1e-3)
    assert fc["cogs_pct_revenue"] == 0.50
    assert fc["sga_pct_revenue"] == 0.15
    assert fc["other_opex_pct_revenue"] == 0.05
    assert fc["capex_pct_revenue"] == pytest.approx(0.03)
    assert fc["tax_rate"] == pytest.approx(0.20)  # derived from EBT (EBIT 115.5B - interest 5.5B = 110B)

    # 4. Valuation checks
    val = p["valuation"]
    assert val["cash"] == 20000000000.0
    assert val["debt"] == 100000000000.0
    assert val["fully_diluted_shares"] == 10000000000.0

    # 5. Check if it parses cleanly into the DCFEngineConfig
    cfg = _build_config_from_payload(p)
    assert cfg.company.ticker == "AAPL"
    assert cfg.forecast.revenue_cagr == pytest.approx(0.10, abs=1e-3)
    assert cfg.forecast.cogs_pct_revenue == 0.50
    assert cfg.forecast.sga_pct_revenue == 0.15
    assert cfg.forecast.other_opex_pct_revenue == 0.05
    assert cfg.forecast.tax_rate == pytest.approx(0.20)
    assert cfg.valuation.fully_diluted_shares == 10000000000.0

    # 6. Verify that no fallback warnings were generated (since all priority concepts were sourced)
    assert not any("Research & Development expense not found" in w for w in result.warnings)
    assert not any("Debt not found" in w for w in result.warnings)
    assert not any("Cash not found" in w for w in result.warnings)
    assert not any("Capex % of revenue not found" in w for w in result.warnings)


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_build_assumptions_sparse_fallbacks(MockEdgarClient):
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

    snapshot = fetch_company_snapshot("AAPL", years=5)
    result = build_assumptions_from_snapshot(snapshot)

    # Missing components should lead to fallback values and detailed warnings
    p = result.payload
    assert p["base_cash"] == 0.0
    assert p["base_ppe"] == 0.0
    assert p["base_nwc"] == 0.0
    assert p["forecast"]["revenue_cagr"] == 0.05
    assert p["forecast"]["cogs_pct_revenue"] == 0.50
    assert p["forecast"]["sga_pct_revenue"] == 0.15
    assert p["forecast"]["tax_rate"] == 0.21
    assert p["valuation"]["fully_diluted_shares"] == 1000000.0

    # Ensure warnings exist for all required fallbacks
    w = result.warnings
    assert any("Cash not found" in msg for msg in w)
    assert any("PP&E Net not found" in msg for msg in w)
    assert any("Net Working Capital components missing" in msg for msg in w)
    assert any("Retained earnings not found" in msg for msg in w)
    assert any("Shares not found" in msg for msg in w)
    assert any("Debt not found" in msg for msg in w)
    assert any("Revenue CAGR not found" in msg for msg in w)
    assert any("COGS % of revenue not found" in msg for msg in w)
    assert any("SG&A % of revenue not found" in msg for msg in w)
    assert any("Research & Development expense not found" in msg for msg in w)
    assert any("Capex % of revenue not found" in msg for msg in w)
    assert any("Tax rate not found" in msg for msg in w)


def test_api_ticker_assumptions_route_validation():
    client = app.test_client()

    # 1. Missing ticker
    resp = client.post("/api/ticker-assumptions", json={"years": 5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert data["error"] == "Ticker is required"

    # 2. Invalid non-integer years (string)
    resp = client.post("/api/ticker-assumptions", json={"ticker": "AAPL", "years": "abc"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "integer" in data["error"]

    # 3. Invalid non-integer years (float)
    resp = client.post("/api/ticker-assumptions", json={"ticker": "AAPL", "years": 5.5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "integer" in data["error"]

    # 4. Out of range years (0)
    resp = client.post("/api/ticker-assumptions", json={"ticker": "AAPL", "years": 0})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "between 1 and 10" in data["error"]

    # 5. Out of range years (11)
    resp = client.post("/api/ticker-assumptions", json={"ticker": "AAPL", "years": 11})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "between 1 and 10" in data["error"]


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_api_ticker_assumptions_run_integration(MockEdgarClient):
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON_2Y
    MockEdgarClient.return_value = mock_instance

    client = app.test_client()

    # 1. Fetch assumptions
    resp = client.post("/api/ticker-assumptions", json={"ticker": "AAPL", "years": 2})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["ticker"] == "AAPL"
    
    payload = data["payload"]
    assert "forecast" in payload
    assert payload["base_year_revenue"] == 330000000000.0

    # Verify source_map is a list of dictionaries (cleanly JSON serializable)
    source_map = data["source_map"]
    assert isinstance(source_map, list)
    assert len(source_map) > 0
    assert isinstance(source_map[0], dict)
    assert source_map[0]["ticker"] == "AAPL"

    # 2. Pipe assumptions directly into /api/run
    # We pass the assumptions payload; /api/run should process it successfully
    run_resp = client.post("/api/run", json=payload)
    assert run_resp.status_code == 200
    run_data = run_resp.get_json()
    assert run_data["success"] is True
    assert "wacc" in run_data
    assert "dcf" in run_data
    assert "scenarios" in run_data
