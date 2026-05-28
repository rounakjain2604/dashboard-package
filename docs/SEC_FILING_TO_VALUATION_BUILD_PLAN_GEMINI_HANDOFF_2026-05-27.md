# Trinsic Filing-To-Valuation Build Plan

Date: 2026-05-27

Audience: a low-cost coding model such as Gemini Flash that must be given small, explicit, testable tasks.

Repository reviewed: `D:\Rounak\Study\Ideas\dashboard_package`

## 0. Final Product Definition

The product is not a generic DCF SaaS.

The product is:

> A valuation-aware SEC filing radar for retail investors, students, creators, and solo analysts.

The app should let a user enter a ticker and answer:

1. What changed in the latest SEC filing?
2. Which changes matter for valuation assumptions?
3. What does the current stock price imply?
4. Are the model assumptions reasonable or dangerous?
5. Which watchlist companies actually changed since the last filing?
6. Can the user export a source-linked mini report or premium Excel DCF workbook?

The existing DCF engine remains the calculation backend. The new product wraps it with SEC source mapping, filing-change detection, reverse DCF, assumption QA, red flags, watchlists, public reports, and paid exports.

## 1. Current Codebase Read

### 1.1 What exists now

The repo already has a working Flask plus Python valuation app:

- `dashboard_api.py`
  - Flask app.
  - Routes:
    - `/`
    - `/dashboard`
    - `/samples/<ticker>`
    - `/download/sample/<ticker>`
    - `/api/version`
    - `/api/run`
    - `/api/export-excel`
    - `/api/request-model`
    - `/api/configs`
    - `/api/config/<filename>`
    - `/api/data-files`
    - `/api/data-file-base-values/<filename>`
  - Builds `DCFEngineConfig` from dashboard JSON.
  - Runs `run_pipeline`.
  - Serializes the DCF pipeline to JSON.
  - Generates Excel exports.

- `src/dcf_engine/pipeline.py`
  - Core 16-step engine.
  - Builds income statement, working capital, capex, debt, cash flow, balance sheet, WACC, DCF, scenarios, Monte Carlo, sensitivity, tornado, comps, Excel, PDF.

- `src/dcf_engine/config.py`
  - Dataclasses for all model assumptions.
  - Important objects:
    - `DCFEngineConfig`
    - `CompanyInfo`
    - `ForecastConfig`
    - `WACCConfig`
    - `ValuationConfig`
    - `MonteCarloConfig`
    - `SensitivityConfig`
    - `CompsConfig`
    - `DebtTranche`
    - `ScenarioOverrides`

- `src/dcf_engine/ingestion/edgar_client.py`
  - Already resolves ticker to CIK.
  - Pulls SEC companyfacts.
  - Maps a useful set of US-GAAP concepts.
  - Produces tidy financials with columns:
    - `period`
    - `account`
    - `amount`
    - `statement`
  - Current limitation: it discards most source metadata, so the app cannot yet show strong source trails.

- `src/dcf_engine/ingestion/market_data.py`
  - Optional yfinance helpers.
  - Pulls risk-free rate, beta, company snapshot, peer snapshots, ERP fallback.
  - `yfinance` is not currently in `requirements.txt`, so these features are effectively optional.

- `src/dcf_engine/output/excel_builder.py`
  - Builds a formula-linked Excel workbook.
  - Calls:
    - `build_cover`
    - `build_assumptions`
    - `build_is`
    - `build_wc`
    - `build_capex_da`
    - `build_debt_schedule`
    - `build_bs`
    - `build_cf`
    - `build_wacc`
    - `build_dcf`
    - analytics tabs

- `src/dcf_engine/output/sheets_core.py`
  - Builds formula-linked core tabs.
  - Important row maps:
    - `IS`
    - `WC`
    - `CD`
    - `DS`
    - `BS`
    - `CF`
    - `WR`
    - `DC`
  - Current limitation: Excel revenue formulas are CAGR-based.

- `src/dcf_engine/output/sheets_analytics.py`
  - Builds scenario, sensitivity, Monte Carlo, tornado, comps, checks, and audit tabs.
  - Current audit tab stores config snapshot, but not SEC source facts.

- `templates/dashboard.html`
  - Single-file React dashboard.
  - It is large, around 3,000 lines.
  - It currently centers around manual DCF assumptions and Excel export.
  - It has a frontend paywall modal, but backend export is still callable unless server-side gating is added.

- `templates/landing.html`
  - Public landing page.
  - Current positioning: editable DCF Excel models.
  - Needs to become filing-to-valuation intelligence.

- `src/dcf_engine/sample_models.py`
  - Public samples for NVDA, TSLA, AAPL, MSFT, AMZN.

- `docs/BUSINESS_MODEL_FEATURE_ROADMAP_2026-05-27.md`
  - Already recommends the pivot toward SEC-backed valuation workflow.
  - This new document converts that strategy into a phase-by-phase implementation plan.

### 1.2 Test status observed

This command was run:

```powershell
python -m pytest tests\test_v5_cross_check.py tests\test_mc_update.py tests\test_comprehensive_model.py -q
```

Result:

```text
90 passed, 4 xfailed
```

Important: not every test file behaves like a normal pytest module. Some tests are script-style and can call `sys.exit` at import time. Before building a real SaaS, test discovery should be cleaned up.

### 1.3 Current strategic gaps

The current app does not yet have:

- Source-linked SEC facts shown to the user.
- Filing comparison between latest and prior 10-K/10-Q/8-K.
- Text section extraction from filings.
- Valuation impact scanner.
- Reverse DCF.
- Assumption quality scoring.
- Red flag radar.
- Watchlists.
- Filing alerts or digests.
- User auth.
- Usage limits.
- Subscription state.
- Payment webhooks.
- Server-side export gating.
- Public filing-to-valuation report pages.

## 2. Non-Negotiable Build Rules For Gemini

Give these rules to Gemini before every phase.

1. Do not rewrite the app.
   - Preserve the existing DCF engine.
   - Add new modules around it.
   - Keep changes small and reviewable.

2. Do not edit `templates/dashboard.html` unless the phase specifically says to.
   - It is too large for a weaker model.
   - Prefer adding new backend endpoints and small public templates first.

3. Do not invent financial facts.
   - If SEC data is missing, return a warning.
   - Never silently fill missing values while pretending they are sourced.

4. Do not use LLMs for calculations.
   - DCF, reverse DCF, QA rules, and impact classification must be deterministic.
   - AI summaries can be added later only after source citations are stable.

5. Every public API response must include:
   - `success`
   - `request_id`
   - `warnings`
   - `errors` or `error` when failed

