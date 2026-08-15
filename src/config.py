"""
Central place for every file path and setting used in the project.

Why this exists: instead of writing the same folder/file paths again in
extract.py, load.py, generate_data.py, etc, every module imports the paths
from here. If we ever move a file, we change it in exactly one place.
"""

from pathlib import Path

# BASE_DIR is the project root folder (the parent of the "src" folder).
# __file__ is the path to this config.py file, so .parent.parent walks up
# from src/config.py -> src/ -> project root.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- OLTP source (SQLite) ---
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
SQLITE_DB_PATH = DATA_DIR / "oltp.sqlite"

# --- OLAP warehouse (DuckDB) ---
DUCKDB_PATH = BASE_DIR / "warehouse.duckdb"

# --- SQL scripts ---
SQL_DIR = BASE_DIR / "sql"
OLTP_SCHEMA_PATH = SQL_DIR / "oltp_schema.sql"
WAREHOUSE_SCHEMA_PATH = SQL_DIR / "warehouse_schema.sql"
ANALYTICS_QUERIES_PATH = SQL_DIR / "analytics_queries.sql"

# --- Data generation settings ---
RANDOM_SEED = 42  # fixed seed so the "random" data is the same on every run
NUM_CUSTOMERS = 300
NUM_PRODUCTS = 80
NUM_ORDERS = 3000
