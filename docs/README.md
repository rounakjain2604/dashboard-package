# IB-Grade DCF Valuation Engine — V12.0.0

**A fully automated, investment-banking-grade Discounted Cash Flow (DCF) valuation engine with an interactive React dashboard, formula-linked Excel export, and PDF memo generation.**

---

## 1. Project Overview

### What This Application Does

This is a production-ready DCF modeling platform that takes a company's historical financials and forecast assumptions, then produces:

- A **16-step financial model** (3-statement model → valuation → analytics)
- An **interactive web dashboard** with 10 analysis tabs and live re-computation
- A **fully formula-linked Excel workbook** (not static values — every cell references the Assumptions sheet)
- Scenario analysis (Base / Bull / Bear), Monte Carlo simulation, sensitivity tables, tornado charts, and comparable company analysis

### Key Features

| Feature | Description |
|---------|-------------|
| **3-Statement Model** | Income Statement, Balance Sheet (IFRS IAS 1 order), Cash Flow Statement |
| **Working Capital Schedule** | DSO/DIO/DPO-driven with prepaid, accrued, and other current items |
| **Capex & Depreciation** | PP&E rollforward with half-year convention for new capex depreciation |
| **Multi-Tranche Debt** | Mandatory amortisation, bullet maturity, cash sweeps |
| **WACC (CAPM)** | Synthetic credit rating (Damodaran grid), optional live data pulls |
| **DCF Valuation** | Gordon Growth + Exit Multiple blended terminal value, mid-year convention |
| **Scenario Analysis** | Configurable Base/Bull/Bear with revenue multipliers, margin shifts, capex adjustments |
| **Monte Carlo** | 10,000-iteration simulation across 5 randomised drivers |
| **Sensitivity Tables** | 2D heatmaps: WACC vs Terminal Growth, Revenue Growth vs EBITDA Margin |
| **Tornado Chart** | ±20% driver swings ranked by equity value impact |
| **Comparable Companies** | Live peer data via yfinance with implied valuation |
| **Excel Export** | Formula-linked workbook with 17 tabs (Verdana, IB-formatted) |
| **PDF Memo** | 10–15 page investment memo (requires ReportLab) |

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, Flask 3.0+ |
| **Frontend** | React 18 (CDN, Babel standalone JSX), Chart.js 4 |
| **Excel** | openpyxl (formula-linked, not static) |
| **PDF** | ReportLab (optional) |
| **Data** | pandas, numpy |
| **Live Data** | yfinance, SEC EDGAR XBRL API (optional) |
| **Deployment** | Vercel (serverless Python), or any WSGI server |

---

## 2. Architecture

### High-Level Diagram

```
┌──────────────────────┐       POST /api/run         ┌────────────────────────┐
│   React Dashboard    │ ──────────────────────────>  │     Flask Backend      │
│  (templates/         │ <──────────────────────────  │   (dashboard_api.py)   │
│   dashboard.html)    │       JSON response          │                        │
│                      │                              │  _build_config_from_   │
│  - 10 analysis tabs  │  POST /api/export-excel      │  payload()             │
│  - Sidebar inputs    │ ──────────────────────────>  │         │              │
│  - Chart.js charts   │ <──────────────────────────  │         ▼              │
│  - KPI cards         │       .xlsx download         │  run_pipeline()        │
└──────────────────────┘                              └──────────┬─────────────┘
                                                                 │
                                                                 ▼
                                                    ┌────────────────────────┐
                                                    │  src/dcf_engine/       │
                                                    │  pipeline.py           │
                                                    │                        │
                                                    │  16-Step Pipeline:     │
                                                    │  IS → WC → CapexDA →  │
                                                    │  Debt → BS → CF →     │
                                                    │  WACC → DCF →         │
                                                    │  Scenarios → MC →     │
                                                    │  Sensitivity →        │
                                                    │  Tornado → Comps →    │
                                                    │  Excel → PDF          │
                                                    └────────────────────────┘
```

### Frontend

