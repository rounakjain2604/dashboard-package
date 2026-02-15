"""
PDF Investment Memo generator — 10-15 page output.

Creates a professional PDF memo with executive summary, financial analysis,
valuation results, charts, and appendix using ReportLab.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    logger.warning("reportlab not installed. PDF generation will be skipped.")
    # Mock classes to prevent NameError if used in type hints or elsewhere
    class colors:
        HexColor = lambda x: None
        white = None
        grey = None


# ── Colour palette ───────────────────────────────────────────────────
NAVY = colors.HexColor("#1F3864")
BLUE = colors.HexColor("#4472C4")
GREEN = colors.HexColor("#548235")
ORANGE = colors.HexColor("#ED7D31")
LIGHT_GREY = colors.HexColor("#F2F2F2")
WHITE = colors.white


def _get_styles():
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=NAVY, spaceAfter=6, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle", parent=styles["Title"],
        fontSize=16, textColor=BLUE, spaceAfter=20, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading1"],
        fontSize=14, textColor=NAVY, spaceAfter=8, spaceBefore=16,
        borderWidth=1, borderColor=NAVY, borderPadding=4,
    ))
    styles.add(ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=11, textColor=BLUE, spaceAfter=6, spaceBefore=10,
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["BodyText"],
        fontSize=9, leading=13, alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        "Disclaimer", parent=styles["BodyText"],
        fontSize=7, textColor=colors.grey, alignment=TA_CENTER,
    ))
    return styles


def _make_table(data, col_widths=None, header=True):
    """Create a formatted table."""
    if not data:
        return Spacer(1, 0)
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Alternating row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), LIGHT_GREY))
    t.setStyle(TableStyle(style_cmds))
    return t


def _fmt(val, fmt_type="number"):
    """Format a value for display."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    if fmt_type == "pct":
        return f"{val:.1%}"
    if fmt_type == "price":
        return f"${val:,.2f}"
    if fmt_type == "mult":
        return f"{val:.1f}x"
    return f"{val:,.0f}"