6. Every sourced number must keep a source trail:
   - ticker
   - CIK
   - accession number if available
   - form
   - filed date
   - fiscal period end
   - XBRL concept
   - value
   - unit

7. Every phase must end with tests.
   - Add focused tests for the new module.
   - Run at least the targeted new tests plus a small existing core test set.

8. US public companies only for the MVP.
   - Avoid banks, insurers, REITs, funds, ADR edge cases, and foreign issuers until later.
   - If a ticker is unsupported, return a clean warning.

9. No stock recommendations.
   - Use wording like "review", "changed", "may affect assumptions".
   - Do not use "buy", "sell", "undervalued", "guaranteed", or "price target" as a product promise.

10. No frontend-only paywalls.
    - If export is paid, backend must enforce credits or plan access.

## 3. Target Architecture

Add new code mostly under a new package:

```text
src/dcf_engine/intelligence/
```

Recommended files:

```text
src/dcf_engine/intelligence/__init__.py
src/dcf_engine/intelligence/models.py
src/dcf_engine/intelligence/source_map.py
src/dcf_engine/intelligence/sec_snapshot.py
src/dcf_engine/intelligence/assumption_builder.py
src/dcf_engine/intelligence/assumption_qa.py
src/dcf_engine/intelligence/reverse_dcf.py
src/dcf_engine/intelligence/filing_changes.py
src/dcf_engine/intelligence/red_flags.py
src/dcf_engine/intelligence/report_builder.py
src/dcf_engine/intelligence/cache.py
```

Later, when auth and payments are needed:

```text
src/dcf_engine/saas/
src/dcf_engine/saas/db.py
src/dcf_engine/saas/usage.py
src/dcf_engine/saas/payments.py
src/dcf_engine/saas/auth.py
```

Do not put all new logic in `dashboard_api.py`. That file should only route requests to service functions and serialize responses.

## 4. Core Data Models

Implement these dataclasses in `src/dcf_engine/intelligence/models.py`.

Keep fields simple. Do not use pydantic unless the project already uses it.

### 4.1 SourceFact

```python
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
```

### 4.2 CompanySnapshot

```python
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
```

### 4.3 AssumptionBuildResult

```python
@dataclass
class AssumptionBuildResult:
    payload: dict
    base_values: dict[str, float]
    source_map: list[SourceFact]
    warnings: list[str]
```

The `payload` must be compatible with the existing `_build_config_from_payload(data)` in `dashboard_api.py`.

### 4.4 AssumptionWarning

```python
@dataclass
class AssumptionWarning:
    code: str
    severity: str  # "low", "medium", "high"
    title: str
    detail: str
    affected_assumption: str | None = None
    source_account: str | None = None
```

### 4.5 FilingChange

```python
@dataclass
class FilingChange:
    category: str
    account: str
    latest_value: float | None
    prior_value: float | None
    absolute_change: float | None
    percent_change: float | None
    severity: str
    valuation_impact: str
    source_fact_latest: SourceFact | None = None
    source_fact_prior: SourceFact | None = None
```

### 4.6 ReverseDCFResult

```python
@dataclass
class ReverseDCFResult:
    ticker: str
    target_price: float | None
    target_equity_value: float | None
    target_enterprise_value: float | None
    implied_revenue_cagr: float | None
    implied_ebitda_margin: float | None
    implied_terminal_growth: float | None
    base_case_price: float | None
    warnings: list[str]
```

### 4.7 RedFlag

```python
@dataclass
class RedFlag:
    code: str
    severity: str
    title: str
    detail: str
    source_type: str  # "xbrl", "filing_text", "metadata"
    source_url: str | None = None
    snippet: str | None = None
```

## 5. API Contracts

Add new routes gradually to `dashboard_api.py`.

Use POST for actions that fetch and compute data.

### 5.1 `/api/company-snapshot`

Request:

```json
{
  "ticker": "AAPL",
  "years": 5
}
```

Response:

```json
{
  "success": true,
  "request_id": "abc123",
  "ticker": "AAPL",
  "cik": "0000320193",
  "company_name": "Apple Inc.",
  "latest_period": "2025-09-27",
  "key_metrics": {
    "revenue": 0,
    "gross_margin": 0,
    "operating_margin": 0,
    "net_income": 0,
    "cash": 0,
    "debt": 0,
    "shares": 0,
    "capex": 0,
    "cfo": 0,
    "fcf": 0
  },
  "financials": [],
  "source_map": [],
  "warnings": []
}
```

### 5.2 `/api/valuation-preview`

Purpose: one ticker in, source-linked valuation preview out.

Request:

```json
{
  "ticker": "AAPL",
  "years": 5,
  "overrides": {
    "forecast": {},
    "valuation": {},
    "wacc": {}
  }
}
```

Response:

```json
{
  "success": true,
  "request_id": "abc123",
  "ticker": "AAPL",
  "snapshot": {},
  "assumptions": {},
  "qa": [],
  "valuation": {},
  "reverse_dcf": {},
  "source_map": [],
  "warnings": []
}
```

Internally:

1. Build snapshot from EDGAR.
2. Build assumptions from snapshot.
3. Apply user overrides.
4. Run existing pipeline.
5. Run assumption QA.
6. Run reverse DCF if market price and shares exist.
7. Return compact output, not the entire giant `/api/run` response.

### 5.3 `/api/filing-changes`

Request:

```json
{
  "ticker": "AAPL",
  "form": "10-K"
}
```

Response:

```json
{
  "success": true,
  "request_id": "abc123",
  "ticker": "AAPL",
  "latest_filing": {},
  "prior_filing": {},
  "numeric_changes": [],
  "valuation_impacts": [],
  "red_flags": [],
  "warnings": []
}
```

### 5.4 `/api/report/<ticker>`

Later phase.

Purpose: public SEO-friendly HTML report for a ticker.

It should render a template, not return raw JSON.

URL examples:

```text
/reports/aapl-filing-valuation
/reports/nvda-reverse-dcf
/reports/tsla-risk-factor-changes
```

### 5.5 `/api/watchlist/refresh`

Later phase.

Request:

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA"]
}
```

Response:

```json
{
  "success": true,
  "request_id": "abc123",
  "items": [
    {
      "ticker": "AAPL",
      "changed": true,
      "change_count": 4,
      "red_flag_count": 1,
      "top_valuation_impact": "Share count increased; review per-share valuation."
    }
  ],
  "warnings": []
}
```

## 6. Phase-By-Phase Build Plan

Build exactly one phase at a time.

After each phase:

1. Run tests.
2. Manually smoke test the affected endpoint.
3. Commit or at least inspect diffs.
4. Do not start the next phase until the current one works.

## Phase 0: Baseline Lock And Test Hygiene

Goal: make sure future changes do not break the current engine.

### Tasks

1. Add `pytest.ini` at repo root if missing.
2. Configure pytest to ignore script-style tests that call `sys.exit` at import time, or convert those tests properly.
3. Keep the already passing tests passing.
4. Add a short `docs/TESTING.md` explaining which commands to run.

### Suggested pytest.ini

```ini
[pytest]
testpaths = tests
python_files =
    test_v5_cross_check.py
    test_mc_update.py
    test_comprehensive_model.py
    test_cross_check.py
