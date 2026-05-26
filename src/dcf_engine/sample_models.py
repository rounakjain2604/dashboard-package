"""Public sample model presets for the Trinsic launch funnel.

These are deliberately simple starter assumptions, not investment advice.
They let the public site generate polished sample workbooks without relying
on live data during the first validation push.
"""
from __future__ import annotations

from copy import deepcopy


_BASE_SCENARIOS = {
    "Base": {"name": "Base"},
    "Bull": {
        "name": "Bull",
        "revenue_multiplier": 1.10,
        "margin_delta_bps": 200,
        "working_capital_days_delta": -3,
    },
    "Bear": {
        "name": "Bear",
        "revenue_multiplier": 0.90,
        "margin_delta_bps": -200,
        "working_capital_days_delta": 4,
    },
}


SAMPLE_MODELS = {
    "NVDA": {
        "name": "NVIDIA Corporation",
        "industry": "Semiconductors",
        "tagline": "High-growth AI infrastructure sample model",
        "summary": "A high-growth semiconductor DCF starter workbook with explicit WACC, terminal value, Monte Carlo, and sensitivity tabs.",
        "payload": {
            "company_name": "NVIDIA Corporation",
            "ticker": "NVDA",
            "industry": "Semiconductors",
            "currency": "USD",
            "analyst_name": "Trinsic",
            "base_year_revenue": 130_500_000_000,
            "base_cash": 43_200_000_000,
            "base_ppe": 5_800_000_000,
            "base_nwc": 12_000_000_000,
            "base_common_stock": 1_000_000_000,
            "forecast": {
                "projection_years": 5,
                "revenue_cagr": 0.18,
                "cogs_pct_revenue": 0.25,
                "sga_pct_revenue": 0.06,
                "other_opex_pct_revenue": 0.12,
                "depreciation_rate": 0.16,
                "capex_pct_revenue": 0.035,
                "tax_rate": 0.15,
                "dso": 45,
                "dio": 80,
                "dpo": 55,
            },
            "wacc": {
                "risk_free_rate": 0.043,
                "equity_risk_premium": 0.05,
                "beta": 1.55,
                "target_debt_weight": 0.05,
                "target_equity_weight": 0.95,
                "interest_coverage_ratio": 20.0,
                "tax_rate": 0.15,
                "use_live_data": False,
            },
            "valuation": {
                "terminal_growth_rate": 0.035,
                "exit_ev_ebitda_multiple": 24.0,
                "gordon_weight": 0.35,
                "cash": 43_200_000_000,
                "debt": 11_000_000_000,
                "fully_diluted_shares": 24_600_000_000,
            },
        },
    },
    "TSLA": {
        "name": "Tesla, Inc.",
        "industry": "Automobiles",
        "tagline": "Auto, energy, and optionality valuation sample",
        "summary": "A growth-company DCF workbook for testing revenue, margin, and exit multiple sensitivity in an editable Excel model.",
        "payload": {
            "company_name": "Tesla Inc",
            "ticker": "TSLA",
            "industry": "Automobiles",
            "currency": "USD",
            "analyst_name": "Trinsic",
            "base_year_revenue": 97_700_000_000,
            "base_cash": 29_000_000_000,
            "base_ppe": 34_000_000_000,
            "base_nwc": 6_000_000_000,
            "forecast": {
                "projection_years": 5,
                "revenue_cagr": 0.12,
                "cogs_pct_revenue": 0.80,
                "sga_pct_revenue": 0.07,
                "other_opex_pct_revenue": 0.05,
                "depreciation_rate": 0.10,
                "capex_pct_revenue": 0.08,
                "tax_rate": 0.18,
                "dso": 18,
                "dio": 65,
                "dpo": 70,
            },
            "wacc": {
                "risk_free_rate": 0.043,
                "equity_risk_premium": 0.05,
                "beta": 1.85,
                "target_debt_weight": 0.05,
                "target_equity_weight": 0.95,
                "interest_coverage_ratio": 18.0,
                "tax_rate": 0.18,
                "use_live_data": False,
            },
            "valuation": {
                "terminal_growth_rate": 0.03,
                "exit_ev_ebitda_multiple": 18.0,
                "gordon_weight": 0.35,
                "cash": 29_000_000_000,
                "debt": 7_000_000_000,
                "fully_diluted_shares": 3_250_000_000,
            },
        },
    },
    "AAPL": {
        "name": "Apple Inc.",
        "industry": "Consumer Electronics",
        "tagline": "Mature cash compounder sample model",
        "summary": "A mature-company DCF starter workbook emphasizing buyback-like cash generation, terminal value, and downside cases.",
        "payload": {
            "company_name": "Apple Inc",
            "ticker": "AAPL",
            "industry": "Consumer Electronics",
            "currency": "USD",
            "analyst_name": "Trinsic",
            "base_year_revenue": 391_000_000_000,
            "base_cash": 65_000_000_000,
            "base_ppe": 43_000_000_000,
            "base_nwc": -15_000_000_000,
            "forecast": {
                "projection_years": 5,
                "revenue_cagr": 0.045,
                "cogs_pct_revenue": 0.54,
                "sga_pct_revenue": 0.07,
                "other_opex_pct_revenue": 0.08,
                "depreciation_rate": 0.09,
                "capex_pct_revenue": 0.03,
                "tax_rate": 0.16,
                "dso": 30,
                "dio": 12,
                "dpo": 85,
            },
            "wacc": {
                "risk_free_rate": 0.043,
                "equity_risk_premium": 0.05,
                "beta": 1.20,
                "target_debt_weight": 0.10,
                "target_equity_weight": 0.90,
                "interest_coverage_ratio": 25.0,
                "tax_rate": 0.16,
                "use_live_data": False,
            },
            "valuation": {
                "terminal_growth_rate": 0.025,
                "exit_ev_ebitda_multiple": 16.0,
                "gordon_weight": 0.50,
                "cash": 65_000_000_000,
                "debt": 108_000_000_000,
                "fully_diluted_shares": 15_300_000_000,
            },
        },
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "industry": "Software",
        "tagline": "Cloud and software platform sample model",
        "summary": "A durable software/platform DCF workbook with high margins, clean cash conversion, and scenario analysis.",
        "payload": {
            "company_name": "Microsoft Corporation",
            "ticker": "MSFT",
            "industry": "Software",
            "currency": "USD",
            "analyst_name": "Trinsic",
            "base_year_revenue": 245_000_000_000,
            "base_cash": 80_000_000_000,
            "base_ppe": 135_000_000_000,
            "base_nwc": 15_000_000_000,
            "forecast": {
                "projection_years": 5,
                "revenue_cagr": 0.11,
                "cogs_pct_revenue": 0.30,
                "sga_pct_revenue": 0.12,
                "other_opex_pct_revenue": 0.14,
                "depreciation_rate": 0.12,
                "capex_pct_revenue": 0.12,
                "tax_rate": 0.19,
                "dso": 55,
                "dio": 5,
                "dpo": 45,
            },
            "wacc": {
                "risk_free_rate": 0.043,
                "equity_risk_premium": 0.05,
                "beta": 1.05,
                "target_debt_weight": 0.08,
                "target_equity_weight": 0.92,
                "interest_coverage_ratio": 30.0,
                "tax_rate": 0.19,
                "use_live_data": False,
            },
            "valuation": {
                "terminal_growth_rate": 0.03,
                "exit_ev_ebitda_multiple": 20.0,
                "gordon_weight": 0.45,
                "cash": 80_000_000_000,
                "debt": 70_000_000_000,
                "fully_diluted_shares": 7_430_000_000,
            },
        },
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "industry": "E-commerce and Cloud",
        "tagline": "Retail plus AWS margin expansion sample",
        "summary": "A margin-expansion DCF starter workbook for a scaled commerce/cloud company with sensitivity and Monte Carlo tabs.",
        "payload": {
            "company_name": "Amazon.com Inc",
            "ticker": "AMZN",
            "industry": "E-commerce and Cloud",
            "currency": "USD",
            "analyst_name": "Trinsic",
            "base_year_revenue": 638_000_000_000,
            "base_cash": 89_000_000_000,
            "base_ppe": 270_000_000_000,
            "base_nwc": -20_000_000_000,
            "forecast": {
                "projection_years": 5,
                "revenue_cagr": 0.09,
                "cogs_pct_revenue": 0.67,
                "sga_pct_revenue": 0.08,
                "other_opex_pct_revenue": 0.08,
                "depreciation_rate": 0.11,
                "capex_pct_revenue": 0.09,
                "tax_rate": 0.20,
                "dso": 22,
                "dio": 38,
                "dpo": 75,
            },
            "wacc": {
                "risk_free_rate": 0.043,
                "equity_risk_premium": 0.05,
                "beta": 1.30,
                "target_debt_weight": 0.08,
                "target_equity_weight": 0.92,
                "interest_coverage_ratio": 18.0,
                "tax_rate": 0.20,
                "use_live_data": False,
            },
            "valuation": {
                "terminal_growth_rate": 0.03,
                "exit_ev_ebitda_multiple": 17.0,
                "gordon_weight": 0.40,
                "cash": 89_000_000_000,
                "debt": 135_000_000_000,
                "fully_diluted_shares": 10_600_000_000,
            },
        },
    },
}


