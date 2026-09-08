"""
Builds an Excel workbook straight from the warehouse: a real Excel Table,
SUMIFS/XLOOKUP/LARGE formulas, charts, and a budget-vs-actual sheet.
Formulas are written as formulas, not pre-computed values, so opening the
file in Excel actually recalculates everything.

Run with: python -m src.generate_excel
"""

import statistics
from collections import defaultdict

import duckdb
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from src.config import DUCKDB_PATH, EXCEL_PATH

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
INPUT_FONT = Font(color="0070C0")  # blue = input cell, standard FP&A convention
MONEY_FMT = "#,##0.00"

QUERY = """
    SELECT
        d.full_date AS order_date,
        d.year AS year,
        d.month_name AS month_name,
        p.name AS product_name,
        p.category AS category,
        c.name AS customer_name,
        c.country AS country,
        ch.name AS channel,
        f.quantity AS quantity,
        f.gross_amount AS gross_amount,
        f.discount_amount AS discount_amount,
        f.net_amount AS net_amount,
        f.cost_amount AS cost_amount,
        f.margin AS margin
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    JOIN dim_product p ON f.product_key = p.product_key
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_channel ch ON f.channel_key = ch.channel_key
    ORDER BY d.full_date
"""

HEADERS = [
    "Order Date", "Year", "Month Name", "Product", "Category",
    "Customer", "Country", "Channel", "Quantity",
    "Gross Amount", "Discount Amount", "Net Amount", "Cost Amount", "Margin",
]


def fetch_rows():
    connection = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    rows = connection.execute(QUERY).fetchall()
    connection.close()
    return rows


def style_header(ws, n_cols):
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


