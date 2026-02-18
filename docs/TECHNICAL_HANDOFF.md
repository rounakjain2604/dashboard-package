# Technical Handoff: IB-Grade DCF Valuation Engine

## 1. Executive Summary

This application is a hybrid valuation platform that combines a modern frontend experience with a Python calculation backend to produce institutional-grade valuation outputs for analysts, investors, and buyers.

At its core, the system runs financial projections, scenario analysis, and Monte Carlo simulation in Python (10,000+ iterations in local mode), then injects the resulting model logic into a live, formula-linked Excel workbook using OpenPyXL rather than exporting static numbers.

The result is a dual-delivery model:
- **Interactive runtime analytics** via web API for immediate analysis.
- **Auditable Excel output** where end users can change assumptions and watch formulas recalculate natively.

## 2. System Architecture

### Frontend

- **Target architecture:** Next.js (React), Tailwind CSS, Lucide Icons.
- **Current codebase implementation:** React-based SPA served from `templates/dashboard.html` via Flask, with Chart.js visualizations and no Node build dependency.
- The backend contract is JSON-first, so a Next.js/Tailwind/Lucide UI can consume the same endpoints with minimal API adaptation.

### Backend

- **Language:** Python 3.10+
- **Web framework:** Flask (`dashboard_api.py`) with serverless entry compatibility (`api/index.py`).
- **Core engine:** modular valuation pipeline under `src/dcf_engine/`.

### Key Libraries

- `pandas` & `numpy`: financial data shaping, vectorized projection logic, Monte Carlo arrays.
- `openpyxl`: workbook creation, formula injection, formatting, chart embedding.
- `scipy`: statistical distributions and sampling support for simulation workflows.
- Optional integrations: `yfinance` (market/comps live pulls), `reportlab` (PDF memo).

### Data Flow

1. Frontend captures user assumptions (forecast, WACC, valuation, scenarios, Monte Carlo inputs).
2. Payload is sent to Python backend (`POST /api/run`).
3. Backend maps JSON into typed config dataclasses and runs the 16-step valuation pipeline.
4. Pipeline returns structured outputs (statements, DCF, sensitivities, tornado, comps, simulation stats).
5. For export, backend reruns pipeline and writes a formula-linked workbook (`POST /api/export-excel`).
6. User receives either API JSON for UI rendering or a downloadable `.xlsx` for offline analysis.

## 3. Directory Structure & Key Files

- `dashboard_api.py` — primary Flask app; request parsing, config assembly, pipeline invocation, JSON serialization, export endpoint.
- `api/index.py` — serverless bootstrap for Vercel deployment.
- `templates/dashboard.html` — single-file frontend UI and dashboard logic.
- `src/dcf_engine/pipeline.py` — 16-step orchestration layer for all modeling stages.
- `src/dcf_engine/valuation/monte_carlo.py` — **Monte Carlo logic** (distribution sampling, valuation distribution, histogram/stats).
- `src/dcf_engine/output/excel_builder.py` — **Excel injection/export orchestrator** (builds final workbook).
- `src/dcf_engine/output/sheets_core.py` — core formula-linked sheet writers and row/cell mapping helpers.
- `src/dcf_engine/output/sheets_valuation.py` — valuation sheet formulas (WACC/DCF/terminal value bridge).
- `src/dcf_engine/output/excel_formats.py` — style system and assumptions row map used by formula generators.
- `src/dcf_engine/config.py` — typed configuration objects and alias/backward-compatibility mapping.
- `config.example.json` — canonical template config for onboarding.
- `config.asian_street_ib_grade.json` — production-grade sample assumptions for demo/use-case replication.
- `data/asian_street_financials.csv` — historical financial input sample.

## 4. The "Secret Sauce": Excel Injection Logic

### Formula Injection vs Value Dumping

Instead of exporting static values, the engine writes native Excel formulas into target cells so the workbook is computationally alive after export.

Examples of injected formula behavior:
- Revenue growth formulas reference Assumptions inputs.
- Statement links (IS/BS/CF) remain interconnected.
- DCF discount factors and terminal value formulas recalculate automatically when assumptions change.

This provides auditability and buyer confidence because Excel remains transparent and editable.

### Mapping Python Logic to Excel Coordinates

The export layer uses deterministic row/column maps and helper utilities to place formulas:

- `excel_formats.py` contains the `A` map (assumption keys → fixed row numbers on the Assumptions sheet).
- Sheet builders (`sheets_core.py`, `sheets_valuation.py`, `sheets_analytics.py`) define line-item row constants and generate formulas referencing those coordinates.
- Helper conventions (e.g., absolute references like `Assumptions!$B$<row>`) ensure formulas remain stable when workbook opens on client machines.

Practically, Python computes where each line item belongs, writes either an Excel expression string or a value, applies institutional formatting, and preserves cross-sheet linkage for downstream tabs.

## 5. Installation & Setup Guide

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd dashboard_package
```

### Step 2: Backend Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Frontend Setup

Current implementation is server-rendered/static from Flask and does not require Node.

If migrating to a dedicated Next.js frontend, use:

```bash
npm install
npm run dev
```

and point frontend API calls to the Python backend base URL.

### Step 4: Environment Variables

- `VERCEL` / `VERCEL_ENV` (optional): toggles cloud-safe behavior (caps Monte Carlo iterations, disables live market pulls).
- No mandatory `.env` variables are required for local core operation.

## 6. Extension Guide (How to Customize)

### Scenario A: Add a New Valuation Model (e.g., LBO)

1. Add a new module under `src/dcf_engine/valuation/` (e.g., `lbo.py`) containing assumptions, debt waterfall logic, and return metrics (IRR/MOIC).
2. Extend `src/dcf_engine/config.py` with typed LBO config sections.
3. Integrate orchestration in `src/dcf_engine/pipeline.py` as a new step (or optional branch) without breaking DCF path.
4. Expose output payload fields in `dashboard_api.py` for UI rendering.
5. Add an export tab writer in `src/dcf_engine/output/sheets_analytics.py` or a new sheet module for LBO output.

Design rule: preserve separation between **calculation layer** (Python objects) and **presentation/export layer** (API/Excel).

### Scenario B: Update Excel Template (e.g., Colors or New Rows)

1. Update style tokens and reusable formats in `src/dcf_engine/output/excel_formats.py`.
2. If adding rows, update row-constant maps and all dependent formula references in relevant sheet builder files.
3. Keep assumption row mapping synchronized (`A` dictionary) to avoid broken references.
4. Validate exported workbook by changing assumptions directly in Excel and confirming full model recalculation.

Best practice: treat row maps as schema. Any insertion requires controlled updates to all downstream formulas.

## 7. API Reference (Brief)

Primary implemented endpoints:

- `GET /` — serves dashboard UI.
- `POST /api/run` — runs full valuation pipeline and returns JSON model outputs.
- `POST /api/export-excel` — runs pipeline and returns downloadable formula-linked `.xlsx`.
- `GET /api/configs` — lists available `config.*.json` presets.
- `GET /api/config/<filename>` — loads a specific configuration JSON.
- `GET /api/data-files` — lists available historical source files.
- `GET /api/data-file-base-values/<filename>` — extracts latest base-year values from historical data.

Equivalent naming for external frontend teams:
- `/api/calculate` can map to `/api/run`.
- `/api/export` can map to `/api/export-excel`.

Typical `POST /api/run` payload blocks:
- `company`: name, ticker, industry, currency metadata.
- `forecast`: projection horizon, revenue mode, margin assumptions, capex/WC/tax drivers.
- `wacc`: CAPM inputs and target capital structure weights.
- `valuation`: terminal assumptions, bridge items, diluted shares.
- `monte_carlo`, `sensitivity`, `scenarios`, `debt_tranches`, plus optional `data_file` and base-year values.

## 8. Financial Logic Validation

The model’s valuation framework follows standard corporate finance methodology:

- **WACC:** CAPM-derived cost of equity, synthetic rating-based cost of debt, tax-effected blended capital cost.
- **DCF:** discounted FCF stream with mid-year convention support.
- **Terminal Value:** Gordon Growth and Exit Multiple approaches, including weighted blend (`gordon_weight`).

Model integrity controls include:

- **Balance Sheet balancing logic** with cash plug behavior to enforce Assets = Liabilities + Equity.
- **IS re-linking after schedule build** (depreciation and interest are overwritten from Capex/Debt schedules before final NI).
- **Cross-statement coherence checks** (e.g., BS cash consistency with CF outputs).
- **Assumption-to-formula traceability** in Excel through explicit cell-coordinate mapping.

For client transfer readiness, these controls should be validated using sample configs before production go-live and after any structural model edits.
