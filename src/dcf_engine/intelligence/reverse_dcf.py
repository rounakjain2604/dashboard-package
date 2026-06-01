"""
Reverse DCF Tracker — Phase 5

Solves for implied revenue CAGR and implied EBITDA margin that justify
a given market price, using deterministic bisection and a lightweight
DCF approximation (no full pipeline in the bisection loop).

NOTE: The implied metrics are approximations. The lightweight helper
uses simplified projected revenue, EBITDA, UFCF, and terminal value
calculations. Full pipeline parity is not guaranteed.
"""
from __future__ import annotations

import copy
import math
import logging

logger = logging.getLogger(__name__)


# ── Lightweight DCF helper ───────────────────────────────────────────

def _quick_dcf(
    base_revenue: float,
    revenue_cagr: float,
    ebitda_margin: float,
    tax_rate: float,
    capex_pct_revenue: float,
    depreciation_rate: float,
    base_ppe: float,
    wacc: float,
    terminal_growth: float,
    exit_multiple: float,
    gordon_weight: float,
    projection_years: int,
    cash: float,
    debt: float,
    shares: float,
) -> float | None:
    """
    Approximate implied share price using a simplified DCF model.

    This is intentionally lightweight for use inside bisection loops.
    It does NOT run the full pipeline — it projects revenue, EBITDA,
    UFCF, discounts at WACC, computes blended terminal value, and
    derives equity value per share.

    Returns implied share price or None if inputs are degenerate.
    """
    if shares is None or shares <= 0 or wacc <= 0 or base_revenue <= 0:
        return None
    if wacc <= terminal_growth:
        return None

    pv_ufcf_total = 0.0
    last_ufcf = 0.0
    last_ebitda = 0.0

    for yr in range(1, projection_years + 1):
        revenue = base_revenue * ((1 + revenue_cagr) ** yr)
        ebitda = revenue * ebitda_margin
        # Approximate D&A: depreciation_rate * base_ppe (held constant for simplicity)
        da = base_ppe * depreciation_rate if base_ppe > 0 else revenue * 0.03
        ebit = ebitda - da
        taxes = max(0.0, ebit * tax_rate)
        nopat = ebit - taxes
        capex = revenue * capex_pct_revenue
        ufcf = nopat + da - capex
        # Mid-year discounting
        discount_factor = 1.0 / ((1 + wacc) ** (yr - 0.5))
        pv_ufcf_total += ufcf * discount_factor
        last_ufcf = ufcf
        last_ebitda = ebitda

    # Terminal value (blended Gordon Growth + Exit Multiple)
    terminal_fcf = last_ufcf * (1 + terminal_growth)
    gordon_tv = terminal_fcf / (wacc - terminal_growth) if wacc > terminal_growth else 0.0
    exit_tv = last_ebitda * exit_multiple if last_ebitda > 0 else 0.0
    blended_tv = gordon_weight * gordon_tv + (1 - gordon_weight) * exit_tv

    tv_discount = 1.0 / ((1 + wacc) ** projection_years)
    pv_tv = blended_tv * tv_discount

    ev = pv_ufcf_total + pv_tv
    equity_value = ev - debt + cash
    price = equity_value / shares

    return price


# ── WACC estimator (reused from assumption_qa pattern) ───────────────

def _estimate_wacc_from_payload(payload: dict) -> float:
    """Estimate WACC from payload CAPM parameters."""
    wacc_cfg = payload.get("wacc", {})
    rf = float(wacc_cfg.get("risk_free_rate", 0.042))
    erp = float(wacc_cfg.get("equity_risk_premium", 0.055))
    beta = float(wacc_cfg.get("beta", 1.1))
    size_premium = float(wacc_cfg.get("size_premium", 0.0))
    crp = float(wacc_cfg.get("country_risk_premium", 0.0))
    debt_weight = float(wacc_cfg.get("target_debt_weight", 0.30))
    equity_weight = float(wacc_cfg.get("target_equity_weight", 0.70))
    tax_rate = float(wacc_cfg.get("tax_rate", 0.25))
    icr = float(wacc_cfg.get("interest_coverage_ratio", 5.0))

    cost_of_equity = rf + beta * erp + size_premium + crp

    # Estimate cost of debt from ICR-based spread
    if icr >= 8.5:
        spread = 0.0063
    elif icr >= 6.5:
        spread = 0.0100
    elif icr >= 5.5:
        spread = 0.0125
    elif icr >= 4.25:
        spread = 0.0150
    elif icr >= 3.0:
        spread = 0.0200
    elif icr >= 2.5:
        spread = 0.0250
    elif icr >= 2.0:
        spread = 0.0350
    elif icr >= 1.5:
        spread = 0.0500
    else:
        spread = 0.0800

    cost_of_debt = rf + spread

    wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
    return max(wacc, 0.01)


