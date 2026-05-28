from __future__ import annotations
import pandas as pd
import logging
from src.dcf_engine.ingestion.edgar_client import EdgarClient, PRIORITY_CONCEPTS, XBRL_CONCEPT_MAP
from src.dcf_engine.intelligence.models import SourceFact, CompanySnapshot
from src.dcf_engine.intelligence.source_map import make_source_url

logger = logging.getLogger(__name__)

def fetch_company_snapshot(ticker: str, years: int = 5) -> CompanySnapshot:
    """
    Fetch company facts from SEC EDGAR, preserve all source metadata,
    and build a clean, deduplicated CompanySnapshot.
    """
    client = EdgarClient()
    ticker = ticker.upper()
    
    # Resolve ticker to CIK
    cik = client.ticker_to_cik(ticker)
    if not cik:
        if ticker.isdigit() and len(ticker) <= 10:
            cik = ticker.zfill(10)
        else:
            raise ValueError(f"Could not resolve ticker '{ticker}' to CIK")
            
    cik_padded = cik.zfill(10)
    
    # Retrieve the company facts endpoint
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    data = client._get(url)
    if data is None:
        return CompanySnapshot(
            ticker=ticker,
            cik=cik_padded,
            company_name="Unknown",
            latest_period=None,
            financials=pd.DataFrame(),
            facts=[],
            key_metrics={},
            warnings=[f"Failed to fetch SEC facts for {ticker} (CIK: {cik_padded})"]
        )
        
    company_name = data.get("entityName", "Unknown")
    us_gaap = data.get("facts", {}).get("us-gaap", {})
    
    source_facts_raw = []
    
    for concept in PRIORITY_CONCEPTS:
        friendly = XBRL_CONCEPT_MAP.get(concept, concept)
        concept_data = us_gaap.get(concept)
        if concept_data is None:
            continue
            
        units = concept_data.get("units", {})
        # Prefer USD, then shares, then pure
        unit_name = None
        unit_data = None
        for u in ("USD", "shares", "USD/shares", "pure"):
            if u in units:
                unit_name = u
                unit_data = units[u]
                break
                
        if not unit_data:
            continue
            
        for fact in unit_data:
            form = fact.get("form", "")
            if form not in ("10-K", "10-K/A"):
                continue
            if fact.get("frame") is None and fact.get("end") is None:
                continue
                
            end_date = fact.get("end")
            if end_date is None:
                continue
                
            start_date = fact.get("start")
            is_instant = start_date is None
            
            source_facts_raw.append({
                "period": end_date,
                "account": friendly,
                "amount": float(fact.get("val", 0)),
                "concept": concept,
                "is_instant": is_instant,
                "form": form,
                "filed": fact.get("filed", ""),
                "unit": unit_name,
                "fy": fact.get("fy"),
                "fp": fact.get("fp"),
                "accn": fact.get("accn"),
                "frame": fact.get("frame")
            })
            
    if not source_facts_raw:
        return CompanySnapshot(
            ticker=ticker,
            cik=cik_padded,
            company_name=company_name,
            latest_period=None,
            financials=pd.DataFrame(),
            facts=[],
            key_metrics={},
            warnings=["No parseable XBRL facts found"]
        )
        
    df_all = pd.DataFrame(source_facts_raw)
    df_all["period_dt"] = pd.to_datetime(df_all["period"], errors="coerce")
    
    # Keep only the most recent N unique periods
    unique_periods = sorted(df_all["period_dt"].dropna().unique(), reverse=True)
    cutoff_periods = unique_periods[:years]
    df_filtered = df_all[df_all["period_dt"].isin(cutoff_periods)].copy()
    
    # Deduplicate: for the same (period_dt, account), keep the latest filing
    df_filtered = df_filtered.sort_values("filed", ascending=False)
    df_dedup = df_filtered.drop_duplicates(subset=["period_dt", "account"], keep="first").copy()
    
    # Statement mapping helper
    is_items = {"Revenue", "COGS", "SGA", "R&D", "D&A", "Depreciation",
                "EBIT", "Interest Expense", "Tax Expense", "Net Income",
                "EPS Basic", "EPS Diluted"}
    bs_items = {"Total Assets", "Current Assets", "Cash", "Accounts Receivable",
                "Inventory", "Prepaid & Other Current", "PP&E Net",
                "Goodwill", "Intangibles", "Total Liabilities", "Current Liabilities",
                "Accounts Payable", "Accrued Liabilities", "Long-Term Debt",
                "Short-Term Debt", "Total Equity", "Retained Earnings",
                "Shares Outstanding (BS)"}
    cf_items = {"CFO", "Capex", "CFI", "CFF"}

    def _stmt(acct: str) -> str:
        if acct in is_items:
            return "IS"
        if acct in bs_items:
            return "BS"
        if acct in cf_items:
            return "CF"
        return "IS"
        
    df_dedup["statement"] = df_dedup["account"].apply(_stmt)
    
    # Sort and format the financials DataFrame
    df_dedup_sorted = df_dedup.sort_values(["period_dt", "statement", "account"]).reset_index(drop=True)
    
    # Keep period as string representation to keep API responses simple
    df_financials = df_dedup_sorted[["period", "account", "amount", "statement"]].copy()
    
    # Build list of SourceFacts
    facts = []
    for _, row in df_dedup_sorted.iterrows():
        accn = row.get("accn")
        source_url = make_source_url(cik_padded, accn)
        
        fy_val = row.get("fy")
        fy_str = str(int(fy_val)) if fy_val is not None and not pd.isna(fy_val) else None
        
        sf = SourceFact(
            ticker=ticker,
            cik=cik_padded,
            company_name=company_name,
            account=row["account"],
            concept=row["concept"],
            value=row["amount"],
            unit=row["unit"],
            form=row["form"],
            filed=row["filed"],
            period_end=row["period"],
            fiscal_year=fy_str,
            fiscal_period=row.get("fp"),
            accession=accn,
            frame=row.get("frame"),
            source_url=source_url
        )
        facts.append(sf)
        
    # Build key metrics from the latest period
    latest_period = None
    key_metrics = {}
    warnings = []
    
    if unique_periods:
        latest_period_dt = unique_periods[0]
        latest_period = latest_period_dt.strftime("%Y-%m-%d")
        
        latest_rows = df_dedup_sorted[df_dedup_sorted["period_dt"] == latest_period_dt]
        
        def get_val(acct: str) -> float | None:
            match = latest_rows[latest_rows["account"] == acct]
            if not match.empty:
                return float(match.iloc[0]["amount"])
            return None
            
        revenue = get_val("Revenue")
        cogs = get_val("COGS")
        gross_profit = (revenue - cogs) if revenue is not None and cogs is not None else None
        gross_margin = (gross_profit / revenue) if gross_profit is not None and revenue else None
        
        ebit = get_val("EBIT")
        operating_margin = (ebit / revenue) if ebit is not None and revenue else None
        
        net_income = get_val("Net Income")
        cash = get_val("Cash")
        
        lt_debt = get_val("Long-Term Debt")
        st_debt = get_val("Short-Term Debt")
        if lt_debt is not None or st_debt is not None:
            debt = (lt_debt or 0.0) + (st_debt or 0.0)
        else:
            debt = None
            
        shares = get_val("Shares Diluted") or get_val("Shares Outstanding") or get_val("Shares Outstanding (BS)")
        
        capex_val = get_val("Capex")
        capex = abs(capex_val) if capex_val is not None else None
        cfo = get_val("CFO")
        fcf = (cfo - capex) if cfo is not None and capex is not None else None
        
        ppe = get_val("PP&E Net")
        ar = get_val("Accounts Receivable")
        inv = get_val("Inventory")
        ap = get_val("Accounts Payable")
        if ar is not None and inv is not None and ap is not None:
            nwc = ar + inv - ap
        else:
            nwc = None
        
        # Check and append missing warnings
        if revenue is None:
            warnings.append("Missing priority concept: Revenue")
        if gross_margin is None:
            warnings.append("Missing priority concept: Gross Margin")
        if operating_margin is None:
            warnings.append("Missing priority concept: Operating Margin")
        if net_income is None:
            warnings.append("Missing priority concept: Net Income")
        if cash is None:
            warnings.append("Missing priority concept: Cash")
        if debt is None:
            warnings.append("Missing priority concept: Debt")
        if shares is None:
            warnings.append("Missing priority concept: Shares")
        if capex is None:
            warnings.append("Missing priority concept: Capex")
        if cfo is None:
            warnings.append("Missing priority concept: CFO")
        if fcf is None:
            warnings.append("Missing priority concept: FCF")
        if ppe is None:
            warnings.append("Missing priority concept: PP&E Net")
        if nwc is None:
            warnings.append("Missing priority concept: NWC")
            
        key_metrics = {
            "revenue": revenue,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "net_income": net_income,
            "cash": cash,
            "debt": debt,
            "shares": shares,
            "capex": capex,
            "cfo": cfo,
            "fcf": fcf,
            "ppe": ppe,
            "nwc": nwc
        }
    else:
        warnings.append("No financial data found for any period")
        
    return CompanySnapshot(
        ticker=ticker,
        cik=cik_padded,
        company_name=company_name,
        latest_period=latest_period,
        financials=df_financials,
        facts=facts,
        key_metrics=key_metrics,
        warnings=warnings
    )
