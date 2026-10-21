-- Raw layer: typed landing tables written by src/ingest.py.
-- Only rows that pass validation land here; the rest go to raw.rejected_rows.

CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.payments, raw.order_items, raw.orders,
                     raw.products, raw.customers, raw.rejected_rows CASCADE;

CREATE TABLE raw.customers (
    customer_id  INTEGER PRIMARY KEY,
    first_name   TEXT        NOT NULL,
    last_name    TEXT        NOT NULL,
    email        TEXT        NOT NULL UNIQUE,
    country      TEXT        NOT NULL,
    signup_date  DATE        NOT NULL
);

CREATE TABLE raw.products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT           NOT NULL,
    category      TEXT           NOT NULL,
    unit_price    NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE raw.orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES raw.customers (customer_id),
    order_date   DATE    NOT NULL,
    status       TEXT    NOT NULL
);

CREATE TABLE raw.order_items (
    order_item_id  INTEGER PRIMARY KEY,
    order_id       INTEGER        NOT NULL REFERENCES raw.orders (order_id),
    product_id     INTEGER        NOT NULL REFERENCES raw.products (product_id),
    quantity       INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price     NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE raw.payments (
    payment_id      INTEGER PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES raw.orders (order_id),
    payment_method  TEXT           NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    paid_at         TIMESTAMP      NOT NULL
);

CREATE TABLE raw.rejected_rows (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT        NOT NULL,
    reason      TEXT        NOT NULL,
    row_data    JSONB       NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON raw.orders (customer_id);
CREATE INDEX ON raw.order_items (order_id);
CREATE INDEX ON raw.payments (order_id);
