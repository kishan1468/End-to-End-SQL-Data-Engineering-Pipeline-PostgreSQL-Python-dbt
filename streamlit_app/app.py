"""Streamlit dashboard on top of the dbt marts.

Reads CSV snapshots from ./data (exported from PostgreSQL by src/export_marts.py),
so it deploys to Streamlit Community Cloud without a database server.

Run locally:  streamlit run streamlit_app/app.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"
REPO_URL = "https://github.com/kishan1468/End-to-End-SQL-Data-Engineering-Pipeline-PostgreSQL-Python-dbt"

st.set_page_config(page_title="E-commerce Analytics Pipeline", page_icon="📊", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


def as_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["t", "true", "1"])


orders = load("fct_orders")
orders["order_date"] = pd.to_datetime(orders["order_date"])
orders["is_revenue_order"] = as_bool(orders["is_revenue_order"])
customers = load("dim_customers")
products = load("dim_products")
rfm = load("customer_rfm")
ingestion = load("ingestion_summary")
rejects = load("rejected_report")

# ------------------------------------------------------------------ sidebar
st.sidebar.header("Filters")
all_countries = sorted(orders["country"].unique())
countries = st.sidebar.multiselect("Country", all_countries, default=all_countries)
min_d, max_d = orders["order_date"].min().date(), orders["order_date"].max().date()
date_range = st.sidebar.date_input("Order date", (min_d, max_d), min_value=min_d, max_value=max_d)
start, end = (date_range if len(date_range) == 2 else (min_d, max_d))

mask = (
    orders["country"].isin(countries)
    & (orders["order_date"].dt.date >= start)
    & (orders["order_date"].dt.date <= end)
)
filtered = orders[mask]
rev = filtered[filtered["is_revenue_order"]]

st.sidebar.caption("Revenue = completed + shipped orders. Refunded, cancelled and pending are excluded.")
st.sidebar.markdown(f"[Source code on GitHub]({REPO_URL})")

# ------------------------------------------------------------------ header
st.title("📊 E-commerce Analytics")
st.caption("PostgreSQL · Python validation · dbt Core · SQL window functions — synthetic data")

tab_overview, tab_customers, tab_quality, tab_about = st.tabs(
    ["Overview", "Customers", "Data quality", "About"]
)

# ------------------------------------------------------------------ overview
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", f"€{rev['order_total'].sum():,.0f}")
    c2.metric("Orders", f"{len(rev):,}")
    c3.metric("Avg order value", f"€{rev['order_total'].mean():,.2f}" if len(rev) else "–")
    c4.metric("Active customers", f"{rev['customer_id'].nunique():,}")

    if rev.empty:
        st.warning("No orders match the current filters.")
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("Monthly revenue")
            monthly = rev.set_index("order_date")["order_total"].resample("MS").sum()
            st.bar_chart(monthly)
        with right:
            st.subheader("Daily revenue and 7-day average")
            daily = rev.set_index("order_date")["order_total"].resample("D").sum().to_frame("revenue")
            daily["7-day avg"] = daily["revenue"].rolling(7, min_periods=1).mean()
            st.line_chart(daily)

        left, right = st.columns(2)
        with left:
            st.subheader("Revenue by country")
            st.bar_chart(rev.groupby("country")["order_total"].sum().sort_values(ascending=False))
        with right:
            st.subheader("Payment methods")
            pay = filtered["payment_method"].value_counts()
            st.bar_chart(pay)

        left, right = st.columns(2)
        with left:
            st.subheader("Order status mix")
            st.bar_chart(filtered["status"].value_counts())
        with right:
            st.subheader("Revenue by category (all countries)")
            st.bar_chart(products.groupby("category")["revenue"].sum().sort_values(ascending=False))

        st.subheader("Top products in each category (all countries)")
        top = (
            products[products["revenue_rank_in_category"] <= 3]
            .sort_values(["category", "revenue_rank_in_category"])
            [["category", "revenue_rank_in_category", "product_name", "units_sold", "revenue"]]
        )
        st.dataframe(top, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ customers
with tab_customers:
    cust = customers[customers["country"].isin(countries)]
    rfm_f = rfm[rfm["customer_id"].isin(cust["customer_id"])]

    st.subheader("RFM segments")
    seg = (
        rfm_f.groupby("segment")
        .agg(customers=("customer_id", "count"), avg_recency_days=("recency_days", "mean"),
             avg_orders=("frequency", "mean"), total_revenue=("monetary", "sum"))
        .round(1)
        .sort_values("total_revenue", ascending=False)
    )
    seg["pct_of_revenue"] = (100 * seg["total_revenue"] / seg["total_revenue"].sum()).round(1)
    l, r = st.columns([2, 3])
    l.dataframe(seg, use_container_width=True)
    r.bar_chart(seg["total_revenue"])

    st.subheader("Top 10 customers by lifetime revenue")
    st.dataframe(
        cust.sort_values("lifetime_revenue", ascending=False).head(10)
        [["customer_id", "full_name", "country", "lifetime_orders", "lifetime_revenue", "revenue_quartile"]],
        use_container_width=True, hide_index=True,
    )

# ------------------------------------------------------------------ data quality
with tab_quality:
    st.subheader("Ingestion reconciliation")
    st.caption("Every table satisfies: rows read = rows loaded + rows rejected.")
    st.dataframe(ingestion, use_container_width=True, hide_index=True)
    st.subheader("Why rows were rejected")
    st.dataframe(rejects, use_container_width=True, hide_index=True)
    st.info(
        "Rejected rows are quarantined in `raw.rejected_rows` with a reason and the original payload. "
        "Foreign keys are checked in dependency order, so orders of a rejected customer are rejected too."
    )

# ------------------------------------------------------------------ about
with tab_about:
    st.markdown(
        f"""
**Pipeline**

1. `generate_data.py` creates seeded synthetic CSVs with deliberately bad rows.
2. `ingest.py` validates them in pandas, loads clean rows into PostgreSQL with `COPY`, and quarantines the rest.
3. dbt Core builds `staging → intermediate → marts` and runs schema and business-rule tests.
4. `export_marts.py` snapshots the marts to CSV, which this dashboard reads.

Code and documentation: [{REPO_URL}]({REPO_URL})
"""
    )
