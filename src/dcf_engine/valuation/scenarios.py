"""
Scenario manager — runs the full model under Base / Bull / Bear cases.

Each scenario gets its own 3-statement build, DCF, and valuation output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from ..config import DCFEngineConfig, ScenarioOverrides


@dataclass
class ScenarioResult:
    name: str
    income_statement: pd.DataFrame
    balance_sheet: pd.DataFrame
    cash_flow: pd.DataFrame
    fcf_table: pd.DataFrame
    dcf_summary: dict          # Key metrics: EV, Equity, Price, WACC, etc.


@dataclass
class ScenarioComparisonResult:
    scenarios: Dict[str, ScenarioResult]
    comparison: pd.DataFrame   # Side-by-side key metrics


def build_scenario_comparison(scenarios: Dict[str, ScenarioResult]) -> ScenarioComparisonResult:
    """
    Build a side-by-side comparison table from completed scenario runs.
    """
    if not scenarios:
        return ScenarioComparisonResult(scenarios={}, comparison=pd.DataFrame())

    metrics = [
        "WACC", "Terminal Growth", "Exit Multiple",
        "EV (Gordon)", "EV (Exit)", "EV (Blended)",
        "Equity (Gordon)", "Equity (Exit)", "Equity (Blended)",
        "Price (Gordon)", "Price (Exit)", "Price (Blended)",
        "Revenue Yr5", "EBITDA Yr5", "EBITDA Margin Yr5",
        "Total FCF (5yr)", "TV % of EV",
    ]

    data = {}
    for name, result in scenarios.items():
        s = result.dcf_summary
        data[name] = {m: s.get(m, "") for m in metrics}

    comparison = pd.DataFrame(data)
    comparison.index = metrics
    comparison.index.name = "Metric"

    return ScenarioComparisonResult(scenarios=scenarios, comparison=comparison)