addopts = -q
```

If `test_cross_check.py` is script-style and slow, either convert it into pytest functions or exclude it for now and document why.

### Commands

```powershell
python -m pytest tests\test_v5_cross_check.py tests\test_mc_update.py tests\test_comprehensive_model.py -q
```

Expected:

```text
90 passed, 4 xfailed
```

### Gemini prompt

```text
You are working on the Trinsic Flask DCF project. Do Phase 0 only.

Goal: preserve the current engine and make test execution explicit.

Read:
- dashboard_api.py
- src/dcf_engine/pipeline.py
- tests/

Do not change valuation logic. Add or update pytest configuration only if needed. Add docs/TESTING.md with exact commands. Run the existing focused test command and report the result.
```

### Acceptance criteria

- Existing focused tests still pass.
- There is a clear test command for future phases.
- No product logic changed.

## Phase 1: Source-Linked SEC Snapshot Layer

Goal: preserve source metadata from SEC companyfacts and return a clean company snapshot.

### Why this phase matters

The product cannot be anonymous and trusted unless the output itself proves its work. Source links are the trust layer.

### Files to add

```text
src/dcf_engine/intelligence/__init__.py
src/dcf_engine/intelligence/models.py
src/dcf_engine/intelligence/sec_snapshot.py
src/dcf_engine/intelligence/source_map.py
tests/test_sec_snapshot.py
```

### Files to edit

```text
src/dcf_engine/ingestion/edgar_client.py
dashboard_api.py
```

### Implementation detail

Do not replace `EdgarClient.fetch_financials`. Add a new method or helper that keeps source metadata:

```python
def fetch_company_snapshot(ticker: str, years: int = 5) -> CompanySnapshot:
    ...
```

It should:

1. Resolve ticker to CIK using current `ticker_to_cik`.
2. Pull companyfacts.
3. Iterate through `PRIORITY_CONCEPTS`.
4. For each fact, keep:
   - value
   - unit
   - form
   - filed
   - period end
   - fy
   - fp
   - accn
   - frame
   - concept
5. Build the same tidy `financials` table as current `fetch_financials`.
6. Build a list of `SourceFact`.
7. Build `key_metrics` from latest period.

### Key metric rules

Use latest annual period for MVP.

Map accounts:

```text
revenue -> Revenue
cogs -> COGS
gross_profit -> Revenue - COGS when both exist
gross_margin -> gross_profit / revenue
ebit -> EBIT
operating_margin -> EBIT / revenue
net_income -> Net Income
cash -> Cash
debt -> Long-Term Debt + Short-Term Debt when available
shares -> Shares Diluted or Shares Outstanding
capex -> absolute value of Capex
cfo -> CFO
fcf -> CFO - absolute value of Capex
ppe -> PP&E Net
nwc -> Accounts Receivable + Inventory - Accounts Payable
```

If any item is missing, set it to `None` and append a warning.

### Source URL rules

For now, source URL can be:

```text
https://www.sec.gov/Archives/edgar/data/{cik_without_leading_zeros}/{accession_without_dashes}/
```

If accession is missing, use:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
```

Do not block the phase on perfect primary-document links. Improve this later with the submissions endpoint.

### Add route

In `dashboard_api.py`, add:

```python
@app.route("/api/company-snapshot", methods=["POST"])
def api_company_snapshot():
    ...
```

Rules:

- Uppercase ticker.
- Limit ticker length to 12.
- Default years to 5.
- Catch exceptions.
- Return generic error plus request_id.
- Log full traceback server-side.

### Test with mocks

In `tests/test_sec_snapshot.py`:

- Mock the SEC companyfacts response.
- Verify:
  - source facts keep accession and concept.
  - key metrics derive revenue, cash, debt, shares.
  - missing facts produce warnings.
  - no exception on sparse data.

### Manual smoke test

Run the app:

```powershell
python dashboard_api.py
```

Then POST:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5050/api/company-snapshot -ContentType "application/json" -Body '{"ticker":"AAPL","years":5}'
```

### Gemini prompt

```text
Do Phase 1 only.

Add a source-linked SEC snapshot layer. Preserve existing EdgarClient behavior. Add new dataclasses in src/dcf_engine/intelligence/models.py and new snapshot helper in src/dcf_engine/intelligence/sec_snapshot.py.

Add POST /api/company-snapshot to dashboard_api.py.

Do not modify the DCF pipeline. Do not change templates. Add tests with mocked SEC data. Every missing metric should become a warning, not a crash.

Run:
python -m pytest tests\test_sec_snapshot.py tests\test_v5_cross_check.py tests\test_mc_update.py tests\test_comprehensive_model.py -q
```

### Acceptance criteria

- `/api/company-snapshot` works for AAPL, MSFT, NVDA.
- Response includes `source_map`.
- Sparse data returns warnings.
- Existing engine tests pass.

## Phase 2: SEC-To-Assumption Builder

Goal: convert a company snapshot into a pipeline-ready DCF payload.

### Files to add

```text
src/dcf_engine/intelligence/assumption_builder.py
tests/test_assumption_builder.py
```

### Files to edit

```text
dashboard_api.py
```

### Implementation detail

Create:

```python
def build_assumptions_from_snapshot(snapshot: CompanySnapshot) -> AssumptionBuildResult:
    ...
```

The returned `payload` must match what `/api/run` already expects.

### Default derivation rules

Use these deterministic rules:

```text
base_year_revenue:
  latest Revenue, else 0 with warning

base_cash:
  latest Cash, else 0 with warning

base_ppe:
  latest PP&E Net, else 0 with warning

base_nwc:
  latest AR + Inventory - AP, else 0 with warning

base_common_stock:
  0 for MVP unless source exists

valuation.cash:
  latest Cash, else 0

valuation.debt:
  latest Long-Term Debt + Short-Term Debt, else 0

valuation.fully_diluted_shares:
  latest diluted shares or shares outstanding, else 1,000,000 with high warning

forecast.revenue_cagr:
  CAGR from oldest to latest revenue over available periods.
  Clamp between -0.10 and 0.25 for first MVP.
  If not enough history, use 0.05 with warning.

forecast.cogs_pct_revenue:
  COGS / Revenue, latest or average.
  Clamp 0.05 to 0.95.
  If missing, use 0.50 with warning.

