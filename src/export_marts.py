"""Snapshot the dbt marts (and ingestion stats) to CSV for the Streamlit dashboard.

Usage (after `python src/ingest.py` and `dbt build`):
    python src/export_marts.py
Writes to streamlit_app/data/.
"""
from pathlib import Path

import pandas as pd

from ingest import connect  # reuses the PG* environment variables

OUT = Path(__file__).resolve().parent.parent / "streamlit_app" / "data"
MARTS = ["fct_orders", "dim_customers", "dim_products", "fct_daily_revenue", "customer_rfm"]

REJECTS_SQL = """
    SELECT table_name, reason, COUNT(*) AS rows
    FROM raw.rejected_rows
    GROUP BY table_name, reason
    ORDER BY table_name, reason
"""
SUMMARY_SQL = """
    SELECT t.table_name,
           t.loaded + COALESCE(r.rejected, 0) AS read,
           t.loaded,
           COALESCE(r.rejected, 0)            AS rejected
    FROM (
        SELECT 'customers' AS table_name, COUNT(*) AS loaded FROM raw.customers UNION ALL
        SELECT 'products',    COUNT(*) FROM raw.products     UNION ALL
        SELECT 'orders',      COUNT(*) FROM raw.orders       UNION ALL
        SELECT 'order_items', COUNT(*) FROM raw.order_items  UNION ALL
        SELECT 'payments',    COUNT(*) FROM raw.payments
    ) t
    LEFT JOIN (SELECT table_name, COUNT(*) AS rejected FROM raw.rejected_rows GROUP BY 1) r
           USING (table_name)
"""


def query(cur, sql: str) -> pd.DataFrame:
    cur.execute(sql)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        with conn.cursor() as cur:
            for m in MARTS:
                df = query(cur, f"SELECT * FROM marts.{m}")
                df.to_csv(OUT / f"{m}.csv", index=False)
                print(f"exported {m}: {len(df):,} rows")
            query(cur, REJECTS_SQL).to_csv(OUT / "rejected_report.csv", index=False)
            query(cur, SUMMARY_SQL).to_csv(OUT / "ingestion_summary.csv", index=False)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
