from __future__ import annotations
import math
import logging

logger = logging.getLogger(__name__)

def _safe_get(d: dict, key: str, default):
    """Safely fetch a nested dictionary value using dot-notation, return default if not found."""
    parts = key.split(".")
    curr = d
    for p in parts:
        if not isinstance(curr, dict):
            return default
        curr = curr.get(p)
        if curr is None:
            return default
    return curr

def evaluate_assumption_quality(payload: dict, warnings: list[str] | None = None) -> dict:
    """
    Evaluates DCF model assumptions deterministically, calculates an overall score
    from 0 to 100, maps it to a letter grade, and returns a detailed QA warning list
    along with a plain-English summary.
    """
    if not isinstance(payload, dict):
        payload = {}
    if warnings is None:
        warnings = []

    qa_warnings = []
    score = 100

    # Helper to add warning and apply deduction
    def add_qa_warning(code: str, severity: str, title: str, detail: str, affected: str):
        nonlocal score
        qa_warnings.append({
            "code": code,
            "severity": severity,
            "title": title,
            "detail": detail,
            "affected_assumption": affected
        })
        if severity == "high":
            score -= 20
        elif severity == "medium":
            score -= 10
        elif severity == "low":
            score -= 5

    # 1. fallback_heavy rule
    warn_count = len(warnings)
    if warn_count >= 8:
        add_qa_warning(
            code="fallback_heavy",
            severity="high",
            title="Fallback-heavy assumptions",
            detail=f"There are {warn_count} fallback warnings from snapshot / assumption building. This indicates high reliance on model defaults.",
            affected="multiple"
        )
    elif warn_count >= 4:
        add_qa_warning(
            code="fallback_moderate",
            severity="medium",
            title="Moderate fallback assumptions",
            detail=f"There are {warn_count} fallback warnings from snapshot / assumption building. Several values rely on defaults.",
            affected="multiple"
        )

    # 2. missing_base_revenue rule
    base_rev = _safe_get(payload, "base_year_revenue", 0.0)
    try:
        f_base_rev = float(base_rev)
    except (ValueError, TypeError):
        f_base_rev = 0.0

    if f_base_rev <= 0.0:
        add_qa_warning(
            code="missing_base_revenue",
            severity="high",
            title="Missing base year revenue",
            detail="Base year revenue is missing or non-positive, which prevents standard financial growth projection.",
            affected="base_year_revenue"
        )

    # 3. missing_or_default_shares rule
    shares = _safe_get(payload, "valuation.fully_diluted_shares", 1000000.0)
    try:
        f_shares = float(shares)
    except (ValueError, TypeError):
        f_shares = 1000000.0

    if abs(f_shares - 1000000.0) < 1.0:
        add_qa_warning(
            code="default_shares",
            severity="medium",
            title="Default shares outstanding",
            detail="Shares outstanding is set exactly to the default 1,000,000. Verify this against company filings.",
            affected="valuation.fully_diluted_shares"
        )

    # 4. revenue_growth_extreme rule
    rev_cagr = _safe_get(payload, "forecast.revenue_cagr", 0.05)
    try:
        f_rev_cagr = float(rev_cagr)
    except (ValueError, TypeError):
        f_rev_cagr = 0.05

    if f_rev_cagr < -0.10 or f_rev_cagr > 0.25:
        add_qa_warning(
            code="revenue_growth_extreme",
            severity="high",
            title="Extreme revenue CAGR",
            detail=f"Revenue CAGR is set to {f_rev_cagr*100:.1f}%, which is unusually extreme (expected range [-10.0%, 25.0%]).",
            affected="forecast.revenue_cagr"
        )

    # 5. terminal_growth_high rule
    term_growth = _safe_get(payload, "valuation.terminal_growth_rate", 0.025)
    try:
        f_term_growth = float(term_growth)
    except (ValueError, TypeError):
        f_term_growth = 0.025

    if f_term_growth > 0.035:
        add_qa_warning(
            code="terminal_growth_high",
            severity="medium",
            title="High terminal growth rate",
            detail=f"Terminal growth rate of {f_term_growth*100:.1f}% exceeds standard long-term GDP growth cap (3.5%).",
            affected="valuation.terminal_growth_rate"
        )

    # WACC Estimator Helper
    rf = _safe_get(payload, "wacc.risk_free_rate", 0.042)
    erp = _safe_get(payload, "wacc.equity_risk_premium", 0.055)
    beta = _safe_get(payload, "wacc.beta", 1.1)
    sp = _safe_get(payload, "wacc.size_premium", 0.0)
    crp = _safe_get(payload, "wacc.country_risk_premium", 0.0)
    we = _safe_get(payload, "wacc.target_equity_weight", 0.70)
    wd = _safe_get(payload, "wacc.target_debt_weight", 0.30)
    tax = _safe_get(payload, "wacc.tax_rate", 0.25)
    icr = _safe_get(payload, "wacc.interest_coverage_ratio", 5.0)

    try:
        f_rf = float(rf)
        f_erp = float(erp)
        f_beta = float(beta)
        f_sp = float(sp)
        f_crp = float(crp)
        f_we = float(we)
        f_wd = float(wd)
        f_tax = float(tax)
        f_icr = float(icr)
    except (ValueError, TypeError):
        f_rf, f_erp, f_beta, f_sp, f_crp, f_we, f_wd, f_tax, f_icr = 0.042, 0.055, 1.1, 0.0, 0.0, 0.70, 0.30, 0.25, 5.0

    if f_icr >= 8.5:
        spread = 0.0075
    elif f_icr >= 6.5:
        spread = 0.0100
    elif f_icr >= 5.5:
        spread = 0.0150
    elif f_icr >= 4.25:
        spread = 0.0200
    elif f_icr >= 3.0:
        spread = 0.0300
    else:
        spread = 0.0500

    cost_of_equity = f_rf + f_beta * f_erp + f_sp + f_crp
    cost_of_debt_after_tax = (f_rf + spread) * (1.0 - f_tax)
    wacc_estimated = cost_of_equity * f_we + cost_of_debt_after_tax * f_wd

    # 6. terminal_growth_near_wacc rule
    if abs(f_term_growth - wacc_estimated) <= 0.005:
        add_qa_warning(
            code="terminal_growth_near_wacc",
            severity="high",
            title="Terminal growth too close to WACC",
            detail=f"Terminal growth rate ({f_term_growth*100:.1f}%) is within 0.5% of estimated WACC ({wacc_estimated*100:.1f}%), causing valuation denominator to approach zero.",
            affected="valuation.terminal_growth_rate"
        )

    # 7. margin_negative_or_too_high rule
    cogs_pct = _safe_get(payload, "forecast.cogs_pct_revenue", 0.50)
    sga_pct = _safe_get(payload, "forecast.sga_pct_revenue", 0.15)
    other_opex_pct = _safe_get(payload, "forecast.other_opex_pct_revenue", 0.05)

    try:
        f_cogs = float(cogs_pct)
        f_sga = float(sga_pct)
        f_other_opex = float(other_opex_pct)
    except (ValueError, TypeError):
        f_cogs, f_sga, f_other_opex = 0.50, 0.15, 0.05

    ebitda_margin = 1.0 - f_cogs - f_sga - f_other_opex
    if ebitda_margin < 0.0:
        add_qa_warning(
            code="margin_negative",
            severity="high",
            title="Negative EBITDA margin",
            detail=f"Derived EBITDA margin of {ebitda_margin*100:.1f}% is negative. Model assumptions imply operational losses.",
            affected="forecast.cogs_pct_revenue"
        )
    elif ebitda_margin > 0.60:
        add_qa_warning(
            code="margin_excessive",
            severity="medium",
            title="Excessive EBITDA margin",
            detail=f"Derived EBITDA margin of {ebitda_margin*100:.1f}% is above 60%, which is extremely high for typical public companies.",
            affected="forecast.cogs_pct_revenue"
        )

    # 8. capex_unusually_low rule
    capex_pct = _safe_get(payload, "forecast.capex_pct_revenue", 0.05)
    ppe_net = _safe_get(payload, "base_ppe", 0.0)
    try:
        f_capex_pct = float(capex_pct)
        f_ppe_net = float(ppe_net)
    except (ValueError, TypeError):
        f_capex_pct, f_ppe_net = 0.05, 0.0

    if f_capex_pct <= 0.005 and (f_ppe_net > 1000000.0 or f_base_rev > 10000000.0):
        add_qa_warning(
            code="capex_unusually_low",
            severity="low",
            title="Unusually low Capex",
            detail=f"Capital expenditure of {f_capex_pct*100:.1f}% is extremely low (<= 0.5%) despite material operational PP&E base.",
            affected="forecast.capex_pct_revenue"
        )

    # 9. tax_rate_extreme rule
    tax_rate = _safe_get(payload, "forecast.tax_rate", 0.21)
    try:
        f_tax_rate = float(tax_rate)
    except (ValueError, TypeError):
        f_tax_rate = 0.21

    if f_tax_rate < 0.0 or f_tax_rate > 0.35:
        add_qa_warning(
            code="tax_rate_extreme",
            severity="medium",
            title="Extreme tax rate",
            detail=f"Forecast tax rate of {f_tax_rate*100:.1f}% is outside standard corporate bounds [0.0%, 35.0%].",
            affected="forecast.tax_rate"
        )

    # 10. debt_heavy rule
    debt = _safe_get(payload, "valuation.debt", 0.0)
    cash = _safe_get(payload, "valuation.cash", 0.0)
    try:
        f_debt = float(debt)
        f_cash = float(cash)
    except (ValueError, TypeError):
        f_debt, f_cash = 0.0, 0.0

    if f_debt > f_cash and f_base_rev > 0.0 and (f_debt / f_base_rev) > 0.50:
        add_qa_warning(
            code="heavy_debt_burden",
            severity="medium",
            title="Heavy debt burden",
            detail=f"Total debt ({f_debt:,.0f}) exceeds cash reserves and represents {f_debt/f_base_rev*100:.1f}% of base revenue, creating leverage risk.",
            affected="valuation.debt"
        )

    # Clamp score to [0, 100]
    score = max(0, min(100, score))

    # Grade mapping
    if score >= 85:
        grade = "A"
        summary = "Excellent: Valuation assumptions are robust and fully supported by historical SEC data."
    elif score >= 70:
        grade = "B"
        summary = "Good: Assumptions are reasonable, though minor adjustments or fallbacks exist."
    elif score >= 55:
        grade = "C"
        summary = "Caution: Several assumptions are extreme or rely heavily on default fallbacks."
    elif score >= 40:
        grade = "D"
        summary = "Weak: Assumptions are highly speculative, inconsistent, or fallback-heavy."
    else:
        grade = "F"
        summary = "Critical: Major consistency issues or missing base facts detected. Valuation is highly unreliable."

    return {
        "score": score,
        "grade": grade,
        "warnings": qa_warnings,
        "summary": summary
    }
