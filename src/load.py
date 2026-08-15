"""
Load step: creates the star-schema tables in DuckDB and loads the
dimension and fact DataFrames into them.
"""

import duckdb

from src.config import DUCKDB_PATH, WAREHOUSE_SCHEMA_PATH

# fact_sales has foreign keys into these, so they're created/loaded first.
DIMENSION_TABLES = ["dim_date", "dim_product", "dim_customer", "dim_channel"]


class Loader:
    """Creates the DuckDB warehouse schema and loads all star-schema data into it."""

    def __init__(self, duckdb_path=DUCKDB_PATH):
        self.duckdb_path = duckdb_path

    def create_schema(self, connection):
        # Drop child before parents, then recreate from the schema script,
        # so tables are always empty before the load - DuckDB won't allow
        # deleting dimension rows still referenced by fact_sales, even
        # after fact_sales itself was just cleared in the same transaction.
        connection.execute("DROP TABLE IF EXISTS fact_sales")
        for table_name in DIMENSION_TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table_name}")
        schema_sql = WAREHOUSE_SCHEMA_PATH.read_text()
        connection.execute(schema_sql)

    def _create_indexes(self, connection):
        # Built after the load, not before: an index gets updated on every
        # insert, so indexing empty tables and then bulk-loading is cheaper
        # than maintaining the index across thousands of individual inserts.
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_sales(date_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_product ON fact_sales(product_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fact_channel ON fact_sales(channel_key)")

    def load_all(self, dim_date, dim_product, dim_customer, dim_channel, fact_sales):
        """
        Load every table into DuckDB inside a single transaction, so the
        warehouse either ends up fully updated or not touched at all - if
        anything fails partway through, we roll back instead of leaving
        old and new data mixed together.
        """
        dimension_frames = {
            "dim_date": dim_date,
            "dim_product": dim_product,
            "dim_customer": dim_customer,
            "dim_channel": dim_channel,
        }

        connection = duckdb.connect(str(self.duckdb_path))
        try:
            connection.execute("BEGIN TRANSACTION")
            try:
                self.create_schema(connection)

                for table_name in DIMENSION_TABLES:
                    dataframe = dimension_frames[table_name]
                    # register() exposes a DataFrame to SQL as if it were
                    # a table, so we can INSERT ... SELECT straight from it
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
