FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install MLflow and dependencies
RUN pip install --no-cache-dir \
    mlflow==3.8.1 \
    psycopg2-binary \
    google-cloud-storage

# Expose port
EXPOSE 8080

# Set environment
ENV PORT=8080

# Run MLflow server with uvicorn (default)
CMD mlflow server \
    --host 0.0.0.0 \
    --port $PORT \
    --backend-store-uri $BACKEND_STORE_URI \
    --default-artifact-root $ARTIFACT_ROOT \
    --serve-artifacts \
    --allowed-hosts "*"
