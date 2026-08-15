"""
Runs the full ETL pipeline: Extract (from OLTP SQLite) -> Transform (into
a star schema) -> Load (into the OLAP DuckDB warehouse).

Usage:
    python -m src.pipeline
"""

from src.config import DUCKDB_PATH, SQLITE_DB_PATH
from src.extract import Extractor
from src.load import Loader
from src.transform import Transformer


def run_pipeline():
    """Run Extract, then Transform, then Load, and print a short summary."""
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError(
            f"OLTP database not found at {SQLITE_DB_PATH}. "
            "Run 'python -m data.generate_data' first."
        )

    print("=== EXTRACT ===")
    extractor = Extractor()
    raw_tables = extractor.extract_all()
    for table_name, dataframe in raw_tables.items():
        print(f"  {table_name}: {len(dataframe)} rows")

    print("=== TRANSFORM ===")
    transformer = Transformer()
    dim_date = transformer.build_dim_date(raw_tables["orders"])
    dim_product = transformer.build_dim_product(raw_tables["products"], raw_tables["categories"])
    dim_customer = transformer.build_dim_customer(raw_tables["customers"])
    dim_channel = transformer.build_dim_channel(raw_tables["channels"])
    fact_sales = transformer.build_fact_sales(
        raw_tables["order_items"],
        raw_tables["orders"],
        dim_date,
        dim_product,
        dim_customer,
        dim_channel,
    )
    print(f"  dim_date: {len(dim_date)} rows")
    print(f"  dim_product: {len(dim_product)} rows")
    print(f"  dim_customer: {len(dim_customer)} rows")
    print(f"  dim_channel: {len(dim_channel)} rows")
    print(f"  fact_sales: {len(fact_sales)} rows")

    print("=== LOAD ===")
    loader = Loader()
    row_counts = loader.load_all(dim_date, dim_product, dim_customer, dim_channel, fact_sales)
    print(f"  Warehouse written to: {DUCKDB_PATH}")

    print("=== DONE ===")
    print("Row counts in the warehouse:")
    for table_name, row_count in row_counts.items():
        print(f"  {table_name}: {row_count} rows")


if __name__ == "__main__":
    run_pipeline()
