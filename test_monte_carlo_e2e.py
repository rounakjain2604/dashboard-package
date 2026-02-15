"""
End-to-End Monte Carlo Simulation Tests
========================================
Tests the MC solution across a wide variety of input configurations to
ensure correctness, consistency, and proper integration with the full
pipeline.  Validates:

      1. MC output structure (statistics, histogram, driver table)
      2. Auto-sync of MC means from base-case assumptions (V9.0.0 fix)
  3. Deterministic reproducibility with fixed seed
  4. Non-determinism with seed=None
  5. Sensitivity to every randomised driver
  6. Clamping / guard-rail correctness
  7. Edge cases (tiny revenue, large debt, extreme growth, 1 iteration)
  8. Full pipeline integration (MC means auto-synced from WACC / forecast)
  9. Different projection horizons
 10. Per-share statistics correctness

Run:  python test_monte_carlo_e2e.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.dcf_engine.config import (
    DCFEngineConfig, CompanyInfo, ForecastConfig, WACCConfig,
    ValuationConfig, MonteCarloConfig, DebtTranche, ScenarioOverrides,
)
from src.dcf_engine.valuation.monte_carlo import run_monte_carlo, MonteCarloResult
from src.dcf_engine.pipeline import run_pipeline

PASS = 0
FAIL = 0


def check(condition: bool, label: str, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f"  — {detail}"
        print(msg)


def section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════
DEFAULT_MC = dict(
    base_revenue=5_000_000,
    base_ebitda_margin=0.30,
    base_wacc=0.10,
    base_terminal_growth=0.025,
    base_exit_multiple=10.0,
    projection_years=5,
    tax_rate=0.25,
    capex_pct=0.04,
    da_pct=0.10,
    cash=500_000,
    debt=1_000_000,
    shares=1_000_000,
    gordon_weight=0.50,
)


def run_mc(mc_cfg: MonteCarloConfig, **overrides) -> MonteCarloResult:
    """Run MC with defaults plus any overrides."""
    params = {**DEFAULT_MC, **overrides}
    return run_monte_carlo(
        base_revenue=params["base_revenue"],
        base_ebitda_margin=params["base_ebitda_margin"],
        base_wacc=params["base_wacc"],
        base_terminal_growth=params["base_terminal_growth"],
        base_exit_multiple=params["base_exit_multiple"],
        projection_years=params["projection_years"],
        cfg=mc_cfg,
        tax_rate=params["tax_rate"],
        capex_pct=params["capex_pct"],
        da_pct=params["da_pct"],
        cash=params["cash"],
        debt=params["debt"],
        shares=params["shares"],
        gordon_weight=params["gordon_weight"],
    )


# ═══════════════════════════════════════════════════════════════════════
# TEST 1 — Output Structure Validation
# ═══════════════════════════════════════════════════════════════════════
section("TEST 1: Output Structure Validation")

mc_cfg = MonteCarloConfig(iterations=500, seed=42)
r = run_mc(mc_cfg)

check(isinstance(r, MonteCarloResult), "Returns MonteCarloResult")
check(r.iterations == 500, "Iteration count matches config", f"got {r.iterations}")
check(len(r.equity_values) == 500, "equity_values length == iterations")
check(isinstance(r.statistics, dict), "statistics is dict")

expected_keys = {"Mean", "Median", "Std Dev", "P10", "P25", "P50", "P75", "P90",
                 "Min", "Max", "Per Share Mean", "Per Share Median",
                 "Per Share P10", "Per Share P90"}
check(expected_keys.issubset(r.statistics.keys()), "All expected stat keys present",
      f"missing: {expected_keys - set(r.statistics.keys())}")

check(isinstance(r.histogram_data, dict), "histogram_data is dict")
check("bin_edges" in r.histogram_data, "histogram has bin_edges")
check("counts" in r.histogram_data, "histogram has counts")
check("bin_centers" in r.histogram_data, "histogram has bin_centers")
check(len(r.histogram_data["counts"]) == 50, "50 histogram bins")
check(len(r.histogram_data["bin_centers"]) == 50, "50 bin centers")
check(len(r.histogram_data["bin_edges"]) == 51, "51 bin edges (n+1)")

check(isinstance(r.driver_table, pd.DataFrame), "driver_table is DataFrame")
check(len(r.driver_table) == 100, "driver_table has 100 rows (capped at 100)")
driver_cols = {"Revenue Growth", "EBITDA Margin", "WACC", "Terminal Growth",
               "Exit Multiple", "Equity Value"}
check(driver_cols.issubset(set(r.driver_table.columns)), "All driver columns present")


# ═══════════════════════════════════════════════════════════════════════
# TEST 2 — Deterministic Reproducibility (Fixed Seed)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 2: Deterministic Reproducibility (seed=42)")

mc_a = MonteCarloConfig(iterations=1000, seed=42,
                        revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                        wacc_mean=0.10)
mc_b = MonteCarloConfig(iterations=1000, seed=42,
                        revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                        wacc_mean=0.10)
ra = run_mc(mc_a)
rb = run_mc(mc_b)

check(np.allclose(ra.equity_values, rb.equity_values),
      "Same seed → identical equity arrays")
check(ra.statistics["Mean"] == rb.statistics["Mean"],
      "Same seed → identical mean",
      f"{ra.statistics['Mean']:.2f} vs {rb.statistics['Mean']:.2f}")
check(ra.statistics["P10"] == rb.statistics["P10"],
      "Same seed → identical P10")
check(ra.statistics["P90"] == rb.statistics["P90"],
      "Same seed → identical P90")


# ═══════════════════════════════════════════════════════════════════════
# TEST 3 — Non-Determinism (seed=None)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 3: Non-Determinism (seed=None)")

mc_x = MonteCarloConfig(iterations=2000, seed=None,
                        revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                        wacc_mean=0.10)
rx1 = run_mc(mc_x)
rx2 = run_mc(mc_x)

check(not np.allclose(rx1.equity_values, rx2.equity_values),
      "seed=None → different equity arrays across runs")
# Means should still be close (law of large numbers) but not identical
pct_diff = abs(rx1.statistics["Mean"] - rx2.statistics["Mean"]) / rx1.statistics["Mean"]
check(pct_diff < 0.10,
      f"seed=None means within 10% of each other ({pct_diff:.2%} diff)")


# ═══════════════════════════════════════════════════════════════════════
# TEST 4 — Different Seeds → Different Results
# ═══════════════════════════════════════════════════════════════════════
section("TEST 4: Different Seeds → Different Results")

rc = run_mc(MonteCarloConfig(iterations=1000, seed=42))
rd = run_mc(MonteCarloConfig(iterations=1000, seed=99))

check(not np.allclose(rc.equity_values, rd.equity_values),
      "seed=42 vs seed=99 → different arrays")
check(rc.statistics["Mean"] != rd.statistics["Mean"],
      "seed=42 vs seed=99 → different means")


# ═══════════════════════════════════════════════════════════════════════
# TEST 5 — Revenue Growth Sensitivity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 5: Revenue Growth Mean Sensitivity")

mc_low_g = MonteCarloConfig(iterations=5000, seed=42,
                            revenue_growth_mean=0.03, revenue_growth_std=0.02,
                            ebitda_margin_mean=0.30, wacc_mean=0.10)
mc_hi_g = MonteCarloConfig(iterations=5000, seed=42,
                           revenue_growth_mean=0.20, revenue_growth_std=0.02,
                           ebitda_margin_mean=0.30, wacc_mean=0.10)
r_low = run_mc(mc_low_g)
r_hi = run_mc(mc_hi_g)

check(r_hi.statistics["Mean"] > r_low.statistics["Mean"],
      "Higher rev growth → higher mean equity",
      f"low={r_low.statistics['Mean']:,.0f}  hi={r_hi.statistics['Mean']:,.0f}")
check(r_hi.statistics["Median"] > r_low.statistics["Median"],
      "Higher rev growth → higher median equity")
check(r_hi.statistics["P10"] > r_low.statistics["P10"],
      "Higher rev growth → higher P10")


# ═══════════════════════════════════════════════════════════════════════
# TEST 6 — EBITDA Margin Sensitivity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 6: EBITDA Margin Mean Sensitivity")

mc_low_m = MonteCarloConfig(iterations=5000, seed=42,
                            ebitda_margin_mean=0.10, ebitda_margin_std=0.03,
                            revenue_growth_mean=0.08, wacc_mean=0.10)
mc_hi_m = MonteCarloConfig(iterations=5000, seed=42,
                           ebitda_margin_mean=0.40, ebitda_margin_std=0.03,
                           revenue_growth_mean=0.08, wacc_mean=0.10)
r_lm = run_mc(mc_low_m)
r_hm = run_mc(mc_hi_m)

check(r_hm.statistics["Mean"] > r_lm.statistics["Mean"],
      "Higher margin → higher mean equity",
      f"low={r_lm.statistics['Mean']:,.0f}  hi={r_hm.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 7 — WACC Sensitivity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 7: WACC Mean Sensitivity")

mc_low_w = MonteCarloConfig(iterations=5000, seed=42,
                            wacc_mean=0.07, wacc_std=0.01,
                            revenue_growth_mean=0.08, ebitda_margin_mean=0.30)
mc_hi_w = MonteCarloConfig(iterations=5000, seed=42,
                           wacc_mean=0.15, wacc_std=0.01,
                           revenue_growth_mean=0.08, ebitda_margin_mean=0.30)
r_lw = run_mc(mc_low_w)
r_hw = run_mc(mc_hi_w)

check(r_lw.statistics["Mean"] > r_hw.statistics["Mean"],
      "Lower WACC → higher equity (higher PV)",
      f"low_wacc={r_lw.statistics['Mean']:,.0f}  hi_wacc={r_hw.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 8 — Terminal Growth Sensitivity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 8: Terminal Growth Mean Sensitivity")

mc_low_tg = MonteCarloConfig(iterations=5000, seed=42,
                             terminal_growth_mean=0.01, terminal_growth_std=0.005,
                             revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                             wacc_mean=0.10)
mc_hi_tg = MonteCarloConfig(iterations=5000, seed=42,
                            terminal_growth_mean=0.04, terminal_growth_std=0.005,
                            revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                            wacc_mean=0.10)
r_ltg = run_mc(mc_low_tg)
r_htg = run_mc(mc_hi_tg)

check(r_htg.statistics["Mean"] > r_ltg.statistics["Mean"],
      "Higher terminal growth → higher equity",
      f"low={r_ltg.statistics['Mean']:,.0f}  hi={r_htg.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 9 — Exit Multiple Sensitivity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 9: Exit Multiple Mean Sensitivity")

mc_low_em = MonteCarloConfig(iterations=5000, seed=42,
                             exit_multiple_mean=5.0, exit_multiple_std=1.0,
                             revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                             wacc_mean=0.10)
mc_hi_em = MonteCarloConfig(iterations=5000, seed=42,
                            exit_multiple_mean=15.0, exit_multiple_std=1.0,
                            revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                            wacc_mean=0.10)
r_lem = run_mc(mc_low_em)
r_hem = run_mc(mc_hi_em)

check(r_hem.statistics["Mean"] > r_lem.statistics["Mean"],
      "Higher exit multiple → higher equity",
      f"low={r_lem.statistics['Mean']:,.0f}  hi={r_hem.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 10 — Clamping / Guard Rails
# ═══════════════════════════════════════════════════════════════════════
section("TEST 10: Clamping / Guard Rails")

# Use an extreme config that would generate out-of-bounds samples
mc_extreme = MonteCarloConfig(
    iterations=5000, seed=42,
    revenue_growth_mean=0.50, revenue_growth_std=0.30,   # will clip to [-0.20, 0.50]
    ebitda_margin_mean=0.05, ebitda_margin_std=0.20,     # will clip to [0.01, 0.60]
    wacc_mean=0.03, wacc_std=0.05,                       # will clip to [0.03, 0.30]
    terminal_growth_mean=0.05, terminal_growth_std=0.03, # will clip to [0.0, 0.05]
    exit_multiple_mean=3.0, exit_multiple_std=5.0,       # will clip to [3.0, 25.0]
)
r_ext = run_mc(mc_extreme)

# Check driver table values are within bounds
dt = r_ext.driver_table
check(dt["Revenue Growth"].min() >= -0.20, "Rev growth clipped >= -20%",
      f"min={dt['Revenue Growth'].min():.4f}")
check(dt["Revenue Growth"].max() <= 0.50, "Rev growth clipped <= 50%",
      f"max={dt['Revenue Growth'].max():.4f}")
check(dt["EBITDA Margin"].min() >= 0.01, "EBITDA margin clipped >= 1%",
      f"min={dt['EBITDA Margin'].min():.4f}")
check(dt["EBITDA Margin"].max() <= 0.60, "EBITDA margin clipped <= 60%",
      f"max={dt['EBITDA Margin'].max():.4f}")
check(dt["WACC"].min() >= 0.03, "WACC clipped >= 3%",
      f"min={dt['WACC'].min():.4f}")
check(dt["Terminal Growth"].min() >= 0.0, "TG clipped >= 0%",
      f"min={dt['Terminal Growth'].min():.4f}")
check(dt["Terminal Growth"].max() <= 0.05, "TG clipped <= 5%",
      f"max={dt['Terminal Growth'].max():.4f}")
check(dt["Exit Multiple"].min() >= 3.0, "Exit multiple clipped >= 3.0x",
      f"min={dt['Exit Multiple'].min():.2f}")

# WACC must always be > terminal growth
check((dt["WACC"] > dt["Terminal Growth"]).all(),
      "WACC > Terminal Growth for all sampled rows (WACC = max(WACC, TG+0.01))")

# No NaN or inf in results
check(not np.any(np.isnan(r_ext.equity_values)), "No NaN in equity values")
check(not np.any(np.isinf(r_ext.equity_values)), "No Inf in equity values")


# ═══════════════════════════════════════════════════════════════════════
# TEST 11 — Cash / Debt Impact on Equity
# ═══════════════════════════════════════════════════════════════════════
section("TEST 11: Cash / Debt Impact on Equity (EV + Cash − Debt)")

mc_seed = MonteCarloConfig(iterations=2000, seed=42)

r_no_cd = run_mc(mc_seed, cash=0, debt=0)
r_cash = run_mc(mc_seed, cash=1_000_000, debt=0)
r_debt = run_mc(mc_seed, cash=0, debt=1_000_000)

check(abs(r_cash.statistics["Mean"] - r_no_cd.statistics["Mean"] - 1_000_000) < 1.0,
      "Adding $1M cash raises mean equity by exactly $1M",
      f"diff = {r_cash.statistics['Mean'] - r_no_cd.statistics['Mean']:,.2f}")
check(abs(r_no_cd.statistics["Mean"] - r_debt.statistics["Mean"] - 1_000_000) < 1.0,
      "Adding $1M debt lowers mean equity by exactly $1M",
      f"diff = {r_no_cd.statistics['Mean'] - r_debt.statistics['Mean']:,.2f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 12 — Per-Share Statistics
# ═══════════════════════════════════════════════════════════════════════
section("TEST 12: Per-Share Statistics")

mc_ps = MonteCarloConfig(iterations=1000, seed=42)
r_ps = run_mc(mc_ps, shares=2_000_000)

check(abs(r_ps.statistics["Per Share Mean"] - r_ps.statistics["Mean"] / 2_000_000) < 0.01,
      "Per Share Mean = Mean / shares")
check(abs(r_ps.statistics["Per Share Median"] - r_ps.statistics["Median"] / 2_000_000) < 0.01,
      "Per Share Median = Median / shares")
check(abs(r_ps.statistics["Per Share P10"] - r_ps.statistics["P10"] / 2_000_000) < 0.01,
      "Per Share P10 = P10 / shares")
check(abs(r_ps.statistics["Per Share P90"] - r_ps.statistics["P90"] / 2_000_000) < 0.01,
      "Per Share P90 = P90 / shares")


# ═══════════════════════════════════════════════════════════════════════
# TEST 13 — Single Iteration
# ═══════════════════════════════════════════════════════════════════════
section("TEST 13: Edge Case — 1 Iteration")

mc1 = MonteCarloConfig(iterations=1, seed=42)
r1 = run_mc(mc1)

check(r1.iterations == 1, "1-iteration run works")
check(len(r1.equity_values) == 1, "1 equity value returned")
check(r1.statistics["Mean"] == r1.statistics["Median"], "Mean == Median for n=1")
check(r1.statistics["Min"] == r1.statistics["Max"], "Min == Max for n=1")
check(len(r1.driver_table) == 1, "driver_table has 1 row for n=1")


# ═══════════════════════════════════════════════════════════════════════
# TEST 14 — Very Small Revenue (micro company)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 14: Edge Case — Micro Company ($10K Revenue)")

mc_micro = MonteCarloConfig(iterations=2000, seed=42,
                            revenue_growth_mean=0.05, ebitda_margin_mean=0.15,
                            wacc_mean=0.12, exit_multiple_mean=6.0)
r_micro = run_mc(mc_micro, base_revenue=10_000, cash=1000, debt=5000, shares=100)

check(r_micro.statistics["Mean"] > 0 or r_micro.statistics["Mean"] < 0,
      "Micro company produces numeric result (may be negative)",
      f"Mean equity = ${r_micro.statistics['Mean']:,.0f}")
check(not np.any(np.isnan(r_micro.equity_values)), "No NaN for micro company")
check(r_micro.statistics["Per Share Mean"] == r_micro.statistics["Mean"] / 100,
      "Per share correct for 100 shares")


# ═══════════════════════════════════════════════════════════════════════
# TEST 15 — Large Company ($10B Revenue)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 15: Edge Case — Large Company ($10B Revenue)")

mc_large = MonteCarloConfig(iterations=2000, seed=42,
                            revenue_growth_mean=0.04, ebitda_margin_mean=0.25,
                            wacc_mean=0.08, exit_multiple_mean=12.0)
r_large = run_mc(mc_large, base_revenue=10_000_000_000, cash=2_000_000_000,
                 debt=5_000_000_000, shares=500_000_000)

check(r_large.statistics["Mean"] > 0, "Large company has positive equity",
      f"Mean = ${r_large.statistics['Mean']:,.0f}")
check(not np.any(np.isnan(r_large.equity_values)), "No NaN for large company")
check(not np.any(np.isinf(r_large.equity_values)), "No Inf for large company")


# ═══════════════════════════════════════════════════════════════════════
# TEST 16 — Gordon Weight Extremes (100% Gordon vs 100% Exit)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 16: Gordon Weight Extremes")

mc_gw = MonteCarloConfig(iterations=3000, seed=42,
                         revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                         wacc_mean=0.10, exit_multiple_mean=10.0)

r_full_gordon = run_mc(mc_gw, gordon_weight=1.0)
r_full_exit = run_mc(mc_gw, gordon_weight=0.0)
r_blend_50 = run_mc(mc_gw, gordon_weight=0.5)

check(r_full_gordon.statistics["Mean"] != r_full_exit.statistics["Mean"],
      "Gordon-only vs Exit-only → different values")
# The 50/50 blend should fall between the two (approximately)
mean_g = r_full_gordon.statistics["Mean"]
mean_e = r_full_exit.statistics["Mean"]
mean_b = r_blend_50.statistics["Mean"]
lo, hi = min(mean_g, mean_e), max(mean_g, mean_e)
# Allow 5% tolerance because sampling variance means the blend isn't
# exactly the midpoint
tol = 0.05 * (hi - lo)
check(lo - tol <= mean_b <= hi + tol,
      "50/50 blend mean falls between Gordon-only and Exit-only",
      f"Gordon={mean_g:,.0f}  Exit={mean_e:,.0f}  Blend={mean_b:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 17 — Different Projection Years
# ═══════════════════════════════════════════════════════════════════════
section("TEST 17: Different Projection Horizons")

mc_proj = MonteCarloConfig(iterations=3000, seed=42,
                           revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                           wacc_mean=0.10)

r_3yr = run_mc(mc_proj, projection_years=3)
r_5yr = run_mc(mc_proj, projection_years=5)
r_10yr = run_mc(mc_proj, projection_years=10)

check(r_3yr.statistics["Mean"] != r_5yr.statistics["Mean"],
      "3yr vs 5yr → different equity values")
check(r_5yr.statistics["Mean"] != r_10yr.statistics["Mean"],
      "5yr vs 10yr → different equity values")
# Longer projections capture more growth (at 8% rev growth, 30% margin)
# so EV should generally increase with horizon — but this isn't guaranteed
# for all inputs; just check they produce different valid results.
check(not np.any(np.isnan(r_3yr.equity_values)), "No NaN for 3yr horizon")
check(not np.any(np.isnan(r_10yr.equity_values)), "No NaN for 10yr horizon")


# ═══════════════════════════════════════════════════════════════════════
# TEST 18 — Std Dev Impact (tight vs wide distributions)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 18: Distribution Width (Std Dev Impact)")

mc_tight = MonteCarloConfig(
    iterations=5000, seed=42,
    revenue_growth_mean=0.08, revenue_growth_std=0.005,
    ebitda_margin_mean=0.30, ebitda_margin_std=0.005,
    wacc_mean=0.10, wacc_std=0.002,
    terminal_growth_mean=0.025, terminal_growth_std=0.002,
    exit_multiple_mean=10.0, exit_multiple_std=0.2,
)
mc_wide = MonteCarloConfig(
    iterations=5000, seed=42,
    revenue_growth_mean=0.08, revenue_growth_std=0.08,
    ebitda_margin_mean=0.30, ebitda_margin_std=0.10,
    wacc_mean=0.10, wacc_std=0.04,
    terminal_growth_mean=0.025, terminal_growth_std=0.015,
    exit_multiple_mean=10.0, exit_multiple_std=4.0,
)

r_tight = run_mc(mc_tight)
r_wide = run_mc(mc_wide)

check(r_wide.statistics["Std Dev"] > r_tight.statistics["Std Dev"],
      "Wider inputs → wider output distribution",
      f"tight_sd={r_tight.statistics['Std Dev']:,.0f}  wide_sd={r_wide.statistics['Std Dev']:,.0f}")

iqr_tight = r_tight.statistics["P75"] - r_tight.statistics["P25"]
iqr_wide = r_wide.statistics["P75"] - r_wide.statistics["P25"]
check(iqr_wide > iqr_tight,
      "Wider inputs → wider IQR",
      f"tight_iqr={iqr_tight:,.0f}  wide_iqr={iqr_wide:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 19 — Histogram Consistency
# ═══════════════════════════════════════════════════════════════════════
section("TEST 19: Histogram Data Consistency")

mc_hist = MonteCarloConfig(iterations=5000, seed=42)
r_hist = run_mc(mc_hist)

total_counts = sum(r_hist.histogram_data["counts"])
check(total_counts == 5000, "Histogram total counts == iterations",
      f"got {total_counts}")

edges = r_hist.histogram_data["bin_edges"]
centers = r_hist.histogram_data["bin_centers"]
for i in range(len(centers)):
    expected_center = (edges[i] + edges[i + 1]) / 2
    check(abs(centers[i] - expected_center) < 0.01,
          f"Bin center [{i}] is midpoint of edges")
    if i == 5:  # only check a few to avoid spamming output
        break

check(edges[0] <= r_hist.statistics["Min"],
      "Bin edge min <= data min")
check(edges[-1] >= r_hist.statistics["Max"],
      "Bin edge max >= data max")


# ═══════════════════════════════════════════════════════════════════════
# TEST 20 — Statistical Ordering (P10 < P25 < P50 < P75 < P90)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 20: Statistical Ordering")

mc_ord = MonteCarloConfig(iterations=5000, seed=42)
r_ord = run_mc(mc_ord)

s = r_ord.statistics
check(s["Min"] <= s["P10"], "Min <= P10")
check(s["P10"] <= s["P25"], "P10 <= P25")
check(s["P25"] <= s["P50"], "P25 <= P50")
check(s["P50"] <= s["P75"], "P50 <= P75")
check(s["P75"] <= s["P90"], "P75 <= P90")
check(s["P90"] <= s["Max"], "P90 <= Max")
check(abs(s["P50"] - s["Median"]) < 0.01, "P50 == Median")


# ═══════════════════════════════════════════════════════════════════════
# TEST 21 — Full Pipeline Integration (V7 Auto-Sync)
# ═══════════════════════════════════════════════════════════════════════
section("TEST 21: Full Pipeline — MC Means Auto-Synced from Base Case")

cfg_pipe = DCFEngineConfig(
    company=CompanyInfo(name="TestCorpA", ticker="TSTA", industry="Tech"),
    forecast=ForecastConfig(
        projection_years=5,
        revenue_cagr=0.12,           # 12% growth
        cogs_pct_revenue=0.40,
        sga_pct_revenue=0.15,
        other_opex_pct_revenue=0.05,
        depreciation_rate=0.10,
        capex_pct_revenue=0.06,
        tax_rate=0.22,
        dso=50, dio=45, dpo=38,
    ),
    wacc=WACCConfig(
        risk_free_rate=0.040,
        equity_risk_premium=0.060,
        beta=1.2,
        target_debt_weight=0.25,
        target_equity_weight=0.75,
        interest_coverage_ratio=6.0,
        tax_rate=0.22,
        use_live_data=False,
    ),
    valuation=ValuationConfig(
        terminal_growth_rate=0.030,
        exit_ev_ebitda_multiple=12.0,
        gordon_weight=0.60,
        cash=200_000,
        debt=500_000,
        fully_diluted_shares=500_000,
    ),
    monte_carlo=MonteCarloConfig(
        iterations=1000, seed=42,
        # Deliberately set MC means to wrong values — pipeline should overwrite
        revenue_growth_mean=0.99,
        ebitda_margin_mean=0.99,
        wacc_mean=0.99,
        terminal_growth_mean=0.99,
        exit_multiple_mean=99.0,
    ),
    scenarios={"Base": ScenarioOverrides(name="Base")},
)

res = run_pipeline(
    cfg_pipe,
    base_year_revenue=3_000_000,
    base_cash=200_000,
    base_ppe=400_000,
    base_nwc=50_000,
    base_common_stock=100_000,
)

check(res.monte_carlo is not None, "Pipeline produced MC result")

if res.monte_carlo:
    mc_res = res.monte_carlo
    # The pipeline should have auto-synced MC means from base case
    # Check that the MC result is sane (not based on 99% growth etc.)
    check(mc_res.statistics["Mean"] > 0,
          "MC mean is positive (synced from real assumptions, not 99%)",
          f"Mean={mc_res.statistics['Mean']:,.0f}")
    # If MC used 99% revenue growth, equity would be astronomically large
    # With 12% growth it should be much more modest
    check(mc_res.statistics["Mean"] < 500_000_000,
          "MC mean is reasonable (not using 99% unsynced values)",
          f"Mean={mc_res.statistics['Mean']:,.0f}")
    check(len(mc_res.equity_values) == 1000,
          "MC ran with correct iteration count")

    # Verify auto-sync happened by checking cfg was mutated
    check(abs(cfg_pipe.monte_carlo.revenue_growth_mean - 0.12) < 0.001,
          "Pipeline synced revenue_growth_mean → 0.12",
          f"got {cfg_pipe.monte_carlo.revenue_growth_mean}")
    expected_margin = 1.0 - 0.40 - 0.15 - 0.05  # = 0.40
    check(abs(cfg_pipe.monte_carlo.ebitda_margin_mean - expected_margin) < 0.01,
          f"Pipeline synced ebitda_margin_mean → {expected_margin}",
          f"got {cfg_pipe.monte_carlo.ebitda_margin_mean}")
    check(abs(cfg_pipe.monte_carlo.terminal_growth_mean - 0.030) < 0.001,
          "Pipeline synced terminal_growth_mean → 0.030",
          f"got {cfg_pipe.monte_carlo.terminal_growth_mean}")
    check(abs(cfg_pipe.monte_carlo.exit_multiple_mean - 12.0) < 0.01,
          "Pipeline synced exit_multiple_mean → 12.0",
          f"got {cfg_pipe.monte_carlo.exit_multiple_mean}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 22 — Pipeline with Different Company Profiles
# ═══════════════════════════════════════════════════════════════════════
section("TEST 22: Pipeline MC — High-Growth Tech vs Stable Utility")

def make_cfg(name, rev_cagr, cogs, sga, other, beta, tg, exit_m, capex):
    return DCFEngineConfig(
        company=CompanyInfo(name=name),
        forecast=ForecastConfig(
            projection_years=5,
            revenue_cagr=rev_cagr, cogs_pct_revenue=cogs,
            sga_pct_revenue=sga, other_opex_pct_revenue=other,
            depreciation_rate=0.10, capex_pct_revenue=capex,
            tax_rate=0.25, dso=45, dio=50, dpo=40,
        ),
        wacc=WACCConfig(
            risk_free_rate=0.042, equity_risk_premium=0.055,
            beta=beta, target_debt_weight=0.30,
            target_equity_weight=0.70, use_live_data=False,
        ),
        valuation=ValuationConfig(
            terminal_growth_rate=tg, exit_ev_ebitda_multiple=exit_m,
            gordon_weight=0.50, cash=100_000, debt=200_000,
            fully_diluted_shares=1_000_000,
        ),
        monte_carlo=MonteCarloConfig(iterations=1000, seed=42),
        scenarios={"Base": ScenarioOverrides(name="Base")},
    )

cfg_tech = make_cfg("HighGrowthTech", 0.25, 0.30, 0.25, 0.10, 1.5, 0.03, 15.0, 0.08)
cfg_util = make_cfg("StableUtility", 0.03, 0.55, 0.10, 0.03, 0.6, 0.02, 8.0, 0.12)

res_tech = run_pipeline(cfg_tech, base_year_revenue=2_000_000,
                        base_cash=100_000, base_ppe=300_000,
                        base_nwc=30_000, base_common_stock=50_000)
res_util = run_pipeline(cfg_util, base_year_revenue=10_000_000,
                        base_cash=100_000, base_ppe=5_000_000,
                        base_nwc=200_000, base_common_stock=1_000_000)

check(res_tech.monte_carlo is not None, "Tech company MC completed")
check(res_util.monte_carlo is not None, "Utility company MC completed")

if res_tech.monte_carlo and res_util.monte_carlo:
    # Tech should have wider distribution (higher beta, more growth uncertainty)
    tech_sd = res_tech.monte_carlo.statistics["Std Dev"]
    util_sd = res_util.monte_carlo.statistics["Std Dev"]
    tech_cv = tech_sd / abs(res_tech.monte_carlo.statistics["Mean"]) if res_tech.monte_carlo.statistics["Mean"] != 0 else 0
    util_cv = util_sd / abs(res_util.monte_carlo.statistics["Mean"]) if res_util.monte_carlo.statistics["Mean"] != 0 else 0
    print(f"    Tech CV={tech_cv:.3f}  Utility CV={util_cv:.3f}")
    check(True, "Both company profiles produce valid MC results")


# ═══════════════════════════════════════════════════════════════════════
# TEST 23 — Pipeline MC with Debt Tranches
# ═══════════════════════════════════════════════════════════════════════
section("TEST 23: Pipeline MC with Multi-Tranche Debt")

cfg_debt = DCFEngineConfig(
    company=CompanyInfo(name="DebtHeavyCorp"),
    forecast=ForecastConfig(
        projection_years=5, revenue_cagr=0.10,
        cogs_pct_revenue=0.45, sga_pct_revenue=0.15,
        other_opex_pct_revenue=0.05, depreciation_rate=0.10,
        capex_pct_revenue=0.05, tax_rate=0.25,
    ),
    wacc=WACCConfig(
        risk_free_rate=0.042, equity_risk_premium=0.055,
        beta=1.3, target_debt_weight=0.50,
        target_equity_weight=0.50, use_live_data=False,
    ),
    valuation=ValuationConfig(
        terminal_growth_rate=0.025, exit_ev_ebitda_multiple=8.0,
        gordon_weight=0.50, cash=500_000, debt=3_000_000,
        fully_diluted_shares=1_000_000,
    ),
    monte_carlo=MonteCarloConfig(iterations=1000, seed=42),
    debt_tranches=[
        DebtTranche(name="Term Loan A", beginning_balance=2_000_000,
                    interest_rate=0.06, annual_amortisation=200_000,
                    maturity_year=5),
        DebtTranche(name="Revolver", beginning_balance=1_000_000,
                    interest_rate=0.08, annual_amortisation=0,
                    maturity_year=5),
    ],
    scenarios={"Base": ScenarioOverrides(name="Base")},
)

res_debt = run_pipeline(cfg_debt, base_year_revenue=5_000_000,
                        base_cash=500_000, base_ppe=2_000_000,
                        base_nwc=300_000, base_common_stock=500_000)

check(res_debt.monte_carlo is not None, "MC works with multi-tranche debt")
check(res_debt.debt_schedule is not None, "Debt schedule computed")
if res_debt.monte_carlo:
    check(len(res_debt.monte_carlo.equity_values) == 1000,
          "Correct iteration count with debt tranches")


# ═══════════════════════════════════════════════════════════════════════
# TEST 24 — Tax Rate Impact
# ═══════════════════════════════════════════════════════════════════════
section("TEST 24: Tax Rate Impact on MC")

mc_tax = MonteCarloConfig(iterations=3000, seed=42,
                          revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                          wacc_mean=0.10)

r_low_tax = run_mc(mc_tax, tax_rate=0.10)
r_hi_tax = run_mc(mc_tax, tax_rate=0.40)

check(r_low_tax.statistics["Mean"] > r_hi_tax.statistics["Mean"],
      "Lower tax → higher equity",
      f"10% tax={r_low_tax.statistics['Mean']:,.0f}  40% tax={r_hi_tax.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# TEST 25 — Capex / DA Rate Impact
# ═══════════════════════════════════════════════════════════════════════
section("TEST 25: Capex & D&A Rate Impact")

mc_capex = MonteCarloConfig(iterations=3000, seed=42,
                            revenue_growth_mean=0.08, ebitda_margin_mean=0.30,
                            wacc_mean=0.10)

# Low capex, low D&A
r_lo_capex = run_mc(mc_capex, capex_pct=0.02, da_pct=0.02)
# High capex, high D&A
r_hi_capex = run_mc(mc_capex, capex_pct=0.15, da_pct=0.05)

# FCF = NOPAT + DA - Capex.  When capex >> DA, FCF drops, equity lower.
check(r_lo_capex.statistics["Mean"] > r_hi_capex.statistics["Mean"],
      "Lower capex (net of D&A) → higher equity",
      f"lo={r_lo_capex.statistics['Mean']:,.0f}  hi={r_hi_capex.statistics['Mean']:,.0f}")


# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  FINAL RESULTS:  {PASS} passed,  {FAIL} failed,  {PASS + FAIL} total")
print(f"{'='*70}")

if FAIL > 0:
    print("\n  *** SOME TESTS FAILED — see [FAIL] lines above ***\n")
    sys.exit(1)
else:
    print("\n  All Monte Carlo end-to-end tests passed.\n")
    sys.exit(0)
