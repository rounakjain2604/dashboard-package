# Full Deployment Handover Plan

## Context

This project is a Flask + React single-file dashboard for generating DCF valuation outputs and formula-linked Excel workbooks. The core valuation engine already exists and passes major internal validation tests, but the product is not yet a deployable SaaS.

The objective is to convert the current prototype into a public, paid MVP that can validate demand for a "$5-$10 one-click ticker-to-Excel DCF model" product while keeping the founder anonymous.

The deployment target is initially Vercel or another low-cost host. The founder has a very small budget, limited time, and no manual coding ability, so all changes should be simple, robust, and maintainable.

## Final Deployment Decisions

The implementing AI should not ask the founder to choose between hosting providers unless a hard blocker appears. Use these defaults.

### Hosting Choice

Use **Render Web Service as the primary deployment target**.

Reason:

- This is a Python Flask app, not a static frontend.
- It performs SEC EDGAR network calls.
- It generates Excel files.
- It may later need payment webhooks and a database.
- A normal long-running Python web service is simpler to reason about than serverless functions for this workload.

Do **not** describe EDGAR as a hosting option. EDGAR is the SEC data source used to pull public-company financials. It is not where the app is hosted.

### Vercel Role

Keep the existing Vercel config as an optional fallback only.

Use Vercel only if:

- Render deployment fails for non-code reasons, or
- The founder explicitly wants Vercel despite serverless constraints, or
- A later rewrite separates the frontend into a static/Next.js app and keeps the Python engine elsewhere.

### Domain

The final public domain is:

```text
trinsic.space
```

The existing website currently hosted there will be replaced. The implementing AI should include manual DNS steps for the founder, but should not require the founder to make architectural decisions.

### Repository And Deploy Flow

Use this final flow:

1. Code changes are completed locally.
2. The project is committed to Git.
3. The project is pushed to a GitHub repository.
4. Render is connected to that GitHub repository.
5. Render auto-deploys on future pushes to the main branch.
6. `trinsic.space` is pointed to the Render service using Render's custom domain instructions.

### Database Choice

Use **Supabase Postgres** for credits, payments, and export logs.

Reason:

- Free tier is enough for validation.
- It avoids local SQLite persistence problems on hosted platforms.
- It can support auth later without another migration.

If Supabase setup blocks launch, use a simpler paid-download flow first and defer credits. Do not block the entire launch on perfect account infrastructure.

### Payment Choice

Use **LemonSqueezy** as the preferred payment provider.

Reason:

- It can act as Merchant of Record.
- It is simpler for an India-based anonymous/brand-led product than building direct card billing first.
- It supports checkout links and webhooks.

If webhook implementation takes too long, launch with manual paid exports first:

- User pays through LemonSqueezy payment link.
- User submits ticker/email after payment.
- Founder manually fulfills early requests.

This is acceptable for the first 5-10 customers if needed.

## Product Goal

Ship a public MVP where a user can:

1. Visit the site.
2. Enter a US stock ticker.
3. Generate a valuation dashboard preview.
4. Download a formula-linked Excel model.
5. Pay after a free/demo limit or buy credits.

Do not build an over-engineered SaaS. The first milestone is paid validation: 10-25 paying customers or $200-$250 monthly revenue.

## Non-Negotiable Principles

- Keep the product anonymous and brand-led. Do not expose the founder's name, personal email, or social identity.
- Do not present outputs as investment advice.
- Prioritize reliability, trust, and clean Excel output over feature breadth.
- Avoid adding complex infrastructure unless required.
- Harden all public endpoints before deployment.
- Make every user-facing failure graceful.
- Keep the core engine deterministic and auditable.

## Target MVP Scope

### Must Have

- Public landing page.
- Ticker input for US public companies.
- SEC EDGAR historical data ingestion wired into the main API.
- Market data defaults where available, with graceful fallback.
- Excel export that works in production.
- Basic payment or paid-download flow.
- Usage limiting or simple credit tracking.
- Legal disclaimers.
- Error handling without tracebacks.
- Path traversal protection.
- Production-safe logging.
- Sample downloadable models for 5 tickers.

### Should Have

