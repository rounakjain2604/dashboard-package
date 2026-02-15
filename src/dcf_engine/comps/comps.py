"""
Comparable Companies Analysis & Trading Multiples.

Pulls market data for peer companies and calculates EV/Revenue,
EV/EBITDA, and P/E multiples with implied valuation ranges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

from ..config import CompsConfig
from ..ingestion.market_data import fetch_peer_snapshots, MarketSnapshot


@dataclass
class CompsResult:
    """Comparable companies analysis output."""
    peer_table: pd.DataFrame          # Ticker, MktCap, EV, Rev, EBITDA, NI, multiples
    summary_stats: pd.DataFrame       # Mean, Median, High, Low per multiple
    implied_valuation: pd.DataFrame   # Implied EV and Equity from comps


def build_comps(
    cfg: CompsConfig,
    target_revenue: float = 0.0,
    target_ebitda: float = 0.0,
    target_net_income: float = 0.0,
    target_cash: float = 0.0,
    target_debt: float = 0.0,
) -> CompsResult:
    """
    Build comparable companies analysis.

    Parameters
    ----------
    cfg : CompsConfig with peer_tickers and multiples list.
    target_* : Target company's financials for implied valuation.
    """
    if not cfg.peer_tickers:
        empty = pd.DataFrame()
        return CompsResult(peer_table=empty, summary_stats=empty, implied_valuation=empty)

    # ── Pull market data for peers ───────────────────────────────────
    snapshots = fetch_peer_snapshots(cfg.peer_tickers)

    rows = []
    for ticker, snap in snapshots.items():
        ev = snap.enterprise_value or 0
        rev = snap.trailing_revenue or 0
        ebitda = snap.trailing_ebitda or 0
        ni = snap.trailing_net_income or 0
        mcap = snap.market_cap or 0
        price = snap.current_price or 0
        shares = snap.shares_outstanding or 0

        ev_rev = ev / rev if rev else np.nan
        ev_ebitda = ev / ebitda if ebitda else np.nan
        pe = mcap / ni if ni and ni > 0 else np.nan

        rows.append({
            "Ticker": ticker,
            "Price": price,
            "Market Cap": mcap,
            "Enterprise Value": ev,
            "Revenue": rev,
            "EBITDA": ebitda,
            "Net Income": ni,
            "EV/Revenue": ev_rev,
            "EV/EBITDA": ev_ebitda,
            "P/E": pe,
        })

    peer_df = pd.DataFrame(rows)

    # ── Summary Statistics ───────────────────────────────────────────
    mult_cols = [c for c in ["EV/Revenue", "EV/EBITDA", "P/E"] if c in cfg.multiples]
    if not mult_cols:
        mult_cols = ["EV/Revenue", "EV/EBITDA", "P/E"]

    stats_rows = []
    for col in mult_cols:
        vals = peer_df[col].dropna()
        if vals.empty:
            continue
        stats_rows.append({
            "Multiple": col,
            "Mean": float(vals.mean()),
            "Median": float(vals.median()),
            "High": float(vals.max()),
            "Low": float(vals.min()),
            "Count": int(len(vals)),
        })

    stats_df = pd.DataFrame(stats_rows)

    # ── Implied Valuation ────────────────────────────────────────────
    implied_rows = []
    for _, stat in stats_df.iterrows():
        mult_name = stat["Multiple"]
        for stat_type in ["Mean", "Median", "Low", "High"]:
            mult_val = stat[stat_type]
            if mult_name == "EV/Revenue" and target_revenue > 0:
                implied_ev = target_revenue * mult_val
                implied_eq = implied_ev + target_cash - target_debt
            elif mult_name == "EV/EBITDA" and target_ebitda > 0:
                implied_ev = target_ebitda * mult_val
                implied_eq = implied_ev + target_cash - target_debt
            elif mult_name == "P/E" and target_net_income > 0:
                implied_ev = target_net_income * mult_val + target_debt - target_cash
                implied_eq = target_net_income * mult_val
            else:
                continue

            implied_rows.append({
                "Multiple": mult_name,
                "Statistic": stat_type,
                "Multiple Value": mult_val,
                "Implied EV": implied_ev,
                "Implied Equity": implied_eq,
            })

    implied_df = pd.DataFrame(implied_rows)

    return CompsResult(
        peer_table=peer_df,
        summary_stats=stats_df,
        implied_valuation=implied_df,
    )
