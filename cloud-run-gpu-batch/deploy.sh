#!/bin/bash
# Deployment script for GPU Batch Execution System
# Run from project root directory

set -e

echo "🚀 GPU Batch Execution System - Deployment"
echo "=========================================="

# Change to project root if running from cloud-run-gpu-batch
if [ "$(basename $PWD)" = "cloud-run-gpu-batch" ]; then
    cd ..
fi

# Step 1: Deploy base infrastructure (without Cloud Run Job)
echo ""
echo "Step 1: Deploying base infrastructure..."
echo "  - APIs"
echo "  - Artifact Registry"
echo "  - Service Accounts"
echo "  - GCS Bucket"
echo ""

terraform apply \
  -target=google_project_service.run_api \
  -target=google_project_service.artifact_registry_api \
  -target=google_project_service.iam_api \
  -target=google_artifact_registry_repository.docker_repo \
  -target=google_service_account.cloud_run_job_sa \
  -target=google_service_account.job_invoker_sa \
  -target=google_storage_bucket.job_outputs \
  -target=google_storage_bucket_iam_member.job_sa_storage_admin \
  -target=google_project_iam_member.job_sa_log_writer \
  -target=google_project_iam_member.invoker_sa_run_developer \
  -auto-approve

echo ""
echo "✅ Base infrastructure deployed"

# Step 2: Configure Docker authentication
echo ""
echo "Step 2: Configuring Docker authentication..."
REGION=$(terraform output -raw region)
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo "✅ Docker authenticated"

# Step 3: Build and push Docker image
echo ""
echo "Step 3: Building and pushing Docker image..."
cd cloud-run-gpu-batch
python3 build.py
cd ..

echo "✅ Image built and pushed"

# Step 4: Deploy Cloud Run Job
echo ""
echo "Step 4: Deploying Cloud Run Job..."
terraform apply -auto-approve

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Trigger job: cd cloud-run-gpu-batch && python3 trigger_job.py"
echo "  2. View logs: https://console.cloud.google.com/run/jobs"
echo "  3. View results: gsutil ls gs://$(terraform output -raw gcs_bucket_name)/"
echo ""
