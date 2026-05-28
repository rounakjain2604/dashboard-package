from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass
class SourceFact:
    ticker: str
    cik: str
    company_name: str
    account: str
    concept: str
    value: float
    unit: str
    form: str
    filed: str
    period_end: str
    fiscal_year: str | None = None
    fiscal_period: str | None = None
    accession: str | None = None
    frame: str | None = None
    source_url: str | None = None

@dataclass
class CompanySnapshot:
    ticker: str
    cik: str
    company_name: str
    latest_period: str | None
    financials: pd.DataFrame
    facts: list[SourceFact]
    key_metrics: dict[str, float | None]
    warnings: list[str]

@dataclass
class AssumptionBuildResult:
    payload: dict
    base_values: dict[str, float]
    source_map: list[SourceFact]
    warnings: list[str]


@dataclass
class FilingChange:
    """A detected numeric change between filing periods."""
    category: str           # "revenue", "margin", "debt", etc.
    account: str            # friendly account name
    latest_value: float | None
    prior_value: float | None
    absolute_change: float | None
    percent_change: float | None
    severity: str           # "low", "medium", "high"
    valuation_impact: str   # human-readable impact statement
    source_fact_latest: dict | None = None   # single-source metrics (Revenue, Cash, etc.)
    source_fact_prior: dict | None = None
    source_components: list[dict] | None = None  # composite metrics (Gross Margin, FCF, etc.)


@dataclass
class RedFlag:
    """A detected risk signal from filing data or metadata."""
    code: str
    severity: str           # "medium", "high"
    title: str
    detail: str
    source_type: str        # "xbrl", "metadata"
    affected_assumptions: list[str] | None = None
    source_url: str | None = None