- Email capture for free downloads.
- Admin-only manual credit adjustment.
- Basic analytics events.
- Static SEO pages for sample models.
- A "methodology" page explaining model logic.

### Not Needed For First Launch

- Full multi-user dashboard.
- Complex subscription management.
- Team accounts.
- Full Next.js migration.
- Perfect international stock coverage.
- Advanced AI commentary.
- Mobile-first app polish beyond basic responsiveness.

## Recommended Pricing For Validation

Prefer paid credits before subscription:

- Free: 1 sample model download, or 1 generated model after email capture.
- Paid: $5-$10 per generated model.
- Bundle: $19 for 5 credits.
- Subscription can be tested later after proof of repeat usage.

This reduces buyer friction and avoids needing a complex recurring billing system immediately.

## Technical Workstream 1: Security Hardening

### 1. Remove Tracebacks From API Responses

Current issue:

- `dashboard_api.py` returns `traceback.format_exc()` in `/api/run`.

Required change:

- Log full traceback server-side only.
- Return a generic error to users.
- Include a short request id in the response and logs.

Acceptance criteria:

- No API response exposes local file paths, stack traces, source code paths, or environment details.

### 2. Protect File Path Routes

Current issue:

- `/api/config/<path:filename>` and `/api/data-file-base-values/<path:filename>` join user-controlled path segments directly with `_BASE_DIR`.

Required change:

- Resolve final paths and confirm they are inside approved directories only.
- Config loads should only read from `config/` or approved root config files.
- Data loads should only read from `data/`.
- Reject absolute paths and parent traversal.

Acceptance criteria:

- Requests like `/api/config/../../dashboard_api.py` fail with 400 or 404.
- Requests like `/api/data-file-base-values/../../LICENSE` fail.

### 3. Add Request Size Limits

Required change:

- Set Flask `MAX_CONTENT_LENGTH`.
- Reject oversized JSON payloads.

Acceptance criteria:

- Large payloads return a controlled 413 response.

### 4. Add Basic Rate Limiting

Preferred low-complexity options:

- If using Flask host: `Flask-Limiter`.
- If using Vercel: use provider-level rate limits if available, or implement simple IP+timestamp guard in a hosted KV/store.

Acceptance criteria:

- Public unauthenticated endpoints cannot be spammed indefinitely.
- Export endpoint has stricter rate limits than preview endpoint.

## Technical Workstream 2: Anonymity And Branding Cleanup

### 1. Remove Personal Identifiers

Current issue:

- `edgar_client.py` has a personal email in `_DEFAULT_USER_AGENT`.
- Docs contain personal repository-style references.

Required change:

- Replace with a brand email, e.g. `support@trinsic.space`.
- Search the entire repo for personal names/emails.
- Update public docs, workbook cover pages, audit tabs, and metadata.

Acceptance criteria:

- `rg -n "rounak|gmail|personal|jain" .` returns no public-facing personal identifiers, except private local docs if intentionally kept out of deploy.

### 2. Standardize Brand Name

Current issue:

- Brief mentions "Intrinsic" and `trinsic.space`.

Required change:

- Choose one product name.
- Recommended: `Trinsic` if the domain is `trinsic.space`.
- Update UI, workbook watermark, landing page, metadata, and docs.

Acceptance criteria:

- No mixed naming across user-visible surfaces.

## Technical Workstream 3: Ticker-To-Model Integration

### 1. Add `/api/ticker-model` Endpoint

Purpose:

- User submits a ticker.
- Backend pulls EDGAR historicals.
- Backend derives base-year values.
- Backend creates a reasonable default config.
- Backend runs pipeline.
- Backend returns dashboard JSON plus metadata.

Suggested request:

```json
{
  "ticker": "AAPL",
  "projection_years": 5
}
```

Suggested response:

```json
{
  "success": true,
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "source": {
    "historicals": "SEC EDGAR companyfacts",
    "market_data": "fallback/default or live"
  },
  "warnings": [],
  "model": {}
}
```

### 2. Add `/api/ticker-export-excel` Endpoint

Purpose:

- Same as `/api/ticker-model`, but returns downloadable Excel.
- If payment/credit checks are enabled, enforce them here.

### 3. Wire `EdgarClient`