# ── Extract params helper ────────────────────────────────────────────

def _extract_params(payload: dict) -> dict:
    """Extract all parameters needed for _quick_dcf from a payload dict."""
    fc = payload.get("forecast", {})
    vc = payload.get("valuation", {})

    cogs_pct = float(fc.get("cogs_pct_revenue", 0.50))
    sga_pct = float(fc.get("sga_pct_revenue", 0.15))
    other_pct = float(fc.get("other_opex_pct_revenue", 0.05))
    ebitda_margin = 1.0 - cogs_pct - sga_pct - other_pct

    return {
        "base_revenue": float(payload.get("base_year_revenue", 0)),
        "revenue_cagr": float(fc.get("revenue_cagr", 0.08)),
        "ebitda_margin": ebitda_margin,
        "tax_rate": float(fc.get("tax_rate", 0.21)),
        "capex_pct_revenue": float(fc.get("capex_pct_revenue", 0.05)),
        "depreciation_rate": float(fc.get("depreciation_rate", 0.10)),
        "base_ppe": float(payload.get("base_ppe", 0)),
        "wacc": _estimate_wacc_from_payload(payload),
        "terminal_growth": float(vc.get("terminal_growth_rate", 0.025)),
        "exit_multiple": float(vc.get("exit_ev_ebitda_multiple", 10.0)),
        "gordon_weight": float(vc.get("gordon_weight", 0.50)),
        "projection_years": int(fc.get("projection_years", 5)),
        "cash": float(vc.get("cash", 0)),
        "debt": float(vc.get("debt", 0)),
        "shares": float(vc.get("fully_diluted_shares")) if vc.get("fully_diluted_shares") is not None else None,
    }


# ── Public solvers ───────────────────────────────────────────────────

def solve_implied_revenue_cagr(
    base_payload: dict,
    target_price: float,
    low: float = -0.20,
    high: float = 0.40,
    max_iter: int = 40,
    tol: float = 0.01,
) -> dict:
    """
    Solve for the implied revenue CAGR that produces the target share price,
    using bisection on the lightweight DCF helper.

    Does NOT mutate base_payload.

    Returns dict with:
      implied_revenue_cagr, target_price, base_case_price, converged, warnings
    """
    warnings = []
    params = _extract_params(base_payload)

    if params.get("shares") is None or params["shares"] <= 0:
        return {
            "implied_revenue_cagr": None,
            "target_price": target_price,
            "base_case_price": None,
            "converged": False,
            "warnings": ["Shares outstanding missing or zero; cannot solve implied CAGR."],
        }

    if params["base_revenue"] <= 0:
        return {
            "implied_revenue_cagr": None,
            "target_price": target_price,
            "base_case_price": None,
            "converged": False,
            "warnings": ["Base revenue missing or zero; cannot solve implied CAGR."],
        }

    # Base case price
    base_price = _quick_dcf(**params)

    def price_at_cagr(cagr):
        p = dict(params)
        p["revenue_cagr"] = cagr
        return _quick_dcf(**p)

    price_low = price_at_cagr(low)
    price_high = price_at_cagr(high)

    if price_low is None or price_high is None:
        return {
            "implied_revenue_cagr": None,
            "target_price": target_price,
            "base_case_price": base_price,
            "converged": False,
            "warnings": ["Could not evaluate DCF at bisection boundaries."],
        }

    # Check if target is bracketed
    if not (min(price_low, price_high) <= target_price <= max(price_low, price_high)):
        # Return nearest boundary
        nearest = low if abs(price_low - target_price) < abs(price_high - target_price) else high
        warnings.append(
            f"Target price {target_price:.2f} is outside implied range "
            f"[{min(price_low, price_high):.2f}, {max(price_low, price_high):.2f}]. "
            f"Returning nearest boundary."
        )
        return {
            "implied_revenue_cagr": nearest,
            "target_price": target_price,
            "base_case_price": base_price,
            "converged": False,
            "warnings": warnings,
        }

    # Bisection
    lo, hi = low, high
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        mid_price = price_at_cagr(mid)
        if mid_price is None:
            break

        if abs(mid_price - target_price) < tol:
            return {
                "implied_revenue_cagr": round(mid, 6),
                "target_price": target_price,
                "base_case_price": base_price,
                "converged": True,
                "warnings": warnings,
            }

        # Determine direction based on monotonicity
        if price_low < price_high:
            # Price increases with CAGR
            if mid_price < target_price:
                lo = mid
            else:
                hi = mid
        else:
            # Price decreases with CAGR (unusual)
            if mid_price > target_price:
                lo = mid
            else:
                hi = mid

    final_cagr = (lo + hi) / 2.0
    return {
        "implied_revenue_cagr": round(final_cagr, 6),
        "target_price": target_price,
        "base_case_price": base_price,
        "converged": True,
        "warnings": warnings,
    }


