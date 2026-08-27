"""
Generates the two charts embedded in README.md, straight from the warehouse.

Run with: python -m src.generate_charts
"""

import duckdb
import matplotlib.pyplot as plt

from src.config import DOCS_IMAGES_DIR, DUCKDB_PATH

REVENUE_BY_MONTH_SQL = """
    SELECT d.year, d.month, SUM(f.net_amount) AS revenue
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year, d.month
    ORDER BY d.year, d.month
"""

TOP_PRODUCTS_SQL = """
    SELECT p.name AS product_name, SUM(f.net_amount) AS revenue
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.name
    ORDER BY revenue DESC
    LIMIT 10
"""


def plot_revenue_by_month(connection):
    """Line chart: total revenue per calendar month, across the whole date range."""
    result_df = connection.execute(REVENUE_BY_MONTH_SQL).df()
    labels = [f"{int(year)}-{int(month):02d}" for year, month in zip(result_df["year"], result_df["month"])]

    plt.figure(figsize=(10, 4))
    plt.plot(labels, result_df["revenue"], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.title("Revenue by Month")
    plt.ylabel("Net revenue")
    plt.tight_layout()
    plt.savefig(DOCS_IMAGES_DIR / "revenue_by_month.png", dpi=120)
    plt.close()


def plot_top_products(connection):
    """Horizontal bar chart: top 10 products by revenue."""
    result_df = connection.execute(TOP_PRODUCTS_SQL).df().sort_values("revenue")

    plt.figure(figsize=(8, 5))
    plt.barh(result_df["product_name"], result_df["revenue"])
    plt.title("Top 10 Products by Revenue")
    plt.xlabel("Net revenue")
    plt.tight_layout()
    plt.savefig(DOCS_IMAGES_DIR / "top_products.png", dpi=120)
    plt.close()


def main():
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {DUCKDB_PATH}. Run 'python -m src.pipeline' first."
        )

    DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        plot_revenue_by_month(connection)
        plot_top_products(connection)
    finally:
        connection.close()

    print(f"Charts saved to {DOCS_IMAGES_DIR}")


if __name__ == "__main__":
    main()