Required behavior:

- Resolve ticker to CIK.
- Pull recent annual 10-K financials.
- Map facts into existing tidy historical format.
- Derive latest revenue, cash, PP&E, NWC, debt, shares where possible.
- Use fallback assumptions when a value is missing.
- Return clear warnings for missing fields.

Important:

- Do not silently pretend all data is perfect.
- User trust improves when missing assumptions are disclosed.

### 4. Add Forecast Defaults From Historical Data

Suggested logic:

- Revenue CAGR: compute from last 3-5 years if possible, clamp to a sensible range, e.g. -10% to 25%.
- COGS % revenue: latest or average historical COGS / revenue.
- SG&A % revenue: latest or average if available.
- DSO/DIO/DPO: use defaults unless enough data exists.
- Tax rate: effective tax / pretax income if usable, clamped 0%-35%; fallback 21%-25%.
- Capex % revenue: historical capex / revenue if available; fallback 4%-6%.
- Debt: latest debt from EDGAR if available.
- Cash: latest cash from EDGAR if available.
- Shares: latest diluted shares if available; fallback to yfinance shares if installed; otherwise require user input or use placeholder with warning.

### 5. Market Data Defaults

Current issue:

- `yfinance` is commented out in requirements and disabled on Vercel.

Required decision:

- Either include `yfinance` and use a host that permits it reliably, or treat market data as optional and disclose fallbacks.

Recommended MVP approach:

- Keep EDGAR as primary.
- Use configured WACC defaults if market data fails.
- Show WACC assumptions clearly.
- Avoid making "live data" a core promise until production-proven.

Acceptance criteria:

- AAPL, MSFT, NVDA, TSLA, and AMZN generate without server errors.
- Missing data creates warnings, not crashes.

## Technical Workstream 4: Excel Export Quality

### 1. Fix Excel Revenue Method Parity

Current documented issue:

- Python supports CAGR/YoY/manual.
- Excel export always uses CAGR formulas.

Required change:

- If `revenue_method == "cagr"`, write CAGR formulas.
- If `revenue_method == "yoy"`, expose yearly growth assumptions and write per-year formulas.
- If `revenue_method == "manual"`, expose manual yearly revenue inputs and link formulas accordingly.

Acceptance criteria:

- Python dashboard result and exported Excel match materially for CAGR, YoY, and manual revenue modes.

### 2. Add Historical Data Tab

Required change:

- Add a "Historicals" tab to the workbook.
- Include pulled SEC facts and source labels.
- Add warnings for missing data.

Acceptance criteria:

- A finance user can see where base-year numbers came from.

### 3. Add Model Warnings Tab Or Section

Warnings should include:

- Missing COGS.
- Missing SG&A.
- Missing shares.
- Missing cash/debt.
- Default WACC used.
- Negative or unusual values.
- Terminal growth capped.

Acceptance criteria:

- The workbook does not overstate precision.

### 4. Excel Formula QA

Required tests:

- Generate workbook for at least 5 tickers.
- Open with `openpyxl` and confirm formulas exist.
- If possible on Windows, use Excel COM automation to recalculate and check for `#REF!`, `#DIV/0!`, `#NAME?`, `#VALUE!`.

Acceptance criteria:

- No formula errors in core tabs for sample tickers.

## Technical Workstream 5: Payment And Usage Limiting

### Recommended Simple Architecture

Use LemonSqueezy payment links or checkout for the first version.

Options:

1. Simplest validation:
   - User pays on LemonSqueezy.
   - Redirect to a success page.
   - Success page asks for ticker/email.
   - Backend sends/generates model.

2. Better MVP:
   - User enters email.
   - User buys credits.
   - Webhook records credits.
   - Each export consumes one credit.

### Minimal Database Options

Pick one:

- Supabase free tier.
- Neon Postgres free tier.
- SQLite only if deploying to a persistent server, not Vercel serverless.

Recommended:

- Supabase, because it gives database + auth options later.

### Minimal Tables

`users`

- `id`
- `email`
- `created_at`

`credits`

- `id`
- `email`
- `credits_remaining`
- `updated_at`

`exports`

- `id`
- `email`
- `ticker`
- `status`
- `created_at`
- `warnings_json`

