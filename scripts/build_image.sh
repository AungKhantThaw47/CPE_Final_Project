#!/bin/bash
# Bash script to build and push Docker image using Cloud Build

set -e

# Parse arguments
REGION=""
PROJECT_ID=""
REPOSITORY_ID=""
IMAGE_NAME=""
IMAGE_TAG=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --repository-id)
      REPOSITORY_ID="$2"
      shift 2
      ;;
    --image-name)
      IMAGE_NAME="$2"
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Building and pushing image: ${IMAGE_PATH}"

gcloud builds submit cloud-run-gpu-batch/gpu-job \
    --tag="${IMAGE_PATH}" \
    --project="${PROJECT_ID}" \
    --timeout=20m

if [ $? -ne 0 ]; then
    echo "Build failed with exit code $?"
    exit $?
fi

echo "Build completed successfully!"