- **Single HTML file**: `templates/dashboard.html` (~2,300 lines)
- React 18 loaded via CDN with Babel standalone for JSX transpilation
- Chart.js 4 for all charts (bar, line, heatmap)
- No build step required — runs directly in the browser
- 800ms debounce auto-reruns the model on any input change
- Collapsible sidebar with all model inputs grouped by category

### Backend / API

- **`dashboard_api.py`**: Flask app with these routes:

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Serve dashboard HTML |
| `/api/run` | POST | Run full pipeline, return JSON |
| `/api/export-excel` | POST | Run pipeline, return `.xlsx` |
| `/api/configs` | GET | List preset config files |
| `/api/config/<filename>` | GET | Load a config JSON |
| `/api/data-files` | GET | List CSV/XLSX files in `data/` |
| `/api/data-file-base-values/<filename>` | GET | Extract base-year values from a historical CSV |

### Database

There is no database. All state lives in:
- JSON config files (`config.*.json`) — model assumptions
- CSV files (`data/*.csv`) — historical financials
- The frontend's React state (in-memory)

### Component Communication

1. User adjusts inputs in the sidebar → React state updates
2. 800ms debounce triggers `POST /api/run` with full config JSON
3. Flask builds `DCFEngineConfig` from payload, runs 16-step pipeline
4. Pipeline returns `PipelineResult` → Flask serialises to JSON
5. Dashboard renders tables, charts, and KPI cards from the response

---

## 3. Installation & Setup

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10 or higher |
| pip | Latest |
| Git | For version control |

No Node.js required — the frontend uses CDN libraries.

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/rounakjain2604/dashboard-package.git
cd dashboard-package

# 2. Create a virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Install core dependencies
pip install -r requirements.txt

# 4. (Optional) Install heavy dependencies for full functionality
pip install matplotlib scipy reportlab yfinance
```

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VERCEL` | No | — | Auto-detected on Vercel; caps MC iterations to 2,000, disables live data |
| `VERCEL_ENV` | No | — | Same as `VERCEL` |

No `.env` file is needed for local development.

### How to Run Locally

```bash
# Option A: Direct Python
python dashboard_api.py

# Option B: Windows batch file
run_dashboard.bat

# Option C: With custom port
flask --app dashboard_api run --port 8080
```

The dashboard will be available at **http://localhost:5050**.

---

## 4. Key Files & Folders

### Root Directory

| File | Purpose |
|------|---------|
| `dashboard_api.py` | Flask web server — routes, config parsing, JSON serialisation |
| `config.example.json` | Sample config with default assumptions |
| `config.asian_street_ib_grade.json` | Real config for "Asian Street Eats" (food & beverage) |
| `requirements.txt` | Python dependencies (heavy deps commented out for Vercel) |
| `vercel.json` | Vercel deployment config (routes all traffic to `api/index.py`) |
| `run_dashboard.bat` | Windows launch script |

### `src/dcf_engine/` — Core Engine

| File | Purpose |
|------|---------|
| `__init__.py` | Version (`10.0.0`) |
| `config.py` | All configuration dataclasses (`DCFEngineConfig`, `ForecastConfig`, `WACCConfig`, etc.) with JSON serialisation and alias handling |
| `pipeline.py` | 16-step orchestrator — the heart of the engine |
| `main.py` | CLI entry point (`python -m src.dcf_engine.main`) |

### `src/dcf_engine/statements/` — Financial Statements

| File | Purpose |
|------|---------|
| `income_statement.py` | Projects IS with CAGR/YoY/manual revenue, scenario overrides |
| `balance_sheet.py` | Constructs BS from IS + schedules; cash is a plug to force A=L+E |
| `cash_flow.py` | CFO (indirect) + CFI + CFF; computes UFCF and LFCF |

### `src/dcf_engine/schedules/` — Supporting Schedules

| File | Purpose |
|------|---------|
| `working_capital.py` | DSO/DIO/DPO-driven WC schedule with NWC and Delta NWC |
| `capex_depreciation.py` | PP&E rollforward with half-year convention for new capex |
| `debt_schedule.py` | Multi-tranche debt with amortisation, bullet maturity, cash sweeps |

### `src/dcf_engine/valuation/` — Valuation & Analytics