`payments`

- `id`
- `email`
- `provider`
- `provider_event_id`
- `amount`
- `currency`
- `credits_added`
- `created_at`

### Payment Acceptance Criteria

- A user can buy credits.
- Webhook validates provider signature.
- Duplicate webhook events do not double-credit a user.
- Export is blocked if no credits remain, except for demo/free path.
- Successful export decrements credits.

## Technical Workstream 6: Frontend And Landing Page

### 1. Keep Or Replace Current Frontend?

For first launch, keep the current Flask-served frontend if speed matters.

But add:

- Landing page above or separate from dashboard.
- Ticker input as the primary first-screen action.
- Sample model downloads.
- Pricing section.
- Methodology page.
- Disclaimer.

Do not spend time migrating to Next.js unless deployment/SEO requires it.

### 2. UI Flow

Recommended flow:

1. Landing page:
   - Headline: "Generate editable Excel DCF models from a stock ticker."
   - Primary input: ticker.
   - CTA: "Generate Preview".
   - Sample models visible.

2. Preview page:
   - Shows valuation summary, warnings, and model assumptions.
   - CTA: "Download Excel".

3. Payment gate:
   - If free credit exists, allow download.
   - Otherwise send to checkout.

4. Download:
   - Return workbook.
   - Invite user to reply/report issues.

### 3. Required Public Copy

Add disclaimers:

- "For educational and research use only."
- "Not financial, investment, tax, or legal advice."
- "Outputs depend on public data availability and user/model assumptions."
- "Always review assumptions before relying on the workbook."

## Technical Workstream 7: Deployment

### Deployment Option A: Render Web Service

Pros:

- Better fit for Python Flask.
- Better fit for SEC EDGAR pulls.
- Better fit for Excel generation.
- Simple GitHub auto-deploy.
- Supports custom domains and managed TLS.
- Easier production logs than serverless for this app.

Cons:

- Free services can spin down when idle.
- Free Postgres on Render expires after 30 days, so use Supabase for persistent data.
- May require a paid instance later if traffic grows.

Use Render as the default deployment target.

Render docs to use during setup:

- Web services: https://render.com/docs/web-services
- Free tier limitations: https://render.com/docs/free
- Python version: https://render.com/docs/python-version

### Deployment Option B: Vercel Fallback

Pros:

- Already has `vercel.json`.
- Good GitHub integration.
- Good for static/frontend-heavy apps.

Cons:

- Serverless model is less natural for this backend.
- Function limits and runtime behavior can create export reliability risk.
- External data calls plus Excel generation may be harder to debug.

Use Vercel only as fallback or future frontend host.

If Vercel is used for a paid/commercial version, do not use Vercel Hobby as the long-term plan. Vercel Hobby is intended for personal/non-commercial use, so a paid product should use an appropriate paid plan.

Vercel docs to use if needed:

- Account plans: https://vercel.com/docs/plans
- Hobby plan/function duration: https://vercel.com/docs/accounts/plans/hobby
- Function limits: https://vercel.com/docs/functions/limitations

### Environment Variables

Required:

- `APP_ENV=production`
- `BRAND_NAME=Trinsic`
- `SUPPORT_EMAIL=support@trinsic.space`
- `DATABASE_URL=...`
- `SUPABASE_URL=...`
- `SUPABASE_SERVICE_ROLE_KEY=...`
- `LEMONSQUEEZY_WEBHOOK_SECRET=...`
- `LEMONSQUEEZY_STORE_ID=...`
- `LEMONSQUEEZY_PRODUCT_ID=...`
- `FREE_EXPORT_LIMIT=1`
- `MAX_MONTE_CARLO_ITERATIONS=2000`

### Render Setup Defaults

Add these deployment files if they do not already exist:

`.python-version`

```text
3.13.5
```

Use Python 3.13.x rather than relying on the platform default.

Add `gunicorn` to `requirements.txt`.

Recommended Render service settings:

- Service type: Web Service
- Environment: Python
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn dashboard_api:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- Root directory: repository root if the repo contains only `dashboard_package`; otherwise set root directory to `dashboard_package`
- Branch: `main`
- Auto-deploy: enabled
- Instance type: Free for technical validation only; upgrade before or immediately after accepting real paid customers if budget allows