def build_raw_data_sheet(wb, rows):
    ws = wb.active
    ws.title = "Raw Data"

    ws.append(HEADERS + ["Period"])
    for row in rows:
        ws.append(list(row))

    n_rows = len(rows) + 1
    n_cols = len(HEADERS)

    # Period is a live formula, not pre-computed, so it's visible in the
    # sheet how the month grouping actually works
    period_col = n_cols + 1
    for r in range(2, n_rows + 1):
        ws.cell(row=r, column=period_col, value=f'=TEXT(A{r},"yyyy-mm")')

    style_header(ws, n_cols + 1)

    last_col_letter = get_column_letter(n_cols + 1)
    table = Table(displayName="SalesData", ref=f"A1:{last_col_letter}{n_rows}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)

    for i, header in enumerate(HEADERS + ["Period"], start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, len(header) + 2)

    date_col = HEADERS.index("Order Date") + 1
    for r in range(2, n_rows + 1):
        ws.cell(row=r, column=date_col).number_format = "yyyy-mm-dd"

    for money_header in ["Gross Amount", "Discount Amount", "Net Amount", "Cost Amount", "Margin"]:
        idx = HEADERS.index(money_header) + 1
        for r in range(2, n_rows + 1):
            ws.cell(row=r, column=idx).number_format = MONEY_FMT

    ws.freeze_panes = "A2"
    return n_rows


def build_summary_sheet(wb, categories, channels, periods, products):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Summary (live formulas, referencing the SalesData table)"
    ws["A1"].font = TITLE_FONT

    ws["A3"] = "Revenue by Category"
    ws["A3"].font = Font(bold=True)
    headers_row = 4
    for col, label in enumerate(["Category", "Revenue", "Margin", "Margin %"], start=1):
        c = ws.cell(row=headers_row, column=col, value=label)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT

    start_row = headers_row + 1
    for i, category in enumerate(categories):
        r = start_row + i
        ws.cell(row=r, column=1, value=category)
        ws.cell(row=r, column=2, value=f"=SUMIFS(SalesData[Net Amount],SalesData[Category],A{r})")
        ws.cell(row=r, column=3, value=f"=SUMIFS(SalesData[Margin],SalesData[Category],A{r})")
        ws.cell(row=r, column=4, value=f"=IFERROR(C{r}/B{r},0)")
        ws.cell(row=r, column=2).number_format = MONEY_FMT
        ws.cell(row=r, column=3).number_format = MONEY_FMT
        ws.cell(row=r, column=4).number_format = "0.0%"
    cat_end_row = start_row + len(categories) - 1

    color_rule = ColorScaleRule(
        start_type="min", start_color="F8696B",
        mid_type="percentile", mid_value=50, mid_color="FFEB84",
        end_type="max", end_color="63BE7B",
    )
    ws.conditional_formatting.add(f"D{start_row}:D{cat_end_row}", color_rule)

    channel_title_row = cat_end_row + 3
    ws.cell(row=channel_title_row, column=1, value="Revenue by Channel").font = Font(bold=True)
    ch_header_row = channel_title_row + 1
    for col, label in enumerate(["Channel", "Revenue", "Orders (line items)", "Avg Order Value"], start=1):
        c = ws.cell(row=ch_header_row, column=col, value=label)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
    ch_start_row = ch_header_row + 1
    for i, channel in enumerate(channels):
        r = ch_start_row + i
        ws.cell(row=r, column=1, value=channel)
        ws.cell(row=r, column=2, value=f"=SUMIFS(SalesData[Net Amount],SalesData[Channel],A{r})")
        ws.cell(row=r, column=3, value=f"=COUNTIFS(SalesData[Channel],A{r})")
        ws.cell(row=r, column=4, value=f"=IFERROR(B{r}/C{r},0)")
        ws.cell(row=r, column=2).number_format = MONEY_FMT
        ws.cell(row=r, column=4).number_format = MONEY_FMT
    ch_end_row = ch_start_row + len(channels) - 1

    month_title_row = ch_end_row + 3
    ws.cell(row=month_title_row, column=1, value='Revenue by Month (Period = TEXT(date,"yyyy-mm"))').font = Font(bold=True)
    month_header_row = month_title_row + 1
    for col, label in enumerate(["Period", "Revenue"], start=1):
        c = ws.cell(row=month_header_row, column=col, value=label)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
    month_start_row = month_header_row + 1
    for i, period in enumerate(periods):
        r = month_start_row + i
        ws.cell(row=r, column=1, value=period)
        ws.cell(row=r, column=2, value=f"=SUMIFS(SalesData[Net Amount],SalesData[Period],A{r})")
        ws.cell(row=r, column=2).number_format = MONEY_FMT
    month_end_row = month_start_row + len(periods) - 1

    top_title_row = month_end_row + 3
    ws.cell(row=top_title_row, column=1, value="Top 10 Products by Revenue (LARGE + INDEX/MATCH)").font = Font(bold=True)
    top_header_row = top_title_row + 1
    for col, label in enumerate(["Rank", "Product", "Revenue"], start=1):
        c = ws.cell(row=top_header_row, column=col, value=label)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
    top_start_row = top_header_row + 1

    # helper columns (H:I) hold every product's revenue - LARGE/INDEX/MATCH
    # above search this range to build the ranking
    helper_col_product, helper_col_revenue = 8, 9
    ws.cell(row=top_header_row, column=helper_col_product, value="All Products (helper)").font = Font(italic=True, color="808080")
    ws.cell(row=top_header_row, column=helper_col_revenue, value="Revenue").font = Font(italic=True, color="808080")
    helper_start_row = top_header_row + 1
    for i, product in enumerate(products):
        r = helper_start_row + i
        p_col = get_column_letter(helper_col_product)
        ws.cell(row=r, column=helper_col_product, value=product)
        ws.cell(row=r, column=helper_col_revenue, value=f"=SUMIFS(SalesData[Net Amount],SalesData[Product],{p_col}{r})")
        ws.cell(row=r, column=helper_col_revenue).number_format = MONEY_FMT
    helper_end_row = helper_start_row + len(products) - 1
    helper_rev_range = f"{get_column_letter(helper_col_revenue)}{helper_start_row}:{get_column_letter(helper_col_revenue)}{helper_end_row}"
    helper_prod_range = f"{get_column_letter(helper_col_product)}{helper_start_row}:{get_column_letter(helper_col_product)}{helper_end_row}"

    for k in range(1, 11):
        r = top_start_row + k - 1
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=3, value=f"=LARGE({helper_rev_range},{k})")
        ws.cell(row=r, column=3).number_format = MONEY_FMT
        ws.cell(row=r, column=2, value=f"=INDEX({helper_prod_range},MATCH(C{r},{helper_rev_range},0))")

    lookup_title_row = top_start_row + 12
    ws.cell(row=lookup_title_row, column=1, value="Product Lookup (XLOOKUP demo - type a product name below)").font = Font(bold=True)
    ws.cell(row=lookup_title_row + 1, column=1, value="Product name:")
    input_cell = f"B{lookup_title_row + 1}"
    ws[input_cell] = products[0]
    ws[input_cell].font = INPUT_FONT
    ws.cell(row=lookup_title_row + 2, column=1, value="Revenue:")
    ws.cell(row=lookup_title_row + 2, column=2, value=f'=XLOOKUP({input_cell},{helper_prod_range},{helper_rev_range},"not found")')
    ws.cell(row=lookup_title_row + 2, column=2).number_format = MONEY_FMT

    for col_letter, width in [("A", 26), ("B", 16), ("C", 16), ("D", 12)]:
        ws.column_dimensions[col_letter].width = width
    ws.column_dimensions[get_column_letter(helper_col_product)].width = 26
    ws.column_dimensions[get_column_letter(helper_col_revenue)].width = 14

    return {
        "cat_range": (start_row, cat_end_row),
        "channel_range": (ch_start_row, ch_end_row),
        "month_range": (month_start_row, month_end_row),
    }


