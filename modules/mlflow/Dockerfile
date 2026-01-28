FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install MLflow and dependencies
RUN pip install --no-cache-dir \
    mlflow==3.8.1 \
    psycopg2-binary \
    google-cloud-storage \
    boto3

# Cloud Run sets PORT environment variable
ENV PORT=8080

# Start MLflow server with disabled security middleware for Cloud Run
CMD mlflow server \
    --host 0.0.0.0 \
    --port ${PORT} \
    --backend-store-uri ${BACKEND_STORE_URI} \
    --default-artifact-root ${ARTIFACT_ROOT} \
    --disable-security-middleware