Do not rely on free hosting as the long-term production setup. It is acceptable for smoke testing and early validation, but paid users should eventually be served from a paid instance.

### GitHub Setup Steps For Founder

Claude or Codex should provide exact commands after code is ready, but the founder will need to perform account clicks.

Manual steps:

1. Create a GitHub account or use an existing anonymous/brand account.
2. Create a new private or public repository named `trinsic`.
3. Push this project to GitHub.
4. Confirm the repository contains the app files at the expected root.

Recommended command sequence:

```bash
git init
git add .
git commit -m "Prepare Trinsic MVP deployment"
git branch -M main
git remote add origin <GITHUB_REPO_URL>
git push -u origin main
```

If the repo already exists, do not re-run `git init`; inspect current Git state first.

### Render Click-By-Click Steps For Founder

1. Go to https://render.com/.
2. Sign in with the GitHub account.
3. Click **New**.
4. Click **Web Service**.
5. Select the GitHub repository.
6. Set root directory if needed: `dashboard_package`.
7. Set build command: `pip install -r requirements.txt`.
8. Set start command: `gunicorn dashboard_api:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`.
9. Select Free instance for validation.
10. Add environment variables listed above.
11. Deploy.
12. Open the generated `onrender.com` URL and test `/api/version`.

### Domain Setup For `trinsic.space`

After Render deploys successfully:

1. Open the Render service dashboard.
2. Go to **Settings** or **Custom Domains**.
3. Add:

```text
trinsic.space
www.trinsic.space
```

4. Render will show DNS records to add.
5. Go to the domain registrar where `trinsic.space` is managed.
6. Remove or replace the old website's DNS records.
7. Add the DNS records Render provides.
8. Wait for DNS propagation.
9. Confirm both URLs work:

```text
https://trinsic.space
https://www.trinsic.space
```

10. Confirm HTTPS certificate is active.

Do not point the domain until the Render preview URL works correctly.

### DNS Safety Note

Before replacing DNS, write down or screenshot the current DNS records for the existing website. This allows rollback if needed.

### Deployment Acceptance Criteria

- Home page loads on Render preview URL.
- Home page loads on `https://trinsic.space`.
- `/api/version` works.
- Ticker preview works for 5 sample tickers.
- Excel export works.
- Payment webhook works in test mode.
- No tracebacks are exposed.
- Logs show request ids.
- Abuse rate limits are active.

## Technical Workstream 8: Test Plan

### Existing Test Issue

The full `pytest` run is currently blocked because at least one test file calls `sys.exit(0)` at import time.

Required change:

- Convert script-style tests into normal pytest tests or rename them so pytest does not collect them.
- Add `pytest.ini` with explicit test discovery.

Acceptance criteria:

- `python -m pytest -q` runs cleanly in CI.

### Required Test Groups

1. Core engine tests.
2. API smoke tests.
3. Path traversal/security tests.
4. Ticker ingestion tests with mocked EDGAR responses.
5. Excel export formula tests.
6. Payment webhook idempotency tests.
7. Credit decrement tests.

### Manual QA Checklist

For each sample ticker:

- Generate preview.
- Export Excel.
- Open workbook.
- Confirm cover page brand.
- Confirm assumptions are editable.
- Confirm DCF tab recalculates.
- Confirm no core formula errors.
- Confirm warnings make sense.

## Launch Workstream

### Sample Model Library

Create 5 polished models:

- NVDA
- TSLA
- AAPL
- MSFT
- AMZN

Each sample should have:

- Public SEO page.
- Free downloadable Excel file.
- Methodology notes.
- Clear assumptions.
- Watermark: "Generated by Trinsic - build yours at trinsic.space"

### SEO Pages

Create pages targeting:

- "free Nvidia DCF model Excel"
- "Tesla DCF model Excel download"
- "Apple valuation model Excel"
- "Microsoft DCF model template"
- "editable DCF Excel model"

### Anonymous Distribution Plan

Create brand accounts only:

- Reddit brand/user account.
- X account.
- YouTube account.
- Optional Substack/Medium.

