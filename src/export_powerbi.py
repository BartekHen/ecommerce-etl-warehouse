"""
Exports every warehouse table to a Parquet file, so the star schema can be
loaded straight into Power BI (or any other BI tool that reads Parquet).

Run with: python -m src.export_powerbi
"""

import duckdb

from src.config import DUCKDB_PATH, POWERBI_EXPORT_DIR

TABLE_NAMES = ["dim_date", "dim_product", "dim_customer", "dim_channel", "fact_sales"]


def export_all():
    """Copy every warehouse table into its own .parquet file in POWERBI_EXPORT_DIR."""
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {DUCKDB_PATH}. Run 'python -m src.pipeline' first."
        )

    POWERBI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        for table_name in TABLE_NAMES:
            parquet_path = POWERBI_EXPORT_DIR / f"{table_name}.parquet"
            # DuckDB writes Parquet natively via COPY, no extra library needed
            connection.execute(f"COPY {table_name} TO '{parquet_path}' (FORMAT PARQUET)")
            print(f"  {table_name} -> {parquet_path}")
    finally:
        connection.close()


if __name__ == "__main__":
    print(f"Exporting warehouse tables to {POWERBI_EXPORT_DIR}")
    export_all()
    print("Done.")
