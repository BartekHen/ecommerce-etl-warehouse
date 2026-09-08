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
        # new connection per call, sqlite3 connections aren't thread-safe
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
        # reads are I/O-bound (waiting on SQLite), so threads help here
        # even with the GIL - wouldn't be true for CPU-bound work
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