forecast.sga_pct_revenue:
  SGA / Revenue if available.
  Clamp 0.01 to 0.60.
  If missing, use 0.15 with warning.

forecast.other_opex_pct_revenue:
  R&D / Revenue if R&D exists, else 0.05.

forecast.capex_pct_revenue:
  abs(Capex) / Revenue, latest or average.
  Clamp 0.00 to 0.30.
  If missing, use 0.05 with warning.

forecast.tax_rate:
  Tax Expense / EBT if EBT can be inferred and positive.
  Clamp 0.00 to 0.35.
  If missing, use 0.21 with warning.

forecast.dso, dio, dpo:
  Use current defaults first. Do not over-engineer.

wacc:
  Use defaults from current dashboard unless optional market data succeeds.
  Set use_live_data=False by default in public MVP.

valuation.terminal_growth_rate:
  0.025 default.

valuation.exit_ev_ebitda_multiple:
  10.0 default until comps are configured.
```

### Important warning language

Every fallback must create a warning:

```text
"SG&A not found in SEC facts; used 15.0% of revenue fallback."
```

Do not say:

```text
"SG&A loaded."
```

unless it was actually sourced.

### Add route

Add:

```python
@app.route("/api/ticker-assumptions", methods=["POST"])
def api_ticker_assumptions():
    ...
```

Response:

```json
{
  "success": true,
  "request_id": "...",
  "ticker": "AAPL",
  "payload": {},
  "source_map": [],
  "warnings": []
}
```

### Gemini prompt

```text
Do Phase 2 only.

Create src/dcf_engine/intelligence/assumption_builder.py. It must convert a CompanySnapshot into the same dashboard payload structure consumed by _build_config_from_payload in dashboard_api.py.

Use deterministic fallback rules and warnings. Do not change the DCF engine. Add /api/ticker-assumptions. Add tests for normal data and missing data.

Run targeted tests and existing engine tests.
```

### Acceptance criteria

- AAPL snapshot can become a payload.
- Payload can be posted to existing `/api/run`.
- Missing COGS, SGA, shares, capex produce warnings.
- No hidden assumptions without warnings.

## Phase 3: Valuation Preview Endpoint

Goal: one ticker produces a compact valuation preview, without requiring the user to manually enter assumptions.

### Files to add

```text
src/dcf_engine/intelligence/valuation_preview.py
tests/test_valuation_preview.py
```

### Files to edit

```text
dashboard_api.py
```

### Implementation detail

Create:

```python
def build_valuation_preview(ticker: str, years: int = 5, overrides: dict | None = None) -> dict:
    ...
```

Flow:

1. Get `CompanySnapshot`.
2. Build assumptions from snapshot.
3. Apply safe overrides.
4. Build config using existing `_build_config_from_payload`.
5. Run `_run_payload` or `run_pipeline`.
6. Return compact valuation output:
   - price blended
   - equity blended
   - EV blended
   - WACC
   - terminal growth
   - exit multiple
   - TV percent of EV
   - revenue CAGR
   - EBITDA margin
   - warnings
   - source map

### Override safety

Only allow overrides in:

```text
forecast
wacc
valuation
monte_carlo
sensitivity
peer_tickers
```

Reject unknown top-level keys.

Do not allow:

```text
data_file
output_excel
file paths
```

### Add route

```python
@app.route("/api/valuation-preview", methods=["POST"])
def api_valuation_preview():
    ...
```

### Response shape

```json
{
  "success": true,
  "request_id": "...",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "valuation": {
    "price_blended": 0,
    "equity_blended": 0,
    "ev_blended": 0,
    "wacc": 0,
    "terminal_growth": 0,
    "exit_multiple": 0,
    "tv_pct_of_ev": 0
  },
  "assumptions": {
    "revenue_cagr": 0,
    "ebitda_margin": 0,
    "capex_pct_revenue": 0,
    "tax_rate": 0
  },
  "source_map": [],
  "warnings": []
}
```

### Gemini prompt

```text
Do Phase 3 only.

Add a compact valuation preview service and POST /api/valuation-preview.

It must reuse the Phase 1 snapshot and Phase 2 assumption builder. It must use the existing DCF pipeline. It must return compact valuation outputs and warnings.

Do not edit templates. Do not add auth or payments yet. Add tests with mocked snapshot/assumption data.
```

### Acceptance criteria

- User can POST ticker and get valuation summary.
- Existing `/api/run` still works.
- Existing `/api/export-excel` still works.
- Any failed ticker returns clean JSON, not traceback.

## Phase 4: Assumption Quality Score

Goal: warn the user when model assumptions are weak, risky, inconsistent, or over-precise.

### Files to add

```text
src/dcf_engine/intelligence/assumption_qa.py
tests/test_assumption_qa.py
```

### Rules to implement

Use deterministic rules. Each returns `AssumptionWarning`.

Start with these:

1. `terminal_growth_near_wacc`
   - If WACC minus terminal growth is below 1.0%.
   - Severity high.

2. `terminal_growth_above_cap`
   - If terminal growth above GDP cap.
   - Severity medium.

3. `tv_dependency_high`
   - If terminal value percent of EV above 85%.
   - Severity high.
   - 75% to 85% is medium.

4. `revenue_growth_above_history`
   - If forecast CAGR is more than 10 percentage points above historical CAGR.
   - Severity medium or high.

5. `margin_above_history`
   - If EBITDA margin is more than 5 percentage points above latest or historical average.
   - Severity medium.

6. `capex_below_depreciation`
   - If capex percent of revenue is far below depreciation proxy for asset-heavy company.
   - Severity medium.

7. `shares_missing_or_placeholder`
   - If shares equal exactly 1,000,000 fallback.
   - Severity high.

8. `debt_increased`
   - If debt is above cash and debt/revenue above 50%.
   - Severity medium.

9. `negative_fcf`
   - If latest FCF is negative.
   - Severity medium.

10. `low_source_quality`
    - If many assumptions came from fallback warnings.
    - Severity medium.

### Score

Add an overall score:

```text
100 - high*20 - medium*10 - low*3
```

Clamp between 0 and 100.

Labels:

```text
80-100: "clean"
60-79: "review"
0-59: "high_review"
```

Do not call it "safe" or "good investment".

### Integrate into `/api/valuation-preview`

Add:

```json
"quality": {
  "score": 75,
  "label": "review",
  "warnings": []
}
```

### Gemini prompt

```text
Do Phase 4 only.

Add an assumption QA rules engine with deterministic warnings and a 0-100 score. Integrate it into /api/valuation-preview.

