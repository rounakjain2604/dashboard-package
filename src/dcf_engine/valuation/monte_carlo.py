"""
Monte Carlo simulation for DCF valuation.

Randomises key value drivers (revenue growth, EBITDA margin, WACC,
terminal growth, exit multiple) over 10,000+ iterations and produces
a probability distribution of Equity Value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from ..config import MonteCarloConfig


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation output."""
    iterations: int
    equity_values: np.ndarray
    statistics: dict            # mean, median, std, P10, P25, P50, P75, P90
    driver_table: pd.DataFrame  # All randomised inputs per trial
    histogram_data: dict        # bins, counts for charting


def run_monte_carlo(
    base_revenue: float,
    base_ebitda_margin: float,
    base_wacc: float,
    base_terminal_growth: float,
    base_exit_multiple: float,
    projection_years: int,
    cfg: MonteCarloConfig,
    tax_rate: float = 0.25,
    capex_pct: float = 0.04,
    da_pct: float = 0.04,
    cash: float = 0.0,
    debt: float = 0.0,
    shares: float = 1_000_000.0,
    gordon_weight: float = 0.50,
    discount_convention: str = "mid_year",
    minority_interest: float = 0.0,
    preferred_stock: float = 0.0,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation.

    Each trial:
    1. Sample revenue growth, EBITDA margin, WACC, terminal growth, exit multiple
    2. Project 5-year FCFs
    3. Compute terminal value (blended)
    4. Discount to get Equity Value
    """
    rng = np.random.default_rng(cfg.seed if cfg.seed is not None else None)
    n = cfg.iterations

    # ── Sample random inputs ─────────────────────────────────────────
    rev_growth = rng.normal(cfg.revenue_growth_mean, cfg.revenue_growth_std, n)
    ebitda_margin = rng.normal(cfg.ebitda_margin_mean, cfg.ebitda_margin_std, n)
    wacc_sim = rng.normal(cfg.wacc_mean, cfg.wacc_std, n)
    term_growth = rng.normal(cfg.terminal_growth_mean, cfg.terminal_growth_std, n)
    exit_mult = rng.normal(cfg.exit_multiple_mean, cfg.exit_multiple_std, n)

    # Clamp to reasonable bounds
    rev_growth = np.clip(rev_growth, -0.20, 0.50)
    ebitda_margin = np.clip(ebitda_margin, 0.01, 0.60)
    wacc_sim = np.clip(wacc_sim, 0.03, 0.30)
    term_growth = np.clip(term_growth, 0.0, 0.05)
    exit_mult = np.clip(exit_mult, 3.0, 25.0)

    # Ensure WACC > terminal growth
    wacc_sim = np.maximum(wacc_sim, term_growth + 0.01)

    equity_values = np.zeros(n)

    for i in range(n):
        g = rev_growth[i]
        margin = ebitda_margin[i]
        w = wacc_sim[i]
        tg = term_growth[i]
        em = exit_mult[i]

        # Project simple FCFs
        revenue = base_revenue
        pv_sum = 0.0
        last_fcf = 0.0
        last_ebitda = 0.0

        for yr in range(1, projection_years + 1):
            revenue *= (1 + g)
            ebitda = revenue * margin
            da = revenue * da_pct
            ebit = ebitda - da
            nopat = ebit * (1 - tax_rate)
            capex = revenue * capex_pct
            fcf = nopat + da - capex
            if discount_convention == "mid_year":
                df = 1.0 / ((1 + w) ** (yr - 0.5))
            else:
                df = 1.0 / ((1 + w) ** yr)
            pv_sum += fcf * df
            last_fcf = fcf
            last_ebitda = ebitda

        # Terminal value (blended using gordon_weight)
        gordon_tv = last_fcf * (1 + tg) / max(w - tg, 1e-6)
        exit_tv = last_ebitda * em
        blended_tv = gordon_tv * gordon_weight + exit_tv * (1 - gordon_weight)

        if discount_convention == "mid_year":
            terminal_df = 1.0 / ((1 + w) ** (projection_years - 0.5))
        else:
            terminal_df = 1.0 / ((1 + w) ** projection_years)
        pv_tv = blended_tv * terminal_df

        ev = pv_sum + pv_tv
        equity = ev + cash - debt - minority_interest - preferred_stock
        equity_values[i] = equity

    # ── Statistics ────────────────────────────────────────────────────
    stats = {
        "Mean": float(np.mean(equity_values)),
        "Median": float(np.median(equity_values)),
        "Std Dev": float(np.std(equity_values)),
        "P10": float(np.percentile(equity_values, 10)),
        "P25": float(np.percentile(equity_values, 25)),
        "P50": float(np.percentile(equity_values, 50)),
        "P75": float(np.percentile(equity_values, 75)),
        "P90": float(np.percentile(equity_values, 90)),
        "Min": float(np.min(equity_values)),
        "Max": float(np.max(equity_values)),
        "Per Share Mean": float(np.mean(equity_values) / max(shares, 1)),
        "Per Share Median": float(np.median(equity_values) / max(shares, 1)),
        "Per Share P10": float(np.percentile(equity_values, 10) / max(shares, 1)),
        "Per Share P90": float(np.percentile(equity_values, 90) / max(shares, 1)),
    }

    # Histogram data for charting
    counts, bin_edges = np.histogram(equity_values, bins=50)
    hist_data = {
        "bin_edges": bin_edges.tolist(),
        "counts": counts.tolist(),
        "bin_centers": ((bin_edges[:-1] + bin_edges[1:]) / 2).tolist(),
    }

    # Driver table (first 100 for inspection)
    driver_df = pd.DataFrame({
        "Revenue Growth": rev_growth[:100],
        "EBITDA Margin": ebitda_margin[:100],
        "WACC": wacc_sim[:100],
        "Terminal Growth": term_growth[:100],
        "Exit Multiple": exit_mult[:100],
        "Equity Value": equity_values[:100],
    })

    return MonteCarloResult(
        iterations=n,
        equity_values=equity_values,
        statistics=stats,
        driver_table=driver_df,
        histogram_data=hist_data,
    )