def build_dashboard_sheet(wb, ranges):
    ws = wb.create_sheet("Dashboard")
    ws["A1"] = "E-Commerce Sales Dashboard (Excel)"
    ws["A1"].font = Font(bold=True, size=16, color="1F4E78")

    kpi_labels = ["Total Revenue", "Total Margin", "Margin %", "Total Units", "Avg Order Value"]
    kpi_formulas = [
        "=SUM(SalesData[Net Amount])",
        "=SUM(SalesData[Margin])",
        "=IFERROR(B4/B3,0)",
        "=SUM(SalesData[Quantity])",
        "=IFERROR(B3/COUNTA(SalesData[Order Date]),0)",
    ]
    for i, (label, formula) in enumerate(zip(kpi_labels, kpi_formulas)):
        row = 3 + i
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        cell = ws.cell(row=row, column=2, value=formula)
        cell.number_format = "0.0%" if label == "Margin %" else ("#,##0" if label == "Total Units" else MONEY_FMT)
        cell.font = Font(size=12, bold=True, color="1F4E78")

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 18

    cat_start, cat_end = ranges["cat_range"]
    bar = BarChart()
    bar.title = "Revenue by Category"
    bar.y_axis.title = "Net Revenue"
    data = Reference(wb["Summary"], min_col=2, min_row=cat_start - 1, max_row=cat_end)
    cats = Reference(wb["Summary"], min_col=1, min_row=cat_start, max_row=cat_end)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(cats)
    bar.height, bar.width = 8, 16
    ws.add_chart(bar, "D3")

    month_start, month_end = ranges["month_range"]
    line = LineChart()
    line.title = "Revenue by Month"
    line.y_axis.title = "Net Revenue"
    data = Reference(wb["Summary"], min_col=2, min_row=month_start - 1, max_row=month_end)
    cats = Reference(wb["Summary"], min_col=1, min_row=month_start, max_row=month_end)
    line.add_data(data, titles_from_data=True)
    line.set_categories(cats)
    line.height, line.width = 8, 16
    ws.add_chart(line, "D19")

    ch_start, ch_end = ranges["channel_range"]
    ch_bar = BarChart()
    ch_bar.type = "col"
    ch_bar.title = "Revenue by Channel"
    data = Reference(wb["Summary"], min_col=2, min_row=ch_start - 1, max_row=ch_end)
    cats = Reference(wb["Summary"], min_col=1, min_row=ch_start, max_row=ch_end)
    ch_bar.add_data(data, titles_from_data=True)
    ch_bar.set_categories(cats)
    ch_bar.height, ch_bar.width = 8, 16
    ws.add_chart(ch_bar, "D35")


