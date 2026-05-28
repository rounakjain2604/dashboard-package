# Trinsic Business Model and Feature Roadmap Report

Date: 2026-05-27

Project reviewed: `D:\Rounak\Study\Ideas\dashboard_package`

## 1. Executive conclusion

The current project is not just a formula-linked Excel file. The core engine is a real valuation system: it has a Flask API, a React dashboard, a 16-step DCF pipeline, 3-statement modeling, WACC, scenarios, sensitivities, tornado charts, Monte Carlo, comps, PDF memo generation, and formula-linked Excel output.

The business problem is that the current public offer still looks like "pay for an Excel DCF export." That is fragile because users will rightly think:

- "If I give bad assumptions, the model output is garbage."
- "I can get free stock data elsewhere."
- "I can ask ChatGPT or Claude to summarize a filing."
- "Why should I pay before I trust the data, model, and methodology?"

The better business model is:

1. Use free sign-in to give users a set of trust-building research utilities.
2. Charge $9.99/month, or $99.99/year, for a compact valuation research workflow that saves time even before the user buys or downloads a full DCF model.
3. Keep the full formula-linked DCF workbook as a premium export or credit-based product.
4. Later, sell founder-vetted premium models at a higher price because your CA/CFA background becomes part of the product trust.

Recommended positioning:

> Trinsic is an SEC-backed valuation research workspace. It helps users understand what a stock price implies, checks whether assumptions are reasonable, tracks filing-driven changes, and generates auditable valuation outputs. The full formula-linked DCF model is the premium export or early-subscriber bonus, not the whole product.

The most important strategic shift is this: the subscription should not be sold as "pay us for a DCF." It should be sold as "pay us to shorten your repeatable equity-research workflow." The DCF workbook can still be valuable, but it should sit inside a broader recurring habit: screen, inspect, compare, stress-test, watch, and export.

This reframes the business from "Excel file seller" to "valuation workflow subscription."

## 2. Current project snapshot

### 2.1 What exists now

The repository contains:

- `dashboard_api.py`: Flask backend with public routes, dashboard route, sample pages, API calculation route, Excel export route, and request capture.
- `templates/landing.html`: public landing page with free sample models and current access tiers.
- `templates/dashboard.html`: single-file React dashboard with 10 valuation tabs, settings panel, Chart.js charts, live reruns, and a paywall modal for export.
- `src/dcf_engine/pipeline.py`: 16-step engine orchestration.
- `src/dcf_engine/ingestion/edgar_client.py`: SEC EDGAR XBRL client already built.
- `src/dcf_engine/ingestion/market_data.py`: yfinance-based market data helpers.
- `src/dcf_engine/output/excel_builder.py`: formula-linked Excel workbook builder.
- `src/dcf_engine/sample_models.py`: public sample models for NVDA, TSLA, AAPL, MSFT, and AMZN.
- `docs/FULL_DEPLOYMENT_HANDOVER_PLAN.md`: deployment and monetization handover plan.

The current public offer in code is:

- Free sample workbooks for 5 tickers.
- $19 custom ticker workbook on the landing page.
- $49 5-ticker pack on the landing page and dashboard paywall.
- Checkout links are placeholder/env-driven; when absent, users are sent to email or a temporary LemonSqueezy pause message.

### 2.2 Core strengths

The product already has defensible assets:

- Deterministic valuation math rather than LLM-generated calculations.
- Formula-linked Excel output, not static workbook dumps.
- Scenario, sensitivity, Monte Carlo, tornado, and comps already implemented.
- SEC EDGAR ingestion module already exists.
- Public sample model funnel exists.
- Render deployment configuration exists.
- Basic production hardening has started: request IDs, generic public errors, path safety helper, request size limit.

The most valuable current asset is not the dashboard. It is the ability to convert structured assumptions into an auditable Excel model.

### 2.3 Current business and trust gaps

The important gaps are:

- SEC EDGAR ingestion is not yet wired into the public user journey.
- Market-data defaults exist but are not productized as "one ticker in, clean model preview out."
- No authentication.
- No subscription state.
- No database.
- No usage metering.
- No payment webhook.
- No credit ledger.
- No persistent export history.
- No source map that shows exactly which SEC facts were used.
- No assumption quality score.
- No user-facing methodology page with transparent limitations.
- No clear difference between free, $9.99 core, and premium DCF export.
- The frontend export button is paywalled, but the backend `/api/export-excel` endpoint is still callable if someone posts directly to it.
- Landing page says the sample sheets are protected; `excel_builder.py` uses a static sheet protection password for sample workbooks. That is fine for light friction, not true security.
- Docs mention V12, V13, and dashboard V14 in different places. This is small technically, but bad for trust.

### 2.4 Validation note

I ran a targeted test command:

```powershell
python -m pytest tests\test_cross_check.py tests\test_monte_carlo_e2e.py -q
```

The Monte Carlo e2e script printed 98 passed / 0 failed, but the pytest run ended with an internal error because `tests/test_monte_carlo_e2e.py` calls `sys.exit(0)` at import/collection time. That means the model logic appears to pass that script, but the test file should be cleaned up so it behaves like a normal pytest module.

There is also a test comment in `tests/test_cross_check.py` flagging a potential Python-vs-Excel amortisation mismatch when intangibles are zero. This is not necessarily fatal, but it should be cleaned up before using "fully cross-checked" as a public claim.

## 3. Market landscape and pricing snapshot

Market research was done on 2026-05-27. Pricing can change, so this is a current snapshot rather than a permanent truth.

### 3.1 Competitor pricing and feature implications

| Competitor | Current observed offer | Pricing observed | What it means for Trinsic |
|---|---:|---:|---|
| TIKR | Stock research terminal with financials, filings, estimates, valuation models, and Excel export capabilities | Free, Plus $24.95/month, Pro $54.95/month | Users can already get broad public-company research at $25-$55/month. Trinsic cannot win as a generic stock dashboard. |
| Koyfin | Broad market data, dashboards, screeners, financials, estimates, filings, transcripts, custom formulas/templates | Free, Plus $39/month, Premium $79/month, advisor tiers above that | $9.99 can work only if the product is narrower and faster for valuation-specific workflows. |
| Fiscal.ai / FinChat successor | AI/data research terminal with financials, filings, DCF modeling, AI prompts, estimates, price targets; export in higher tier | Free, Pro $39/month, Enterprise $199/month | AI financial research is already being bundled with data. Trinsic needs auditable model outputs and source-linked assumption QA. |
| Marketsheets | Spreadsheet financial data formulas for Excel/Sheets/web app | Free, Standard $9.99/month | A $9.99 plan cannot be just data-in-spreadsheet. It must include interpretation and model workflow. |
| Wisesheets | Excel/Google Sheets financial data add-on and templates | Official blog describes Pro $60/year and Elite $120/year | This is a direct low-price substitute for raw spreadsheet data. Trinsic must be more than an add-in. |
| GuruFocus | Fundamental investing platform, screener, data, DCF calculator, Excel/Sheets add-ons | Premium $549/year, Premium Plus $1,398/year, Pro $2,448/year | There is willingness to pay for value-investing data, but trust and breadth matter. |
| ValueSense | Intrinsic value tools, DCF, reverse DCF, screeners, AI charting, Excel downloads | Pricing page shows high paid tiers and download limits | DCF and reverse DCF are already product categories. Trinsic needs better auditability and Excel export quality. |
| Intrinsik | Automated SEC filing based DCF, bear/base/bull scenarios, fair value, sensitivity matrix | "Free to start" and 5 free analyses/month shown publicly | This is the clearest direct warning. A simple "ticker to DCF fair value" preview is not enough. |
| Tegus / Canalyst | 4,000+ analyst-built functioning financial models, Excel workflows, expert calls, transcripts | Contact sales / institutional | This validates that high-quality Excel models are valuable, but they win on analyst-built quality and data depth. |
| AlphaSense | AI market intelligence with filings, transcripts, broker research, expert calls, private company data | Annual subscriptions, contact sales | Enterprise AI research is not the first target. Trinsic should own the low-cost individual/student/boutique niche. |
| Quartr | Earnings calls, transcripts, filings, slides, AI chat, alerts, transcript search | Free mobile, Pro/API contact sales | Filing/transcript utilities are competitive. If Trinsic adds summaries, they need citations and model integration. |
| ChatGPT Plus | General AI assistant with file upload/analysis and advanced reasoning | $20/month | Plain filing summaries are vulnerable. Trinsic must be deterministic, structured, source-linked, and exportable. |

