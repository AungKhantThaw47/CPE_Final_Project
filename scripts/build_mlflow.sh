#!/bin/bash
set -e

REGION=$1
PROJECT_ID=$2
IMAGE_NAME="mlflow-server"
IMAGE_TAG="latest"

IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/gpu-jobs/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Building MLflow image: ${IMAGE_PATH}"

gcloud builds submit modules/mlflow \
    --tag="${IMAGE_PATH}" \
    --project="${PROJECT_ID}" \
    --timeout=10m

echo "MLflow image built successfully: ${IMAGE_PATH}"