def build_fpa_sheet(wb, periods, actual_by_period):
    ws = wb.create_sheet("FP&A - Budget vs Actual")
    ws["A1"] = "Budget vs Actual (illustrative targets - not real budget data)"
    ws["A1"].font = TITLE_FONT

    ws["A3"] = "Growth assumption vs prior year:"
    ws["B3"] = 0.08
    ws["B3"].number_format = "0%"
    ws["B3"].font = INPUT_FONT
    ws["A4"] = "Fallback baseline (no prior-year period):"
    baseline = round(statistics.mean(actual_by_period.values()) * 0.9, -2) if actual_by_period else 0
    ws["B4"] = baseline
    ws["B4"].number_format = MONEY_FMT
    ws["B4"].font = INPUT_FONT

    header_row = 6
    for col, label in enumerate(["Period", "Budget", "Actual", "Variance", "Variance %"], start=1):
        c = ws.cell(row=header_row, column=col, value=label)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
    start_row = header_row + 1

    # budget is a planning input, not derived from the actuals it's being
    # compared against: prior-year same month + the growth assumption above
    for i, period in enumerate(periods):
        r = start_row + i
        prior_year_period = f"{int(period[:4]) - 1}{period[4:]}"
        if prior_year_period in actual_by_period:
            budget_value = round(actual_by_period[prior_year_period] * (1 + ws["B3"].value), -2)
        else:
            budget_value = baseline

        ws.cell(row=r, column=1, value=period)
        ws.cell(row=r, column=2, value=budget_value)
        ws.cell(row=r, column=2).number_format = MONEY_FMT
        ws.cell(row=r, column=2).font = INPUT_FONT
        ws.cell(row=r, column=3, value=f"=SUMIFS(SalesData[Net Amount],SalesData[Period],A{r})")
        ws.cell(row=r, column=3).number_format = MONEY_FMT
        ws.cell(row=r, column=4, value=f"=C{r}-B{r}")
        ws.cell(row=r, column=4).number_format = MONEY_FMT
        ws.cell(row=r, column=5, value=f"=IFERROR(D{r}/B{r},0)")
        ws.cell(row=r, column=5).number_format = "0.0%"
    end_row = start_row + len(periods) - 1

    ws.conditional_formatting.add(
        f"D{start_row}:D{end_row}",
        CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")),
    )
    ws.conditional_formatting.add(
        f"D{start_row}:D{end_row}",
        CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")),
    )

    for col_letter, width in [("A", 12), ("B", 14), ("C", 14), ("D", 14), ("E", 12)]:
        ws.column_dimensions[col_letter].width = width


def main():
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {DUCKDB_PATH}. Run 'python -m src.pipeline' first."
        )

    rows = fetch_rows()

    categories = sorted({row[4] for row in rows})
    channels = sorted({row[7] for row in rows})
    products = sorted({row[3] for row in rows})

    actual_by_period = defaultdict(float)
    for row in rows:
        order_date = row[0]
        period = f"{order_date.year:04d}-{order_date.month:02d}"
        actual_by_period[period] += float(row[11])
    periods = sorted(actual_by_period.keys())

    wb = Workbook()
    build_raw_data_sheet(wb, rows)
    ranges = build_summary_sheet(wb, categories, channels, periods, products)
    build_dashboard_sheet(wb, ranges)
    build_fpa_sheet(wb, periods, actual_by_period)
    wb.active = wb["Dashboard"]

    EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(EXCEL_PATH)
    print(f"Saved to {EXCEL_PATH}")


if __name__ == "__main__":
    main()
