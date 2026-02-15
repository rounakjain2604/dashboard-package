"""
DCF Engine — core valuation.

Discounts Unlevered FCFs, computes Terminal Value via Gordon Growth +
Exit Multiple, and bridges to Equity Value.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import ValuationConfig
from .wacc import WACCResult


@dataclass
class DCFResult:
    # Per-year detail
    valuation_table: pd.DataFrame   # year_index, UFCF, DF, PV_FCF

    # Terminal Value
    terminal_fcf: float
    terminal_ebitda: float
    gordon_tv: float
    exit_tv: float
    blended_tv: float
    pv_gordon_tv: float
    pv_exit_tv: float
    pv_blended_tv: float

    # Enterprise Value
    pv_fcf_sum: float
    ev_gordon: float
    ev_exit: float
    ev_blended: float

    # Equity Value (after bridge)
    equity_gordon: float
    equity_exit: float
    equity_blended: float

    # Per-share
    price_gordon: float
    price_exit: float
    price_blended: float

    # Cross-checks
    effective_terminal_growth: float
    terminal_wacc_spread: float
    implied_exit_multiple_from_gordon: float
    implied_growth_from_exit: float
    tv_pct_of_ev: float


def run_dcf(
    fcf_table: pd.DataFrame,
    wacc: WACCResult,
    cfg: ValuationConfig,
) -> DCFResult:
    """
    Run the full DCF valuation.

    Parameters
    ----------
    fcf_table : DataFrame with columns [year_index, Unlevered FCF, EBITDA]
    wacc : WACCResult with .wacc
    cfg : ValuationConfig
    """
    df = fcf_table.copy().reset_index(drop=True)
    n = len(df)
    periods = np.arange(1, n + 1, dtype=float)
    effective_wacc = max(float(wacc.wacc), 1e-6)

    # ── Discount Factors ─────────────────────────────────────────────
    if cfg.discount_convention == "mid_year":
        disc = 1.0 / ((1 + effective_wacc) ** (periods - 0.5))
    else:
        disc = 1.0 / ((1 + effective_wacc) ** periods)

    df["Discount Factor"] = disc
    df["PV of UFCF"] = df["Unlevered FCF"] * df["Discount Factor"]
    pv_sum = float(df["PV of UFCF"].sum())

    # ── Terminal Value ───────────────────────────────────────────────
    terminal_fcf = float(df.iloc[-1]["Unlevered FCF"])
    terminal_ebitda = float(df.iloc[-1].get("EBITDA", terminal_fcf * 1.5))

    g = min(cfg.terminal_growth_rate, cfg.gdp_growth_cap)
    spread_floor = max(cfg.terminal_spread_floor_bps / 10_000, 1e-6)
    effective_g = min(g, effective_wacc - spread_floor)

    gordon_tv = terminal_fcf * (1 + effective_g) / max(effective_wacc - effective_g, 1e-6)
    exit_tv = terminal_ebitda * cfg.exit_ev_ebitda_multiple

    # Blend
    gw = min(max(cfg.gordon_weight, 0), 1)
    blended_tv = gordon_tv * gw + exit_tv * (1 - gw)

    # PV of TV
    terminal_df = float(df.iloc[-1]["Discount Factor"])
    pv_gordon = gordon_tv * terminal_df
    pv_exit = exit_tv * terminal_df
    pv_blended = blended_tv * terminal_df

    # ── Enterprise Value ─────────────────────────────────────────────
    ev_gordon = pv_sum + pv_gordon
    ev_exit = pv_sum + pv_exit
    ev_blended = pv_sum + pv_blended

    # ── Equity Bridge ────────────────────────────────────────────────
    def _bridge(ev: float) -> float:
        return ev + cfg.cash - cfg.debt - cfg.minority_interest - cfg.preferred_stock

    eq_gordon = _bridge(ev_gordon)
    eq_exit = _bridge(ev_exit)
    eq_blended = _bridge(ev_blended)

    shares = max(cfg.fully_diluted_shares, 1e-9)
    price_gordon = eq_gordon / shares
    price_exit = eq_exit / shares
    price_blended = eq_blended / shares

    # ── Cross-checks ─────────────────────────────────────────────────
    implied_exit_mult = gordon_tv / max(terminal_ebitda, 1e-9)
    implied_growth = (
        (exit_tv * effective_wacc - terminal_fcf) /
        max(exit_tv + terminal_fcf, 1e-9)
    )
    tv_pct = pv_blended / max(ev_blended, 1e-9)

    return DCFResult(
        valuation_table=df,
        terminal_fcf=terminal_fcf,
        terminal_ebitda=terminal_ebitda,
        gordon_tv=gordon_tv,
        exit_tv=exit_tv,
        blended_tv=blended_tv,
        pv_gordon_tv=pv_gordon,
        pv_exit_tv=pv_exit,
        pv_blended_tv=pv_blended,
        pv_fcf_sum=pv_sum,
        ev_gordon=ev_gordon,
        ev_exit=ev_exit,
        ev_blended=ev_blended,
        equity_gordon=eq_gordon,
        equity_exit=eq_exit,
        equity_blended=eq_blended,
        price_gordon=price_gordon,
        price_exit=price_exit,
        price_blended=price_blended,
        effective_terminal_growth=effective_g,
        terminal_wacc_spread=effective_wacc - effective_g,
        implied_exit_multiple_from_gordon=implied_exit_mult,
        implied_growth_from_exit=implied_growth,
        tv_pct_of_ev=tv_pct,
    )
