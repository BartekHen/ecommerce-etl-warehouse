"""
Extract step of the ETL pipeline: reads the raw OLTP tables from SQLite
into pandas DataFrames, so the rest of the pipeline never has to touch
SQL again.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from src.config import SQLITE_DB_PATH

TABLE_NAMES = ["categories", "channels", "customers", "products", "orders", "order_items"]


class Extractor:
    """Reads every table of the OLTP SQLite database into a pandas DataFrame."""

    def __init__(self, sqlite_path=SQLITE_DB_PATH):
        self.sqlite_path = sqlite_path

    def _read_table(self, table_name):
        """
        Read one table into a DataFrame.

        A brand new sqlite3 connection is opened and closed inside this
        method (instead of reusing one connection stored on self) because a
        single sqlite3 connection is not safe to use from multiple threads
        at once. Opening a short-lived connection per table sidesteps that
        problem entirely and keeps each thread fully independent.
        """
        connection = sqlite3.connect(self.sqlite_path)
        try:
            dataframe = pd.read_sql(f"SELECT * FROM {table_name}", connection)
        finally:
            connection.close()
        return dataframe

    def extract_categories(self):
        """Read the categories table."""
        return self._read_table("categories")

    def extract_channels(self):
        """Read the channels table."""
        return self._read_table("channels")

    def extract_customers(self):
        """Read the customers table."""
        return self._read_table("customers")

    def extract_products(self):
        """Read the products table."""
        return self._read_table("products")

    def extract_orders(self):
        """Read the orders table."""
        return self._read_table("orders")

    def extract_order_items(self):
        """Read the order_items table."""
        return self._read_table("order_items")

    def extract_all(self):
        """
        Read all six OLTP tables, in parallel, using a thread pool.

        WHY THREADS HELP HERE, EVEN THOUGH PYTHON HAS A GIL:
        CPython's GIL (Global Interpreter Lock) allows only one thread to
        execute Python bytecode at any given instant. Because of that,
        threads do NOT speed up CPU-bound work - for example, if every
        thread were busy crunching numbers in a Python loop, they would
        just take turns on one CPU core and finish in roughly the same
        total time as doing it one after another.

        But reading a table from a database is I/O-bound: most of the time
        is spent WAITING for SQLite to read from disk and hand rows back,
        not running Python code. While a thread is blocked waiting on that
        I/O, CPython releases the GIL, so a different thread is free to
        run. That means the six table reads below can overlap in time
        instead of running strictly one after another, which is why
        ThreadPoolExecutor is a good fit for this specific step.

        (If this step instead did something CPU-heavy in pure Python, like
        parsing millions of strings by hand, threads would not help - we'd
        need multiprocessing, i.e. separate OS processes each with their
        own GIL, to get real parallelism.)
        """
        results = {}
        with ThreadPoolExecutor(max_workers=len(TABLE_NAMES)) as executor:
            future_to_table = {
                executor.submit(self._read_table, table_name): table_name
                for table_name in TABLE_NAMES
            }
            for future in as_completed(future_to_table):
                table_name = future_to_table[future]
                results[table_name] = future.result()
        return results