| File | Purpose |
|------|---------|
| `wacc.py` | CAPM cost of equity + synthetic credit rating for cost of debt |
| `dcf_engine.py` | Core DCF: discount FCFs, compute TV (Gordon + Exit), equity bridge |
| `scenarios.py` | Side-by-side scenario comparison builder |
| `monte_carlo.py` | 10,000-iteration MC simulation (5 randomised drivers) |
| `sensitivity.py` | 2D sensitivity tables (WACC/TG and RevGrowth/Margin) |
| `tornado.py` | ±20% driver swing analysis for tornado charts |

### `src/dcf_engine/comps/`

| File | Purpose |
|------|---------|
| `comps.py` | Comparable companies via yfinance (EV/Revenue, EV/EBITDA, P/E) |

### `src/dcf_engine/ingestion/` — Data Loading

| File | Purpose |
|------|---------|
| `file_loader.py` | Flexible CSV/XLSX loader with auto-detection of tidy/wide format |
| `edgar_client.py` | SEC EDGAR XBRL API client for pulling public company financials |
| `market_data.py` | Live data helpers via yfinance (risk-free rate, beta, ERP) |

### `src/dcf_engine/output/` — Export

| File | Purpose |
|------|---------|
| `excel_builder.py` | Orchestrates workbook creation (calls sheet builders) |
| `excel_formats.py` | Shared formatting: fonts, fills, borders, number formats, Assumptions row map |
| `sheets_core.py` | Formula-linked sheets: Cover, Assumptions, IS, WC, CapexDA, Debt Schedule |
| `sheets_valuation.py` | Formula-linked sheets: Balance Sheet, Cash Flow, WACC, DCF |
| `sheets_analytics.py` | Value-based tabs: Scenarios, Sensitivity, MC, Tornado, Comps, Checks, Audit |
| `pdf_memo.py` | ReportLab-based PDF investment memo (graceful degradation if not installed) |

### `templates/`

| File | Purpose |
|------|---------|
| `dashboard.html` | Single-file React 18 SPA with Chart.js — the entire frontend |

### `data/`

| File | Purpose |
|------|---------|
| `asian_street_financials.csv` | 3 years (2022–2024) of historical data for Asian Street Eats |

### `api/`

| File | Purpose |
|------|---------|
| `index.py` | Vercel serverless entry point — imports Flask app from `dashboard_api.py` |

---

## 5. Excel Export Mechanism

### Libraries Used

- **openpyxl** — the sole Excel library; generates `.xlsx` files with live formulas

### Architecture

The Excel workbook has **17 tabs** split into two categories:

#### Formula-Linked Tabs (live Excel formulas)
These tabs contain **Excel formulas**, not static values. Every formula references the **Assumptions** sheet, so the buyer can change any input in column B and the entire model recalculates in Excel.

| Tab | Builder Function | Source File |
|-----|------------------|-------------|
| Cover | `build_cover()` | `sheets_core.py` |
| Assumptions | `build_assumptions()` | `sheets_core.py` |
| Income Statement | `build_is()` | `sheets_core.py` |
| Working Capital | `build_wc()` | `sheets_core.py` |
| Capex DA | `build_capex_da()` | `sheets_core.py` |
| Debt Schedule | `build_debt_schedule()` | `sheets_core.py` |
| Balance Sheet | `build_bs()` | `sheets_valuation.py` |
| Cash Flow | `build_cf()` | `sheets_valuation.py` |
| WACC | `build_wacc()` | `sheets_valuation.py` |
| DCF | `build_dcf()` | `sheets_valuation.py` |
| Checks | `build_checks()` | `sheets_analytics.py` |

#### Value-Based Tabs (Python-computed results)
These contain static numbers from running the Python simulations. They are not formula-linked.

| Tab | Builder Function |
|-----|------------------|
| Scenarios | `build_scenarios()` |
| Sensitivity | `build_sensitivity()` |
| Monte Carlo | `build_monte_carlo()` |
| Tornado | `build_tornado()` |
| Comps | `build_comps()` |
| Audit Trail | `build_audit()` |

### Where Formulas Are Defined

All formula logic lives in two files:

