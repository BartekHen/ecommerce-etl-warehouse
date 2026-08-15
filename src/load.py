"""
Load step of the ETL pipeline: creates the star-schema tables in DuckDB
and loads the dimension and fact DataFrames into them.
"""

import duckdb

from src.config import DUCKDB_PATH, WAREHOUSE_SCHEMA_PATH

# Order matters here because of foreign keys:
# - dim_* tables must be loaded BEFORE fact_sales (fact_sales' foreign
#   keys point at them).
# - when clearing old data, fact_sales must be deleted BEFORE the dim_*
#   tables (you cannot delete a row that something else still points to).
DIMENSION_TABLES = ["dim_date", "dim_product", "dim_customer", "dim_channel"]


class Loader:
    """Creates the DuckDB warehouse schema and loads all star-schema data into it."""

    def __init__(self, duckdb_path=DUCKDB_PATH):
        self.duckdb_path = duckdb_path

    def create_schema(self, connection):
        """Run the DDL script that creates every star-schema table (if missing)."""
        schema_sql = WAREHOUSE_SCHEMA_PATH.read_text()
        connection.execute(schema_sql)

    def _create_indexes(self, connection):
        """
        Create indexes on fact_sales' foreign key columns, AFTER all the
        data has been loaded.

        WHY AFTER THE LOAD, NOT BEFORE:
        An index has to be updated every time a row is inserted into its
        table. If these indexes already existed while we were inserting
        thousands of fact_sales rows, the database would pay that update
        cost on every single insert. It is much cheaper to insert the raw
        data first, with no indexes to maintain, and then build each index
        once, in one pass, at the end.
        """
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_sales(date_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_product ON fact_sales(product_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_channel ON fact_sales(channel_key)")

    def load_all(self, dim_date, dim_product, dim_customer, dim_channel, fact_sales):
        """
        Load every dimension DataFrame and the fact DataFrame into DuckDB,
        all inside a single transaction.

        WHY ONE TRANSACTION (this is TCL - Transaction Control Language,
        and demonstrates the "A" in ACID - Atomicity):
        We want either ALL five tables to load successfully, or NONE of
        them to change at all. Without a transaction, if loading fact_sales
        failed partway through (e.g. bad data) after the dimension tables
        had already been written, the warehouse would be left half-loaded
        and inconsistent - old fact_sales rows next to brand new dimension
        rows. Wrapping every DELETE and INSERT below in
        BEGIN TRANSACTION ... COMMIT makes the whole load one atomic unit:
        if anything raises an exception, we ROLLBACK and the database ends
        up exactly as it was before we started, with no partial data.
        """
        dimension_frames = {
            "dim_date": dim_date,
            "dim_product": dim_product,
            "dim_customer": dim_customer,
            "dim_channel": dim_channel,
        }

        connection = duckdb.connect(str(self.duckdb_path))
        try:
            self.create_schema(connection)

            connection.execute("BEGIN TRANSACTION")
            try:
                # Clear old data first. fact_sales goes first because its
                # foreign keys point at the dimension tables.
                connection.execute("DELETE FROM fact_sales")
                for table_name in DIMENSION_TABLES:
                    connection.execute(f"DELETE FROM {table_name}")

                # Load dimensions before the fact table (parents before child).
                for table_name in DIMENSION_TABLES:
                    dataframe = dimension_frames[table_name]
                    # duckdb.register() makes a pandas DataFrame visible to
                    # SQL as if it were a table, so we can INSERT straight
                    # from Python objects using plain SQL.
                    connection.register("incoming_df", dataframe)
                    connection.execute(f"INSERT INTO {table_name} SELECT * FROM incoming_df")
                    connection.unregister("incoming_df")

                connection.register("incoming_df", fact_sales)
                connection.execute("INSERT INTO fact_sales SELECT * FROM incoming_df")
                connection.unregister("incoming_df")

                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

            self._create_indexes(connection)
        finally:
            connection.close()

        return {
            "dim_date": len(dim_date),
            "dim_product": len(dim_product),
            "dim_customer": len(dim_customer),
            "dim_channel": len(dim_channel),
            "fact_sales": len(fact_sales),
        }
