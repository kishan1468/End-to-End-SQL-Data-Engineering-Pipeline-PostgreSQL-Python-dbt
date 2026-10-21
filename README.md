# End-to-End SQL Data Engineering Pipeline (PostgreSQL · Python · dbt)

**🔴 Live dashboard:** [kishan-ecommerce-pipeline.streamlit.app](https://kishan-ecommerce-pipeline.streamlit.app/)

A small but complete ELT pipeline for a synthetic e-commerce business: raw CSV files are **validated in Python**, loaded into **PostgreSQL**, transformed with **dbt Core** into a tested star-schema-style warehouse, and analysed with **advanced SQL** (CTEs, window functions, cohort and RFM analysis). Everything runs locally with Docker.

## Architecture

```
 generate_data.py          ingest.py                    dbt Core                      SQL analysis
┌────────────────┐   ┌─────────────────────┐   ┌───────────────────────────┐   ┌──────────────────────┐
│ synthetic CSVs │──▶│ validate (pandas)   │──▶│ staging  (views)          │──▶│ sql/analysis/*.sql   │
│ + injected bad │   │ load valid rows     │   │ intermediate (views)      │   │ cohorts, RFM, MoM,   │
│ rows           │   │ via COPY            │   │ marts (tables)            │   │ Pareto, rankings     │
└────────────────┘   │ quarantine rejects  │   │ + schema & custom tests   │   └──────────────────────┘
                     └─────────┬───────────┘   └───────────────────────────┘
                               ▼
                        PostgreSQL 16
              raw.*  ·  raw.rejected_rows  ·  staging.* · intermediate.* · marts.*
```

## Data model

| Layer | Objects |
|---|---|
| `raw` | `customers`, `products`, `orders`, `order_items`, `payments` (PK/FK/CHECK constraints), `rejected_rows` (quarantine with reason + JSON payload) |
| `staging` | `stg_customers`, `stg_products`, `stg_orders`, `stg_order_items`, `stg_payments` – renaming, casing, derived `line_total`, `is_revenue_order` |
| `intermediate` | `int_order_totals` – items, units and total per order |
| `marts` | `fct_orders`, `dim_customers` (lifetime value, revenue quartile), `dim_products` (rank within category), `fct_daily_revenue` (7-day moving average, running total), `customer_rfm` (RFM scores + segment) |

## Data quality – two layers

**1. Ingestion validation (`src/ingest.py`)** – required fields, integer/decimal/date parsing, future dates, e-mail format, duplicate primary keys, accepted status values, non-positive quantities and **foreign-key integrity checked in dependency order** (so an order whose customer was rejected is rejected too, and so are its items and payments). Rejected rows go to `raw.rejected_rows` and `data/rejected_report.csv`, and the run asserts `read = loaded + rejected` for every table.

The generator injects ~400 bad rows on purpose. With the default seed the validator produces:

| table | read | loaded | rejected |
|---|---:|---:|---:|
| customers | 2,005 | 1,980 | 25 |
| products | 120 | 120 | 0 |
| orders | 8,025 | 7,909 | 116 |
| order_items | 24,104 | 23,811 | 293 |
| payments | 6,959 | 6,874 | 85 |

**2. dbt tests (`dbt build`)** – `unique`, `not_null`, `relationships`, `accepted_values` on every model, plus three business-rule tests in `dbt_project/tests/`:

- every completed/shipped/refunded order has a payment equal to its item total
- no order is placed before the customer signed up
- cancelled/pending orders never carry a payment

## Quick start (Docker)

```bash
git clone <your-repo-url> && cd sql-data-engineering-pipeline
docker compose up --build          # starts Postgres, generates data, ingests, runs dbt build
```

Then explore the results:

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d warehouse \
  -f sql/analysis/01_top_customers_by_country.sql
```

## Quick start (local Python)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db                      # or point PG* env vars at your own Postgres
python src/generate_data.py --customers 2000 --orders 8000 --seed 42
python src/ingest.py
export DBT_PROFILES_DIR=$PWD/dbt_project
cd dbt_project && dbt build
```

Connection settings come from the standard `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` variables (defaults: `localhost:5432`, `postgres/postgres`, database `warehouse`).

## Live dashboard (Streamlit)

`streamlit_app/` contains a dashboard (KPIs, monthly/daily revenue, country, category, RFM segments, data-quality tab) that reads CSV snapshots of the dbt marts, so it needs no database when deployed.

```bash
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Refresh the snapshot after re-running the pipeline: `python src/export_marts.py`.

**Deploy on Streamlit Community Cloud:** push the repo to GitHub, open [share.streamlit.io](https://share.streamlit.io), click *Create app*, pick the repo and branch, set the main file path to `streamlit_app/app.py`, and deploy. Then add the public URL to the top of this README.

## Analytical queries (`sql/analysis/`)

| File | Question | Techniques |
|---|---|---|
| `01_top_customers_by_country.sql` | Top 3 customers by revenue per country | CTE, `DENSE_RANK() OVER (PARTITION BY …)` |
| `02_monthly_revenue_growth.sql` | MoM and YoY revenue growth | `DATE_TRUNC`, `LAG()` with named window |
| `03_cohort_retention.sql` | Share of each signup cohort still ordering N months later | multi-CTE, date arithmetic |
| `04_category_pareto.sql` | Which products make up 80 % of category revenue | running `SUM() OVER`, share of partition |
| `05_rfm_segment_summary.sql` | Size and revenue share of RFM segments | aggregate over mart, `SUM(SUM()) OVER ()` |
| `06_payment_method_mix.sql` | Payment mix and AOV per country | window share per partition |

## Project layout

```
├── src/                 generate_data.py, ingest.py, export_marts.py
├── streamlit_app/       app.py, requirements.txt, data/ (mart snapshots)
├── sql/                 00_schema.sql (raw DDL) · analysis/*.sql
├── dbt_project/         models/{staging,intermediate,marts}, tests/, macros/, profiles.yml
├── Dockerfile · docker-compose.yml · Makefile · requirements.txt
```

## Design decisions

- **Validate before load, quarantine instead of drop** – bad data is never silently lost and every rejection has a reason that can be audited.
- **Constraints in the raw layer too** – PK/FK/CHECK in Postgres act as a second line of defence behind the Python rules.
- **Staging → intermediate → marts** – the standard dbt layering keeps each model small and testable.
- **Custom `generate_schema_name` macro** – models land in `staging` / `marts` rather than `analytics_staging`.
- **Reproducible** – the generator is seeded, so results are deterministic.

## Possible extensions

Incremental dbt models, `dbt docs generate` lineage screenshots, an Airflow DAG orchestrating the three stages, GitHub Actions CI running `dbt build` against a Postgres service container, and a BI dashboard on top of the marts.
