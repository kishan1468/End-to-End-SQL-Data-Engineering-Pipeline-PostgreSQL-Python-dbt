FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV DBT_PROFILES_DIR=/app/dbt_project

CMD ["bash", "-c", "python src/generate_data.py && python src/ingest.py && cd dbt_project && dbt build"]