### 3.2 What competitors are really charging for

The pricing is not mainly justified by hosting. Hosting is a small cost at the validation stage. The real pricing power comes from five things:

1. Licensed and standardized data.

   Platforms like Koyfin, Fiscal.ai, Finsheet, Finbox, Wisesheets, and TIKR charge for clean history, estimates, ratios, market data, transcripts, exports, and breadth. The hard part is not showing a table; it is making thousands of companies comparable, current, and trusted.

2. Data normalization and auditability.

   SEC data is free, but raw XBRL is messy. A user pays when the product maps concepts correctly, handles missing facts, flags inconsistencies, and shows where the number came from.

3. Workflow speed.

   Tools like Daloopa, V7 Go, and Fiscal.ai sell "do the tedious work in minutes." This is the real user pain: spreading historicals, checking filings, comparing peers, updating models, and exporting usable outputs.

4. Retention loops.

   Watchlists, alerts, saved screens, saved dashboards, new filing notices, and repeat screens justify monthly billing better than one-off DCF downloads.

5. Trust.

   The buyer is ultimately paying for confidence: fewer formula mistakes, fewer bad assumptions, clearer sources, and repeatable methodology. This is where your CA/CFA background can matter, but only if the product expresses it through review notes, methodology pages, caveats, and source trails.

The implication for Trinsic is clear: the low-price advantage can work only if Trinsic avoids expensive licensed-data dependency in the beginning and builds on free SEC EDGAR data, cached carefully and presented with strong source metadata. Undercutting competitors is not a pricing trick; it must come from a lower-cost data architecture and a narrower product promise.

### 3.3 Free alternatives users can use

Users can get many inputs for free:

- SEC EDGAR has public APIs for submissions and XBRL company facts, with no API key required.
- Company 10-Ks, 10-Qs, and 8-Ks are free.
- Yahoo Finance and similar websites give price, market cap, financial summaries, and rough ratios.
- Free DCF calculators exist.
- ChatGPT, Claude, Gemini, Perplexity, and other assistants can summarize text and explain concepts.
- Google Sheets and Excel can pull some market data.
- Reddit, Substack, and finance blogs publish templates and valuation writeups.

Therefore, the $9.99 plan must not sell "access to data." It must sell a workflow:

- Source-linked facts.
- Time saved.
- Assumption sanity checks.
- Reverse DCF interpretation.
- Peer context.
- Watchlist/alerts.
- Clean exportable outputs.

### 3.4 Market demand view

Demand likely exists, but not for a generic "AI stock tool."

Demand is strongest for:

- Students and early analysts who need clean valuation outputs quickly.
- Retail fundamental investors who want a better sanity-check process.
- Finance creators who need repeatable stock snapshots.
- Small advisory/research shops that cannot justify Koyfin/TIKR/Fiscal/GuruFocus.
- Users who want Excel outputs but do not want to build models from scratch.

Demand is weak for:

- People who want buy/sell signals.
- Users who expect full institutional data at $5.
- Users who do not understand valuation assumptions.
- Users who just want a one-line fair value estimate.

The product should avoid promising "accurate intrinsic value." It should promise "a disciplined valuation workflow."

## 4. Strategic business model recommendation

### 4.1 Recommended product ladder

| Tier | Price | Purpose | What users get |
|---|---:|---|---|
| Free sign-in | $0 | Build trust and collect qualified users | Limited ticker snapshots, reverse DCF teasers, source-linked SEC facts, sample workbooks, methodology pages |
| Core subscription | $9.99/month or $99.99/year | Recurring low-friction research workflow | Top five tools: SEC snapshot, reverse DCF, peer comps, filing-change alerts, watchlist/screening workflow, plus lite PDF/CSV |
| DCF export credits | $5-$10/export or $19/5 credits | Monetize high-intent users without forcing a heavy subscription | Full unlocked formula-linked Excel DCF exports |
| Premium DCF subscription | $19.99-$29.99/month after demand is proven | Increase ARPU once trust exists | More exports, saved models, richer source maps, sector templates |
| Founder-vetted model | $49-$99/model | Sell trust and expertise, not automation | CA/CFA-reviewed assumptions, notes, and quality check |

