# Project Viability Assessment Brief

## Instructions for the Reviewing AI

You are being asked to provide an **independent, brutally honest viability assessment** of a software project. The founder wants your unbiased opinion — not encouragement, not pessimism, but a grounded, quantitative assessment.

**Before answering**, please analyze the full codebase in this repository (`dashboard_package/`). Key files to examine:

- `dashboard_api.py` — Flask backend, API endpoints, full pipeline orchestration
- `src/dcf_engine/pipeline.py` — 16-step valuation pipeline
- `src/dcf_engine/config.py` — Typed configuration objects (WACC, DCF, Monte Carlo, Scenarios)
- `src/dcf_engine/ingestion/edgar_client.py` — SEC EDGAR XBRL API client (auto-pulls financials by ticker)
- `src/dcf_engine/ingestion/market_data.py` — Live market data (yfinance: beta, risk-free rate, ERP, peer snapshots)
- `src/dcf_engine/valuation/monte_carlo.py` — 10,000+ iteration Monte Carlo simulation
- `src/dcf_engine/output/excel_builder.py` — Excel export orchestrator
- `src/dcf_engine/output/sheets_core.py` — Formula injection engine (writes native Excel formulas, not static values)
- `src/dcf_engine/output/sheets_valuation.py` — WACC/DCF/Terminal Value formula sheet builder
- `templates/dashboard.html` — Full React + Chart.js frontend (single-file, premium UI)
- `docs/TECHNICAL_HANDOFF.md` — Full technical architecture documentation

---

## 1. What Has Been Built

A **hybrid valuation platform** that combines a modern web frontend with a Python calculation backend to produce institutional-grade valuation outputs. The system:

### Core Engine
- Runs a **16-step financial modeling pipeline** covering: Income Statement, Balance Sheet (with cash-plug balancing logic), Cash Flow Statement, Working Capital Schedules, Capex & D&A Schedules, Debt Schedules, WACC (CAPM-derived), DCF Valuation (Gordon Growth + Exit Multiple blend with mid-year convention), Sensitivity Analysis (WACC vs. Terminal Growth, Revenue vs. Margin), Tornado Charts, Scenario Comparison (Base/Bull/Bear), Monte Carlo Simulation (10,000+ iterations), and Comparable Company Analysis.
- All financial math is **deterministic Python** (numpy, pandas, scipy). Zero reliance on LLMs for calculations. No hallucination risk.

### Data Ingestion (Already Built)
- **SEC EDGAR Client** (`edgar_client.py`): Resolves ticker → CIK, pulls XBRL company facts, maps ~40 US-GAAP concepts to friendly names, filters to 10-K annual filings, deduplicates, and outputs a tidy DataFrame. Rate-limited per SEC policy.
- **Live Market Data** (`market_data.py`): Pulls live 10-Year Treasury yield (risk-free rate), company beta, peer snapshots (market cap, EV, revenue, EBITDA, net income), and Damodaran's implied Equity Risk Premium — all via yfinance and web scraping.

### Excel Export (The "Secret Sauce")
- Instead of dumping static numbers, the engine **injects native Excel formulas** into cells using openpyxl. Revenue growth formulas reference Assumptions inputs. IS/BS/CF statements remain interconnected. DCF discount factors and terminal value formulas recalculate automatically when assumptions change.
- Uses deterministic row/column coordinate mapping so formulas remain stable across machines.
- The output is an **auditable, fully unlocked, formula-active .xlsx workbook** that any analyst can open in Excel, change assumptions, and watch the entire model recalculate natively.

### Frontend
- Premium React-based SPA with Chart.js visualizations, served via Flask.
- Clean, institutional-grade aesthetic (DM Serif Display + DM Sans typography, warm neutral palette, card-based layout with KPI rows, heatmaps, distribution bars, and interactive data tables).
- Sidebar navigation, settings panel, and real-time model status indicators.

### Deployment Readiness
- `vercel.json` and `api/index.py` already configured for Vercel serverless deployment.
- Monte Carlo iterations auto-capped on Vercel to prevent timeouts.
- Live market data calls disabled on Vercel (can be toggled).

---

## 2. What Has NOT Been Built Yet

The following pieces are missing and would need to be added (estimated 6-10 hours of vibe-coding):

1. **Ticker-to-Live-Model Integration**: The `EdgarClient` and `market_data` modules exist but are NOT yet wired into the main `/api/run` and `/api/export-excel` endpoints. Currently, users must manually upload a CSV or configure all assumptions by hand. The planned upgrade: user types a ticker (e.g., "NVDA"), and the system auto-pulls SEC historicals, auto-calculates WACC from live market data, and auto-populates forecast defaults from historical averages.

2. **Payment Gateway**: No payment integration exists. Plan is to use Lemonsqueezy (Merchant of Record) to avoid RBI/Stripe India compliance issues. Pricing: $10/month with a "5 free models, then pay" freemium tier.

3. **User Authentication / Usage Tracking**: No login system or usage limiter. Needed for the freemium model.

