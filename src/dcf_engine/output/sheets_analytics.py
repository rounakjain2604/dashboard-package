"""Value-based tabs (simulation results) + Checks + Audit Trail."""
from __future__ import annotations
import numpy as np
from datetime import datetime
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter as CL
from .excel_formats import *
from .sheets_core import BS


def build_scenarios(wb, scenario_comparison):
    """Write scenario comparison table (values from simulation)."""
    ws = wb.create_sheet("Scenarios")
    ws.sheet_properties.tabColor = "BF8F00"
    if scenario_comparison is None or scenario_comparison.comparison.empty:
        ws.cell(1,1,value="No scenario data").font = FN; return
    comp = scenario_comparison.comparison
    ws.cell(1,1,value="Scenario Comparison").font = FK
    auto_col(ws,1,24)
    cols = list(comp.columns)
    ws.cell(2,1,value="Metric").font = FH; ws.cell(2,1).fill = FILL_HDR
    for j,cn in enumerate(cols,2):
        ws.cell(2,j,value=cn).font = FH; ws.cell(2,j).fill = FILL_HDR
        auto_col(ws,j,16)
    for i,metric in enumerate(comp.index,3):
        ws.cell(i,1,value=metric).font = FN
        for j,cn in enumerate(cols,2):
            v = comp.loc[metric,cn]
            cell = ws.cell(i,j,value=v if not (isinstance(v,float) and np.isnan(v)) else 0)
            cell.font = FN; cell.alignment = AR
            cell.number_format = PF if isinstance(v,float) and abs(v)<2 else NF
    fit_to_width(ws)


def build_sensitivity(wb, sensitivity_result):
    ws = wb.create_sheet("Sensitivity")
    ws.sheet_properties.tabColor = "305496"
    if sensitivity_result is None:
        ws.cell(1,1,value="No sensitivity data").font = FN; return
    auto_col(ws,1,20)
    r = 1
    for title,tbl in [("WACC vs Terminal Growth",sensitivity_result.wacc_vs_growth),
                       ("Revenue Growth vs EBITDA Margin",sensitivity_result.revenue_vs_margin)]:
        ws.cell(r,1,value=title).font = FK; r += 1
        df = tbl.reset_index()
        for j,cn in enumerate(df.columns):
            ws.cell(r,j+1,value=str(cn)).font = FH; ws.cell(r,j+1).fill = FILL_HDR
            auto_col(ws,j+1,14)
        r += 1
        for _, row in df.iterrows():
            for j,v in enumerate(row):
                cell = ws.cell(r,j+1,value=v if not (isinstance(v,float) and np.isnan(v)) else 0)
                cell.font = FN; cell.alignment = AR; cell.number_format = NF
            r += 1
        # Heatmap
        _apply_heatmap(ws, r-len(df), r-1, 2, len(df.columns)-1)
        r += 2
    fit_to_width(ws)


def _apply_heatmap(ws, start_row, end_row, start_col, num_cols):
    vals = []
    for r in range(start_row, end_row+1):
        for c in range(start_col, start_col+num_cols):
            v = ws.cell(r,c).value
            if isinstance(v,(int,float)): vals.append(v)
    if not vals: return
    mn,mx = min(vals),max(vals); rng = mx-mn if mx!=mn else 1
    for r in range(start_row, end_row+1):
        for c in range(start_col, start_col+num_cols):
            v = ws.cell(r,c).value
            if isinstance(v,(int,float)):
                pct = (v-mn)/rng
                red = int(255*(1-pct)); green = int(200*pct+55)
                ws.cell(r,c).fill = PatternFill("solid",fgColor=f"{min(red,255):02X}{min(green,255):02X}55")


def build_monte_carlo(wb, mc_result):
    ws = wb.create_sheet("Monte Carlo")
    ws.sheet_properties.tabColor = "7030A0"
    if mc_result is None:
        ws.cell(1,1,value="No Monte Carlo data").font = FN; return
    ws.cell(1,1,value="Monte Carlo Simulation").font = FK
    auto_col(ws,1,22); auto_col(ws,2,16)
    r = 3
    for k,v in mc_result.statistics.items():
        ws.cell(r,1,value=k).font = FN
        cell = ws.cell(r,2,value=v)
        cell.font = FN; cell.number_format = PF2 if "Per Share" in k else NF
        r += 1
    r += 1; hist_start = r
    ws.cell(r-1,1,value="Bin").font = FH; ws.cell(r-1,1).fill = FILL_HDR
    ws.cell(r-1,2,value="Frequency").font = FH; ws.cell(r-1,2).fill = FILL_HDR
    hist_data = mc_result.histogram_data if hasattr(mc_result, 'histogram_data') and mc_result.histogram_data else {}
    bin_centers = hist_data.get("bin_centers", [])
    counts = hist_data.get("counts", [])
    if bin_centers and counts:
        for bc, freq in zip(bin_centers, counts):
            ws.cell(r,1,value=bc).number_format = NF; ws.cell(r,1).font = FN
            ws.cell(r,2,value=freq).number_format = NF; ws.cell(r,2).font = FN
            r += 1
        chart = BarChart(); chart.type = "col"
        chart.title = "Equity Value Distribution"; chart.y_axis.title = "Frequency"
        chart.style = 10; chart.width = 20; chart.height = 12
        data = Reference(ws,min_col=2,min_row=hist_start-1,max_row=r-1)
        cats = Reference(ws,min_col=1,min_row=hist_start,max_row=r-1)
        chart.add_data(data,titles_from_data=True); chart.set_categories(cats)
        chart.shape = 4; ws.add_chart(chart,f"D3")
    fit_to_width(ws)


