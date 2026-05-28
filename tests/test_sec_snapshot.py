import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.dcf_engine.intelligence.models import SourceFact, CompanySnapshot
from src.dcf_engine.intelligence.sec_snapshot import fetch_company_snapshot
from src.dcf_engine.intelligence.source_map import make_source_url

# Mock facts JSON
MOCK_FACTS_JSON = {
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
            },
            "CostOfGoodsAndServicesSold": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-09-30",
                            "val": 214137000000.0,
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
                            "val": 29975000000.0,
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
                            "val": 15812500000.0,
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
                            "val": 43715000000.0,
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
                            "val": 61250000000.0,
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
                            "val": 7250000000.0,
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
                            "val": 46250000000.0,
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
            }
        }
    }
}

@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_fetch_company_snapshot_success(MockEdgarClient):
    # Setup mock client
    mock_instance = MagicMock()
    mock_instance.ticker_to_cik.return_value = "0000320193"
    mock_instance._get.return_value = MOCK_FACTS_JSON
    MockEdgarClient.return_value = mock_instance

    snapshot = fetch_company_snapshot("AAPL", years=5)

    assert snapshot.ticker == "AAPL"
    assert snapshot.cik == "0000320193"
    assert snapshot.company_name == "Apple Inc."
    assert snapshot.latest_period == "2023-09-30"

    # Verify financials shape
    assert not snapshot.financials.empty
    assert "Revenue" in snapshot.financials["account"].values
    assert "COGS" in snapshot.financials["account"].values
    assert "R&D" in snapshot.financials["account"].values
    assert "Short-Term Debt" in snapshot.financials["account"].values

    # Verify key metrics derivation
    assert snapshot.key_metrics["revenue"] == 383285000000.0
    assert snapshot.key_metrics["gross_margin"] == pytest.approx(
        (383285000000.0 - 214137000000.0) / 383285000000.0
    )
    assert snapshot.key_metrics["cash"] == 29975000000.0
    assert snapshot.key_metrics["shares"] == 15812500000.0
    assert snapshot.key_metrics["ppe"] == 43715000000.0
    assert snapshot.key_metrics["nwc"] == 61250000000.0 + 7250000000.0 - 46250000000.0
    assert snapshot.key_metrics["debt"] == 20000000000.0

    # Verify source facts kept accession and concept
    assert len(snapshot.facts) > 0
    first_fact = snapshot.facts[0]
    assert first_fact.ticker == "AAPL"
    assert first_fact.accession == "0000320193-23-000106"
    assert first_fact.fiscal_year == "2023"
    assert first_fact.source_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"


@patch("src.dcf_engine.intelligence.sec_snapshot.EdgarClient")
def test_fetch_company_snapshot_sparse_data(MockEdgarClient):
    # Setup mock facts with sparse data (missing COGS and Cash)
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

    # Sparse data shouldn't crash, it should return warnings
    assert snapshot.ticker == "AAPL"
    assert snapshot.key_metrics["revenue"] == 383285000000.0
    assert snapshot.key_metrics["cash"] is None
    assert snapshot.key_metrics["debt"] is None
    
    # Confirm warnings exist for missing values
    assert len(snapshot.warnings) > 0
    assert any("Missing priority concept: Cash" in w for w in snapshot.warnings)
    assert any("Missing priority concept: Debt" in w for w in snapshot.warnings)


def test_make_source_url():
    # Accession with dashes converted
    url = make_source_url("0000320193", "0000320193-23-000106")
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"

    # Fallback to CIK facts when accession is None
    url_fallback = make_source_url("0000320193", None)
    assert url_fallback == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


from dashboard_api import app

def test_api_company_snapshot_validation():
    client = app.test_client()

    # 1. Missing ticker
    resp = client.post("/api/company-snapshot", json={"years": 5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert data["error"] == "Ticker is required"

    # 2. Invalid non-integer years (string)
    resp = client.post("/api/company-snapshot", json={"ticker": "AAPL", "years": "abc"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "integer" in data["error"]

    # 3. Invalid non-integer years (float)
    resp = client.post("/api/company-snapshot", json={"ticker": "AAPL", "years": 5.5})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "integer" in data["error"]

    # 4. Out of range years (0)
    resp = client.post("/api/company-snapshot", json={"ticker": "AAPL", "years": 0})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "between 1 and 10" in data["error"]

    # 5. Out of range years (11)
    resp = client.post("/api/company-snapshot", json={"ticker": "AAPL", "years": 11})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "request_id" in data
    assert data["warnings"] == []
    assert "between 1 and 10" in data["error"]


from src.dcf_engine.ingestion.edgar_client import EdgarClient, _CIK_LOOKUP

@patch("src.dcf_engine.ingestion.edgar_client.requests.Session")
def test_edgar_client_ticker_to_cik_url(MockSession):
    # Verify corrected CIK lookup URL is indeed used
    assert _CIK_LOOKUP == "https://www.sec.gov/files/company_tickers.json"

    # Setup mock response
    mock_session_inst = MagicMock()
    MockSession.return_value = mock_session_inst
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"}
    }
    mock_session_inst.get.return_value = mock_resp

    client = EdgarClient()
    cik = client.ticker_to_cik("AAPL")
    assert cik == "0000320193"
    
    mock_session_inst.get.assert_called_with("https://www.sec.gov/files/company_tickers.json", timeout=30)
