"""Validate the CSV files and load them into PostgreSQL (raw schema).

Steps
-----
1. Read every CSV with pandas (all columns as strings so nothing is silently coerced).
2. Apply table-specific validation rules in dependency order
   (customers/products -> orders -> order_items/payments).
3. Bulk-load valid rows with COPY; write rejected rows (with a reason) to
   raw.rejected_rows and to data/rejected_report.csv.
4. Print a reconciliation summary: read = loaded + rejected, per table.

Usage:
    python src/ingest.py            # uses env vars / defaults for the connection
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
from datetime import date
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
SCHEMA_SQL = ROOT / "sql" / "00_schema.sql"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
VALID_STATUSES = {"pending", "shipped", "completed", "cancelled", "refunded"}

COLUMNS = {
    "customers": ["customer_id", "first_name", "last_name", "email", "country", "signup_date"],
    "products": ["product_id", "product_name", "category", "unit_price"],
    "orders": ["order_id", "customer_id", "order_date", "status"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
    "payments": ["payment_id", "order_id", "payment_method", "amount", "paid_at"],
}


def connect():
    import psycopg2  # imported lazily so the validation rules can be tested without a driver

    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "warehouse"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
class Validator:
    """Collects a boolean mask + reason per rule; first failing rule wins."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.reason = pd.Series([None] * len(df), index=df.index, dtype="object")

    def fail(self, mask: pd.Series, reason: str) -> "Validator":
        mask = mask.fillna(True) & self.reason.isna()
        self.reason[mask] = reason
        return self

    def required(self, cols: list[str]) -> "Validator":
        for c in cols:
            self.fail(self.df[c].isna() | (self.df[c].astype(str).str.strip() == ""), f"{c} is null/empty")
        return self

    def integer(self, col: str, minimum: int | None = None) -> "Validator":
        num = pd.to_numeric(self.df[col], errors="coerce")
        self.fail(num.isna() | (num % 1 != 0), f"{col} is not an integer")
        if minimum is not None:
            self.fail(num < minimum, f"{col} < {minimum}")
        return self

    def decimal(self, col: str, minimum: float = 0) -> "Validator":
        num = pd.to_numeric(self.df[col], errors="coerce")
        self.fail(num.isna(), f"{col} is not numeric")
        self.fail(num < minimum, f"{col} < {minimum}")
        return self

    def date_col(self, col: str, allow_future: bool = False) -> "Validator":
        parsed = pd.to_datetime(self.df[col], errors="coerce")
        self.fail(parsed.isna(), f"{col} is not a valid date")
        if not allow_future:
            self.fail(parsed > pd.Timestamp(date.today()), f"{col} is in the future")
        return self

    def unique(self, col: str) -> "Validator":
        dup = self.df[col].duplicated(keep="first")
        self.fail(dup, f"duplicate {col}")
        return self

    def regex(self, col: str, pattern: re.Pattern, label: str) -> "Validator":
        self.fail(~self.df[col].fillna("").astype(str).str.match(pattern), f"invalid {label}")
        return self

    def isin(self, col: str, allowed: set[str]) -> "Validator":
        self.fail(~self.df[col].isin(allowed), f"{col} not in allowed values")
        return self

    def foreign_key(self, col: str, valid_keys: set[int], parent: str) -> "Validator":
        keys = pd.to_numeric(self.df[col], errors="coerce")
        self.fail(~keys.isin(valid_keys), f"orphan {col} (no matching {parent})")
        return self

    def split(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        bad = self.reason.notna()
        rejected = self.df[bad].assign(_reason=self.reason[bad])
        return self.df[~bad].copy(), rejected


# ---------------------------------------------------------------------------
# Per-table rules
# ---------------------------------------------------------------------------
def validate_customers(df):
    v = Validator(df).required(COLUMNS["customers"]).integer("customer_id", 1)
    v.date_col("signup_date").regex("email", EMAIL_RE, "email").unique("customer_id").unique("email")
    return v.split()


def validate_products(df):
    v = Validator(df).required(COLUMNS["products"]).integer("product_id", 1).decimal("unit_price")
    v.unique("product_id")
    return v.split()


def validate_orders(df, customer_ids):
    v = Validator(df).required(COLUMNS["orders"]).integer("order_id", 1).integer("customer_id", 1)
    v.date_col("order_date").isin("status", VALID_STATUSES).unique("order_id")
    v.foreign_key("customer_id", customer_ids, "customer")
    return v.split()


def validate_order_items(df, order_ids, product_ids):
    v = Validator(df).required(COLUMNS["order_items"]).integer("order_item_id", 1)
    v.integer("quantity", 1).decimal("unit_price").unique("order_item_id")
    v.foreign_key("order_id", order_ids, "order").foreign_key("product_id", product_ids, "product")
    return v.split()


def validate_payments(df, order_ids):
    v = Validator(df).required(COLUMNS["payments"]).integer("payment_id", 1).decimal("amount")
    v.date_col("paid_at").unique("payment_id").foreign_key("order_id", order_ids, "order")
    return v.split()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def copy_df(cur, table: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df[COLUMNS[table]].to_csv(buf, index=False, header=False)
    buf.seek(0)
    cur.copy_expert(f"COPY raw.{table} ({', '.join(COLUMNS[table])}) FROM STDIN WITH CSV", buf)


def save_rejects(cur, table: str, rejected: pd.DataFrame) -> None:
    for _, row in rejected.iterrows():
        payload = {k: (None if pd.isna(v) else v) for k, v in row.drop("_reason").items()}
        cur.execute(
            "INSERT INTO raw.rejected_rows (table_name, reason, row_data) VALUES (%s, %s, %s)",
            (table, row["_reason"], json.dumps(payload)),
        )


def read(table: str) -> pd.DataFrame:
    path = DATA_DIR / f"{table}.csv"
    return pd.read_csv(path, dtype=str, keep_default_na=True)


def main() -> None:
    raw = {t: read(t) for t in COLUMNS}
    for t, df in raw.items():
        log.info("read %-12s %6d rows", t, len(df))

    results: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    results["customers"] = validate_customers(raw["customers"])
    results["products"] = validate_products(raw["products"])
    cust_ids = set(results["customers"][0]["customer_id"].astype(int))
    prod_ids = set(results["products"][0]["product_id"].astype(int))
    results["orders"] = validate_orders(raw["orders"], cust_ids)
    order_ids = set(results["orders"][0]["order_id"].astype(int))
    results["order_items"] = validate_order_items(raw["order_items"], order_ids, prod_ids)
    results["payments"] = validate_payments(raw["payments"], order_ids)

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text())
            for table in COLUMNS:  # dependency order is preserved by dict order
                good, bad = results[table]
                copy_df(cur, table, good)
                save_rejects(cur, table, bad)
    finally:
        conn.close()

    # reconciliation report
    summary, all_rejects = [], []
    for t, (good, bad) in results.items():
        summary.append({"table": t, "read": len(raw[t]), "loaded": len(good), "rejected": len(bad)})
        assert len(raw[t]) == len(good) + len(bad), f"row count mismatch in {t}"
        all_rejects.append(bad.assign(table_name=t)[["table_name", "_reason"]])
    print("\n" + pd.DataFrame(summary).to_string(index=False))

    rej = pd.concat(all_rejects)
    if len(rej):
        report = rej.groupby(["table_name", "_reason"]).size().reset_index(name="rows")
        report.to_csv(DATA_DIR / "rejected_report.csv", index=False)
        print("\nRejection reasons:\n" + report.to_string(index=False))
    log.info("ingestion finished")


if __name__ == "__main__":
    main()
