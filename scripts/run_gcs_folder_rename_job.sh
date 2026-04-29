#!/usr/bin/env bash

set -euo pipefail

JOB_NAME="${JOB_NAME:-gcs-folder-rename-job}"
REGION="${REGION:-asia-southeast1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
BUCKET="${GCS_BUCKET:-cpe-final-project-pipeline-data}"
SOURCE_PREFIX="${SOURCE_PREFIX:-}"
DESTINATION_PREFIX="${DESTINATION_PREFIX:-}"
APPLY="${APPLY:-false}"
OVERWRITE="${OVERWRITE:-false}"
TASKS="${TASKS:-8}"
TASK_TIMEOUT="${TASK_TIMEOUT:-3600s}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID is required. Set PROJECT_ID or configure gcloud."
  exit 1
fi

if [[ -z "$SOURCE_PREFIX" || -z "$DESTINATION_PREFIX" ]]; then
  echo "SOURCE_PREFIX and DESTINATION_PREFIX are required."
  echo "Example: SOURCE_PREFIX=pending_review/old-hash/ DESTINATION_PREFIX=pending_review/new-hash/"
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Missing required tool: gcloud"
  exit 1
fi

echo "============================================================"
echo "Cloud Run folder rename job"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Job: $JOB_NAME"
echo "Bucket: gs://$BUCKET"
echo "Source: $SOURCE_PREFIX"
echo "Destination: $DESTINATION_PREFIX"
echo "Mode: $APPLY"
echo "Overwrite destination objects: $OVERWRITE"
echo "Tasks: $TASKS"
echo "Task timeout: $TASK_TIMEOUT"
echo "============================================================"

gcloud run jobs execute "$JOB_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --tasks "$TASKS" \
  --task-timeout "$TASK_TIMEOUT" \
  --update-env-vars "GCS_BUCKET=$BUCKET,SOURCE_PREFIX=$SOURCE_PREFIX,DESTINATION_PREFIX=$DESTINATION_PREFIX,APPLY=$APPLY,OVERWRITE=$OVERWRITE" \
  --wait
