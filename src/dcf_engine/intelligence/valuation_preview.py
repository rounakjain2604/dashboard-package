from __future__ import annotations
import math
import logging
import pandas as pd
import numpy as np

from src.dcf_engine.intelligence.sec_snapshot import fetch_company_snapshot
from src.dcf_engine.intelligence.assumption_builder import build_assumptions_from_snapshot

logger = logging.getLogger(__name__)


def _try_get_market_price(ticker: str) -> float | None:
    """Attempt to fetch current market price via yfinance. Returns None if unavailable."""
    try:
        from src.dcf_engine.ingestion.market_data import fetch_company_snapshot as fetch_market_snapshot
        snap = fetch_market_snapshot(ticker)
        if snap and snap.current_price:
            return float(snap.current_price)
    except Exception:
        pass
    return None


def _compute_reverse_dcf(payload: dict, ticker: str) -> dict:
    """Attempt reverse DCF using lightweight solver. Gracefully degrades."""
    try:
        from src.dcf_engine.intelligence.reverse_dcf import solve_implied_metrics
        target_price = _try_get_market_price(ticker)
        return solve_implied_metrics(payload, target_price=target_price)
    except Exception as exc:
        logger.warning("Reverse DCF failed for %s: %s", ticker, exc)
        return {"warnings": [f"Reverse DCF computation failed: {exc}"]}


def _compute_filing_analysis(snapshot) -> dict:
    """Compute filing changes + valuation impacts from a snapshot. Returns empty if < 2 periods."""
    try:
        from src.dcf_engine.intelligence.filing_changes import detect_filing_changes
        from src.dcf_engine.intelligence.red_flags import detect_red_flags
        from src.dcf_engine.intelligence.valuation_impacts import build_valuation_impacts
        from src.dcf_engine.ingestion.edgar_client import EdgarClient

        change_result = detect_filing_changes(snapshot)
        numeric_changes = change_result.get("numeric_changes", [])

        submissions = None
        metadata_checked = False
        warnings = []

        if snapshot.cik:
            try:
                client = EdgarClient()
                submissions = client.fetch_submissions(snapshot.cik)
                if submissions is not None:
                    metadata_checked = True
                else:
                    warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")
            except Exception as e:
                logger.warning("Submissions fetch failed for CIK %s: %s", snapshot.cik, e)
                warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")
        else:
            warnings.append("SEC submissions metadata unavailable; metadata red flags were not checked.")

        if not numeric_changes:
            if change_result.get("prior_period") is None:
                warnings.append("Fewer than two filing periods available; numeric filing changes were not computed.")

        red_flags = detect_red_flags(
            snapshot=snapshot,
            filing_changes=numeric_changes,
            submissions=submissions
        )
        impacts = build_valuation_impacts(numeric_changes, red_flags)
        return {
            "valuation_impacts": impacts,
            "warnings": warnings,
            "metadata_checked": metadata_checked
        }
    except Exception as exc:
        logger.warning("Filing analysis failed: %s", exc)
        return {
            "valuation_impacts": [],
            "warnings": [f"Filing analysis failed: {exc}"],
            "metadata_checked": False
        }

# Strictly whitelisted keys for safe overrides
WHITELISTED_KEYS = {
    "forecast.revenue_cagr",
    "forecast.cogs_pct_revenue",
    "forecast.sga_pct_revenue",
    "forecast.other_opex_pct_revenue",
    "forecast.capex_pct_revenue",
    "forecast.tax_rate",
    "valuation.terminal_growth_rate",
    "valuation.exit_ev_ebitda_multiple",
    "wacc.risk_free_rate",
    "wacc.equity_risk_premium",
    "wacc.beta",
    "wacc.size_premium",
    "wacc.country_risk_premium",
    "wacc.target_debt_weight",
    "wacc.target_equity_weight",
    "wacc.interest_coverage_ratio",
    "wacc.tax_rate",
}