def build_tornado(wb, tornado_result):
    ws = wb.create_sheet("Tornado")
    ws.sheet_properties.tabColor = "ED7D31"
    if tornado_result is None:
        ws.cell(1,1,value="No tornado data").font = FN; return
    ws.cell(1,1,value="Tornado Analysis").font = FK
    auto_col(ws,1,22)
    df = tornado_result.drivers
    r = 3
    for j,cn in enumerate(df.columns):
        ws.cell(r-1,j+1,value=cn).font = FH; ws.cell(r-1,j+1).fill = FILL_HDR
        auto_col(ws,j+1,16)
    for _,row in df.iterrows():
        for j,(cn,v) in enumerate(row.items()):
            cell = ws.cell(r,j+1,value=v)
            cell.font = FN; cell.number_format = NF if isinstance(v,(int,float)) else '@'
        r += 1
    chart = BarChart(); chart.type = "bar"
    chart.title = "Impact on Equity Value"; chart.style = 10
    chart.width = 20; chart.height = 12
    low = Reference(ws,min_col=5,min_row=2,max_row=r-1)
    high = Reference(ws,min_col=6,min_row=2,max_row=r-1)
    cats = Reference(ws,min_col=1,min_row=3,max_row=r-1)
    chart.add_data(low,titles_from_data=True); chart.add_data(high,titles_from_data=True)
    chart.set_categories(cats); ws.add_chart(chart,f"A{r+1}")
    fit_to_width(ws)


def build_comps(wb, comps_result):
    ws = wb.create_sheet("Comps")
    ws.sheet_properties.tabColor = "548235"
    if comps_result is None or comps_result.peer_table.empty:
        ws.cell(1,1,value="No comparable company data").font = FN; return
    ws.cell(1,1,value="Comparable Companies").font = FK
    pt = comps_result.peer_table
    auto_col(ws,1,14)
    for j,cn in enumerate(pt.columns,1):
        ws.cell(2,j,value=cn).font = FH; ws.cell(2,j).fill = FILL_HDR; auto_col(ws,j,16)
    for i,(_,row) in enumerate(pt.iterrows(),3):
        for j,(cn,v) in enumerate(row.items(),1):
            cell = ws.cell(i,j,value=v if v is not None and not (isinstance(v,float) and np.isnan(v)) else 0)
            cell.font = FN; cell.number_format = XF if cn != "Ticker" else '@'
    # Summary stats
    if hasattr(comps_result,'summary_stats') and not comps_result.summary_stats.empty:
        r = len(pt)+4
        ws.cell(r,1,value="Summary Statistics").font = FK; r += 1
        ss = comps_result.summary_stats
        for j,cn in enumerate(ss.columns,1):
            ws.cell(r,j,value=cn).font = FH; ws.cell(r,j).fill = FILL_HDR
        r += 1
        for _,row in ss.iterrows():
            for j,(cn,v) in enumerate(row.items(),1):
                ws.cell(r,j,value=v if v is not None else 0).font = FN
                ws.cell(r,j).number_format = XF if cn != "Statistic" else '@'
            r += 1
    fit_to_width(ws)


def build_checks(wb, n):
    """Formula-linked checks tab."""
    ws = wb.create_sheet("Checks")
    ws.sheet_properties.tabColor = "00B050"
    auto_col(ws,1,28)
    ws.cell(1,1,value="Model Integrity Checks").font = FK
    for j in range(n):
        ws.cell(2,j+2,value=f"Year {j+1}"); auto_col(ws,j+2,14)
    hdr_row(ws,2,n+1)
    style_label(ws,3,1,"BS Balance (A-L-E)",bold=True)
    style_label(ws,4,1,"BS Status")
    style_label(ws,6,1,"CF Ending Cash = BS Cash",bold=True)
    style_label(ws,7,1,"CF Status")
    for j in range(n):
        c = CL(j+2)
        ws[f"{c}3"] = f"='Balance Sheet'!{c}{BS['Chk']}"
        ws[f"{c}4"] = f"='Balance Sheet'!{c}{BS['Stat']}"
        ws[f"{c}6"] = f"='Cash Flow'!{c}23-'Balance Sheet'!{c}{BS['Cash']}"
        ws[f"{c}7"] = f'=IF(ABS({c}6)<1,"PASS","FAIL")'
        for r in [3,6]:
            ws.cell(r,j+2).number_format = NF; ws.cell(r,j+2).font = FN
        for r in [4,7]:
            ws.cell(r,j+2).font = FN
    fit_to_width(ws)


def build_audit(wb, cfg):
    ws = wb.create_sheet("Audit Trail")
    ws.sheet_properties.tabColor = "A5A5A5"
    auto_col(ws,1,24); auto_col(ws,2,18); auto_col(ws,3,30)
    ws.cell(1,1,value="Audit Trail").font = FK
    ws.cell(3,1,value="Generated At").font = FB
    ws.cell(3,2,value=datetime.now().strftime("%Y-%m-%d %H:%M:%S")).font = FN
    ws.cell(4,1,value="Company").font = FB
    ws.cell(4,2,value=cfg.company.name).font = FN
    r = 6
    ws.cell(r,1,value="Configuration Snapshot").font = FK; r += 1
    try:
        d = cfg.to_dict()
        for section,params in d.items():
            if isinstance(params,dict):
                for k,v in params.items():
                    ws.cell(r,1,value=section).font = FN
                    ws.cell(r,2,value=k).font = FN
                    ws.cell(r,3,value=str(v)).font = FN; r += 1
    except Exception:
        ws.cell(r,1,value="Config serialization not available").font = FN
    fit_to_width(ws)