My recommendation: do not start with a $29/month DCF subscription. Start with $9.99/month or $99.99/year for the core workflow, and keep DCF exports as credits or early-subscriber bonuses. Once 10-20 users have paid and 50-100 users repeatedly use free/core tools, test a premium DCF tier.

### 4.2 Why $9.99 can work

$9.99 is too low for a broad data platform, but it can work for a narrow valuation workflow if the product delivers quick wins:

- "What is the market currently pricing in?"
- "Are my assumptions stupid?"
- "What did the company actually report?"
- "How do peers trade?"
- "What changed since the last filing?"
- "Can I export a clean starter memo/CSV?"
- "Did anything important change in my watchlist since the last filing?"

That is a no-brainer if it saves even 30-60 minutes per month. The annual plan at $99.99 matters because it reduces churn and lets early users feel they are locking in a founder price.

### 4.3 What not to sell in Core

Do not include unlimited unlocked Excel DCF exports in the $9.99 plan. That would destroy the premium value. A fair compromise is 1-2 early-subscriber export credits or a small number of watermarked/lite exports.

Do not market Core as "AI equity research." That competes directly with $20 AI subscriptions and $39 Fiscal.ai.

Do not market Core as "stock picks." That raises trust, regulatory, and user-expectation problems.

## 5. The top five services users could pay $9.99/month for

These are the services I recommend for the Core plan. They are close enough to the existing DCF product, but useful even before a user buys the full DCF model. The filter I am applying is simple: if a user would run it only once, it should not be in the subscription core; if a user would return weekly or every earnings season, it belongs in the core plan.

### Service 1: SEC-backed company snapshot

User enters a ticker. Trinsic returns:

- Revenue, gross profit, operating income, net income, CFO, capex, cash, debt, shares.
- 3-5 year trend table.
- Margins and growth rates.
- Cash conversion.
- Debt/cash position.
- Filing dates and source concepts.

Why this works:

- SEC EDGAR integration already exists.
- Users trust sourced filings more than random AI output.
- This becomes the input layer for the premium DCF model.

Core plan value:

- 50 ticker snapshots/month.
- US public companies first.
- No unlocked DCF Excel export.

Implementation notes:

- Add `/api/ticker-snapshot`.
- Use `EdgarClient.fetch_financials`.
- Cache by ticker/filing period.
- Store source concepts and filing metadata.

### Service 2: Reverse DCF / "What is priced in?"

Instead of asking users to forecast the future, solve backward from current price:

- What revenue CAGR is implied?
- What terminal growth is implied?
- What EBITDA margin is implied?
- What WACC range would justify the price?
- What margin of safety exists under conservative/base/aggressive assumptions?

Why this works:

- It directly addresses "DCF inputs are garbage."
- It teaches users that valuation is assumption-sensitive.
- It gives immediate value even if the user never downloads Excel.

Core plan value:

- 100 reverse DCF runs/month.
- Save/view last 20 runs.
- Export a small PDF/CSV summary.

Implementation notes:

- Add solver helpers around the existing DCF engine.
- Use deterministic bisection/grid search.
- Add chart to dashboard.
- Add "market-implied assumptions" card to free ticker pages.

### Service 3: Assumption quality score and red-flag checklist

For any DCF preview, Trinsic should grade the assumptions:

- Terminal value as % of EV too high.
- Terminal growth too close to WACC.
- Terminal growth above GDP cap.
- Revenue CAGR inconsistent with historical growth.
- EBITDA margin above historical/peer range.
- Capex below depreciation for asset-heavy companies.
- Working capital days unrealistic.
- WACC weights do not sum to 100%.
- Debt/cash bridge inconsistent.
- Negative or unstable FCF.
- Valuation too dependent on exit multiple.

Why this works:

- This converts the product from "calculator" into "review assistant."
- It builds confidence before selling the premium workbook.
- It is hard for generic AI to do reliably unless the user provides structured data.

Core plan value:

- Included in every snapshot and DCF preview.
- Free users see limited top 3 flags.
- Core users see full diagnostics.

Implementation notes:

- Add a rules engine.
- Surface flags in dashboard and Excel audit tab.
- Keep language educational, not advisory.

### Service 4: Peer comps and valuation range builder

User enters target ticker. Trinsic suggests peers or allows manual peer tickers, then returns:

- EV/Revenue, EV/EBITDA, P/E.
- Mean, median, low, high.
- Implied enterprise/equity value range.
- Outlier flags.
- Optional "why this peer may be weak" notes.

Why this works:

- Comps already exists but requires manual peer tickers.
- Competitors include comps, but not necessarily as a low-cost quick workflow.
- It is a natural trust bridge into DCF.

Core plan value:

- 25 peer comp screens/month.
- CSV/lite PDF export.
- Premium export includes comps tab in Excel.

Implementation notes:

- Start with manual peer input plus saved peer sets.
- Add auto-peer later via SIC/industry/sector mapping.
- Cache yfinance calls.

### Service 5: Watchlist, screener, and filing-change monitor

This should combine the recurring-use pieces into one product surface rather than scattering them across multiple features. Users save companies and get:

- Current price vs last intrinsic-value preview.
- Reverse DCF implied growth changes.
- Latest 10-K/10-Q filing date.
- Revenue, margin, debt, cash, share count changes.
- Risk factor section changed materially or not.
- Going concern, impairment, restructuring, customer concentration keyword flags.
- New filing available.
- Peer multiple changes.
- A simple screen of saved/covered companies by valuation, quality, growth, leverage, and FCF conversion.

Why this works:

- It is the retention engine, because the watchlist changes over time.
- It gives the user a reason to keep paying even when they are not downloading DCF workbooks.
- It turns SEC filings into a living workflow rather than a static model.

Core plan value:

- 20-25 watchlist tickers.
- Weekly email digest later; manual refresh first.
- Filing alert emails later.
- "Run full DCF export" upsell when material changes occur.

Implementation notes:

- Requires auth and database.
- Start with manual "refresh watchlist" before building cron/email.
- Use a simple screener first: valuation, quality, growth, leverage, FCF conversion, and filing freshness.
- Supabase table: users, watchlist, snapshots, alerts.

### Service 5 implementation detail: filing red flags

Inside the watchlist and filing-change monitor, Trinsic should show:

- Latest 10-K/10-Q filing date.
- Revenue, margin, debt, cash, share count changes.
- Risk factor section changed materially or not.
- New debt/liquidity language.
- Going concern, impairment, restructuring, customer concentration keyword flags.
- Simple "changed since last filing" summary.

Why this works:

- Users need this before trusting assumptions.
- It is filing-linked, not generic AI chat.
- It can be a high-retention tool because users come back after filings.

Core plan value:

- 20 filing checks/month.
- Watchlist filing alerts.

Implementation notes:

- Start deterministic: XBRL facts plus keyword sections.
- Later add AI summary only with citations and source snippets.
- Avoid presenting this as legal/investment advice.

## 6. Additional feature backlog

### 6.1 High-priority trust features

1. Source map tab

Every reported number should show:

- Source: SEC EDGAR companyfacts.
- Filing form.
- Fiscal period.
- XBRL concept.
- Pull timestamp.

This should appear in the dashboard and premium Excel audit tab.

2. Model methodology page

Public page explaining:

- DCF method.
- WACC method.
- Terminal value methods.
- Synthetic credit spread logic.
- Monte Carlo driver assumptions.
- Known limitations.
- Not investment advice disclaimer.

3. Model quality badges

Use factual badges, not marketing fluff:

- "SEC facts loaded."
- "Balance sheet check passed."
- "FCF bridge check passed."
- "Terminal growth cap applied."
- "Source map available."

4. Assumption presets by company maturity

Simple presets:

- Mature compounder.
- High-growth tech.
- Cyclical industrial.
- Asset-heavy.
- Early-stage negative FCF.

These help reduce garbage inputs.

5. Historical default builder

Auto-fill assumptions from history:

- Revenue CAGR from past 3-5 years.
- Gross margin average.
- Operating margin average.
- DSO/DIO/DPO where data exists.
- Capex as % revenue.
- Tax rate average.