def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Helper to flatten a nested dictionary into a flat dictionary of dotted keys."""
    flat = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten_dict(v, key))
        else:
            flat[key] = v
    return flat

def build_valuation_preview(ticker: str, years: int = 5, overrides: dict | None = None) -> dict:
    """
    Service function that fetches a snapshot, builds pipeline-ready assumptions,
    applies strictly validated whitelisted overrides, runs the valuation pipeline,
    and returns a compact valuation summary dictionary.
    """
    # 1. Validate overrides container type
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError("overrides parameter must be a dictionary")

    ticker = ticker.strip().upper()
    override_warnings = []
    
    # 2. Fetch company snapshot and build initial assumptions
    snapshot = fetch_company_snapshot(ticker=ticker, years=years)
    result = build_assumptions_from_snapshot(snapshot)
    payload = result.payload

    # Prevent fallback to sample CSV by explicitly setting data_file to an empty/non-existent path inside the data directory
    payload["data_file"] = "data/nonexistent_sec_preview_file.csv"
    
    # 3. Process and apply safe whitelisted overrides
    if overrides:
        flat_overrides = _flatten_dict(overrides)
        for key, val in flat_overrides.items():
            if key not in WHITELISTED_KEYS:
                override_warnings.append(f"Override '{key}' is not allowed and was ignored.")
                continue
                
            # Value checks: must be numeric, not boolean, not NaN/Inf
            if isinstance(val, bool) or not isinstance(val, (int, float, np.integer, np.floating)):
                override_warnings.append(f"Override '{key}' has invalid non-numeric value '{val}' and was ignored.")
                continue
                
            f_val = float(val)
            if math.isnan(f_val) or math.isinf(f_val):
                override_warnings.append(f"Override '{key}' has invalid value '{val}' (NaN/Inf) and was ignored.")
                continue
                
            # Range check for weights
            if key in ("wacc.target_debt_weight", "wacc.target_equity_weight"):
                if f_val < 0.0 or f_val > 1.0:
                    override_warnings.append(f"Override '{key}' value {val} is outside allowed range [0.0, 1.0] and was ignored.")
                    continue
                    
            # Range check for rates and other non-negative fields
            non_negative_keys = (
                "wacc.risk_free_rate",
                "wacc.equity_risk_premium",
                "wacc.beta",
                "wacc.size_premium",
                "wacc.country_risk_premium",
                "wacc.interest_coverage_ratio",
                "wacc.tax_rate",
                "forecast.tax_rate",
                "forecast.cogs_pct_revenue",
                "forecast.sga_pct_revenue",
                "forecast.other_opex_pct_revenue",
                "forecast.capex_pct_revenue",
            )
            if key in non_negative_keys:
                if f_val < 0.0:
                    override_warnings.append(f"Override '{key}' value {val} cannot be negative and was ignored.")
                    continue
            
            # Apply the override
            category, field = key.split(".", 1)
            payload[category][field] = f_val
            
            # Update dependent assumptions
            if key == "forecast.revenue_cagr":
                payload["forecast"]["revenue_yoy"] = [f_val] * 5

    # Serialize source map facts to clean dictionary records
    source_map_serialized = []
    for f in result.source_map:
        source_map_serialized.append({
            "ticker": f.ticker,
            "cik": f.cik,
            "company_name": f.company_name,
            "account": f.account,
            "concept": f.concept,
            "value": f.value,
            "unit": f.unit,
            "form": f.form,
            "filed": f.filed,
            "period_end": f.period_end,
            "fiscal_year": f.fiscal_year,
            "fiscal_period": f.fiscal_period,
            "accession": f.accession,
            "frame": f.frame,
            "source_url": f.source_url
        })

    # Combine warnings
    all_warnings = []
    for w in result.warnings:
        if w not in all_warnings:
            all_warnings.append(w)
    for w in override_warnings:
        if w not in all_warnings:
            all_warnings.append(w)

    cogs_pct = float(payload["forecast"]["cogs_pct_revenue"])
    sga_pct = float(payload["forecast"]["sga_pct_revenue"])
    other_opex_pct = float(payload["forecast"]["other_opex_pct_revenue"])
    ebitda_margin = 1.0 - cogs_pct - sga_pct - other_opex_pct

    # Compact key assumptions summary
    key_assumptions = {
        "revenue_cagr": float(payload["forecast"]["revenue_cagr"]),
        "cogs_pct_revenue": cogs_pct,
        "sga_pct_revenue": sga_pct,
        "other_opex_pct_revenue": other_opex_pct,
        "tax_rate": float(payload["forecast"]["tax_rate"]),
        "wacc": None,
        "beta": float(payload["wacc"]["beta"]),
        "risk_free_rate": float(payload["wacc"]["risk_free_rate"]),
        "equity_risk_premium": float(payload["wacc"]["equity_risk_premium"]),
        "terminal_growth_rate": float(payload["valuation"]["terminal_growth_rate"]),
        "exit_ev_ebitda_multiple": float(payload["valuation"]["exit_ev_ebitda_multiple"]),
        "fully_diluted_shares": float(payload["valuation"]["fully_diluted_shares"]),
    }

    # 4. Compute filing changes and valuation impacts from snapshot (if >= 2 periods)
    filing_change_result = _compute_filing_analysis(snapshot)
    valuation_impacts_list = filing_change_result.get("valuation_impacts", [])
    metadata_checked = filing_change_result.get("metadata_checked", False)
    filing_analysis_warnings = filing_change_result.get("warnings", [])
    for w in filing_analysis_warnings:
        if w not in all_warnings:
            all_warnings.append(w)

    # 5. If base_year_revenue is zero or missing, abort and return a clean failure/no-valuation result
    if float(payload.get("base_year_revenue", 0.0)) <= 0.0:
        all_warnings.append("Valuation preview aborted: SEC-derived base year revenue is missing or zero.")
        from src.dcf_engine.intelligence.assumption_qa import evaluate_assumption_quality
        qa_result = evaluate_assumption_quality(payload, all_warnings)
        
        return {
            "ticker": ticker,
            "blended_enterprise_value": None,
            "blended_equity_value": None,
            "implied_share_price": None,
            "wacc": None,
            "terminal_growth": float(payload["valuation"]["terminal_growth_rate"]),
            "exit_multiple": float(payload["valuation"]["exit_ev_ebitda_multiple"]),
            "revenue_cagr": float(payload["forecast"]["revenue_cagr"]),
            "ebitda_margin": ebitda_margin,
            "tv_pct_of_ev": None,
            "warnings": all_warnings,
            "source_map": source_map_serialized,
            "key_assumptions": key_assumptions,
            "assumption_quality": qa_result,
            "reverse_dcf": {"warnings": ["Reverse DCF not computed: missing base revenue."]},
            "valuation_impacts": valuation_impacts_list,
            "payload": payload,
            "metadata_checked": metadata_checked,
        }

    # 5. Dynamic import of _run_payload to avoid circular dependencies
    from dashboard_api import _run_payload

    # 6. Run the pipeline
    pipeline_result = _run_payload(payload)

    # 7. Extract metrics and handle missing data
    wacc_val = None
    if pipeline_result.wacc is not None:
        wacc_val = float(pipeline_result.wacc.wacc)
        key_assumptions["wacc"] = wacc_val

    blended_equity_value = None
    blended_enterprise_value = None
    implied_share_price = None
    tv_pct_of_ev = None

    if pipeline_result.dcf is not None:
        blended_equity_value = float(pipeline_result.dcf.equity_blended)
        blended_enterprise_value = float(pipeline_result.dcf.ev_blended)
        implied_share_price = float(pipeline_result.dcf.price_blended)
        tv_pct_of_ev = float(pipeline_result.dcf.tv_pct_of_ev)

    for err in pipeline_result.errors:
        if err not in all_warnings:
            all_warnings.append(err)

    # Compute assumption quality
    from src.dcf_engine.intelligence.assumption_qa import evaluate_assumption_quality
    qa_result = evaluate_assumption_quality(payload, all_warnings)

    # 8. Reverse DCF: attempt to fetch market price and solve implied metrics
    reverse_dcf_result = _compute_reverse_dcf(payload, ticker)

    return {
        "ticker": ticker,
        "blended_enterprise_value": blended_enterprise_value,
        "blended_equity_value": blended_equity_value,
        "implied_share_price": implied_share_price,
        "wacc": wacc_val,
        "terminal_growth": float(payload["valuation"]["terminal_growth_rate"]),
        "exit_multiple": float(payload["valuation"]["exit_ev_ebitda_multiple"]),
        "revenue_cagr": float(payload["forecast"]["revenue_cagr"]),
        "ebitda_margin": ebitda_margin,
        "tv_pct_of_ev": tv_pct_of_ev,
        "warnings": all_warnings,
        "source_map": source_map_serialized,
        "key_assumptions": key_assumptions,
        "assumption_quality": qa_result,
        "reverse_dcf": reverse_dcf_result,
        "valuation_impacts": valuation_impacts_list,
        "payload": payload,
        "metadata_checked": metadata_checked,
    }
