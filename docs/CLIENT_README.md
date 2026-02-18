# IB-Grade DCF Valuation Engine — V13.0.0

A fully automated, investment-banking-grade Discounted Cash Flow valuation engine with an interactive web dashboard, formula-linked Excel export, and PDF memo generation.

> **Full product documentation**: See the included **IB_Grade_DCF_Engine_Client_Document.docx** for a complete walkthrough, feature reference, and technical guide.

---

## Quick Start

```bash
# 1. Install Python 3.10+

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard
python dashboard_api.py
```

Open **http://localhost:5050** in your browser.

On Windows you can also double-click `run_dashboard.bat`.

---

## What You Get

| Deliverable | Description |
|-------------|-------------|
| Web Dashboard | 10-tab interactive analysis with live re-computation |
| Excel Workbook | 17-tab formula-linked .xlsx (every cell references the Assumptions sheet) |
| PDF Memo | 10-15 page investment memo (requires optional `reportlab` package) |

---

## Folder Structure

```
dcf_engine_v13/
  dashboard_api.py        Flask web server
  run_dashboard.bat       Windows one-click launcher
  requirements.txt        Python dependencies
  IB_Grade_DCF_Engine_Client_Document.docx   Full product documentation
  configs/                Preset model configurations
    config.example.json
    config.asian_street_ib_grade.json
  data/                   Historical financial data (CSV)
  templates/              Dashboard UI (single HTML file)
  src/                    Core engine source code
  api/                    Vercel serverless entry point
  vercel.json             Vercel deployment config
```

---

## Loading Your Own Data

1. Place a CSV in `data/` with this format:

   ```csv
   period,account,amount,statement
   2024,Revenue,5000000,income
   2024,COGS,2250000,income
   2024,Cash,500000,balance
   ```

2. Copy `configs/config.example.json`, customise assumptions, and save as a new JSON in `configs/`.

3. Load the config from the dashboard dropdown or run via CLI:
   ```bash
   python -m src.dcf_engine.main --config configs/your_config.json
   ```

---

## Dashboard Tabs

| Tab | Content |
|-----|---------|
| Overview | KPI cards, revenue/margin charts, equity bridge |
| Income Statement | P&L waterfall, stacked breakdown, full IS table |
| Balance Sheet | Assets vs liabilities composition, IFRS-ordered table |
| Cash Flow | CFO/CFI/CFF breakdown, FCF analysis |
| WACC | CAPM build-up, cost of debt, capital structure |
| DCF | Discount factor schedule, terminal value, equity bridge |
| Scenarios | Side-by-side Base/Bull/Bear comparison |
| Sensitivity | 2D heatmaps (WACC vs TG, Revenue Growth vs Margin) |
| Monte Carlo | 10,000-iteration simulation histogram and statistics |
| Tornado | Driver sensitivity ranking by equity value impact |

---

## Excel Export

Click "Export Excel" in the dashboard sidebar. The workbook has 17 tabs:

- **Formula-linked tabs** (live Excel formulas referencing the Assumptions sheet): Cover, Assumptions, IS, Working Capital, Capex DA, Debt Schedule, Balance Sheet, Cash Flow, WACC, DCF, Checks
- **Analytics tabs** (Python-computed values): Scenarios, Sensitivity, Monte Carlo, Tornado, Comps, Audit Trail

To customise: change any value on the Assumptions sheet and the entire model recalculates.

---

## Optional Dependencies

The core engine runs with the packages in `requirements.txt`. For full functionality:

```bash
pip install matplotlib scipy reportlab yfinance
```

| Package | Purpose |
|---------|---------|
| `yfinance` | Live beta, risk-free rate, comparable companies |
| `reportlab` | PDF investment memo generation |
| `matplotlib` | Additional chart rendering |
| `scipy` | Statistical functions for Monte Carlo |

---

## Deployment

### Local
```bash
python dashboard_api.py          # http://localhost:5050
```

### Vercel (Serverless)
```bash
npm i -g vercel
vercel --prod
```

### Production WSGI
```bash
# Linux/macOS
gunicorn dashboard_api:app --bind 0.0.0.0:8080

# Windows
waitress-serve --port=8080 dashboard_api:app
```

---

## Support

For questions or customisation requests, contact the development team.