Do not change DCF math. Do not add UI. Add focused tests for each warning rule.
```

### Acceptance criteria

- QA warnings are explainable.
- No investment advice language.
- Tests cover high/medium/low warning logic.

## Phase 5: Reverse DCF Tracker

Goal: show what the current market price implies.

### Files to add

```text
src/dcf_engine/intelligence/reverse_dcf.py
tests/test_reverse_dcf.py
```

### Required inputs

From market data:

- current price
- shares outstanding
- market cap if available

From SEC snapshot:

- base revenue
- cash
- debt
- margin assumptions

### MVP solver

Use bisection, not scipy.

Implement:

```python
def solve_implied_revenue_cagr(
    base_payload: dict,
    target_price: float,
    low: float = -0.20,
    high: float = 0.40,
    max_iter: int = 40,
) -> ReverseDCFResult:
    ...
```

Algorithm:

1. Read shares from payload.
2. If target price or shares missing, return warning.
3. Define `price_for_growth(g)`:
   - copy payload
   - set `forecast.revenue_cagr = g`
   - run valuation in a light deterministic way
4. Check whether target price is between low and high outputs.
5. If not bracketed, return nearest boundary and warning.
6. Else bisection until close.

Important: running the full pipeline 40 times can be slow. For MVP, either:

- Use a simplified DCF helper based on existing sensitivity `_quick_dcf`, or
- Add a `run_preview_pipeline` that skips Monte Carlo, comps, Excel, and PDF.

Prefer the simplified DCF helper for Phase 5. Later, improve parity.

### Also solve implied EBITDA margin

Implement:

```python
def solve_implied_ebitda_margin(...)
```

Use range:

```text
0.01 to 0.60
```

### Integrate into `/api/valuation-preview`

Add:

```json
"reverse_dcf": {
  "target_price": 0,
  "implied_revenue_cagr": 0,
  "implied_ebitda_margin": 0,
  "base_case_price": 0,
  "warnings": []
}
```

### Market data fallback

If `yfinance` is unavailable:

- Return warning:
  - "Live market price unavailable; reverse DCF not computed."
- Do not crash.

### Gemini prompt

```text
Do Phase 5 only.

Add reverse DCF helpers using deterministic bisection and no scipy. Integrate into /api/valuation-preview. If market data is unavailable, return a warning and skip reverse DCF.

Do not change the main DCF engine. Add tests for bracketed, unbracketed, missing price, and missing shares cases.
```

### Acceptance criteria

- Reverse DCF returns implied revenue CAGR when price is available.
- Missing price returns warning.
- No external network calls in tests.

## Phase 6: Numeric Filing Change Detector

Goal: compare the latest filing period against the prior period and classify what changed.

### Files to add

```text
src/dcf_engine/intelligence/filing_changes.py
tests/test_filing_changes.py
```

### MVP scope

Start with XBRL numeric changes only. Text comparison comes later.

Compare latest annual periods first:

- revenue
- gross margin
- operating margin
- net income
- CFO
- capex
- FCF
- cash
- debt
- diluted shares
- PP&E
- NWC

### Change classification rules

Revenue:

```text
abs(percent_change) < 5%: low
5% to 15%: medium
above 15%: high
valuation impact: "Review revenue growth base and forecast CAGR."
```

Gross margin / operating margin:

```text
change under 100 bps: low
100 to 300 bps: medium
above 300 bps: high
valuation impact: "Review margin assumptions."
```

Debt:

```text
debt increase under 10%: low
10% to 30%: medium
above 30%: high
valuation impact: "Review debt bridge, interest burden, and WACC assumptions."
```

Cash:

```text
large decline: medium/high
valuation impact: "Review equity bridge cash and liquidity cushion."
```

Shares:

```text
increase under 1%: low
1% to 3%: medium
above 3%: high
valuation impact: "Review dilution and per-share valuation."
```

Capex:

```text
capex/revenue change above 200 bps: medium
above 500 bps: high
valuation impact: "Review reinvestment assumptions and FCF conversion."
```

FCF:

```text
positive to negative: high
negative to positive: medium
large decline: medium/high
valuation impact: "Review FCF base and terminal value reliability."
```

### Add route

```python
@app.route("/api/filing-changes", methods=["POST"])
def api_filing_changes():
    ...
```

### Response

Return both raw changes and a concise impact list:

```json
{
  "numeric_changes": [],
  "valuation_impacts": [
    {
      "severity": "high",
      "title": "Diluted shares increased 4.2%",
      "detail": "Review per-share valuation and dilution assumptions."
    }
  ]
}
```

### Gemini prompt

```text
Do Phase 6 only.

Add numeric filing change detection based on the source-linked company snapshot. Compare latest and prior annual periods for key accounts. Classify severity and valuation impact using deterministic rules.

Add POST /api/filing-changes. Do not parse filing text yet. Add tests with fake two-period data.
```

### Acceptance criteria

- A two-period snapshot returns meaningful changes.
- No text parsing yet.
- Changes include source facts for latest and prior values.

## Phase 7: Red Flag Radar

Goal: detect high-emotion filing risks that users fear missing.

### Files to add

```text
src/dcf_engine/intelligence/red_flags.py
tests/test_red_flags.py
```

### MVP red flags

Start deterministic.

From XBRL/numeric data:

1. Revenue down more than 20%.
2. FCF turned negative.
3. Debt up more than 30%.
4. Shares up more than 5%.
5. Cash down more than 30%.
6. Net income positive to negative.

From filing metadata:

1. Late filing forms:
   - NT 10-K
   - NT 10-Q
2. Amendments:
   - 10-K/A
   - 10-Q/A
3. 8-K presence in last 30 days.

From filing text in later subphase:

Keywords:

```text
going concern
substantial doubt
material weakness
restatement
impairment
restructuring
auditor resignation
change in auditor
customer concentration
covenant default
liquidity risk
delisting
bankruptcy
```

### Subphase 7A: numeric and metadata only

Use companyfacts plus submissions API metadata.

Add to `edgar_client.py`:

```python
def fetch_submissions(self, cik: str) -> dict | None:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
```

Keep rate limiting and User-Agent.

### Subphase 7B: filing text keyword scan

Only after 7A works.

Download latest filing document from submissions metadata.

Add dependency only if needed:

```text
beautifulsoup4
```

Extract plain text:

1. Remove scripts/styles.
2. Collapse whitespace.
3. Search keywords.
4. Store short snippets, max 300 chars.

Do not build full risk factor semantic comparison yet.

### Integrate into `/api/filing-changes`

Add:

```json
"red_flags": []
```

### Gemini prompt

```text
Do Phase 7A only first.

Add deterministic red flag detection from numeric changes and SEC submissions metadata. Do not parse full filing text yet. Add tests with fake filings metadata.