def list_samples() -> list[dict]:
    """Return public metadata for sample model cards/pages."""
    return [
        {
            "ticker": ticker,
            "name": item["name"],
            "industry": item["industry"],
            "tagline": item["tagline"],
            "summary": item["summary"],
        }
        for ticker, item in SAMPLE_MODELS.items()
    ]


def get_sample(ticker: str) -> dict | None:
    """Return a deep copy of a public sample model by ticker."""
    sample = SAMPLE_MODELS.get(ticker.upper())
    return deepcopy(sample) if sample else None


def get_sample_payload(ticker: str) -> dict | None:
    """Return a pipeline-ready sample payload with default analytics config."""
    sample = get_sample(ticker)
    if sample is None:
        return None

    payload = deepcopy(sample["payload"])
    payload.setdefault("monte_carlo", {})
    payload["monte_carlo"].update({
        "iterations": 2_000,
        "revenue_growth_std": 0.03,
        "ebitda_margin_std": 0.04,
        "wacc_std": 0.015,
        "terminal_growth_std": 0.006,
        "exit_multiple_std": 1.5,
        "seed": 42,
    })
    payload.setdefault("sensitivity", {})
    payload.setdefault("scenarios", deepcopy(_BASE_SCENARIOS))
    payload.setdefault("peer_tickers", [])
    payload.setdefault("multiples", ["EV/Revenue", "EV/EBITDA", "P/E"])
    return payload
