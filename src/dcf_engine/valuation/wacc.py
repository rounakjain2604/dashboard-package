"""
WACC calculator with live data pulls.

Implements CAPM for cost of equity, synthetic credit rating for cost
of debt, and weighted-average blending.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..config import WACCConfig
from ..ingestion.market_data import (
    fetch_risk_free_rate,
    fetch_beta,
    fetch_equity_risk_premium,
)

logger = logging.getLogger(__name__)


@dataclass
class WACCResult:
    cost_of_equity: float
    cost_of_debt_pre_tax: float
    cost_of_debt_after_tax: float
    wacc: float
    synthetic_rating: str
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    size_premium: float
    country_risk_premium: float
    debt_weight: float
    equity_weight: float
    credit_spread: float = 0.02


# ── Synthetic Credit Rating (Damodaran) ──────────────────────────────
_RATING_GRID = [
    (12.5, "AAA", 0.0063),
    (9.5,  "AA",  0.0078),
    (7.5,  "A+",  0.0098),
    (6.0,  "A",   0.0108),
    (4.5,  "A-",  0.0122),
    (4.0,  "BBB", 0.0156),
    (3.5,  "BB+", 0.0200),
    (3.0,  "BB",  0.0240),
    (2.5,  "B+",  0.0325),
    (2.0,  "B",   0.0400),
    (1.5,  "B-",  0.0500),
    (1.25, "CCC", 0.0600),
    (0.8,  "CC",  0.0750),
    (0.5,  "C",   0.0900),
    (0.0,  "D",   0.1200),
]


def synthetic_credit_spread(icr: float) -> tuple[str, float]:
    """Return (rating, spread) based on interest-coverage ratio."""
    for threshold, rating, spread in _RATING_GRID:
        if icr >= threshold:
            return rating, spread
    return "D", 0.12


def compute_wacc(
    cfg: WACCConfig,
    ticker: Optional[str] = None,
) -> WACCResult:
    """
    Compute WACC with optional live data pulls.

    Live data is attempted when ``cfg.use_live_data`` is True and a
    ticker is provided.  Falls back to config defaults on failure.
    """
    rf = cfg.risk_free_rate
    beta = cfg.beta
    erp = cfg.equity_risk_premium

    # ── Live data pulls ──────────────────────────────────────────────
    if cfg.use_live_data:
        live_rf = fetch_risk_free_rate()
        if live_rf is not None:
            rf = live_rf
            logger.info("Using live risk-free rate: %.4f", rf)

        if ticker:
            live_beta = fetch_beta(ticker)
            if live_beta is not None:
                beta = live_beta
                logger.info("Using live beta for %s: %.2f", ticker, beta)

        live_erp = fetch_equity_risk_premium()
        if live_erp is not None:
            erp = live_erp

    # ── Cost of Equity (CAPM) ────────────────────────────────────────
    cost_of_equity = rf + beta * erp + cfg.size_premium + cfg.country_risk_premium

    # ── Cost of Debt (synthetic rating) ──────────────────────────────
    rating, spread = synthetic_credit_spread(cfg.interest_coverage_ratio)
    cost_of_debt_pre = rf + spread
    cost_of_debt_post = cost_of_debt_pre * (1 - cfg.tax_rate)

    # ── WACC ─────────────────────────────────────────────────────────
    wacc = (cfg.target_equity_weight * cost_of_equity +
            cfg.target_debt_weight * cost_of_debt_post)

    return WACCResult(
        cost_of_equity=cost_of_equity,
        cost_of_debt_pre_tax=cost_of_debt_pre,
        cost_of_debt_after_tax=cost_of_debt_post,
        wacc=wacc,
        synthetic_rating=rating,
        risk_free_rate=rf,
        beta=beta,
        equity_risk_premium=erp,
        size_premium=cfg.size_premium,
        country_risk_premium=cfg.country_risk_premium,
        debt_weight=cfg.target_debt_weight,
        equity_weight=cfg.target_equity_weight,
        credit_spread=spread,
    )
