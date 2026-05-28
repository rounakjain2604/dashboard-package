from __future__ import annotations
import logging
import pandas as pd
from src.dcf_engine.intelligence.models import CompanySnapshot, AssumptionBuildResult

logger = logging.getLogger(__name__)

def build_assumptions_from_snapshot(snapshot: CompanySnapshot) -> AssumptionBuildResult:
    """
    Converts a CompanySnapshot into a pipeline-ready dashboard payload
    compatible with _build_config_from_payload(data) in dashboard_api.py.
    """
    warnings: list[str] = []
    
    # Helper to get the latest value of an account (guarded against empty dataframe/missing columns)
    def get_latest_val(acct: str) -> float | None:
        if not snapshot.latest_period or snapshot.financials.empty or "account" not in snapshot.financials.columns or "period" not in snapshot.financials.columns:
            return None
        match = snapshot.financials[
            (snapshot.financials["period"] == snapshot.latest_period) &
            (snapshot.financials["account"] == acct)
        ]
        if not match.empty:
            return float(match.iloc[0]["amount"])
        return None

    # 1. Base-Year & Top-Level Values
    revenue = get_latest_val("Revenue")
    if revenue is None:
        revenue = 0.0
        warnings.append("Revenue not found in SEC facts; used 0.0 fallback.")

    cash = get_latest_val("Cash")
    if cash is None:
        cash = 0.0
        warnings.append("Cash not found in SEC facts; used 0.0 fallback.")

    ppe = get_latest_val("PP&E Net")
    if ppe is None:
        ppe = 0.0
        warnings.append("PP&E Net not found in SEC facts; used 0.0 fallback.")

    ar = get_latest_val("Accounts Receivable")
    inv = get_latest_val("Inventory")
    ap = get_latest_val("Accounts Payable")
    
    missing_nwc_components = []
    if ar is None: missing_nwc_components.append("Accounts Receivable")
    if inv is None: missing_nwc_components.append("Inventory")
    if ap is None: missing_nwc_components.append("Accounts Payable")
    
    if missing_nwc_components:
        warnings.append(f"Net Working Capital components missing: {', '.join(missing_nwc_components)}; NWC set to 0.0.")
        nwc = 0.0
    else:
        nwc = ar + inv - ap

    retained_earnings = get_latest_val("Retained Earnings")
    if retained_earnings is None:
        retained_earnings = 0.0
        warnings.append("Retained earnings not found in SEC facts; used 0.0 fallback.")

    goodwill = get_latest_val("Goodwill") or 0.0
    intangibles_acct = get_latest_val("Intangibles") or 0.0
    intangibles = goodwill + intangibles_acct

    # 2. Valuation fully diluted shares derivation
    shares = get_latest_val("Shares Diluted")
    if shares is None:
        shares = get_latest_val("Shares Outstanding")
    if shares is None:
        shares = get_latest_val("Shares Outstanding (BS)")
    if shares is None:
        shares = 1000000.0
        warnings.append("Shares not found in SEC facts; used 1,000,000 fallback.")

    # 3. Debt schedule derivation
    lt_debt = get_latest_val("Long-Term Debt")
    st_debt = get_latest_val("Short-Term Debt")
    if lt_debt is None and st_debt is None:
        debt = 0.0
        warnings.append("Debt not found in SEC facts; used 0.0 fallback.")
    else:
        debt = (lt_debt or 0.0) + (st_debt or 0.0)

    # 4. Revenue CAGR derivation (minimum 2 periods required for actual historical growth)
    rev_df = pd.DataFrame()
    if not snapshot.financials.empty and "account" in snapshot.financials.columns and "period" in snapshot.financials.columns:
        rev_df = snapshot.financials[snapshot.financials["account"] == "Revenue"].sort_values("period")
        
    if len(rev_df) >= 2:
        oldest_row = rev_df.iloc[0]
        latest_row = rev_df.iloc[-1]
        oldest_val = float(oldest_row["amount"])
        latest_val = float(latest_row["amount"])
        
        oldest_dt = pd.to_datetime(oldest_row["period"])
        latest_dt = pd.to_datetime(latest_row["period"])
        n_years = (latest_dt - oldest_dt).days / 365.25
        
        if n_years >= 0.5 and oldest_val > 0.0 and latest_val > 0.0:
            cagr = (latest_val / oldest_val) ** (1.0 / n_years) - 1.0
            revenue_cagr = max(-0.10, min(0.25, cagr))
            if revenue_cagr != cagr:
                warnings.append(f"Derived Revenue CAGR of {cagr*100:.1f}% was clamped to safe limits [-10.0%, 25.0%].")
        else:
            revenue_cagr = 0.05
            warnings.append("Revenue growth history insufficient or invalid; used 5.0% CAGR fallback.")
    else:
        revenue_cagr = 0.05
        warnings.append("Revenue CAGR not found in SEC facts; used 5.0% CAGR fallback.")

    # 5. COGS % of Revenue
    cogs = get_latest_val("COGS")
    if cogs is not None and revenue > 0.0:
        cogs_pct = cogs / revenue
        cogs_pct_revenue = max(0.05, min(0.95, cogs_pct))
        if cogs_pct_revenue != cogs_pct:
            warnings.append(f"Derived COGS % of revenue of {cogs_pct*100:.1f}% was clamped to safe limits [5.0%, 95.0%].")
    else:
        cogs_pct_revenue = 0.50
        warnings.append("COGS % of revenue not found in SEC facts; used 50.0% fallback.")

    # 6. SGA % of Revenue
    sga = get_latest_val("SGA")
    if sga is not None and revenue > 0.0:
        sga_pct = sga / revenue
        sga_pct_revenue = max(0.01, min(0.60, sga_pct))
        if sga_pct_revenue != sga_pct:
            warnings.append(f"Derived SG&A % of revenue of {sga_pct*100:.1f}% was clamped to safe limits [1.0%, 60.0%].")
    else:
        sga_pct_revenue = 0.15
        warnings.append("SG&A % of revenue not found in SEC facts; used 15.0% fallback.")

    # 7. Other OpEx % of Revenue (Research & Development fallback)
    rd = get_latest_val("R&D")
    if rd is not None and revenue > 0.0:
        other_opex_pct_revenue = rd / revenue
    else:
        other_opex_pct_revenue = 0.05
        warnings.append("Research & Development expense not found in SEC facts; used 5.0% other opex fallback.")

    # 8. Capex % of Revenue
    capex_val = get_latest_val("Capex")
    if capex_val is not None and revenue > 0.0:
        capex_pct = abs(capex_val) / revenue
        capex_pct_revenue = max(0.0, min(0.30, capex_pct))
        if capex_pct_revenue != capex_pct:
            warnings.append(f"Derived Capex % of revenue of {capex_pct*100:.1f}% was clamped to safe limits [0.0%, 30.0%].")
    else:
        capex_pct_revenue = 0.05
        warnings.append("Capex % of revenue not found in SEC facts; used 5.0% fallback.")

    # 9. Tax Rate Calculation
    tax_expense = get_latest_val("Tax Expense")
    ebit = get_latest_val("EBIT")
    interest_expense = get_latest_val("Interest Expense")
    net_income = get_latest_val("Net Income")
    
    ebt = None
    if ebit is not None and interest_expense is not None:
        ebt = ebit - interest_expense
    elif net_income is not None and tax_expense is not None:
        ebt = net_income + tax_expense
        
    if ebt is not None and tax_expense is not None and ebt > 0.0 and tax_expense > 0.0:
        derived_tax_rate = tax_expense / ebt
        tax_rate = max(0.00, min(0.35, derived_tax_rate))
        if tax_rate != derived_tax_rate:
            warnings.append(f"Derived Tax Rate of {derived_tax_rate*100:.1f}% was clamped to safe limits [0.0%, 35.0%].")
    else:
        tax_rate = 0.21
        warnings.append("Tax rate not found in SEC facts; used 21.0% fallback.")

    # Build the dictionary of base values
    base_values = {
        "base_year_revenue": revenue,
        "base_cash": cash,
        "base_ppe": ppe,
        "base_nwc": nwc,
        "base_common_stock": 0.0,
        "base_retained_earnings": retained_earnings,
        "base_intangibles": intangibles,
    }

    # Construct the complete pipeline-ready dashboard payload
    payload = {
        # Top-level root fields required by /api/run
        "company_name": snapshot.company_name,
        "ticker": snapshot.ticker,
        "base_year_revenue": revenue,
        "base_cash": cash,
        "base_ppe": ppe,
        "base_nwc": nwc,
        "base_common_stock": 0.0,
        "base_retained_earnings": retained_earnings,
        "base_intangibles": intangibles,
        
        # Forecast Config
        "forecast": {
            "projection_years": 5,
            "revenue_method": "cagr",
            "revenue_cagr": revenue_cagr,
            "revenue_yoy": [revenue_cagr] * 5,
            "revenue_manual": {},
            "cogs_pct_revenue": cogs_pct_revenue,
            "sga_pct_revenue": sga_pct_revenue,
            "other_opex_pct_revenue": other_opex_pct_revenue,
            "depreciation_rate": 0.10,
            "amortisation_pct_revenue": 0.005,
            "capex_method": "pct_revenue",
            "capex_pct_revenue": capex_pct_revenue,
            "capex_fixed": 0.0,
            "capex_manual": {},
            "dso": 45.0,
            "dio": 50.0,
            "dpo": 40.0,
            "prepaid_pct_revenue": 0.005,
            "accrued_pct_revenue": 0.01,
            "other_current_assets_pct_revenue": 0.005,
            "other_current_liabilities_pct_revenue": 0.005,
            "tax_rate": tax_rate,
            "dividend_payout_ratio": 0.0,
        },
        
        # WACC Config
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
            "use_live_data": False,
        },
        
        # Valuation Config
        "valuation": {
            "terminal_growth_rate": 0.025,
            "exit_ev_ebitda_multiple": 10.0,
            "discount_convention": "mid_year",
            "gordon_weight": 0.50,
            "cash": cash,
            "debt": debt,
            "minority_interest": 0.0,
            "preferred_stock": 0.0,
            "fully_diluted_shares": shares,
            "gdp_growth_cap": 0.035,
            "terminal_spread_floor_bps": 50.0,
        },
        
        # Monte Carlo Config
        "monte_carlo": {
            "iterations": 10000,
            "revenue_growth_mean": revenue_cagr,
            "revenue_growth_std": 0.03,
            "ebitda_margin_mean": max(0.01, 1.0 - cogs_pct_revenue - sga_pct_revenue - other_opex_pct_revenue),
            "ebitda_margin_std": 0.05,
            "wacc_mean": 0.10,
            "wacc_std": 0.02,
            "terminal_growth_mean": 0.025,
            "terminal_growth_std": 0.01,
            "exit_multiple_mean": 10.0,
            "exit_multiple_std": 2.0,
            "seed": 42,
        },
        
        # Sensitivity Config
        "sensitivity": {
            "wacc_range": [-0.02, -0.01, 0.0, 0.01, 0.02],
            "terminal_growth_range": [-0.01, -0.005, 0.0, 0.005, 0.01],
            "revenue_growth_range": [-0.03, -0.015, 0.0, 0.015, 0.03],
            "ebitda_margin_range": [-0.05, -0.025, 0.0, 0.025, 0.05],
        },
        
        "peer_tickers": [],
        "multiples": ["EV/Revenue", "EV/EBITDA", "P/E"],
        "debt_tranches": [],
        "scenarios": {
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
            }
        }
    }

    # Add all unique warnings from snapshot as well
    combined_warnings = list(snapshot.warnings)
    for w in warnings:
        if w not in combined_warnings:
            combined_warnings.append(w)

    return AssumptionBuildResult(
        payload=payload,
        base_values=base_values,
        source_map=snapshot.facts,
        warnings=combined_warnings,
    )
