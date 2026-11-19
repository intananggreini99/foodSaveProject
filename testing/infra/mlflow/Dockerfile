# Server MLflow: tracking (database "mlflow" di PostgreSQL) + Model Registry + artefak.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1
RUN pip install --no-cache-dir "mlflow==3.18.0" "psycopg[binary]==3.3.8"
RUN useradd --system --create-home mlflow && mkdir -p /mlflow/artifacts \
    && chown -R mlflow /mlflow
USER mlflow
EXPOSE 5000