Post as educational resource, not spam:

- "I built a free editable NVDA DCF model in Excel. Sharing methodology and assumptions."
- Include screenshots.
- Include direct free download.
- Include one low-friction CTA.

Target communities:

- r/CFA
- r/FinancialCareers
- r/SecurityAnalysis
- r/ValueInvesting
- r/FinancialModeling
- finance Discords with resource channels

Do not overpost. Each post should teach something.

## Analytics

Track:

- Landing page visits.
- Ticker preview attempts.
- Excel export attempts.
- Payment clicks.
- Completed payments.
- Failed model generations.
- Most requested tickers.

Minimal tools:

- Plausible, Umami, or Vercel Analytics.
- Server-side event logs in database for model generations.

Validation targets:

- 1,000 targeted visitors.
- 100 free downloads.
- 10 paid purchases.
- $200-$250 monthly revenue.

## Suggested Execution Order

### Phase 1: Production Hardening

1. Remove tracebacks.
2. Add path protection.
3. Add request limits.
4. Remove personal identifiers.
5. Standardize brand.
6. Clean pytest collection.

### Phase 2: Ticker MVP

1. Wire EDGAR ticker ingestion.
2. Build default assumption derivation.
3. Add ticker preview endpoint.
4. Add ticker export endpoint.
5. Add warnings.
6. Test 5 sample tickers.

### Phase 3: Excel Trust

1. Fix Excel revenue method parity.
2. Add Historicals tab.
3. Add Warnings tab/section.
4. Generate sample workbooks.
5. Run formula QA.

### Phase 4: Payment MVP

1. Add email capture.
2. Add credits table.
3. Add LemonSqueezy checkout.
4. Add webhook.
5. Add credit decrement on export.
6. Test payment sandbox.

### Phase 5: Public Launch

1. Push final code to GitHub.
2. Deploy to Render.
3. Test Render preview URL.
4. Connect `trinsic.space`.
5. Publish sample pages.
6. Publish methodology page.
7. Start anonymous distribution.
8. Measure conversion.
9. Iterate only after real usage data.

## Definition Of Done

The project is ready for public validation when:

- A stranger can visit the domain and understand the product in 10 seconds.
- A stranger can generate a ticker model without manual CSV upload.
- A stranger can pay and receive an Excel workbook.
- The workbook opens cleanly and contains editable formulas.
- The site does not expose private errors or personal identifiers.
- At least 5 sample model pages are live.
- Core tests and API smoke tests pass.
- The founder can monitor failures and payments.

## Claude Implementation Prompt

Use this prompt to start the implementation:

```text
You are taking over a Flask + Python valuation dashboard project. Your job is to convert the existing prototype into a production-ready paid MVP for public validation.

Read these files first:
- docs/FULL_DEPLOYMENT_HANDOVER_PLAN.md
- docs/PROJECT_VIABILITY_BRIEF.md
- docs/README.md
- dashboard_api.py
- src/dcf_engine/pipeline.py
- src/dcf_engine/ingestion/edgar_client.py
- src/dcf_engine/ingestion/market_data.py
- src/dcf_engine/output/excel_builder.py
- src/dcf_engine/output/sheets_core.py
- src/dcf_engine/output/sheets_valuation.py
- templates/dashboard.html
- requirements.txt

Follow the handover plan in phases. Do not rewrite the entire app unless necessary. Preserve existing engine behavior where tests already pass. Make small, reviewable changes.

Important deployment decisions are already made:
- Use Render Web Service as the primary host.
- Use GitHub auto-deploy to Render.
- Use Supabase Postgres for persistent credits/payments/export logs.
- Use LemonSqueezy for payments.
- Use trinsic.space as the final custom domain.
- Keep Vercel only as an optional fallback.
- EDGAR is a data source, not a hosting provider.

Start with Phase 1:
1. Remove traceback exposure from API responses.
2. Harden path handling for config/data routes.
3. Add request size limits.
4. Remove personal identifiers and standardize the brand as Trinsic.
5. Fix pytest collection so `python -m pytest -q` can run cleanly.

After each phase, run tests and document what changed. If a decision is ambiguous, choose the simplest production-safe option and note the tradeoff.
```