def build_pdf_memo(
    output_path: str | Path,
    cfg: "DCFEngineConfig",
    income_stmt: Optional[pd.DataFrame] = None,
    balance_sheet_table: Optional[pd.DataFrame] = None,
    cash_flow_table: Optional[pd.DataFrame] = None,
    fcf_table: Optional[pd.DataFrame] = None,
    wacc_result=None,
    dcf_result=None,
    scenario_comparison=None,
    sensitivity_result=None,
    monte_carlo_result=None,
    tornado_result=None,
    comps_result=None,
) -> Optional[Path]:
    """Build 10-15 page PDF Investment Memo."""
    if not HAS_REPORTLAB:
        logger.error("ReportLab not installed. Skipping PDF generation.")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _get_styles()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    story = []

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 1: Cover
    # ═══════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("CONFIDENTIAL", styles["Disclaimer"]))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(cfg.company.name, styles["CoverTitle"]))
    story.append(Paragraph("Discounted Cash Flow Valuation", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.5 * inch))

    cover_data = [
        ["Ticker", cfg.company.ticker or "N/A"],
        ["Industry", cfg.company.industry or "N/A"],
        ["Analyst", cfg.company.analyst_name],
        ["Date", cfg.company.report_date or timestamp],
    ]
    story.append(_make_table(cover_data, col_widths=[2 * inch, 3 * inch], header=False))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 2: Executive Summary
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Executive Summary", styles["SectionHeader"]))
    story.append(Spacer(1, 6))

    if dcf_result:
        summary_text = (
            f"Based on our discounted cash flow analysis using a {cfg.forecast.projection_years}-year "
            f"projection period, we derive a blended equity value of <b>{_fmt(dcf_result.equity_blended)}</b> "
            f"(implied price per share of <b>{_fmt(dcf_result.price_blended, 'price')}</b>). "
            f"The WACC used is <b>{_fmt(wacc_result.wacc if wacc_result else 0, 'pct')}</b> with a "
            f"terminal growth rate of <b>{_fmt(dcf_result.effective_terminal_growth, 'pct')}</b>. "
            f"Terminal value represents <b>{_fmt(dcf_result.tv_pct_of_ev, 'pct')}</b> of enterprise value."
        )
        story.append(Paragraph(summary_text, styles["BodyText2"]))
        story.append(Spacer(1, 12))

        val_table = [
            ["Metric", "Gordon Growth", "Exit Multiple", "Blended"],
            ["Enterprise Value", _fmt(dcf_result.ev_gordon), _fmt(dcf_result.ev_exit), _fmt(dcf_result.ev_blended)],
            ["Equity Value", _fmt(dcf_result.equity_gordon), _fmt(dcf_result.equity_exit), _fmt(dcf_result.equity_blended)],
            ["Price/Share", _fmt(dcf_result.price_gordon, "price"), _fmt(dcf_result.price_exit, "price"), _fmt(dcf_result.price_blended, "price")],
        ]
        story.append(_make_table(val_table, col_widths=[1.8*inch, 1.6*inch, 1.6*inch, 1.6*inch]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 3: Company Overview
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Company Overview", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    overview = (
        f"<b>{cfg.company.name}</b> operates in the <b>{cfg.company.industry or 'N/A'}</b> sector. "
        f"The company's fiscal year ends in <b>{cfg.company.fiscal_year_end}</b> and reports in "
        f"<b>{cfg.company.currency}</b>. {cfg.company.description or ''}"
    )
    story.append(Paragraph(overview, styles["BodyText2"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGES 4-5: Financial Analysis
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Historical Financial Analysis", styles["SectionHeader"]))
    story.append(Spacer(1, 6))

    if income_stmt is not None and not income_stmt.empty:
        story.append(Paragraph("Income Statement Summary", styles["SubHeader"]))
        is_cols = ["year_index", "Revenue", "EBITDA", "EBITDA Margin", "Net Income"]
        is_display = income_stmt[[c for c in is_cols if c in income_stmt.columns]].copy()
        is_data = [list(is_display.columns)]
        for _, row in is_display.iterrows():
            is_data.append([
                f"Year {int(row.get('year_index', 0))}",
                *[_fmt(row[c], "pct" if "Margin" in c else "number") for c in is_display.columns[1:]]
            ])
        story.append(_make_table(is_data))
        story.append(Spacer(1, 12))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGES 5-6: Forecast & Assumptions
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Forecast Summary & Key Assumptions", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    assumptions_data = [
        ["Parameter", "Value"],
        ["Revenue Growth (CAGR)", _fmt(cfg.forecast.revenue_cagr, "pct")],
        ["COGS % Revenue", _fmt(cfg.forecast.cogs_pct_revenue, "pct")],
        ["SGA % Revenue", _fmt(cfg.forecast.sga_pct_revenue, "pct")],
        ["Capex % Revenue", _fmt(cfg.forecast.capex_pct_revenue, "pct")],
        ["Tax Rate", _fmt(cfg.forecast.tax_rate, "pct")],
        ["DSO / DIO / DPO", f"{cfg.forecast.dso:.0f} / {cfg.forecast.dio:.0f} / {cfg.forecast.dpo:.0f}"],
    ]
    story.append(_make_table(assumptions_data, col_widths=[3*inch, 2.5*inch]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGES 7-8: DCF Valuation
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. DCF Valuation", styles["SectionHeader"]))
    story.append(Spacer(1, 6))

    if wacc_result:
        story.append(Paragraph("WACC Build", styles["SubHeader"]))
        wacc_data = [
            ["Component", "Value"],
            ["Cost of Equity (Ke)", _fmt(wacc_result.cost_of_equity, "pct")],
            ["Cost of Debt (after-tax)", _fmt(wacc_result.cost_of_debt_after_tax, "pct")],
            ["Equity Weight", _fmt(wacc_result.equity_weight, "pct")],
            ["Debt Weight", _fmt(wacc_result.debt_weight, "pct")],
            ["WACC", _fmt(wacc_result.wacc, "pct")],
        ]
        story.append(_make_table(wacc_data, col_widths=[3*inch, 2.5*inch]))
        story.append(Spacer(1, 12))

    if fcf_table is not None and not fcf_table.empty:
        story.append(Paragraph("Projected Free Cash Flows", styles["SubHeader"]))
        fcf_cols = ["year_index", "Unlevered FCF"]
        fcf_display = fcf_table[[c for c in fcf_cols if c in fcf_table.columns]]
        fcf_data = [["Year", "Unlevered FCF"]]
        for _, row in fcf_display.iterrows():
            fcf_data.append([f"Year {int(row['year_index'])}", _fmt(row.get("Unlevered FCF", 0))])
        story.append(_make_table(fcf_data, col_widths=[2*inch, 3*inch]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 9: Scenario Analysis
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Scenario Analysis", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    if scenario_comparison and not scenario_comparison.comparison.empty:
        comp = scenario_comparison.comparison
        scen_data = [["Metric"] + list(comp.columns)]
        for metric in comp.index[:10]:
            row_vals = comp.loc[metric]
            scen_data.append([metric] + [_fmt(v) if isinstance(v, (int, float)) else str(v) for v in row_vals])
        story.append(_make_table(scen_data))
    else:
        story.append(Paragraph("Scenario comparison data not available.", styles["BodyText2"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 10: Comparable Companies
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Comparable Companies Analysis", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    if comps_result and not comps_result.peer_table.empty:
        pt = comps_result.peer_table
        cols = [c for c in ["Ticker", "EV/Revenue", "EV/EBITDA", "P/E"] if c in pt.columns]
        comps_data = [cols]
        for _, row in pt.iterrows():
            comps_data.append([row.get(c, "") if c == "Ticker" else _fmt(row.get(c, 0), "mult") for c in cols])
        story.append(_make_table(comps_data))
    else:
        story.append(Paragraph("No comparable company data available.", styles["BodyText2"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGES 11-12: Sensitivity & Risk
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("8. Sensitivity & Risk Analysis", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    if sensitivity_result:
        story.append(Paragraph("WACC vs Terminal Growth Rate", styles["SubHeader"]))
        t1 = sensitivity_result.wacc_vs_growth.reset_index()
        data1 = [list(t1.columns)]
        for _, row in t1.iterrows():
            data1.append([str(v) if isinstance(v, str) else _fmt(v) for v in row])
        story.append(_make_table(data1))
        story.append(Spacer(1, 12))
    if tornado_result:
        story.append(Paragraph("Tornado Chart — Key Drivers", styles["SubHeader"]))
        td = tornado_result.drivers
        tornado_data = [["Driver", "Low", "High", "Impact"]]
        for _, row in td.iterrows():
            tornado_data.append([
                row["Driver"], _fmt(row["Equity at Low"]),
                _fmt(row["Equity at High"]), _fmt(row["Impact"]),
            ])
        story.append(_make_table(tornado_data))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 13: Monte Carlo
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("9. Monte Carlo Simulation", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    if monte_carlo_result:
        mc_text = (
            f"A {monte_carlo_result.iterations:,}-iteration Monte Carlo simulation yields a "
            f"mean equity value of <b>{_fmt(monte_carlo_result.statistics.get('Mean', 0))}</b> "
            f"with a median of <b>{_fmt(monte_carlo_result.statistics.get('Median', 0))}</b>. "
            f"The P10–P90 range is <b>{_fmt(monte_carlo_result.statistics.get('P10', 0))}</b> to "
            f"<b>{_fmt(monte_carlo_result.statistics.get('P90', 0))}</b>."
        )
        story.append(Paragraph(mc_text, styles["BodyText2"]))
        story.append(Spacer(1, 12))
        mc_data = [["Statistic", "Value"]]
        for k, v in monte_carlo_result.statistics.items():
            fmt = "price" if "Per Share" in k else "number"
            mc_data.append([k, _fmt(v, fmt)])
        story.append(_make_table(mc_data, col_widths=[3*inch, 2.5*inch]))
    else:
        story.append(Paragraph("Monte Carlo data not available.", styles["BodyText2"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 14-15: Appendix
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("10. Appendix: Detailed Schedules", styles["SectionHeader"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Full projected financial statements and supporting schedules "
                           "are provided in the accompanying Excel workbook.", styles["BodyText2"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Disclaimer", styles["SubHeader"]))
    story.append(Paragraph(
        "This document is prepared for informational purposes only and does not constitute "
        "an offer or solicitation. All projections are based on assumptions that may not "
        "materialize. Past performance is not indicative of future results.",
        styles["Disclaimer"],
    ))

    # ── Build PDF ────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        title=f"{cfg.company.name} — DCF Valuation",
        author=cfg.company.analyst_name,
    )

    doc.build(story)
    logger.info("PDF memo saved to %s", output_path)
    return output_path