1. **`sheets_core.py`** — Row constant maps (`IS`, `WC`, `CD`, `DS`, `BS`, `CF`, `WR`, `DC`) define which row number each line item occupies. The `ar(key)` helper generates absolute references like `Assumptions!$B$4`.

2. **`sheets_valuation.py`** — Balance Sheet, Cash Flow, WACC, and DCF formulas.

### Assumptions Sheet Row Map

The `A` dictionary in `excel_formats.py` maps named keys to row numbers in the Assumptions sheet:

```python
A = {
    "rev_cagr": 4, "cogs_pct": 5, "sga_pct": 6, "oopex_pct": 7,
    "dep_rate": 8, "capex_pct": 9, "tax": 10,
    "dso": 11, "dio": 12, "dpo": 13, "div": 14,
    "amort_pct": 15, "prepaid_pct": 16, "accrued_pct": 17,
    "oca_pct": 18, "ocl_pct": 19,
    "rf": 23, "erp": 24, "beta": 25, "sp": 26, "crp": 27,
    "dw": 28, "ew": 29, "icr": 30,
    "tg": 34, "exit_m": 35, "gw": 36, "shares": 37, "cash": 38, "debt": 39,
    "brev": 43, "bcash": 44, "bppe": 45, "bnwc": 46, "bre": 47, "bcs": 48,
    "debt_bal": 51, "debt_rate": 52, "debt_amort": 53, "debt_maturity": 54,
    "goodwill": 57, "intangibles": 58, "olt_assets": 59, "olt_liab": 60,
    "capex_method": 62, "capex_fixed": 63,
}
```

### Key Formula Patterns

```
Revenue (Year 1) = Base_Year_Revenue × (1 + Revenue_CAGR)
Revenue (Year N) = Prior_Year_Revenue × (1 + Revenue_CAGR)
COGS             = Revenue × COGS_%
Gross Profit     = Revenue − COGS
EBITDA           = GP − SGA − Other_OpEx
Depreciation     = →linked from Capex DA sheet
Interest         = →linked from Debt Schedule sheet
UFCF             = NOPAT + D&A − Capex − ΔNWC
DCF DF           = 1 / (1 + WACC)^(year − 0.5)   [mid-year convention]
TV (Gordon)      = Terminal_FCF × (1 + g) / (WACC − g)
TV (Exit)        = Terminal_EBITDA × Exit_Multiple
TV (Blended)     = Gordon × weight + Exit × (1 − weight)
Equity           = EV + Cash − Debt − Minority − Preferred
```

---

## 6. Data Flow

### How User Inputs Flow Through the System

```
User Input (Sidebar)
       │
       ▼
React State (DEFAULT_CONFIG)
       │  800ms debounce
       ▼
POST /api/run  (JSON payload)
       │
       ▼
_build_config_from_payload()
       │  Constructs DCFEngineConfig from:
       │  - forecast (revenue, COGS, SGA, capex, WC, tax)
       │  - wacc (Rf, ERP, beta, weights)
       │  - valuation (TV params, equity bridge)
       │  - monte_carlo (distribution params)
       │  - sensitivity (range params)
       │  - scenarios (Base/Bull/Bear overrides)
       │  - debt_tranches (amortisation schedules)
       ▼
run_pipeline(cfg, historical, base_year_values)
       │
       ▼
PipelineResult → JSON serialisation → HTTP response
       │
       ▼
Dashboard renders: tables, charts, KPIs
```

### Pipeline Computation Steps (in order)