### 6.2 Core plan features

6. Lite research memo export

Core users can export a 1-2 page PDF/HTML:

- Snapshot.
- Reverse DCF.
- Key flags.
- Peer comps.
- Source list.

Full DCF Excel remains premium.

7. Saved cases

Save ticker, assumptions, and outputs. Limit by plan:

- Free: 3 saved cases.
- Core: 50 saved cases.
- Premium: unlimited or higher.

8. Watchlist dashboard

Show:

- Ticker.
- Last run date.
- Price.
- Implied growth.
- New filing flag.
- Last red flag count.

9. Sector peer sets

Save reusable peer sets:

- Big Tech.
- Semiconductors.
- SaaS.
- Payments.
- Banks should be excluded at first unless a bank-specific model is built.

10. Compare two companies

Side-by-side:

- Growth.
- Margins.
- ROIC proxy.
- FCF conversion.
- Leverage.
- Implied expectations.

### 6.3 Premium DCF features

11. One-click ticker-to-DCF preview

This is the main premium funnel:

- Ticker in.
- SEC facts loaded.
- Historical defaults calculated.
- Assumption quality score shown.
- User can tune assumptions.
- Premium export downloads full Excel.

12. Unlocked Excel export with source/audit tabs

Add premium-only tabs:

- Source Map.
- Assumption QA.
- Reverse DCF.
- Peer Comps.
- Filing Change Log.

This makes the premium workbook meaningfully better than the current export.

13. Founder-vetted model option

Add a higher-priced option:

- "Reviewed by CA Finalist / CFA Level 2 candidate."
- Includes assumption notes.
- Includes top 5 caveats.
- 24-72 hour turnaround at first.

This is where your qualifications become monetizable.

14. Coverage library

Build public pages:

- `/stocks/nvda-dcf-model`
- `/stocks/aapl-dcf-model`
- `/stocks/tsla-dcf-model`

Each page includes free snapshot + upgrade CTA.

15. Versioned model history

Let premium users compare:

- Last quarter model vs current quarter model.
- Change in revenue base.
- Change in WACC.
- Change in valuation output.
- Change in red flags.

## 7. One-month implementation plan

This assumes the goal is to produce a sellable validation-stage product, not a perfect SaaS.

### Week 1: Productize ticker ingestion and trust layer

Build:

- `/api/ticker-snapshot`.
- Wire `EdgarClient` into the dashboard flow.
- Convert SEC facts into base-year values.
- Add source metadata to responses.
- Add source map data structure.
- Add caching file or lightweight DB table.
- Add methodology page.
- Clean docs version mismatch.

Acceptance criteria:

- User can enter AAPL/NVDA/MSFT and see a sourced snapshot.
- Dashboard shows "SEC facts loaded" or a clear fallback error.
- No stack traces are exposed.
- Source concepts are visible.

### Week 2: Build Core plan utilities

Build:

- Reverse DCF solver.
- Assumption QA score.
- Red-flag checklist.
- Peer comps workflow with manual peers.
- Lite PDF/HTML/CSV export.
- Free limits in UI, even if backend enforcement is simple at first.

Acceptance criteria:

- Free user can run limited snapshots.
- Core value proposition is visible without Excel export.
- The output answers "what does price imply?" and "are assumptions sane?"

### Week 3: Add accounts, usage, and payment gating

Build:

- Supabase auth or magic-link email login.
- Users table.
- Usage events table.
- Credits table.
- Export logs.
- LemonSqueezy payment links or webhooks.
- Server-side protection on `/api/export-excel`.

Acceptance criteria:

- Frontend paywall is not the only protection.
- Anonymous direct POST to `/api/export-excel` cannot bypass payment.
- Export consumes credit or requires paid access.
- Admin can see requests and payments.

### Week 4: Launch funnel and premium DCF upgrade

Build:

- Update landing page positioning.
- Add free sign-in CTA.
- Add 5 sample stock pages.
- Add email capture for free sample download.
- Add Core $9.99 plan page.
- Add DCF credit pricing.
- Add source/audit tabs to premium Excel if time allows.
- Add usage analytics events.

Acceptance criteria:

- A new visitor can sign in, run a free snapshot, see value, and understand the $9.99 upgrade.
- A paid user can buy credits and export.
- Founder can monitor usage and failures.

## 8. Recommended plan packaging

### Free plan after sign-in

Offer enough to build trust:

- 5 company snapshots/month.
- 5 reverse DCF previews/month.
- 3 peer comp screens/month.
- 3 assumption QA checks/month.
- Public sample workbook downloads.
- No unlocked DCF exports.
- No watchlist alerts beyond 3 tickers.

### Core plan: $9.99/month or $99.99/year

Package:

- 50 SEC-backed company snapshots/month.
- 100 reverse DCF runs/month.
- 25 peer comp screens/month.
- Full assumption QA and red flags.
- 10 watchlist tickers.
- Weekly watchlist digest.
- Lite PDF/CSV export.
- Discounted DCF export credits.

This is the "no-brainer" product if it saves the user at least 30-60 minutes per month.

### Premium DCF exports

Initial validation pricing:

- $5-$10 per unlocked DCF export.
- $19 for 5 export credits.
- $49 for 5 founder-prioritized custom ticker models if manual fulfillment is needed.

Later recurring pricing:

- $19.99/month: 5 exports/month.
- $29.99/month: 20 exports/month, source/audit tabs, saved model history.

### Founder-vetted models

Price:

- $49-$99 per company during validation.

Offer:

- Full Excel.
- Assumption review.
- 1-2 page note.
- Red-flag caveats.
- Methodology and source trail.

This is not "AI-generated file." This is "automation plus qualified human review."

## 9. Positioning changes needed

### Current positioning problem

Current copy emphasizes:

- Premium Excel DCF.
- Institutional-grade.
- Fully editable workbooks.
- $19 custom / $49 pack.

That makes users evaluate the product too late in the workflow. They ask, "Do I trust this Excel model enough to pay?"

### Better positioning

Lead with:

- SEC-backed valuation research.
- Reverse DCF and assumption sanity checks.
- Filing-to-model source trail.
- Fast valuation workflow.
- Premium Excel only after trust is established.

Suggested homepage headline:

> Understand what the market is pricing before you build the model.

Suggested subheadline:

> Trinsic turns SEC filings into source-linked valuation snapshots, reverse DCF checks, peer comps, and auditable Excel models when you are ready to go deeper.

Suggested CTA:

- "Run a free ticker snapshot"
- "See priced-in assumptions"
- "Export full DCF model"

## 10. Competitive defense

### Against free SEC/Yahoo/Google data

Defense:

- Trinsic maps raw facts into a valuation workflow.
- Users do not need to wrangle concepts or spreadsheet formulas.
- Source trail remains visible.

### Against ChatGPT Plus

Defense:

- ChatGPT can summarize, but Trinsic calculates.
- Trinsic has structured SEC data, deterministic math, and Excel output.
- Trinsic can cite exact SEC concepts and periods.
- Trinsic has assumption QA, reverse DCF, and model audit checks.

### Against TIKR/Koyfin/Fiscal

Defense:

- Those are broad platforms.
- Trinsic is cheaper, narrower, and faster for valuation prep.
- Trinsic's premium output is a usable formula-linked workbook.

### Against Intrinsik and other automated DCF tools

Defense:

- Do not compete only on "automated fair value."
- Compete on "auditability, Excel export, source map, assumption diagnostics, and founder-vetted premium models."

### Against Canalyst/Tegus

Defense:

- They serve institutions and professional teams.
- Trinsic serves individuals, students, creators, and boutiques at a tiny fraction of the cost.
- Do not claim equal data depth. Claim better affordability and faster starter workflows.

## 11. Critical risks

### Risk 1: Garbage in, garbage out

Mitigation:

- Auto-fill from SEC history.
- Assumption QA score.
- Historical/peer benchmark comparisons.
- Reverse DCF framing.
- Show warnings before export.

### Risk 2: Free alternatives

Mitigation:

- Package workflow, not raw data.
- Add saved cases and watchlists for retention.
- Keep premium Excel export separate.

### Risk 3: AI commoditization

Mitigation:

- Use AI only for cited summaries, not core math.
- Build deterministic finance logic.
- Make source trail and Excel auditability the core moat.

