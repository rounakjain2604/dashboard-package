"""
Numeric Filing Change Detector — Phase 6

Compares the latest annual filing period against the prior period
for key financial accounts. Classifies severity and valuation impact
using deterministic rules.

Only XBRL numeric changes. No text comparison.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from src.dcf_engine.intelligence.models import CompanySnapshot, FilingChange

logger = logging.getLogger(__name__)


# ── Change classification rules ──────────────────────────────────────

def _classify_revenue(pct_change: float) -> tuple[str, str]:
    """Classify revenue percent change -> (severity, impact)."""
    abspct = abs(pct_change)
    if abspct < 0.05:
        return "low", "Revenue change is modest; review revenue growth base and forecast CAGR."
    elif abspct < 0.15:
        return "medium", "Revenue changed materially; review base-year revenue and forecast CAGR."
    else:
        return "high", "Revenue changed significantly; review revenue growth base and forecast CAGR."


def _classify_margin_bps(bps_change: float) -> tuple[str, str]:
    """Classify margin change in basis points -> (severity, impact)."""
    absbps = abs(bps_change)
    if absbps < 100:
        return "low", "Margin shift is minor; no immediate assumption changes likely needed."
    elif absbps < 300:
        return "medium", "Margin shifted materially; review margin assumptions."
    else:
        return "high", "Margin shifted significantly; review margin assumptions."


def _classify_debt(pct_change: float) -> tuple[str, str]:
    abspct = abs(pct_change)
    if abspct < 0.10:
        return "low", "Debt change is modest; monitor debt bridge and WACC assumptions."
    elif abspct < 0.30:
        return "medium", "Debt changed materially; review debt bridge, interest burden, and WACC assumptions."
    else:
        return "high", "Debt changed significantly; review debt bridge, interest burden, and WACC assumptions."


def _classify_cash(pct_change: float) -> tuple[str, str]:
    if pct_change < -0.30:
        return "high", "Cash declined substantially; review equity bridge cash and liquidity cushion."
    elif pct_change < -0.15:
        return "medium", "Cash declined; review equity bridge cash and liquidity cushion."
    else:
        return "low", "Cash change is modest."


def _classify_shares(pct_change: float) -> tuple[str, str]:
    abspct = abs(pct_change)
    if abspct < 0.01:
        return "low", "Share count change is minimal."
    elif abspct < 0.03:
        return "medium", "Share count changed; review dilution and per-share valuation."
    else:
        return "high", "Share count changed significantly; review dilution and per-share valuation."


def _classify_capex_ratio(bps_change: float) -> tuple[str, str]:
    absbps = abs(bps_change)
    if absbps < 200:
        return "low", "Capex-to-revenue ratio is stable."
    elif absbps < 500:
        return "medium", "Capex ratio shifted; review reinvestment assumptions and FCF conversion."
    else:
        return "high", "Capex ratio changed significantly; review reinvestment assumptions and FCF conversion."


def _classify_fcf(latest: float | None, prior: float | None, pct: float) -> tuple[str, str]:
    if prior is not None and latest is not None:
        if prior > 0 and latest < 0:
            return "high", "FCF turned negative; review FCF base and terminal value reliability."
        if prior < 0 and latest > 0:
            return "medium", "FCF turned positive; review FCF base and terminal value reliability."
    abspct = abs(pct)
    if abspct > 0.30:
        return "high" if pct < 0 else "medium", "FCF changed materially; review FCF base and terminal value reliability."
    elif abspct > 0.15:
        return "medium", "FCF changed; review FCF base and terminal value reliability."
    return "low", "FCF change is modest."


def _classify_generic(pct_change: float) -> tuple[str, str]:
    abspct = abs(pct_change)
    if abspct < 0.05:
        return "low", "Change is modest."
    elif abspct < 0.15:
        return "medium", "Changed materially; review related assumptions."
    else:
        return "high", "Changed significantly; review related assumptions."


# ── Source fact extraction helpers ────────────────────────────────────

def _find_fact_dict(snapshot: CompanySnapshot, account: str, period: str) -> dict | None:
    """Find a SourceFact dict for a single-source account at a given period."""
    for f in snapshot.facts:
        if f.account == account and f.period_end == period:
            return {
                "account": f.account,
                "concept": f.concept,
                "value": f.value,
                "unit": f.unit,
                "form": f.form,
                "filed": f.filed,
                "period_end": f.period_end,
                "accession": f.accession,
                "source_url": f.source_url,
            }
    return None


def _build_source_components(
    snapshot: CompanySnapshot,
    accounts: list[str],
    period: str,
) -> list[dict]:
    """Build source_components list for composite metrics."""
    components = []
    for acct in accounts:
        fact = _find_fact_dict(snapshot, acct, period)
        if fact:
            components.append(fact)
    return components


# ── Period-level metric extraction ───────────────────────────────────

def _get_period_value(df, account: str, period_str: str) -> float | None:
    """Get an account value at a specific period from the financials DataFrame."""
    match = df[(df["account"] == account) & (df["period"] == period_str)]
    if not match.empty:
        return float(match.iloc[0]["amount"])
    return None


def _compute_period_metrics(df, period_str: str) -> dict:
    """Compute all tracked metrics for a single period."""
    revenue = _get_period_value(df, "Revenue", period_str)
    cogs = _get_period_value(df, "COGS", period_str)
    ebit = _get_period_value(df, "EBIT", period_str)
    net_income = _get_period_value(df, "Net Income", period_str)
    cfo = _get_period_value(df, "CFO", period_str)
    capex_raw = _get_period_value(df, "Capex", period_str)
    capex = abs(capex_raw) if capex_raw is not None else None
    cash = _get_period_value(df, "Cash", period_str)
    lt_debt = _get_period_value(df, "Long-Term Debt", period_str)
    st_debt = _get_period_value(df, "Short-Term Debt", period_str)
    shares = (
        _get_period_value(df, "Shares Diluted", period_str)
        or _get_period_value(df, "Shares Outstanding", period_str)
        or _get_period_value(df, "Shares Outstanding (BS)", period_str)
    )
    ppe = _get_period_value(df, "PP&E Net", period_str)
    ar = _get_period_value(df, "Accounts Receivable", period_str)
    inv = _get_period_value(df, "Inventory", period_str)
    ap = _get_period_value(df, "Accounts Payable", period_str)

    # Derived metrics
    gross_margin = None
    if revenue and revenue != 0 and cogs is not None:
        gross_margin = (revenue - cogs) / revenue

    operating_margin = None
    if revenue and revenue != 0 and ebit is not None:
        operating_margin = ebit / revenue

    debt = None
    if lt_debt is not None or st_debt is not None:
        debt = (lt_debt or 0.0) + (st_debt or 0.0)

    fcf = None
    if cfo is not None and capex is not None:
        fcf = cfo - capex

    nwc = None
    if ar is not None and inv is not None and ap is not None:
        nwc = ar + inv - ap

    capex_pct = None
    if capex is not None and revenue and revenue != 0:
        capex_pct = capex / revenue

    return {
        "revenue": revenue,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "net_income": net_income,
        "cfo": cfo,
        "capex": capex,
        "fcf": fcf,
        "cash": cash,
        "debt": debt,
        "shares": shares,
        "ppe": ppe,
        "nwc": nwc,
        "capex_pct_revenue": capex_pct,
    }


# ── Tracked metric definitions ───────────────────────────────────────

# Each entry: (metric_key, category, display_account, is_composite, component_accounts, classifier_fn, is_bps)
TRACKED_METRICS = [
    ("revenue", "revenue", "Revenue", False, ["Revenue"], _classify_revenue, False),
    ("gross_margin", "margin", "Gross Margin", True, ["Revenue", "COGS"], None, True),
    ("operating_margin", "margin", "Operating Margin", True, ["Revenue", "EBIT"], None, True),
    ("net_income", "earnings", "Net Income", False, ["Net Income"], _classify_generic, False),
    ("cfo", "cash_flow", "CFO", False, ["CFO"], _classify_generic, False),
    ("capex", "capex", "Capex", False, ["Capex"], _classify_generic, False),
    ("fcf", "cash_flow", "FCF", True, ["CFO", "Capex"], None, False),
    ("cash", "cash", "Cash", False, ["Cash"], _classify_cash, False),
    ("debt", "debt", "Total Debt", True, ["Long-Term Debt", "Short-Term Debt"], _classify_debt, False),
    ("shares", "shares", "Diluted Shares", False, ["Shares Diluted"], _classify_shares, False),
    ("ppe", "assets", "PP&E Net", False, ["PP&E Net"], _classify_generic, False),
    ("nwc", "working_capital", "NWC", True, ["Accounts Receivable", "Inventory", "Accounts Payable"], _classify_generic, False),
    ("capex_pct_revenue", "capex", "Capex % Revenue", True, ["Capex", "Revenue"], None, True),
]


# ── Main function ────────────────────────────────────────────────────

def detect_filing_changes(snapshot: CompanySnapshot) -> dict:
    """
    Compare the latest annual filing period against the prior period
    and classify what changed.

    Returns dict with:
      ticker, latest_period, prior_period, numeric_changes (list of FilingChange dicts),
      warnings
    """
    warnings = list(snapshot.warnings)  # preserve snapshot warnings
    ticker = snapshot.ticker
    df = snapshot.financials

    if df is None or df.empty:
        return {
            "ticker": ticker,
            "latest_period": None,
            "prior_period": None,
            "numeric_changes": [],
            "warnings": warnings + ["No financial data available for filing change detection."],
        }

    # Get unique periods sorted descending
    import pandas as pd
    periods = sorted(df["period"].dropna().unique(), reverse=True)

    if len(periods) < 2:
        return {
            "ticker": ticker,
            "latest_period": periods[0] if periods else None,
            "prior_period": None,
            "numeric_changes": [],
            "warnings": warnings + ["Only one period available; cannot compare filing changes."],
        }

    latest_period = periods[0]
    prior_period = periods[1]

    latest_metrics = _compute_period_metrics(df, latest_period)
    prior_metrics = _compute_period_metrics(df, prior_period)

    changes = []

    for metric_key, category, display_name, is_composite, component_accounts, classifier_fn, is_bps in TRACKED_METRICS:
        latest_val = latest_metrics.get(metric_key)
        prior_val = prior_metrics.get(metric_key)

        if latest_val is None or prior_val is None:
            continue

        abs_change = latest_val - prior_val

        # Compute percent change
        if prior_val != 0:
            pct_change = abs_change / abs(prior_val)
        else:
            pct_change = None

        # Classify severity
        if is_bps:
            # Margin and ratio changes in basis points
            bps_change = abs_change * 10000
            if metric_key == "gross_margin" or metric_key == "operating_margin":
                severity, impact = _classify_margin_bps(bps_change)
            elif metric_key == "capex_pct_revenue":
                severity, impact = _classify_capex_ratio(bps_change)
            else:
                severity, impact = "low", "Change is modest."
        elif metric_key == "fcf":
            severity, impact = _classify_fcf(latest_val, prior_val, pct_change or 0)
        elif classifier_fn and pct_change is not None:
            severity, impact = classifier_fn(pct_change)
        else:
            severity, impact = "low", "Change is modest."

        # Source handling: single vs composite
        if is_composite:
            source_fact_latest = None
            source_fact_prior = None
            source_components = (
                _build_source_components(snapshot, component_accounts, latest_period)
                + _build_source_components(snapshot, component_accounts, prior_period)
            )
            if not source_components:
                source_components = None
        else:
            primary_account = component_accounts[0] if component_accounts else display_name
            source_fact_latest = _find_fact_dict(snapshot, primary_account, latest_period)
            source_fact_prior = _find_fact_dict(snapshot, primary_account, prior_period)
            source_components = None

        change = FilingChange(
            category=category,
            account=display_name,
            latest_value=latest_val,
            prior_value=prior_val,
            absolute_change=abs_change,
            percent_change=round(pct_change, 6) if pct_change is not None else None,
            severity=severity,
            valuation_impact=impact,
            source_fact_latest=source_fact_latest,
            source_fact_prior=source_fact_prior,
            source_components=source_components,
        )
        changes.append(asdict(change))

    return {
        "ticker": ticker,
        "latest_period": latest_period,
        "prior_period": prior_period,
        "numeric_changes": changes,
        "warnings": warnings,
    }