4. **Public Deployment**: The app has not been deployed to production. Domain `trinsic.space` is already purchased.

---

## 3. Founder Profile & Constraints

- **Background**: CA Finalist (Chartered Accountancy, India) + CFA Level 2 Candidate. Deep domain expertise in corporate finance, valuation, IFRS/US-GAAP, and financial modeling.
- **Coding Ability**: Cannot write code manually. Uses AI-assisted "vibe coding" (ChatGPT/Claude/Gemini) to generate all code. Successfully built the entire existing codebase this way.
- **Time Constraints**: Currently in a full-time CA Articleship (Monday-Saturday, 11 AM - 7 PM). CA Final exams in May 2027. Available time: evenings, late nights, and Sundays only.
- **Financial Constraints**: ~$20 budget for AI coding tools. No VC funding. Pure bootstrap.
- **Anonymity Requirement**: Must remain 100% anonymous. Cannot use real name, personal LinkedIn, or personal social media. Product must be marketed under a brand name only.
- **Prior Attempt**: Previously tried to sell the raw codebase for $500. Found zero buyers (not even free users), because the product required Python setup and local installation — too much friction for finance professionals.

---

## 4. The Business Plan

### Target Market
- **Primary**: Retail investors, CFA/MBA/CA students, and boutique investment analysts globally who want institutional-grade, formula-active Excel valuation models but cannot afford Canalyst ($10,000+/year) or AlphaSense.
- **Secondary**: Independent financial advisors, family offices, and small-to-mid-sized PE/VC firms.

### Pricing
- **Freemium**: 5 free model generations (any ticker), then $10/month for unlimited access.

### Distribution Strategy (Anonymous, Zero-Budget)
1. Generate 5 pristine Excel models for high-interest stocks (Nvidia, Tesla, Apple, Reliance, Microsoft).
2. Post educational methodology breakdowns + free Google Drive download links on Reddit (r/CFA, r/FinancialModeling, r/ValueInvesting, r/wallstreetbets).
3. Screen-record a 45-second faceless demo video, post on X (Twitter) and YouTube Shorts.
4. Seed free templates in Finance Discord servers and Telegram groups.
5. All files contain a watermark/note: "Generated by Trinsic. Build yours at trinsic.space"
6. SEO: Landing page optimized for long-tail keywords like "free Nvidia DCF model Excel download."

### Revenue Target
- $200 MRR (20 paying subscribers) within 3-4 weeks of launch.

---

## 5. Competitive Landscape

### Direct Competitors (Enterprise Tier — $10,000+/year)
- **AlphaSense / Canalyst**: Pre-built, drivable financial models for thousands of companies. Enterprise-only pricing.
- **Hebbia** ($700M valuation): AI-native document analysis and Excel model generation from unstructured data.
- **Fintool** (Acquired by Microsoft, April 2026): AI copilot for SEC filing analysis with traceable citations.

### Indirect Competitors (Free/Low-Cost Tier)
- **Screener.in / Tickertape**: Read-only financial dashboards. No editable Excel export. No DCF. No Monte Carlo.
- **Yahoo Finance**: Basic financials. No modeling, no export.
- **Wall Street Prep / BIWS**: Sell static Excel templates for $200-$500. Not dynamically generated. Not ticker-specific.
- **Generic ChatGPT/Claude**: Can discuss valuation concepts but cannot generate formula-active Excel workbooks with deterministic math.

### Unique Differentiator
No product on the market currently allows a user to type a stock ticker and instantly download a fully formula-active, institutional-grade Excel workbook (with 3-statement model, DCF, Monte Carlo, sensitivity analysis, and comps) for $10/month. The closest alternative (Canalyst) costs 100x more and only sells to institutions.

---

## 6. Questions for Your Assessment

Please provide your honest, independent opinion on the following:

1. **Technical Quality**: After examining the codebase, is the engineering quality sufficient for a production SaaS product? Are there critical architectural flaws?

2. **Market Viability**: Is there genuine, paying demand for a $10/month "1-click DCF Excel generator" among retail investors, finance students, and boutique analysts? Or is this a solution looking for a problem?

3. **Competitive Risk**: Given that Hebbia, AlphaSense, and Microsoft (via Fintool) are investing billions in AI-powered financial analysis, will this product be made obsolete within 12 months? Or is the "formula-active Excel export" niche sufficiently differentiated?

4. **Distribution Feasibility**: Can the anonymous, zero-budget Reddit/Discord/X seeding strategy realistically generate 1,000+ targeted visitors and 20 paying users within 3-4 weeks?

5. **Founder-Market Fit**: Given the founder's constraints (CA articleship, no coding skills, anonymity requirement, $20 budget), is this project realistically executable, or is the execution risk too high?

6. **Overall Verdict**: On a scale of 1-10, rate the overall viability of this project. What is the single biggest risk, and what is the single biggest opportunity?

7. **What am I missing?**: Is there a critical blind spot — either a hidden opportunity or a fatal flaw — that the founder has not considered?