After 7A passes, ask before doing 7B.
```

### Acceptance criteria

- Numeric red flags work without network in tests.
- Late filings and amendments are flagged.
- No false claim that keyword text was scanned unless it was.

## Phase 8: Valuation Impact Scanner

Goal: translate filing changes into valuation assumption impacts.

This is the core wedge.

### Files to add

```text
src/dcf_engine/intelligence/valuation_impacts.py
tests/test_valuation_impacts.py
```

### Implementation

Create:

```python
def build_valuation_impacts(changes: list[FilingChange], red_flags: list[RedFlag]) -> list[dict]:
    ...
```

### Impact categories

Use these categories:

```text
revenue_growth
margin
working_capital
capex
cash_flow
debt_wacc
share_count
terminal_value
source_quality
red_flag
```

### Example outputs

Revenue:

```json
{
  "category": "revenue_growth",
  "severity": "medium",
  "title": "Revenue base changed materially",
  "detail": "Revenue increased 11.8% versus prior year. Review base-year revenue and forecast CAGR.",
  "affected_assumptions": ["base_year_revenue", "forecast.revenue_cagr"]
}
```

Share count:

```json
{
  "category": "share_count",
  "severity": "high",
  "title": "Dilution increased",
  "detail": "Diluted shares increased 4.2%. Review per-share valuation and share count assumptions.",
  "affected_assumptions": ["valuation.fully_diluted_shares"]
}
```

Debt:

```json
{
  "category": "debt_wacc",
  "severity": "high",
  "title": "Debt burden increased",
  "detail": "Debt increased 35.0%. Review debt bridge, interest expense, and WACC capital structure.",
  "affected_assumptions": ["valuation.debt", "wacc.target_debt_weight", "wacc.interest_coverage_ratio"]
}
```

### Integrate

Add impacts to:

- `/api/filing-changes`
- `/api/valuation-preview`

### Gemini prompt

```text
Do Phase 8 only.

Add valuation impact scanner that maps numeric changes and red flags into affected DCF assumptions. This is deterministic rule mapping, not AI.

Integrate with /api/filing-changes and /api/valuation-preview. Add tests for revenue, margin, debt, dilution, capex, and FCF impact categories.
```

### Acceptance criteria

- The app says what changed and what assumption to review.
- It does not say "this stock is overvalued" or "sell".
- Every impact has affected assumptions.

## Phase 9: Watchlist Digest MVP

Goal: retention loop.

For the first implementation, avoid full auth. Build a stateless manual refresh endpoint first.

### Files to add

```text
src/dcf_engine/intelligence/watchlist.py
tests/test_watchlist.py
```

### Route

```python
@app.route("/api/watchlist/refresh", methods=["POST"])
def api_watchlist_refresh():
    ...
```

### Request

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA"]
}
```

Limits:

- Free unauthenticated endpoint should allow max 10 tickers.
- Later paid plan can allow 25.

### Response

For each ticker:

- latest filing date
- count of numeric changes
- count of red flags
- top 1 to 3 valuation impacts
- whether source quality is weak

### Do not build email alerts yet

Email adds deliverability, spam, auth, unsubscribe, and job scheduling complexity.

### Gemini prompt

```text
Do Phase 9 only.

Add stateless watchlist refresh. It accepts up to 10 tickers, calls the existing filing change/impact logic, and returns a digest sorted by highest severity.

No database, no auth, no email yet. Add tests by mocking per-ticker change results.
```

### Acceptance criteria

- User can refresh 5 tickers and see which ones matter.
- Errors for one ticker do not fail the entire watchlist.
- Response sorts high-severity items first.

## Phase 10: Public Reports And Anonymous Distribution Funnel

Goal: let anonymous distribution work by showing public proof.

### Files to add

```text
templates/report.html
src/dcf_engine/intelligence/report_builder.py
tests/test_report_builder.py
```

### Routes

```python
@app.route("/reports/<ticker>")
def report_page(ticker):
    ...
```

Optional SEO variants later:

```text
/reports/<ticker>/filing-changes
/reports/<ticker>/reverse-dcf
/reports/<ticker>/red-flags
```

### Report content

Each public report should include:

1. Company identity.
2. Latest filing date.
3. Key financial changes.
4. Valuation impacts.
5. Reverse DCF if available.
6. Red flags.
7. Source links.
8. Methodology/disclaimer.
9. CTA:
   - track this ticker
   - run another ticker
   - export premium Excel

### Design rule

Do not create a marketing page only. The first screen should show the actual ticker report.

### Static sample pages

Start with:

```text
/reports/NVDA
/reports/TSLA
/reports/AAPL
/reports/MSFT
/reports/AMZN
```

### Gemini prompt

```text
Do Phase 10 only.

Add a public report page template and /reports/<ticker>. It should render existing valuation-preview and filing-change data in a clean source-linked report.

Do not redesign the whole landing page. Do not add payments yet. Add disclaimers. Add tests for report builder data shaping.
```

### Acceptance criteria

- Public report pages load.
- Users can inspect source-linked output without signing up.
- No founder identity is exposed.

## Phase 11: Lite Export And Premium Excel Source Tabs

Goal: create trust-building exports and improve premium export.

### 11A: Lite HTML/PDF report

Start with HTML export only.

Add route:

```python
@app.route("/reports/<ticker>/print")
def printable_report(ticker):
    ...
```

Keep it printable in browser.

Do not add PDF dependency unless needed. Current `pdf_memo.py` uses ReportLab optionally, but HTML print is cheaper.

### 11B: Excel source tabs

Edit:

```text
src/dcf_engine/output/excel_builder.py
src/dcf_engine/output/sheets_analytics.py
```

Add new optional builder functions:

```python
build_source_map(wb, source_facts)
build_warnings(wb, warnings)
build_filing_changes(wb, changes)
build_valuation_impacts(wb, impacts)
```

Modify `build_excel` signature carefully:

```python
def build_excel(..., source_facts=None, warnings=None, filing_changes=None, valuation_impacts=None, **kwargs):
```

Existing callers must not break.

### Excel tab order

Premium workbook should include:

1. Cover
2. Assumptions
3. Source Map
4. Filing Changes
5. Valuation Impacts
6. Warnings
7. Income Statement
8. Working Capital
9. Capex DA
10. Debt Schedule
11. Balance Sheet
12. Cash Flow
13. WACC
14. DCF
15. Scenarios
16. Sensitivity
17. Monte Carlo
18. Tornado
19. Comps
20. Checks
21. Audit Trail

### Gemini prompt

```text
Do Phase 11 only.

Add optional Excel tabs for Source Map, Filing Changes, Valuation Impacts, and Warnings. Preserve all existing callers and existing workbook behavior when these optional values are None.

Add tests that build an Excel workbook with and without source data and verify sheet names exist.
```

