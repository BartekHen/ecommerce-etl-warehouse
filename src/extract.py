"""
Extract step: reads the OLTP tables from SQLite into pandas DataFrames.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from src.config import SQLITE_DB_PATH

TABLE_NAMES = ["categories", "channels", "customers", "products", "orders", "order_items"]


class Extractor:
    """Reads the OLTP SQLite database into pandas DataFrames, one per table."""

    def __init__(self, sqlite_path=SQLITE_DB_PATH):
        self.sqlite_path = sqlite_path

    def _read_table(self, table_name):
        # New connection per call - sqlite3 connections aren't safe to
        # share across threads, and extract_all() calls this from a pool.
        connection = sqlite3.connect(self.sqlite_path)
        try:
            dataframe = pd.read_sql(f"SELECT * FROM {table_name}", connection)
        finally:
            connection.close()
        return dataframe

    def extract_categories(self):
        return self._read_table("categories")

    def extract_channels(self):
        return self._read_table("channels")

    def extract_customers(self):
        return self._read_table("customers")

    def extract_products(self):
        return self._read_table("products")

    def extract_orders(self):
        return self._read_table("orders")

    def extract_order_items(self):
        return self._read_table("order_items")

    def extract_all(self):
        """
        Read all six tables at once using a thread pool.

        This helps because reading from SQLite is I/O-bound - most of the
        time a thread spends here is waiting on disk, not running Python.
        CPython releases the GIL while a thread waits on I/O, so the reads
        overlap instead of running one after another. This wouldn't help
        for CPU-bound work (e.g. crunching numbers in a loop), since the
        GIL only lets one thread run Python bytecode at a time - that case
        would need multiprocessing instead.
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
