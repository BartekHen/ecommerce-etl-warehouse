-- Reference DDL for the OLTP source (SQLite), normalized to 3NF: a
-- category name lives only in "categories", never copied into "products".
--
-- generate_data.py builds this same schema itself in Python; this file
-- is not executed, it's here for reference.

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
    order_date  TEXT NOT NULL,  -- ISO format date, e.g. "2025-03-14"
    status      TEXT NOT NULL,  -- 'completed', 'pending' or 'cancelled'
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL,  -- price at the moment of the order
    discount      REAL NOT NULL,  -- fraction, e.g. 0.10 = 10% off
    FOREIGN KEY (order_id) REFERENCES orders (order_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);