### Acceptance criteria

- Existing sample downloads still work.
- Premium source-linked workbook includes new tabs.
- No formula-linked core tab is broken.

## Phase 12: Auth, Usage Limits, And Payment Gating

Goal: convert the product from demo to paid SaaS.

Do not start this before the filing-to-valuation product loop works.

### Recommended simple stack

- Database: Supabase Postgres using `DATABASE_URL`.
- Python DB driver: `psycopg[binary]`.
- Payments: LemonSqueezy.
- Auth v1: email-based access link or simple email token.

If this becomes too heavy, launch paid exports manually first. Do not let payment complexity block product validation.

### Files to add

```text
src/dcf_engine/saas/__init__.py
src/dcf_engine/saas/db.py
src/dcf_engine/saas/usage.py
src/dcf_engine/saas/payments.py
src/dcf_engine/saas/auth.py
tests/test_usage.py
tests/test_payments.py
```

### Tables

Use SQL migrations stored in:

```text
db/schema.sql
```

Tables:

```sql
create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    created_at timestamptz not null default now()
);

create table if not exists subscriptions (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    provider text not null,
    provider_customer_id text,
    provider_subscription_id text,
    plan text not null,
    status text not null,
    current_period_end timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists usage_events (
    id uuid primary key default gen_random_uuid(),
    email text,
    anonymous_id text,
    event_type text not null,
    ticker text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists export_credits (
    email text primary key,
    credits_remaining integer not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists exports (
    id uuid primary key default gen_random_uuid(),
    email text,
    ticker text not null,
    status text not null,
    warnings jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists payment_events (
    id uuid primary key default gen_random_uuid(),
    provider text not null,
    provider_event_id text not null unique,
    event_type text not null,
    email text,
    amount integer,
    currency text,
    raw jsonb not null,
    created_at timestamptz not null default now()
);
```

### Backend gating rules

Free anonymous:

- 3 valuation previews per day per IP/session.
- 1 watchlist refresh per day.
- No premium Excel export.

Free signed-in:

- 5 valuation previews per month.
- 3 filing-change checks per month.
- 3 watchlist tickers.
- No premium Excel export unless credits exist.

Core $9.99:

- 50 company snapshots per month.
- 100 reverse DCF runs per month.
- 25 filing-change checks per month.
- 25 watchlist tickers.
- Lite report export.
- Discounted DCF export credits.

Premium export credit:

- Each full Excel export consumes 1 credit.

### Server-side export protection

Edit `/api/export-excel` and any new ticker export endpoint:

1. Identify user by token/email.
2. Check plan or credits.
3. If no access, return 402 JSON:

```json
{
  "success": false,
  "error": "Export requires a paid plan or export credit.",
  "checkout_url": "..."
}
```

4. On successful export, decrement credit.
5. Log export row.

### Payment webhook

Before implementing LemonSqueezy webhooks, check current official docs. Payment webhook signatures and event names can change.

Rules:

- Verify webhook signature against raw body.
- Store provider event ID.
- Enforce idempotency.
- Never double-credit the same event.

### Gemini prompt

```text
Do Phase 12 only.

Add database-backed usage and export credit gating. Use DATABASE_URL with psycopg. Add schema.sql. Protect Excel export server-side.

Do not rely on frontend paywall. Do not implement complex team accounts. Add tests for credit decrement and duplicate webhook idempotency using mocked DB/payment payloads.

Before coding LemonSqueezy webhook signature verification, check the latest official LemonSqueezy docs and cite the exact header/event assumptions in comments.
```

### Acceptance criteria

- Anonymous direct POST cannot export premium Excel.
- Paid/credited user can export.
- Credit decrements after success.
- Duplicate webhook does not double-credit.

## Phase 13: Frontend Product Surface

Goal: make the app usable as filing-to-valuation intelligence.

Only do this after backend endpoints are stable.

### Avoid editing the existing huge dashboard first

Create simpler pages:

```text
templates/research.html
templates/report.html
templates/watchlist.html
```

Then link them from landing.

### Add routes

```python
@app.route("/research")
def research():
    return render_template("research.html")

@app.route("/watchlist")
def watchlist():
    return render_template("watchlist.html")
```

### Research page workflow

First screen:

- ticker input
- button: "Analyze filing impact"

Then sections:

- latest filing status
- key changes
- valuation impacts
- reverse DCF
- red flags
- source map
- CTA to export

### Watchlist page workflow

- text input for tickers
- "Refresh"
- table of companies sorted by materiality

### Landing page rewrite

Only after research/report pages exist.

New headline:

```text
SEC filings, translated into valuation assumptions.
```

Subcopy:

```text
Trinsic shows what changed in a company's latest filing, whether it affects revenue, margin, debt, dilution, or terminal value assumptions, and links every number back to source filings.
```

Primary CTA:

```text
Analyze a ticker
```

Secondary CTA:

```text
See sample reports
```

### Gemini prompt

```text
Do Phase 13 only.

Create a simple research page that calls /api/valuation-preview and /api/filing-changes. Do not rewrite the large dashboard. The page should show actual output first: key changes, valuation impacts, reverse DCF, red flags, source links.

Keep design consistent with existing Trinsic branding. Add disclaimers. Ensure mobile layout does not overlap.
```

### Acceptance criteria

- User can enter ticker and get an understandable report.
- Output has source links.
- No in-app text overpromises investment advice.

## Phase 14: Launch QA

Goal: product is safe enough for public validation.

### Required automated tests

Run:

```powershell
python -m pytest tests\test_sec_snapshot.py tests\test_assumption_builder.py tests\test_valuation_preview.py tests\test_assumption_qa.py tests\test_reverse_dcf.py tests\test_filing_changes.py tests\test_red_flags.py tests\test_valuation_impacts.py tests\test_watchlist.py tests\test_v5_cross_check.py tests\test_mc_update.py tests\test_comprehensive_model.py -q
```

### Required manual tests

For each:

```text
AAPL
MSFT
NVDA
TSLA
AMZN
```

Check:

1. `/api/company-snapshot`
2. `/api/valuation-preview`
3. `/api/filing-changes`
4. `/api/watchlist/refresh`
5. `/reports/<ticker>`
6. Premium Excel export if enabled

### Excel QA

For exported workbooks:

- Workbook opens.
- Core tabs exist.
- Source Map tab exists.
- Warnings tab exists.
- DCF tab has formulas.
- Checks tab passes or explains failures.
- No `#REF!`, `#DIV/0!`, `#NAME?`, `#VALUE!` in core tabs if Excel recalculation is available.

### Security QA

Test:

```text
/api/config/../../dashboard_api.py
/api/data-file-base-values/../../LICENSE
```

Expected:

- 400 or 404
- no local file content
- no traceback

### Public copy QA

Search:

```powershell
rg -n "buy|sell|guaranteed|undervalued|overvalued|financial advice|investment advice|personal name|gmail" .
```

Review results. Some disclaimer use of "not investment advice" is fine.

### Acceptance criteria

The product is launchable when:

- A stranger can understand the report in 10 seconds.
- Ticker analysis works without manual CSV upload.
- Every important number has source context or a warning.
- Full Excel export is server-side gated.
- Public pages show proof before asking for money.
- No founder identity is required.

## 7. Connected Product Flow

The final user journey should be:

1. User lands on homepage.
2. User enters ticker.
3. App loads public report:
   - what changed
   - why it matters
   - valuation impacts
   - reverse DCF
   - red flags
   - source links
4. User can add tickers to watchlist.
5. User sees watchlist digest:
   - only companies with meaningful changes rise to top.
6. User can export lite report.
7. User upgrades to $9.99/month for:
   - more watchlist tickers
   - more filing checks
   - full source-linked reports
8. User buys export credits for:
   - premium formula-linked DCF workbook
   - source map
   - filing changes
   - valuation impacts
   - warnings

This keeps the DCF engine as the powerful backend instead of the product's fragile front door.

## 8. Distribution Plan For Anonymous Selling

### 8.1 Positioning

Do not position as:

```text
AI stock picker
DCF calculator
Filing alert tool
Excel template seller
```

Position as:

```text
SEC filing changes translated into valuation assumptions.
```

### 8.2 Trust without founder identity

You can stay anonymous if the product is transparent.

Required trust assets:

- public sample reports
- visible source links
- methodology page
- warning/fallback transparency
- no fake precision
- refund policy
- no investment advice claims

### 8.3 First public report set

Publish:

```text
/reports/NVDA
/reports/TSLA
/reports/AAPL
/reports/MSFT
/reports/AMZN
```

Then add small/mid-cap examples because serious value investors often care more about those.

### 8.4 Reddit distribution

Do not spam tool links.

Post useful analysis first.

Example post title:

```text
I compared Tesla's latest 10-K against the prior year. These are the filing changes that actually affect valuation assumptions.
```

Post structure:

1. Short intro.
2. 5 to 7 source-linked findings.
3. Explain valuation assumption impacted.
4. Mention the report was generated with your tool.
5. Soft CTA at end or in profile.

Target communities:

```text
r/ValueInvesting
r/SecurityAnalysis
r/CFA
r/FinancialCareers
r/FinancialModeling
```

### 8.5 X/Twitter brand account

Post daily:

```text
Filing change of the day:
Company X disclosed Y.
Valuation assumption affected: debt / margin / dilution / capex.
Source: SEC filing link.
```

No founder face needed.

### 8.6 SEO pages

Create pages targeting:

```text
AAPL 10-K changes
NVDA filing changes
TSLA reverse DCF
MSFT risk factor changes
BamSEC alternative
SEC filing alerts for retail investors
10-K risk factor comparison tool
DCF assumptions from SEC filings
```

### 8.7 Free tool funnel

Free:

- 3 ticker analyses per month
- limited source map
- limited watchlist
- no premium Excel

Paid $9.99:

- 25 watchlist companies
- full valuation impacts
- red flag radar
- watchlist digest
- lite exports

Premium export:

- full Excel DCF workbook

## 9. What Gemini Must Never Do

Never accept these shortcuts:

1. "Let's summarize filings with AI first."
   - No. Build deterministic source-linked data first.

2. "Let's rewrite the frontend in React/Vite/Next.js."
   - No. The existing app is Flask-served. Build value first.

3. "Let's put all logic in dashboard_api.py."
   - No. Use service modules.

4. "Let's hide warnings to make output look cleaner."
   - No. Warnings are trust.

5. "Let's make Excel export free with only frontend paywall."
   - No. Server-side gating is mandatory.

6. "Let's support all global companies."
   - No. US public companies first.

7. "Let's promise fair value accuracy."
   - No. The product reviews assumptions and source-linked changes.

8. "Let's build email alerts before watchlist works manually."
   - No. Manual refresh first.

## 10. Recommended Coding Order Summary

Follow this exact order:

1. Phase 0: test hygiene.
2. Phase 1: source-linked SEC snapshot.
3. Phase 2: SEC-to-assumption builder.
4. Phase 3: valuation preview endpoint.
5. Phase 4: assumption QA.
6. Phase 5: reverse DCF.
7. Phase 6: numeric filing change detector.
8. Phase 7: red flag radar.
9. Phase 8: valuation impact scanner.
10. Phase 9: watchlist digest.
11. Phase 10: public report pages.
12. Phase 11: lite export and premium Excel source tabs.
13. Phase 12: auth, usage, payment gating.
14. Phase 13: frontend research page and landing rewrite.
15. Phase 14: launch QA.

If a phase fails, stop and fix it. Do not start the next phase.

## 11. Master Prompt To Start Gemini

Use this as the first prompt:

```text
You are taking over an existing Flask plus Python DCF engine project called Trinsic.

Your job is not to rewrite the app. Your job is to gradually convert it from a DCF Excel dashboard into a valuation-aware SEC filing radar.

Read this file first:
- docs/SEC_FILING_TO_VALUATION_BUILD_PLAN_GEMINI_HANDOFF_2026-05-27.md

Then read:
- dashboard_api.py
- src/dcf_engine/config.py
- src/dcf_engine/pipeline.py
- src/dcf_engine/ingestion/edgar_client.py
- src/dcf_engine/ingestion/market_data.py
- src/dcf_engine/output/excel_builder.py
- templates/landing.html
- templates/dashboard.html
- requirements.txt

Rules:
- Do one phase only.
- Do not rewrite the whole app.
- Do not add AI summaries yet.
- Do not invent financial facts.
- Preserve source metadata.
- Add tests.
- Run tests before reporting done.

Start with Phase 0 only.
```

## 12. Definition Of Finished Product

The product is finished enough for first paid validation when:

1. Public visitors can run a ticker report.
2. Reports show SEC-backed numbers with source links.
3. Reports show filing changes and valuation impacts.
4. Reverse DCF works when market price is available.
5. Assumption QA warns users about weak model assumptions.
6. Red flag radar catches obvious filing risks.
7. Watchlist refresh identifies companies where something changed.
8. Public sample reports exist and can be shared anonymously.
9. Premium Excel export includes source map and warning tabs.
10. Backend blocks unpaid premium exports.
11. No founder identity is required for trust.
12. The app avoids investment advice language.

That is the product people can pay $9.99/month for.

