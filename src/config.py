"""
File paths and settings shared by the whole pipeline.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- OLTP source (SQLite) ---
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
SQLITE_DB_PATH = DATA_DIR / "oltp.sqlite"

# --- OLAP warehouse (DuckDB) ---
DUCKDB_PATH = BASE_DIR / "warehouse.duckdb"

# --- Power BI export (Parquet files for Get Data -> Folder) ---
POWERBI_EXPORT_DIR = BASE_DIR / "powerbi_export"

# --- SQL scripts ---
SQL_DIR = BASE_DIR / "sql"
OLTP_SCHEMA_PATH = SQL_DIR / "oltp_schema.sql"
WAREHOUSE_SCHEMA_PATH = SQL_DIR / "warehouse_schema.sql"
ANALYTICS_QUERIES_PATH = SQL_DIR / "analytics_queries.sql"

# --- AI insights ---
INSIGHTS_DIR = BASE_DIR / "insights"

# --- README chart images ---
DOCS_IMAGES_DIR = BASE_DIR / "docs" / "images"

# --- Data generation settings ---
RANDOM_SEED = 42
NUM_CUSTOMERS = 300
NUM_PRODUCTS = 80
NUM_ORDERS = 3000