### Risk 4: Trust and liability

Mitigation:

- Strong disclaimers.
- Methodology transparency.
- No buy/sell recommendations.
- Educational/research framing.
- Versioned audit log.

### Risk 5: Payment bypass

Mitigation:

- Server-side auth on export endpoints.
- Credits table.
- Export logs.
- Rate limiting.
- Never rely on frontend paywall only.

### Risk 6: Data quality

Mitigation:

- Store raw SEC facts used.
- Show missing-data warnings.
- Prefer US companies first.
- Exclude banks/insurers until sector-specific models exist.
- Add manual override path.

## 12. What to avoid in the next month

Do not build these yet:

- A general AI chat interface.
- Portfolio performance tracking with brokerage connections.
- Options analytics.
- Crypto/forex.
- Full Bloomberg/Koyfin-style market terminal.
- Complex team billing.
- Mobile app.
- International filings.
- Bank/insurance valuation models.
- "AI stock picks."

These either dilute the product, increase liability, or compete with better-funded platforms.

## 13. Success metrics for the first month

Track:

- Visitor to free sign-in conversion.
- Free sign-in to first snapshot conversion.
- Snapshot to reverse DCF conversion.
- Reverse DCF to saved case conversion.
- Free to $9.99 conversion.
- $9.99 to DCF export credit purchase.
- Number of repeat weekly users.
- Number of support/model quality complaints.
- Number of users who run 3+ tickers.

Practical first goal:

- 100 free signups.
- 25 users who run 3+ ticker snapshots.
- 5-10 Core subscribers.
- 3-5 paid DCF export purchases.

If you get that, the product has a pulse.

## 14. Final recommendation

Build the $9.99 product around:

1. SEC-backed company snapshots.
2. Reverse DCF.
3. Assumption quality score.
4. Peer comps.
5. Watchlist, screener, and filing-change alerts.

Keep the DCF workbook as premium.

The current engine is strong enough to become a business, but the commercial wrapper needs to change. The customer should not be asked to trust the DCF on day one. Instead, they should first use Trinsic to understand a company, inspect source-linked facts, test implied assumptions, compare peers, and spot obvious valuation risks. Once they trust that workflow, the Excel DCF becomes the natural paid upgrade.

## 15. Sources reviewed for market context

- TIKR pricing: https://www.tikr.com/pricing
- Koyfin pricing: https://www.koyfin.com/pricing
- Fiscal.ai pricing: https://fiscal.ai/pricing/
- Marketsheets pricing: https://www.marketsheets.io/
- Wisesheets documentation: https://www.wisesheets.io/pages/docs
- Wisesheets options/data pricing release: https://markets.financialcontent.com/stocks/article/getnews-2026-3-13-wisesheets-brings-real-time-options-chain-data-into-excel-and-google-sheets-making-it-the-only-spreadsheet-tool-to-offer-full-options-coverage-for-under-10-per-month
- Finsheet pricing: https://finsheet.io/
- Finbox product and pricing help: https://finbox.com/ and https://help.finbox.com/hc/en-us/articles/4406100611985-Starter-Plan-Explained
- Financial Modeling Prep API FAQ: https://site.financialmodelingprep.com/faqs
- Daloopa plans: https://www.daloopa.com/plans
- GuruFocus pricing/reviews: https://www.gurufocus.com/reviews
- ValueSense pricing: https://valuesense.io/pricing
- Intrinsik public product page: https://intrinsik.io/
- V7 Go DCF modeling agent: https://www.v7labs.com/go/agents/dcf-modeling-agent
- Tegus / Canalyst financial models: https://www.tegus.com/canalyst
- AlphaSense pricing page: https://www.alpha-sense.com/pricing
- Quartr pricing page: https://quartr.com/pricing/overview
- SEC EDGAR API documentation: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC EDGAR fair access guidance: https://www.sec.gov/os/accessing-edgar-data
- CFI free DCF template: https://corporatefinanceinstitute.com/resources/financial-modeling/dcf-model-template/
- Wall Street Oasis free financial modeling templates: https://www.wallstreetoasis.com/resources/templates/excel-financial-modeling
- ChatGPT Plus pricing reference: https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus
