-- Central integrated database (SQLite). Created fresh by integrate.py on every run.
PRAGMA foreign_keys = ON;

-- Children before parents, so foreign keys never block a drop.
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customer_id_map;
DROP TABLE IF EXISTS rejected_records;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;

-- Customers integrated from the Customer Data System (relational source).
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,          -- keeps the source cust_id
    first_name  TEXT    NOT NULL,
    last_name   TEXT    NOT NULL,
    address     TEXT,
    city        TEXT,
    phone       TEXT CHECK (phone IS NULL OR phone GLOB '+2547[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    email       TEXT UNIQUE CHECK (email IS NULL OR email LIKE '%_@_%._%')
);

-- Products integrated from the Product Data System (CSV feed).
CREATE TABLE products (
    product_id TEXT    PRIMARY KEY,
    name       TEXT    NOT NULL,
    price      NUMERIC NOT NULL CHECK (price > 0),
    stock_qty  INTEGER NOT NULL CHECK (stock_qty >= 0)
);

-- Orders link customers and products through foreign keys.
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
    product_id  TEXT    NOT NULL REFERENCES products (product_id),
    order_date  DATE    NOT NULL CHECK (order_date = date(order_date)),
    quantity    INTEGER NOT NULL CHECK (quantity > 0)
);
CREATE INDEX idx_orders_customer ON orders (customer_id);
CREATE INDEX idx_orders_product  ON orders (product_id);

-- Lineage: duplicate source customers mapped to the record that survived the merge.
CREATE TABLE customer_id_map (
    source_cust_id    INTEGER PRIMARY KEY,
    surviving_cust_id INTEGER NOT NULL REFERENCES customers (customer_id)
);

-- Every row that failed validation, with the reason, so nothing is silently dropped.
CREATE TABLE rejected_records (
    source TEXT NOT NULL,
    record TEXT NOT NULL,
    reason TEXT NOT NULL
);