| Step | Name | Depends On | Produces |
|------|------|------------|----------|
| 1 | Income Statement | config, historical | Revenue, COGS, GP, SGA, EBITDA, NI (D&A=0, Interest=0 placeholder) |
| 2 | Working Capital | IS revenue/COGS | AR, Inv, Prep, AP, Accrued, NWC, ΔNWC |
| 3 | Capex & D&A | IS revenue | PP&E rollforward, Depreciation |
| 3b | Auto Debt Tranche | config | Creates tranche from valuation.debt if no explicit tranches |
| 4 | Debt Schedule | debt tranches | Beginning/Ending balance, Interest, Repayment |
| 5 | **Re-link IS** | CapexDA, DebtSched | **Overwrites IS Depreciation & Interest, recalculates EBIT→NI** |
| 6 | Balance Sheet | IS, WC, CapexDA, Debt | Assets = L + E (cash as plug) |
| 7 | Cash Flow | IS, WC, CapexDA, Debt | CFO + CFI + CFF, UFCF, LFCF |
| 8 | WACC | config, live data | Ke (CAPM), Kd (synthetic rating), WACC |
| 9 | DCF | CF, WACC | PV of FCFs, TV, EV, Equity, Price per Share |
| 10 | Scenarios | repeat Steps 1–5+7+9 per scenario | Bull/Bear comparisons |
| 11 | Monte Carlo | config | 10,000 equity value simulations |
| 12 | Sensitivity | config | 2D tables (WACC/TG and RevGrowth/Margin) |
| 13 | Tornado | config | ±20% driver impact ranking |
| 14 | Comps | yfinance | Peer multiples and implied valuation |
| 15 | Excel | all results | Formula-linked .xlsx workbook |
| 16 | PDF | all results | Investment memo (if ReportLab installed) |

**Step 5 is critical** — the IS is initially built with placeholder zeros for Depreciation and Interest. After the Capex DA and Debt Schedule are computed, Step 5 overwrites those values and recalculates EBIT, EBT, Tax, and Net Income downstream.

### How Charts Are Generated

- **Frontend**: Chart.js 4 renders all charts client-side from the JSON response
- **Excel**: openpyxl `BarChart` objects are embedded in the Monte Carlo and Tornado tabs
- **PDF**: ReportLab canvas drawing (if installed)

---

## 7. Deployment

### Local Development

```bash
python dashboard_api.py
# Runs on http://localhost:5050
```

### Vercel (Production)

The project is pre-configured for Vercel serverless deployment:

