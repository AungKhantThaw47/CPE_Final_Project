#!/bin/bash
# Build and push the Docker image for the scheduled job

set -e

PROJECT_ID="$1"
IMAGE_NAME="$2"
REGION="${3:-asia-southeast1}"

if [ -z "$PROJECT_ID" ] || [ -z "$IMAGE_NAME" ]; then
    echo "Usage: $0 <project_id> <image_name> [region]"
    exit 1
fi

IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/gpu-jobs/${IMAGE_NAME}:latest"

echo "Building Docker image..."
cd function
docker build -t "$IMAGE_TAG" .

echo "Pushing image to Artifact Registry..."
docker push "$IMAGE_TAG"

echo "Image pushed successfully: $IMAGE_TAG"
