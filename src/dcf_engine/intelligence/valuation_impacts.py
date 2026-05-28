"""
Valuation Impact Scanner — Phase 8

Maps numeric filing changes and red flags into affected DCF assumptions
with actionable review guidance. Deterministic rule mapping only.

Does NOT provide investment advice. Uses neutral language:
"review", "changed", "may affect assumptions".
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ── Impact category mapping rules ────────────────────────────────────

# (change_account, change_category) -> impact template
_CHANGE_IMPACT_RULES: list[tuple[str, dict]] = [
    (
        "Revenue",
        {
            "category": "revenue_growth",
            "title_template": "Revenue base changed {direction}",
            "detail_template": "Revenue {verb} {pct}% versus prior year. Review base-year revenue and forecast CAGR.",
            "affected_assumptions": ["base_year_revenue", "forecast.revenue_cagr"],
            "min_severity": "medium",
        },
    ),
    (
        "Gross Margin",
        {
            "category": "margin",
            "title_template": "Gross margin shifted {direction}",
            "detail_template": "Gross margin changed {bps} basis points. Review COGS and margin assumptions.",
            "affected_assumptions": ["forecast.cogs_pct_revenue"],
            "min_severity": "medium",
        },
    ),
    (
        "Operating Margin",
        {
            "category": "margin",
            "title_template": "Operating margin shifted {direction}",
            "detail_template": "Operating margin changed {bps} basis points. Review SG&A and operating cost assumptions.",
            "affected_assumptions": ["forecast.cogs_pct_revenue", "forecast.sga_pct_revenue", "forecast.other_opex_pct_revenue"],
            "min_severity": "medium",
        },
    ),
    (
        "Total Debt",
        {
            "category": "debt_wacc",
            "title_template": "Debt burden {direction}",
            "detail_template": "Total debt {verb} {pct}%. Review debt bridge, interest expense, and WACC capital structure.",
            "affected_assumptions": ["valuation.debt", "wacc.target_debt_weight", "wacc.interest_coverage_ratio"],
            "min_severity": "medium",
        },
    ),
    (
        "Diluted Shares",
        {
            "category": "share_count",
            "title_template": "Dilution {direction}",
            "detail_template": "Diluted shares {verb} {pct}%. Review per-share valuation and share count assumptions.",
            "affected_assumptions": ["valuation.fully_diluted_shares"],
            "min_severity": "medium",
        },
    ),
    (
        "Capex",
        {
            "category": "capex",
            "title_template": "Capital expenditure changed {direction}",
            "detail_template": "Capex {verb} {pct}%. Review reinvestment assumptions and FCF conversion.",
            "affected_assumptions": ["forecast.capex_pct_revenue"],
            "min_severity": "medium",
        },
    ),
    (
        "Capex % Revenue",
        {
            "category": "capex",
            "title_template": "Capex-to-revenue ratio shifted {direction}",
            "detail_template": "Capex as percentage of revenue changed {bps} basis points. Review capex assumptions.",
            "affected_assumptions": ["forecast.capex_pct_revenue"],
            "min_severity": "medium",
        },
    ),
    (
        "FCF",
        {
            "category": "cash_flow",
            "title_template": "Free cash flow changed {direction}",
            "detail_template": "FCF {verb} {pct}%. Review FCF base and terminal value reliability.",
            "affected_assumptions": ["forecast.capex_pct_revenue", "valuation.terminal_growth_rate"],
            "min_severity": "medium",
        },
    ),
    (
        "Cash",
        {
            "category": "cash_flow",
            "title_template": "Cash position changed {direction}",
            "detail_template": "Cash {verb} {pct}%. Review equity bridge cash and liquidity assumptions.",
            "affected_assumptions": ["valuation.cash"],
            "min_severity": "medium",
        },
    ),
    (
        "Net Income",
        {
            "category": "margin",
            "title_template": "Net income changed {direction}",
            "detail_template": "Net income {verb} {pct}%. Review profitability and tax assumptions.",
            "affected_assumptions": ["forecast.tax_rate", "forecast.cogs_pct_revenue"],
            "min_severity": "medium",
        },
    ),
    (
        "NWC",
        {
            "category": "working_capital",
            "title_template": "Net working capital changed {direction}",
            "detail_template": "NWC {verb} {pct}%. Review working capital day assumptions.",
            "affected_assumptions": ["forecast.dso", "forecast.dio", "forecast.dpo"],
            "min_severity": "medium",
        },
    ),
]

# Build lookup
_CHANGE_RULE_MAP = {rule[0]: rule[1] for rule in _CHANGE_IMPACT_RULES}

_SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def _severity_at_least(actual: str, minimum: str) -> bool:
    """Check if actual severity meets the minimum threshold."""
    return _SEVERITY_ORDER.get(actual, 0) >= _SEVERITY_ORDER.get(minimum, 0)


def _format_impact(change: dict, rule: dict) -> dict:
    """Format a single valuation impact from a filing change and its rule."""
    pct = change.get("percent_change")
    abs_change = change.get("absolute_change", 0)

    if pct is not None:
        direction = "increased" if pct > 0 else "decreased"
        verb = direction
        pct_str = f"{abs(pct) * 100:.1f}"
    else:
        direction = "materially"
        verb = "changed"
        pct_str = "N/A"

    bps_str = f"{abs(abs_change) * 10000:.0f}" if abs_change else "N/A"

    title = rule["title_template"].format(direction=direction)
    detail = rule["detail_template"].format(
        verb=verb, pct=pct_str, bps=bps_str, direction=direction
    )

    return {
        "category": rule["category"],
        "severity": change.get("severity", "low"),
        "title": title,
        "detail": detail,
        "affected_assumptions": rule["affected_assumptions"],
    }


# ── Main function ────────────────────────────────────────────────────

def build_valuation_impacts(
    changes: list[dict],
    red_flags: list[dict],
) -> list[dict]:
    """
    Map numeric filing changes and red flags into valuation assumption impacts.

    Args:
        changes: list of FilingChange dicts from detect_filing_changes
        red_flags: list of RedFlag dicts from detect_red_flags

    Returns:
        list of impact dicts, sorted by severity (high first).
        Each dict: {category, severity, title, detail, affected_assumptions}
    """
    impacts = []

    # Process filing changes
    for change in changes:
        account = change.get("account", "")
        severity = change.get("severity", "low")

        rule = _CHANGE_RULE_MAP.get(account)
        if rule is None:
            continue

        # Only include impacts at or above minimum severity threshold
        if not _severity_at_least(severity, rule["min_severity"]):
            continue

        impact = _format_impact(change, rule)
        impacts.append(impact)

    # Process red flags as impacts
    for flag in red_flags:
        code = flag.get("code", "")
        severity = flag.get("severity", "medium")
        title = flag.get("title", "Red flag detected")
        detail = flag.get("detail", "")
        affected = flag.get("affected_assumptions") or []

        impacts.append({
            "category": "red_flag",
            "severity": severity,
            "title": title,
            "detail": detail,
            "affected_assumptions": affected,
        })

    # Sort by severity (high first)
    impacts.sort(key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "low"), 0), reverse=True)

    return impacts
