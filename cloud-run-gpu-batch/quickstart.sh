#!/bin/bash
# Quick Start Script for GPU Batch Execution System
# Run this after configuring terraform.tfvars

set -e

echo "🚀 GPU Batch Execution System - Quick Start"
echo "=========================================="

# Check prerequisites
echo ""
echo "Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not found. Please install Terraform first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.10+ first."
    exit 1
fi

echo "✅ All prerequisites installed"

# Check for terraform.tfvars
if [ ! -f "terraform.tfvars" ]; then
    echo ""
    echo "⚠️  terraform.tfvars not found"
    echo "Creating from example..."
    cp terraform.tfvars.example terraform.tfvars
    echo "❗ Please edit terraform.tfvars with your GCP project ID"
    echo "   Then run this script again"
    exit 1
fi

echo ""
echo "Step 1: Deploying infrastructure with Terraform..."
terraform init
terraform plan
read -p "Apply Terraform changes? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
    terraform apply -auto-approve
else
    echo "Terraform apply cancelled"
    exit 1
fi

echo ""
echo "Step 2: Installing Python dependencies..."
pip install google-auth google-auth-httplib2 requests google-cloud-storage

echo ""
echo "Step 3: Configuring Docker authentication..."
REGION=$(terraform output -raw region)
PROJECT_ID=$(terraform output -raw project_id)

echo "Authenticating Docker to Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

echo ""
echo "Step 4: Building and pushing Docker image..."
python build.py

echo ""
echo "=========================================="
echo "✅ SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "To trigger a job:"
echo "  python trigger_job.py"
echo ""
echo "To view results:"
echo "  gsutil ls gs://${PROJECT_ID}-gpu-job-outputs/"
echo ""
echo "To view logs:"
echo "  https://console.cloud.google.com/run/jobs"
echo ""
