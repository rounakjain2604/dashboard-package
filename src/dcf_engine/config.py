"""
Configuration dataclasses for the IB-Grade DCF Engine.

Every tunable parameter lives here as a typed dataclass field so the
entire model can be serialised to / from JSON and reproduced exactly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Literal, Optional


# ── Type aliases ──────────────────────────────────────────────────────
DiscountConvention = Literal["mid_year", "end_period"]
TerminalMethod = Literal["gordon_growth", "exit_multiple", "both"]
RevenueMethod = Literal["cagr", "yoy", "manual"]
CostMethod = Literal["pct_revenue", "fixed_inflation", "historical_avg"]
CapexMethod = Literal["pct_revenue", "fixed"]


# ── Scenario ──────────────────────────────────────────────────────────
@dataclass
class ScenarioOverrides:
    """Per-scenario adjustments layered on top of base assumptions."""
    name: str = "Base"
    revenue_growth_override: Optional[float] = None        # absolute override (e.g. 0.05 = 5%)
    revenue_multiplier: float = 1.0                        # multiplicative tweak
    ebitda_margin_override: Optional[float] = None         # absolute EBITDA margin
    margin_delta_bps: float = 0.0                          # additive bps shift on margin
    wacc_override: Optional[float] = None
    terminal_growth_override: Optional[float] = None
    exit_multiple_override: Optional[float] = None
    working_capital_days_delta: float = 0.0
    capex_multiplier: float = 1.0


# ── Debt Tranche ──────────────────────────────────────────────────────
@dataclass
class DebtTranche:
    """A single tranche of debt with its own amortisation schedule."""
    name: str = "Term Loan A"
    beginning_balance: float = 0.0
    interest_rate: float = 0.06
    annual_amortisation: float = 0.0           # mandatory annual repayment
    maturity_year: int = 5                     # year index (1-based) when bullet matures
    optional_prepayment: float = 0.0           # optional annual prepayment
    cash_sweep_pct: float = 0.0                # % of excess cash flow swept


# ── Forecast ──────────────────────────────────────────────────────────
@dataclass
class ForecastConfig:
    """Base-case forecast assumptions."""
    projection_years: int = 5
    historical_years: int = 3

    # Revenue
    revenue_method: RevenueMethod = "cagr"
    revenue_cagr: float = 0.08
    revenue_yoy: List[float] = field(default_factory=lambda: [0.08, 0.07, 0.06, 0.05, 0.05])
    revenue_manual: Dict[int, float] = field(default_factory=dict)

    # COGS
    cogs_method: CostMethod = "pct_revenue"
    cogs_pct_revenue: float = 0.45
    cogs_yoy: List[float] = field(default_factory=list)

    # SGA / Operating Expenses
    sga_method: CostMethod = "pct_revenue"
    sga_pct_revenue: float = 0.20

    # Other OpEx (R&D, etc.)
    other_opex_pct_revenue: float = 0.05

    # D&A
    depreciation_rate: float = 0.10            # % of beginning PP&E
    amortisation_pct_revenue: float = 0.005

    # Capex
    capex_method: CapexMethod = "pct_revenue"
    capex_pct_revenue: float = 0.04
    capex_manual: Dict[int, float] = field(default_factory=dict)

    # Working Capital (days)
    dso: float = 45.0
    dio: float = 50.0
    dpo: float = 40.0
    prepaid_pct_revenue: float = 0.005
    accrued_pct_revenue: float = 0.01
    other_current_assets_pct_revenue: float = 0.005
    other_current_liabilities_pct_revenue: float = 0.005

    # Tax
    tax_rate: float = 0.25

    # Dividends
    dividend_payout_ratio: float = 0.0


# ── WACC ──────────────────────────────────────────────────────────────
@dataclass
class WACCConfig:
    risk_free_rate: float = 0.042              # 10-yr Treasury
    equity_risk_premium: float = 0.055         # Damodaran ERP
    beta: float = 1.1
    size_premium: float = 0.0                  # Duff & Phelps
    country_risk_premium: float = 0.0
    target_debt_weight: float = 0.30
    target_equity_weight: float = 0.70
    interest_coverage_ratio: float = 5.0       # for synthetic rating
    tax_rate: float = 0.25
    use_live_data: bool = True                 # attempt live pulls


# ── Valuation ─────────────────────────────────────────────────────────
@dataclass
class ValuationConfig:
    terminal_method: TerminalMethod = "both"
    terminal_growth_rate: float = 0.025
    exit_ev_ebitda_multiple: float = 10.0
    discount_convention: DiscountConvention = "mid_year"
    gordon_weight: float = 0.50                # blend weight
    cash: float = 0.0
    debt: float = 0.0
    minority_interest: float = 0.0
    preferred_stock: float = 0.0
    fully_diluted_shares: float = 1_000_000.0
    gdp_growth_cap: float = 0.035
    terminal_spread_floor_bps: float = 50.0


# ── Monte Carlo ───────────────────────────────────────────────────────
@dataclass
class MonteCarloConfig:
    iterations: int = 10_000
    revenue_growth_mean: float = 0.08
    revenue_growth_std: float = 0.03
    ebitda_margin_mean: float = 0.20
    ebitda_margin_std: float = 0.05
    wacc_mean: float = 0.10
    wacc_std: float = 0.02
    terminal_growth_mean: float = 0.025
    terminal_growth_std: float = 0.01
    exit_multiple_mean: float = 10.0
    exit_multiple_std: float = 2.0
    seed: Optional[int] = 42


# ── Sensitivity ───────────────────────────────────────────────────────
@dataclass
class SensitivityConfig:
    wacc_range: List[float] = field(
        default_factory=lambda: [-0.02, -0.01, 0.0, 0.01, 0.02]
    )
    terminal_growth_range: List[float] = field(
        default_factory=lambda: [-0.01, -0.005, 0.0, 0.005, 0.01]
    )
    revenue_growth_range: List[float] = field(
        default_factory=lambda: [-0.03, -0.015, 0.0, 0.015, 0.03]
    )
    ebitda_margin_range: List[float] = field(
        default_factory=lambda: [-0.05, -0.025, 0.0, 0.025, 0.05]
    )


# ── Comparable Companies ─────────────────────────────────────────────
@dataclass
class CompsConfig:
    peer_tickers: List[str] = field(default_factory=list)
    multiples: List[str] = field(
        default_factory=lambda: ["EV/Revenue", "EV/EBITDA", "P/E"]
    )


# ── Company Info ──────────────────────────────────────────────────────
@dataclass
class CompanyInfo:
    name: str = "Target Company"
    ticker: Optional[str] = None
    cik: Optional[str] = None
    industry: str = ""
    description: str = ""
    fiscal_year_end: str = "December"
    currency: str = "USD"
    analyst_name: str = "DCF Engine"
    report_date: str = ""


# ── Master Config ─────────────────────────────────────────────────────
@dataclass
class DCFEngineConfig:
    """Top-level configuration tying every sub-config together."""
    company: CompanyInfo = field(default_factory=CompanyInfo)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    wacc: WACCConfig = field(default_factory=WACCConfig)
    valuation: ValuationConfig = field(default_factory=ValuationConfig)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    sensitivity: SensitivityConfig = field(default_factory=SensitivityConfig)
    comps: CompsConfig = field(default_factory=CompsConfig)
    debt_tranches: List[DebtTranche] = field(default_factory=list)
    scenarios: Dict[str, ScenarioOverrides] = field(
        default_factory=lambda: {
            "Base": ScenarioOverrides(name="Base"),
            "Bull": ScenarioOverrides(
                name="Bull",
                revenue_multiplier=1.10,
                margin_delta_bps=200,
                working_capital_days_delta=-3,
            ),
            "Bear": ScenarioOverrides(
                name="Bear",
                revenue_multiplier=0.90,
                margin_delta_bps=-200,
                working_capital_days_delta=4,
            ),
        }
    )

    # ── Serialisation helpers ────────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def from_json(cls, path: str | Path) -> "DCFEngineConfig":
        raw = json.loads(Path(path).read_text())
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, d: dict) -> "DCFEngineConfig":
        company = CompanyInfo(**d.get("company", {}))
        forecast = ForecastConfig(**d.get("forecast", {}))
        wacc = WACCConfig(**d.get("wacc", {}))
        valuation = ValuationConfig(**d.get("valuation", {}))
        mc = MonteCarloConfig(**d.get("monte_carlo", {}))
        sens = SensitivityConfig(**d.get("sensitivity", {}))
        comps = CompsConfig(**d.get("comps", {}))
        tranches = [DebtTranche(**t) for t in d.get("debt_tranches", [])]
        scenarios = {
            k: ScenarioOverrides(**v) if isinstance(v, dict) else v
            for k, v in d.get("scenarios", {}).items()
        }
        return cls(
            company=company,
            forecast=forecast,
            wacc=wacc,
            valuation=valuation,
            monte_carlo=mc,
            sensitivity=sens,
            comps=comps,
            debt_tranches=tranches,
            scenarios=scenarios,
        )
