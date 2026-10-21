.PHONY: up generate ingest dbt export app analysis all down

export DBT_PROFILES_DIR := $(CURDIR)/dbt_project

up:            ## start PostgreSQL in Docker
	docker compose up -d db

generate:      ## create synthetic CSV data
	python src/generate_data.py

ingest:        ## validate + load into PostgreSQL (raw schema)
	python src/ingest.py

dbt:           ## build models and run all tests
	cd dbt_project && dbt build

export:        ## snapshot marts to CSV for the dashboard
	python src/export_marts.py

app:           ## run the Streamlit dashboard
	streamlit run streamlit_app/app.py

analysis:      ## run an analytical query, e.g. make analysis Q=01_top_customers_by_country
	PGPASSWORD=postgres psql -h localhost -U postgres -d warehouse -f sql/analysis/$(Q).sql

all: up generate ingest dbt

down:
	docker compose down -v