1. Install the [Vercel CLI](https://vercel.com/docs/cli):
   ```bash
   npm i -g vercel
   ```

2. Deploy:
   ```bash
   vercel --prod
   ```

**How it works:**
- `vercel.json` routes all requests to `api/index.py`
- `api/index.py` adds the project root to `sys.path` and imports the Flask app
- On Vercel: Monte Carlo is capped at 2,000 iterations, live data pulls are disabled

### Other Deployment Options

The Flask app is WSGI-compatible. Deploy with:

```bash
# Gunicorn (Linux/macOS)
gunicorn dashboard_api:app --bind 0.0.0.0:8080

# Waitress (Windows)
waitress-serve --port=8080 dashboard_api:app
```

### Third-Party Services

| Service | Required? | Purpose |
|---------|-----------|---------|
| Vercel | Optional | Serverless hosting |
| yfinance (Yahoo Finance) | Optional | Live beta, risk-free rate, peer comps |
| SEC EDGAR | Optional | Historical financials for public companies |
| Damodaran ERP | Optional | Live equity risk premium |

None of these are required for the core dashboard to function.

---

## 8. Configuration

### Config File Structure

All model assumptions are stored in a single JSON config file. See `config.example.json` for a full template.

```json
{
  "company": { "name": "...", "ticker": "...", "industry": "..." },
  "forecast": {
    "projection_years": 5,
    "revenue_method": "cagr",
    "revenue_cagr": 0.08,
    "cogs_pct_revenue": 0.45,
    "sga_pct_revenue": 0.20,
    "other_opex_pct_revenue": 0.05,
    "tax_rate": 0.25,
    "capex_method": "pct_revenue",
    "capex_pct_revenue": 0.04,
    "depreciation_rate": 0.10,
    "dso": 45, "dio": 50, "dpo": 40
  },
  "wacc": {
    "risk_free_rate": 0.042,
    "equity_risk_premium": 0.055,
    "beta": 1.1,
    "target_debt_weight": 0.30,
    "target_equity_weight": 0.70
  },
  "valuation": {
    "terminal_growth_rate": 0.025,
    "exit_ev_ebitda_multiple": 10.0,
    "gordon_weight": 0.50,
    "cash": 0, "debt": 0,
    "fully_diluted_shares": 1000000
  }
}
```

### Config Aliases

The config parser supports aliases for backward compatibility:

| Alias (in JSON) | Maps To |
|------------------|---------|
| `years` | `projection_years` |
| `opex_pct_revenue` | `sga_pct_revenue` |
| `market_risk_premium` | `equity_risk_premium` |
| `terminal_value_blend_weight_gordon` | `gordon_weight` |
| `accrued_expenses_pct_revenue` | `accrued_pct_revenue` |

### Adding Your Own Data

1. Place a CSV in `data/` with tidy format:
   ```csv
   period,account,amount,statement
   2024,Revenue,5000000,income
   2024,COGS,2250000,income
   2024,Cash,500000,balance
   ```

2. Create a config JSON (copy `config.example.json` and customise)

3. Load the preset from the dashboard dropdown, or pass it via CLI:
   ```bash
   python -m src.dcf_engine.main --config your_config.json
   ```

---

## 9. Known Issues / TODO

### Known Limitations

| Area | Issue | Severity |
|------|-------|----------|
| **Excel Revenue Method** | Excel IS always uses CAGR formulas regardless of `revenue_method` (YoY and manual are not reflected in Excel formulas) | Medium |
| **Excel Scenarios** | Excel does not contain scenario IS/BS — scenarios are value-only in the Scenarios tab | Low |
| **Monte Carlo Defaults** | ~~Fixed in V9.0.0~~ — MC distribution means are now auto-synced from the base case. | ~~Low~~ |
| **Comps Tab** | Requires `yfinance` installed and working internet for peer data. Falls back gracefully. | Low |
| **PDF Memo** | Requires `reportlab` installed. Gracefully skipped if not available. | Low |

### Recommended Improvements

1. **Excel YoY/Manual Revenue** — Extend `build_is()` in `sheets_core.py` to write YoY or manual growth formulas instead of always using CAGR
2. ~~**Auto-sync MC Parameters**~~ — ✅ Completed in V9.0.0
3. **Historical Tab in Excel** — Add a historical data sheet to the Excel workbook with VLOOKUP-based references
4. **Multi-currency Support** — Currency conversion for international models
5. **Unit Tests** — Add pytest fixtures for each pipeline step with known expected outputs
6. **Docker Container** — Containerise for one-command deployment

---

## 10. V12.0.0 Changelog

### Bug Fixed in V12.0.0

| # | Bug | Fix |
|---|-----|-----|
| 1 | **Monte Carlo Excel tab produced `#NAME?` errors on all 1,000 simulation rows** — The `NORM.INV` function used by openpyxl to generate random normal draws was not recognised by Excel because the OOXML format requires the `_xlfn.` prefix for functions introduced in Excel 2010+ (functions with dots in their names). This caused all five driver columns (Revenue Growth, EBITDA Margin, Terminal Growth, WACC, Exit Multiple) to show `#NAME?`, which cascaded into every downstream cell: PV of FCFs, PV of TV, Equity Value, Per Share, all output statistics (Mean, Median, P10–P90), and the histogram frequency bins. | **Prefixed `NORM.INV` with `_xlfn.`** in all five `NORM.INV(RAND(),μ,σ)` formula templates (Cols B–F, rows 67–1066). All simulation, statistics, and histogram formulas now evaluate correctly. Verified via COM automation: zero formula errors across all 1,000 rows, and row-level formula verification matches Python's MC computation to $0.00 precision. |
| 2 | **Monte Carlo histogram bin centers displayed `###` in Excel** — The simulation table header set Column A width to 6 (for the `#` iteration counter), overriding the initial width. Histogram bin center values (e.g. 1,461,310) couldn't render in 6-char-wide cells. | **Increased Column A width** from 6 to 14 so both iteration numbers and histogram bin centers display correctly. |

### Files Changed in V12.0.0

| File | Change |
|------|--------|
| `src/dcf_engine/__init__.py` | Version bumped to `12.0.0` |
| `src/dcf_engine/output/sheets_analytics.py` | Fixed `NORM.INV` → `_xlfn.NORM.INV` in all 5 MC simulation columns; increased Column A width from 6 to 14 |
| `templates/dashboard.html` | Updated dashboard tracker badge from `V11` to `V12` |
| `README.md` | Updated to V12.0.0, added changelog |

---

## 11. V10.0.0 Changelog

### Changes in V10.0.0

| # | Change | Details |
|---|--------|---------|
| 1 | **Dashboard typography and compact layout refresh** | Migrated dashboard UI to Verdana/Consolas system fonts, removed external Google Fonts dependency, and tightened spacing/padding across inputs, cards, tabs, and tables for a professional compact presentation. |
| 2 | **Excel Balance Sheet totals label fix** | Fixed missing label lines in exported Balance Sheet caused by row-key collision in `build_bs()` label map. `TOTAL ASSETS`, `TOTAL LIABILITIES`, and related total labels now render correctly. |
| 3 | **Release tracker update in dashboard** | Updated the dashboard tracker badge from `V9` to `V10`. |
| 4 | **Client delivery packaging workflow** | Added `package_for_client.bat` and `CLIENT_README.md` for deterministic packaging of shippable artifacts into `dist/dcf_engine_v10/`. |

### Files Changed in V10.0.0

| File | Change |
|------|--------|
| `src/dcf_engine/__init__.py` | Version bumped to `10.0.0` |
| `templates/dashboard.html` | Updated UI typography/layout and dashboard tracker badge to `V10` |
| `src/dcf_engine/output/sheets_valuation.py` | Fixed BS label row-key collisions so total lines render in exported Excel |
| `package_for_client.bat` | Added client packaging script with V10 dist path |
| `CLIENT_README.md` | Added client-facing delivery README (V10) |

---

## 12. V9.0.0 Changelog

### Bug Fixed in V9.0.0

| # | Bug | Fix |
|---|-----|-----|
| 1 | **Analysis tabs in Excel not updating when dashboard assumptions change** — Monte Carlo distribution means (`revenue_growth_mean`, `ebitda_margin_mean`, `wacc_mean`, `terminal_growth_mean`, `exit_multiple_mean`) were independent inputs with hardcoded defaults (8% rev growth, 20% margin, 10% WACC, 2.5% TG, 10× exit). When a user changed core assumptions (revenue growth, margins, WACC inputs, terminal value params) in the dashboard, the MC simulation continued to centre on the old defaults, making the Monte Carlo tab in Excel appear stale/unchanged. | **Auto-sync MC means from base case.** Pipeline Step 11 now overwrites MC distribution means with the actual computed values before running the simulation: `revenue_growth_mean` ← `forecast.revenue_cagr`, `ebitda_margin_mean` ← `1 − COGS% − SGA% − Other OpEx%`, `wacc_mean` ← computed WACC from Step 8, `terminal_growth_mean` ← `valuation.terminal_growth_rate`, `exit_multiple_mean` ← `valuation.exit_ev_ebitda_multiple`. The frontend also auto-syncs the MC sidebar inputs via a `useEffect` that fires whenever any upstream assumption changes, so the MC config fields always display the current base-case values. Users can still override the means manually in the Monte Carlo sidebar section. |

### Files Changed in V9.0.0

| File | Change |
|------|--------|
| `src/dcf_engine/__init__.py` | Version bumped to `9.0.0` |
| `src/dcf_engine/pipeline.py` | Step 11 now auto-syncs `cfg.monte_carlo.*_mean` fields from the computed base case before running the MC simulation |
| `templates/dashboard.html` | Added `useEffect` hook that auto-syncs MC distribution means from upstream config values (forecast, WACC, valuation) whenever they change |
| `README.md` | Updated to V9.0.0, added changelog, marked MC auto-sync TODO as completed |

---

## 13. V5.0.0 Changelog

### Bugs Fixed in V5.0.0

| # | Bug | Fix |
|---|-----|-----|
| 1 | **Year 0 BS doesn't balance when `base_retained_earnings` is wrong** — If the provided `base_retained_earnings` doesn't satisfy `Cash + PPE + NWC − Debt − Common Stock`, the BS cash-plug diverges from CF Ending Cash, causing a persistent BS Cash ≠ CF Cash mismatch across all projected years | Pipeline Step 6b now **auto-computes** the implied retained earnings from base values. If the supplied value differs by more than $1, it is overridden with a logged warning. This ensures Year 0 BS balances perfectly, eliminating the cash-plug divergence |
| 2 | **Asian Street Eats config had `base_retained_earnings: 0`** — The sample config omitted a correct RE, causing a $128,000 BS/CF mismatch on every projected year | Updated to `base_retained_earnings: 128000` (= $25k cash + $100k PPE + $3k NWC) |

### Tests Added in V5.0.0

| # | Test | Coverage |
|---|------|----------|
| 1 | **`test_v5_cross_check.py`** — Comprehensive 17-category cross-check | Income Statement, Working Capital, Capex & DA, Debt Schedule (multi-tranche), IS Re-linking, Cash Flow, BS Cash == CF Cash, BS Balance, Auto RE, WACC, DCF, UFCF, Excel formulas, Scenarios, Tornado, Multi-Tranche debt, Excel vs Python values |
| 2 | **Deliberately extreme inputs** — Revenue $7.78M, 28% tax, 0.85 beta, 15% dividend payout, two debt tranches, negative auto-RE | Ensures the engine handles edge cases and all figures cross-check to the penny |

---

## 14. V4.0.0 Changelog

### Bugs Fixed in V4.0.0

| # | Bug | Fix |
|---|-----|-----|
| 1 | **CF Ending Cash ≠ BS Cash** — Balance Sheet used a WC placeholder for cash instead of linking to Cash Flow Ending Cash | Pipeline now builds CF *before* BS (swapped Steps 6/7) and passes `cf_ending_cash` to the BS builder |
| 2 | **Shares in millions in Excel** — `build_assumptions` stored `shares/1e6` (e.g. 2.0 for 2M shares), so the DCF formula `Equity/B37` divided by 2 instead of 2,000,000 | Assumptions now stores the absolute share count |
| 3 | **Credit spread not surfaced** — `WACCResult` had no `credit_spread` field; pipeline fallback logic used `pre_tax_kd − rf` which differed from the actual synthetic spread | Added `credit_spread` to `WACCResult` dataclass, populated from `synthetic_credit_spread()` |
| 4 | **Amortisation uncapped** — Python IS computed `Rev × amort_pct` every year regardless of remaining intangible balance; Excel used `MIN(Rev×amort_pct, intangibles)` | Step 5 and Step 10 (Scenarios) re-linking now tracks `_remaining_intangibles` and caps amortisation at surviving balance |

### V3.0.0 Changelog (prior release)

| # | Bug | Fix |
|---|-----|-----|
| 1 | Monte Carlo received `cogs_pct_revenue` as EBITDA margin (e.g., 33% instead of actual ~6%) | Now passes correct EBITDA margin: `1 − COGS% − SGA% − Other OpEx%` |
| 2 | Scenario IS had Depreciation=0 and Interest=0 (no re-linking from schedules) | Scenarios now re-link D&A from Capex schedule and Interest from Debt schedule, then recalculate EBIT→NI |
| 3 | Monte Carlo hardcoded 50/50 TV blend, ignoring `gordon_weight` | Now uses configurable `gordon_weight` from `ValuationConfig` |
| 4 | Monte Carlo TV discount factor used end-of-year but FCFs used mid-year | TV now uses `(1+WACC)^(n−0.5)` for consistency with mid-year FCF convention |
| 5 | Tornado used `da = revenue × capex_pct` (D&A = Capex, netting to zero in FCF) | Tornado now accepts a separate `da_pct` parameter for depreciation |
| 6 | Sensitivity hardcoded 50/50 TV blend | Now uses configurable `gordon_weight` |
| 7 | Sensitivity/Tornado TV discount factors used end-of-year convention | Both now use mid-year convention matching the core DCF engine |
| 8 | Balance Sheet intangibles used `amort × year_index` approximation | Now tracks cumulative amortisation properly across years |
| 9 | Tornado Excel chart referenced wrong columns (col 6,7 instead of 5,6) | Fixed to reference correct "Equity at Low" and "Equity at High" columns |
| 10 | Monte Carlo histogram never written to Excel (wrong attribute name) | Fixed `mc_result.histogram` → `mc_result.histogram_data` |

---

## License

This project is licensed under the [MIT License](../LICENSE).
