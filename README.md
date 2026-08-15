# E-Commerce OLTP -> OLAP ETL Pipeline

A small, self-contained data engineering portfolio project. It generates a
synthetic e-commerce database in the style of a real OLTP system, then runs
an ETL pipeline that extracts, transforms and loads that data into an
analytical data warehouse (star schema) built with DuckDB.

The goal of this project is to demonstrate, in plain readable Python, the
core ideas behind data warehousing: normalization vs. denormalization,
OLTP vs. OLAP, star schemas, surrogate keys, transactions/ACID, and basic
parallelism for I/O-bound work.

## OLTP vs. OLAP

| | OLTP (source) | OLAP (warehouse) |
|---|---|---|
| Purpose | Run the day-to-day store (create orders, add customers) | Analyze historical sales |
| Engine | SQLite | DuckDB |
| Schema | Normalized (3NF) - `categories`, `channels`, `customers`, `products`, `orders`, `order_items` | Star schema - `dim_date`, `dim_product`, `dim_customer`, `dim_channel`, `fact_sales` |
| Data shape | Many small related tables, no repeated data | Few wide tables, some data intentionally repeated (denormalized) |
| Typical query | "Insert one new order" | "Total revenue by category and month" |
| Optimized for | Fast, safe writes of single records | Fast aggregation over millions of rows |

## Star schema

```mermaid
erDiagram
    dim_date {
        int date_key PK
        date full_date
        int day
        int month
        string month_name
        int quarter
        int year
        string weekday
    }
    dim_product {
        int product_key PK
        int product_id
        string sku
        string name
        string category
        decimal unit_cost
        decimal price
    }
    dim_customer {
        int customer_key PK
        int customer_id
        string name
        string city
        string country
    }
    dim_channel {
        int channel_key PK
        int channel_id
        string name
    }
    fact_sales {
        int sale_key PK
        int date_key FK
        int product_key FK
        int customer_key FK
        int channel_key FK
        int quantity
        decimal gross_amount
        decimal discount_amount
        decimal net_amount
        decimal cost_amount
        decimal margin
    }
    dim_date ||--o{ fact_sales : ""
    dim_product ||--o{ fact_sales : ""
    dim_customer ||--o{ fact_sales : ""
    dim_channel ||--o{ fact_sales : ""
```

`fact_sales` has one row per order item (its grain). `dim_product.category`
is denormalized: it is pulled in from the OLTP `categories` table during
the transform step, so analytical queries never need to join a separate
category table.

## The pipeline

```
data/generate_data.py          src/pipeline.py
  (stdlib only)          -->     Extract  -->  Transform  -->  Load
        |                          |               |             |
   data/oltp.sqlite          reads SQLite    builds star      writes
   data/csv/*.csv            into pandas     schema in        warehouse.duckdb
                              DataFrames      pandas           in one
                              (in parallel                     transaction,
                              via threads)                     then indexes
```

1. **Generate** (`data/generate_data.py`) - builds a fresh, normalized
   SQLite database of customers, products, orders and order items, using
   only the Python standard library. Also exports each table to CSV.
2. **Extract** (`src/extract.py`) - the `Extractor` class reads all six
   OLTP tables into pandas DataFrames. `extract_all()` reads them
   concurrently with `ThreadPoolExecutor`, since reading from a database is
   I/O-bound (see the docstring in that file for why threads help there
   despite the GIL).
3. **Transform** (`src/transform.py`) - the `Transformer` class builds the
   four dimension tables (assigning surrogate keys, denormalizing category
   onto products) and the fact table (joining in surrogate keys, computing
   `gross_amount`, `discount_amount`, `net_amount`, `cost_amount`,
   `margin`). Only orders with status `completed` are counted as sales.
4. **Load** (`src/load.py`) - the `Loader` class creates the warehouse
   schema in DuckDB and loads every table inside a single transaction
   (`BEGIN` / `COMMIT` / `ROLLBACK`), so the warehouse is never left
   half-updated. Indexes on `fact_sales`' foreign key columns are created
   afterwards, once, instead of being maintained on every row insert.

## Tech stack

- **Python 3** - standard library only for the data generator
- **pandas** - extract and transform
- **DuckDB** - the analytical warehouse (OLAP, columnar, SQL)
- **SQLite** - the OLTP source database

## Repository structure

```
data/
  generate_data.py       synthetic OLTP data generator (stdlib only)
sql/
  oltp_schema.sql         OLTP DDL (reference)
  warehouse_schema.sql    star schema DDL, executed by src/load.py
  analytics_queries.sql   example OLAP queries
src/
  config.py               paths and settings
  models.py                dataclasses describing each warehouse row
  extract.py               Extractor: OLTP -> pandas DataFrames
  transform.py              Transformer: DataFrames -> star schema
  load.py                   Loader: DataFrames -> DuckDB (transaction + indexes)
  pipeline.py               runs Extract -> Transform -> Load
requirements.txt
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Generate the synthetic OLTP database
python -m data.generate_data

# 2. Run the ETL pipeline (OLTP SQLite -> OLAP DuckDB)
python -m src.pipeline

# 3. Explore the warehouse
python3 -c "import duckdb; duckdb.connect('warehouse.duckdb').sql('SELECT * FROM fact_sales LIMIT 5').show()"
# or open sql/analytics_queries.sql and run individual queries against warehouse.duckdb
```

## Example analytical questions this warehouse answers

See `sql/analytics_queries.sql` for the full, runnable versions:

- What is total revenue and margin per sales channel, per month?
- Which 10 products generate the most revenue?
- What is the average order value per country?
- How does revenue trend quarter over quarter?
- Which product category has the best profit margin?
- Who are the top 5 customers by lifetime revenue?
