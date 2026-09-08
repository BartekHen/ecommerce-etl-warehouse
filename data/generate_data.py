"""
Builds a synthetic e-commerce OLTP database in SQLite (stdlib only, no
pandas) and exports each table to CSV.

Run with: python -m data.generate_data
"""

import csv
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import (
    CSV_DIR,
    NUM_CUSTOMERS,
    NUM_ORDERS,
    NUM_PRODUCTS,
    RANDOM_SEED,
    SQLITE_DB_PATH,
)

CATEGORY_NAMES = [
    "Electronics",
    "Books",
    "Clothing",
    "Home & Garden",
    "Sports & Outdoors",
    "Toys & Games",
    "Beauty & Health",
    "Grocery",
]

CHANNEL_NAMES = ["Web Store", "Mobile App", "Marketplace", "Retail Store"]

CITY_COUNTRY_PAIRS = [
    ("Warsaw", "Poland"),
    ("Krakow", "Poland"),
    ("Berlin", "Germany"),
    ("Munich", "Germany"),
    ("Paris", "France"),
    ("Lyon", "France"),
    ("Madrid", "Spain"),
    ("Barcelona", "Spain"),
    ("Rome", "Italy"),
    ("Milan", "Italy"),
    ("London", "United Kingdom"),
    ("Manchester", "United Kingdom"),
    ("Amsterdam", "Netherlands"),
    ("New York", "United States"),
    ("Chicago", "United States"),
]

FIRST_NAMES = [
    "John", "Anna", "Michael", "Sophie", "David", "Laura", "Peter", "Maria",
    "Thomas", "Julia", "James", "Emma", "Robert", "Olivia", "Daniel", "Emily",
    "Paul", "Clara", "Mark", "Nina",
]

LAST_NAMES = [
    "Smith", "Kowalski", "Muller", "Dubois", "Garcia", "Rossi", "Johnson",
    "Nowak", "Weber", "Martin", "Fischer", "Bianchi", "Brown", "Wojcik",
    "Schmidt", "Moreau", "Lopez", "Conti", "Wilson", "Zielinski",
]

PRODUCT_ADJECTIVES = [
    "Classic", "Premium", "Compact", "Wireless", "Eco", "Deluxe", "Portable",
    "Smart", "Essential", "Ultra",
]

PRODUCT_NOUNS_BY_CATEGORY = {
    "Electronics": ["Headphones", "Speaker", "Charger", "Smartwatch", "Camera"],
    "Books": ["Novel", "Cookbook", "Notebook", "Biography", "Atlas"],
    "Clothing": ["T-Shirt", "Jacket", "Jeans", "Sweater", "Scarf"],
    "Home & Garden": ["Lamp", "Planter", "Cushion", "Rug", "Toolset"],
    "Sports & Outdoors": ["Backpack", "Water Bottle", "Yoga Mat", "Tent", "Bike Helmet"],
    "Toys & Games": ["Puzzle", "Board Game", "Action Figure", "Building Blocks", "Drone"],
    "Beauty & Health": ["Shampoo", "Face Cream", "Vitamins", "Toothbrush", "Sunscreen"],
    "Grocery": ["Coffee Beans", "Olive Oil", "Pasta", "Honey", "Tea Set"],
}

# "completed" 3x out of 5 -> roughly 60% of orders, rest pending/cancelled
ORDER_STATUSES = ["completed", "completed", "completed", "pending", "cancelled"]


def create_schema(connection):
    """Create the six OLTP tables (matches sql/oltp_schema.sql)."""
    cursor = connection.cursor()
    cursor.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS channels;
        DROP TABLE IF EXISTS categories;

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            name        TEXT NOT NULL
        );

        CREATE TABLE channels (
            channel_id INTEGER PRIMARY KEY,
            name       TEXT NOT NULL
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            city        TEXT NOT NULL,
            country     TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id  INTEGER PRIMARY KEY,
            sku         TEXT NOT NULL,
            name        TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            unit_cost   REAL NOT NULL,
            price       REAL NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (category_id)
        );

        CREATE TABLE orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            channel_id  INTEGER NOT NULL,
            order_date  TEXT NOT NULL,
            status      TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
            FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id      INTEGER NOT NULL,
            product_id    INTEGER NOT NULL,
            quantity      INTEGER NOT NULL,
            unit_price    REAL NOT NULL,
            discount      REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );
        """
    )
    connection.commit()


def insert_categories(connection):
    cursor = connection.cursor()
    category_ids = []
    for category_id, name in enumerate(CATEGORY_NAMES, start=1):
        cursor.execute(
            "INSERT INTO categories (category_id, name) VALUES (?, ?)",
            (category_id, name),
        )
        category_ids.append(category_id)
    connection.commit()
    return category_ids


def insert_channels(connection):
    cursor = connection.cursor()
    channel_ids = []
    for channel_id, name in enumerate(CHANNEL_NAMES, start=1):
        cursor.execute(
            "INSERT INTO channels (channel_id, name) VALUES (?, ?)",
            (channel_id, name),
        )
        channel_ids.append(channel_id)
    connection.commit()
    return channel_ids


def insert_customers(connection, num_customers):
    cursor = connection.cursor()
    customer_ids = []
    for customer_id in range(1, num_customers + 1):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        city, country = random.choice(CITY_COUNTRY_PAIRS)
        cursor.execute(
            "INSERT INTO customers (customer_id, name, city, country) VALUES (?, ?, ?, ?)",
            (customer_id, name, city, country),
        )
        customer_ids.append(customer_id)
    connection.commit()
    return customer_ids


def insert_products(connection, num_products, category_ids):
    """Insert random products and return a lookup list needed later for order_items."""
    cursor = connection.cursor()
    products = []
    for product_id in range(1, num_products + 1):
        category_id = random.choice(category_ids)
        category_name = CATEGORY_NAMES[category_id - 1]
        noun = random.choice(PRODUCT_NOUNS_BY_CATEGORY[category_name])
        adjective = random.choice(PRODUCT_ADJECTIVES)
        name = f"{adjective} {noun}"
        sku = f"{category_name[:3].upper()}-{product_id:04d}"

        unit_cost = round(random.uniform(5, 200), 2)
        markup = random.uniform(1.3, 1.9)
        price = round(unit_cost * markup, 2)

        cursor.execute(
            """INSERT INTO products
               (product_id, sku, name, category_id, unit_cost, price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_id, sku, name, category_id, unit_cost, price),
        )
        products.append(
            {
                "product_id": product_id,
                "category_id": category_id,
                "unit_cost": unit_cost,
                "price": price,
            }
        )
    connection.commit()
    return products


def insert_orders_and_items(connection, num_orders, customer_ids, channel_ids, products):
    """Insert random orders, each with 1-4 order_items, spread over the last 2 years."""
    cursor = connection.cursor()
    today = date.today()
    two_years_ago = today - timedelta(days=730)

    order_item_id = 1
    for order_id in range(1, num_orders + 1):
        customer_id = random.choice(customer_ids)
        channel_id = random.choice(channel_ids)
        status = random.choice(ORDER_STATUSES)

        days_offset = random.randint(0, (today - two_years_ago).days)
        order_date = two_years_ago + timedelta(days=days_offset)

        cursor.execute(
            """INSERT INTO orders (order_id, customer_id, channel_id, order_date, status)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, customer_id, channel_id, order_date.isoformat(), status),
        )

        num_items = random.randint(1, 4)
        # sample() instead of choice() so an order never repeats a product
        chosen_products = random.sample(products, k=min(num_items, len(products)))
        for product in chosen_products:
            quantity = random.randint(1, 5)
            unit_price = round(product["price"] * random.uniform(0.95, 1.05), 2)
            discount = random.choice([0.0, 0.0, 0.0, 0.05, 0.1, 0.15, 0.2])

            cursor.execute(
                """INSERT INTO order_items
                   (order_item_id, order_id, product_id, quantity, unit_price, discount)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_item_id, order_id, product["product_id"], quantity, unit_price, discount),
            )
            order_item_id += 1

    connection.commit()


def export_tables_to_csv(connection, csv_dir):
    """Write every OLTP table to its own CSV file in csv_dir."""
    csv_dir.mkdir(parents=True, exist_ok=True)
    table_names = ["categories", "channels", "customers", "products", "orders", "order_items"]

    for table_name in table_names:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        column_names = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        csv_path = csv_dir / f"{table_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(column_names)
            writer.writerows(rows)


def main():
    random.seed(RANDOM_SEED)

    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_DB_PATH.exists():
        SQLITE_DB_PATH.unlink()

    connection = sqlite3.connect(SQLITE_DB_PATH)
    try:
        create_schema(connection)
        category_ids = insert_categories(connection)
        channel_ids = insert_channels(connection)
        customer_ids = insert_customers(connection, NUM_CUSTOMERS)
        products = insert_products(connection, NUM_PRODUCTS, category_ids)
        insert_orders_and_items(connection, NUM_ORDERS, customer_ids, channel_ids, products)
        export_tables_to_csv(connection, CSV_DIR)
    finally:
        connection.close()

    print(f"OLTP database created at: {SQLITE_DB_PATH}")
    print(f"CSV export created at:    {CSV_DIR}")
    print(
        f"Generated {len(customer_ids)} customers, {len(products)} products, "
        f"{NUM_ORDERS} orders."
    )


if __name__ == "__main__":
    main()