def solve_implied_ebitda_margin(
    base_payload: dict,
    target_price: float,
    low: float = 0.01,
    high: float = 0.60,
    max_iter: int = 40,
    tol: float = 0.01,
) -> dict:
    """
    Solve for the implied EBITDA margin that produces the target share price,
    using bisection on the lightweight DCF helper.

    The margin is applied directly as ebitda_margin in the quick DCF.
    It validates that the implied cogs_pct_revenue would not go negative.

    Does NOT mutate base_payload.

    Returns dict with:
      implied_ebitda_margin, implied_cogs_pct, target_price, base_case_price,
      converged, warnings
    """
    warnings = []
    params = _extract_params(base_payload)

    if params.get("shares") is None or params["shares"] <= 0:
        return {
            "implied_ebitda_margin": None,
            "implied_cogs_pct": None,
            "target_price": target_price,
            "base_case_price": None,
            "converged": False,
            "warnings": ["Shares outstanding missing or zero; cannot solve implied margin."],
        }

    if params["base_revenue"] <= 0:
        return {
            "implied_ebitda_margin": None,
            "implied_cogs_pct": None,
            "target_price": target_price,
            "base_case_price": None,
            "converged": False,
            "warnings": ["Base revenue missing or zero; cannot solve implied margin."],
        }

    # Current SGA and other opex from payload
    fc = base_payload.get("forecast", {})
    sga_pct = float(fc.get("sga_pct_revenue", 0.15))
    other_pct = float(fc.get("other_opex_pct_revenue", 0.05))
    max_feasible_margin = 1.0 - sga_pct - other_pct  # cogs_pct cannot go below 0

    if high > max_feasible_margin:
        actual_high = max_feasible_margin - 0.001  # small buffer
        if actual_high <= low:
            return {
                "implied_ebitda_margin": None,
                "implied_cogs_pct": None,
                "target_price": target_price,
                "base_case_price": None,
                "converged": False,
                "warnings": [
                    f"Cannot solve implied margin: SG&A ({sga_pct:.1%}) + other opex "
                    f"({other_pct:.1%}) leaves no feasible EBITDA margin range."
                ],
            }
        warnings.append(
            f"Upper margin bound clamped to {actual_high:.1%} to avoid negative COGS "
            f"(SG&A={sga_pct:.1%}, other opex={other_pct:.1%})."
        )
        high = actual_high

    base_price = _quick_dcf(**params)

    def price_at_margin(margin):
        p = dict(params)
        p["ebitda_margin"] = margin
        return _quick_dcf(**p)

    price_low = price_at_margin(low)
    price_high = price_at_margin(high)

    if price_low is None or price_high is None:
        return {
            "implied_ebitda_margin": None,
            "implied_cogs_pct": None,
            "target_price": target_price,
            "base_case_price": base_price,
            "converged": False,
            "warnings": warnings + ["Could not evaluate DCF at margin boundaries."],
        }

    if not (min(price_low, price_high) <= target_price <= max(price_low, price_high)):
        nearest_margin = low if abs(price_low - target_price) < abs(price_high - target_price) else high
        implied_cogs = max(0.0, 1.0 - nearest_margin - sga_pct - other_pct)
        warnings.append(
            f"Target price {target_price:.2f} outside implied margin range "
            f"[{min(price_low, price_high):.2f}, {max(price_low, price_high):.2f}]. "
            f"Returning nearest boundary."
        )
        return {
            "implied_ebitda_margin": nearest_margin,
            "implied_cogs_pct": round(implied_cogs, 6),
            "target_price": target_price,
            "base_case_price": base_price,
            "converged": False,
            "warnings": warnings,
        }

    lo, hi = low, high
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        mid_price = price_at_margin(mid)
        if mid_price is None:
            break

        if abs(mid_price - target_price) < tol:
            implied_cogs = max(0.0, 1.0 - mid - sga_pct - other_pct)
            return {
                "implied_ebitda_margin": round(mid, 6),
                "implied_cogs_pct": round(implied_cogs, 6),
                "target_price": target_price,
                "base_case_price": base_price,
                "converged": True,
                "warnings": warnings,
            }

        if price_low < price_high:
            if mid_price < target_price:
                lo = mid
            else:
                hi = mid
        else:
            if mid_price > target_price:
                lo = mid
            else:
                hi = mid

    final_margin = (lo + hi) / 2.0
    implied_cogs = max(0.0, 1.0 - final_margin - sga_pct - other_pct)
    return {
        "implied_ebitda_margin": round(final_margin, 6),
        "implied_cogs_pct": round(implied_cogs, 6),
        "target_price": target_price,
        "base_case_price": base_price,
        "converged": True,
        "warnings": warnings,
    }


