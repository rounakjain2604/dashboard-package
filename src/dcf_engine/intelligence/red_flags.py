"""
Red Flag Radar — Phase 7A (Numeric + Metadata)

Detects high-emotion filing risks from:
1. Numeric filing changes (revenue decline, FCF flip, debt surge, etc.)
2. SEC submission metadata (late filings, amendments, recent 8-K)

Does NOT parse full filing text (Phase 7B scope).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from src.dcf_engine.intelligence.models import RedFlag

logger = logging.getLogger(__name__)


# ── Numeric red flag rules ───────────────────────────────────────────

def _check_numeric_flags(filing_changes: list[dict]) -> list[dict]:
    """
    Detect red flags from numeric filing changes.

    Each filing change dict must have: account, percent_change, latest_value, prior_value.
    """
    flags = []

    for change in filing_changes:
        account = change.get("account", "")
        pct = change.get("percent_change")
        latest = change.get("latest_value")
        prior = change.get("prior_value")

        if pct is None:
            continue

        # 1. Revenue down > 20%
        if account == "Revenue" and pct < -0.20:
            flags.append(_make_flag(
                code="revenue_decline_severe",
                severity="high",
                title="Revenue declined more than 20%",
                detail=f"Revenue fell {abs(pct):.1%} versus prior year. Review revenue base and growth assumptions.",
                source_type="xbrl",
                affected=["base_year_revenue", "forecast.revenue_cagr"],
            ))

        # 2. FCF turned negative
        if account == "FCF" and prior is not None and latest is not None:
            if prior > 0 and latest < 0:
                flags.append(_make_flag(
                    code="fcf_turned_negative",
                    severity="high",
                    title="Free cash flow turned negative",
                    detail="FCF was positive in the prior period and is now negative. Review FCF base and terminal value reliability.",
                    source_type="xbrl",
                    affected=["forecast.capex_pct_revenue", "valuation.terminal_growth_rate"],
                ))

        # 3. Debt up > 30%
        if account == "Total Debt" and pct > 0.30:
            flags.append(_make_flag(
                code="debt_surge",
                severity="high",
                title="Debt increased more than 30%",
                detail=f"Total debt increased {pct:.1%}. Review debt bridge, interest expense, and WACC capital structure.",
                source_type="xbrl",
                affected=["valuation.debt", "wacc.target_debt_weight", "wacc.interest_coverage_ratio"],
            ))

        # 4. Shares up > 5%
        if account == "Diluted Shares" and pct > 0.05:
            flags.append(_make_flag(
                code="dilution_high",
                severity="high",
                title="Diluted shares increased more than 5%",
                detail=f"Diluted shares increased {pct:.1%}. Review dilution and per-share valuation.",
                source_type="xbrl",
                affected=["valuation.fully_diluted_shares"],
            ))

        # 5. Cash down > 30%
        if account == "Cash" and pct < -0.30:
            flags.append(_make_flag(
                code="cash_decline_severe",
                severity="high",
                title="Cash declined more than 30%",
                detail=f"Cash declined {abs(pct):.1%}. Review equity bridge cash and liquidity cushion.",
                source_type="xbrl",
                affected=["valuation.cash"],
            ))

        # 6. Net income positive → negative
        if account == "Net Income" and prior is not None and latest is not None:
            if prior > 0 and latest < 0:
                flags.append(_make_flag(
                    code="income_turned_negative",
                    severity="high",
                    title="Net income turned negative",
                    detail="Net income was positive in the prior period and is now negative. Review profitability assumptions.",
                    source_type="xbrl",
                    affected=["forecast.cogs_pct_revenue", "forecast.sga_pct_revenue", "forecast.tax_rate"],
                ))

    return flags


# ── Metadata red flag rules ──────────────────────────────────────────

def _check_metadata_flags(
    submissions: dict | None,
    as_of_date: date | None = None,
) -> list[dict]:
    """
    Detect red flags from SEC submissions metadata.

    Checks for:
    - Late filing forms (NT 10-K, NT 10-Q)
    - Amendments (10-K/A, 10-Q/A)
    - Recent 8-K filings (within 30 days of as_of_date)

    Uses as_of_date for deterministic recency checks (defaults to today).
    """
    if submissions is None:
        return []

    ref_date = as_of_date or date.today()
    flags = []

    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        # Try top-level for simpler structures
        recent = submissions

    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])

    if not forms:
        return []

    late_forms = {"NT 10-K", "NT 10-Q"}
    amendment_forms = {"10-K/A", "10-Q/A"}
    recent_8k_cutoff = ref_date - timedelta(days=30)

    seen_late = False
    seen_amendment = False
    recent_8k_count = 0

    for i, form in enumerate(forms):
        filed_str = filing_dates[i] if i < len(filing_dates) else None

        if form in late_forms and not seen_late:
            seen_late = True
            flags.append(_make_flag(
                code="late_filing",
                severity="high",
                title=f"Late filing detected: {form}",
                detail=f"A {form} form was filed, indicating the company missed its filing deadline. This may indicate operational or accounting difficulties.",
                source_type="metadata",
                affected=["base_year_revenue", "forecast.revenue_cagr"],
            ))

        if form in amendment_forms and not seen_amendment:
            seen_amendment = True
            flags.append(_make_flag(
                code="filing_amendment",
                severity="medium",
                title=f"Filing amendment detected: {form}",
                detail=f"A {form} form was filed, indicating a correction or update to a prior filing. Review affected financial line items.",
                source_type="metadata",
                affected=[],
            ))

        if form == "8-K" and filed_str:
            try:
                filed_date = date.fromisoformat(filed_str)
                if filed_date >= recent_8k_cutoff:
                    recent_8k_count += 1
            except (ValueError, TypeError):
                pass

    if recent_8k_count > 0:
        flags.append(_make_flag(
            code="recent_8k",
            severity="medium",
            title=f"{recent_8k_count} 8-K filing(s) in the last 30 days",
            detail=f"{recent_8k_count} current-report (8-K) filing(s) detected within 30 days of {ref_date.isoformat()}. Review for material events.",
            source_type="metadata",
            affected=[],
        ))

    return flags


# ── Helper ───────────────────────────────────────────────────────────

def _make_flag(
    code: str,
    severity: str,
    title: str,
    detail: str,
    source_type: str,
    affected: list[str],
    source_url: str | None = None,
) -> dict:
    """Create a RedFlag as a dict."""
    flag = RedFlag(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        source_type=source_type,
        affected_assumptions=affected if affected else None,
        source_url=source_url,
    )
    from dataclasses import asdict
    return asdict(flag)


# ── Main function ────────────────────────────────────────────────────

def detect_red_flags(
    snapshot,
    filing_changes: list[dict],
    submissions: dict | None = None,
    as_of_date: date | None = None,
) -> list[dict]:
    """
    Detect red flags from numeric filing changes and SEC submissions metadata.

    Args:
        snapshot: CompanySnapshot (used for ticker context, not directly queried)
        filing_changes: list of FilingChange dicts from detect_filing_changes
        submissions: raw SEC submissions JSON, or None to skip metadata checks
        as_of_date: reference date for recency checks (defaults to today)

    Returns:
        list of RedFlag dicts. If submissions is None, only numeric red flags
        are returned — metadata flags are not claimed to have been checked.

    NOTE: This is Phase 7A — numeric and metadata only. Full filing text
    keyword scanning (going concern, material weakness, etc.) is Phase 7B scope.
    """
    flags = []

    # Numeric red flags
    flags.extend(_check_numeric_flags(filing_changes))

    # Metadata red flags (only if submissions data was provided)
    if submissions is not None:
        flags.extend(_check_metadata_flags(submissions, as_of_date))

    return flags
