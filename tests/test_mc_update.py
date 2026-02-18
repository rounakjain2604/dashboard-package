"""Quick test: does MC produce different results with different inputs?"""
from src.dcf_engine.config import MonteCarloConfig
from src.dcf_engine.valuation.monte_carlo import run_monte_carlo

# Test 1: rev_g=8%, seed=None
mc1 = MonteCarloConfig(iterations=1000, seed=None,
    revenue_growth_mean=0.08, ebitda_margin_mean=0.42, wacc_mean=0.09)
r1 = run_monte_carlo(1175357, 0.42, 0.09, 0.025, 10.0, 5, mc1,
    0.25, 0.04, 0.10, 25000, 0, 1000000, 0.5)

# Test 2: rev_g=15%, seed=None
mc2 = MonteCarloConfig(iterations=1000, seed=None,
    revenue_growth_mean=0.15, ebitda_margin_mean=0.42, wacc_mean=0.09)
r2 = run_monte_carlo(1175357, 0.42, 0.09, 0.025, 10.0, 5, mc2,
    0.25, 0.04, 0.10, 25000, 0, 1000000, 0.5)

# Test 3: rev_g=8%, seed=42 (FIXED)
mc3 = MonteCarloConfig(iterations=1000, seed=42,
    revenue_growth_mean=0.08, ebitda_margin_mean=0.42, wacc_mean=0.09)
r3 = run_monte_carlo(1175357, 0.42, 0.09, 0.025, 10.0, 5, mc3,
    0.25, 0.04, 0.10, 25000, 0, 1000000, 0.5)

# Test 4: rev_g=8%, seed=42 again (should be IDENTICAL to test 3)
mc4 = MonteCarloConfig(iterations=1000, seed=42,
    revenue_growth_mean=0.08, ebitda_margin_mean=0.42, wacc_mean=0.09)
r4 = run_monte_carlo(1175357, 0.42, 0.09, 0.025, 10.0, 5, mc4,
    0.25, 0.04, 0.10, 25000, 0, 1000000, 0.5)

# Test 5: rev_g=15%, seed=42 (FIXED but different mean)
mc5 = MonteCarloConfig(iterations=1000, seed=42,
    revenue_growth_mean=0.15, ebitda_margin_mean=0.42, wacc_mean=0.09)
r5 = run_monte_carlo(1175357, 0.42, 0.09, 0.025, 10.0, 5, mc5,
    0.25, 0.04, 0.10, 25000, 0, 1000000, 0.5)

print("=== MC UPDATE TEST ===")
print(f"Test 1 (seed=None, rev_g= 8%): Mean={r1.statistics['Mean']:>12,.0f}")
print(f"Test 2 (seed=None, rev_g=15%): Mean={r2.statistics['Mean']:>12,.0f}")
print(f"Test 3 (seed=42,   rev_g= 8%): Mean={r3.statistics['Mean']:>12,.0f}")
print(f"Test 4 (seed=42,   rev_g= 8%): Mean={r4.statistics['Mean']:>12,.0f}  << should match Test 3")
print(f"Test 5 (seed=42,   rev_g=15%): Mean={r5.statistics['Mean']:>12,.0f}  << should differ from Test 3")
print()
print(f"MonteCarloConfig DEFAULT seed = {MonteCarloConfig().seed}")
print(f"  ^^^ If this is 42, CLI/config-file runs always get same random draws!")