# ── Orchestrator ─────────────────────────────────────────────────────

def solve_implied_metrics(
    base_payload: dict,
    target_price: float | None,
    market_cap: float | None = None,
) -> dict:
    """
    Orchestrate implied-metric solving for both revenue CAGR and EBITDA margin.

    If target_price is None but market_cap is provided, derives target_price
    from market_cap / shares.

    Does NOT mutate base_payload.

    Returns dict with:
      ticker, target_price, target_equity_value,
      implied_revenue_cagr, implied_ebitda_margin,
      base_case_price, warnings
    """
    warnings = []
    ticker = base_payload.get("ticker", base_payload.get("company_name", "Unknown"))
    vc = base_payload.get("valuation", {})
    shares_val = vc.get("fully_diluted_shares")
    shares = float(shares_val) if shares_val is not None else None

    # Derive target_price from market_cap if needed
    if target_price is None and market_cap is not None and shares is not None and shares > 0:
        target_price = market_cap / shares

    if target_price is None:
        if shares is None or shares <= 0:
            warnings.append("Shares outstanding missing or zero; cannot solve implied metrics.")
        warnings.append("Live market price unavailable; reverse DCF not computed.")
        return {
            "ticker": ticker,
            "target_price": None,
            "target_equity_value": None,
            "implied_revenue_cagr": None,
            "implied_ebitda_margin": None,
            "base_case_price": None,
            "warnings": warnings,
        }

    target_equity_value = target_price * shares if (shares is not None and shares > 0) else None

    cagr_result = solve_implied_revenue_cagr(base_payload, target_price)
    margin_result = solve_implied_ebitda_margin(base_payload, target_price)

    warnings.extend(cagr_result.get("warnings", []))
    warnings.extend(margin_result.get("warnings", []))

    return {
        "ticker": ticker,
        "target_price": target_price,
        "target_equity_value": target_equity_value,
        "implied_revenue_cagr": cagr_result.get("implied_revenue_cagr"),
        "implied_ebitda_margin": margin_result.get("implied_ebitda_margin"),
        "base_case_price": cagr_result.get("base_case_price"),
        "warnings": warnings,
    }
