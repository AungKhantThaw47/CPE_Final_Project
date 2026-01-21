# Cloud Run GPU Batch System - Quick Reference

## Directory Structure

This folder contains the GPU batch execution system.

**Parent directory** contains Terraform infrastructure files.

## Usage

### From cloud-run-gpu-batch/ folder:

```bash
# Build and push Docker image
python build.py

# Trigger a job
python trigger_job.py

# Full deployment (run from parent directory)
cd ..
./cloud-run-gpu-batch/deploy.sh
```

### From project root:

```bash
# Deploy infrastructure
terraform init
terraform apply

# Build image
cd cloud-run-gpu-batch
python build.py

# Trigger job
python trigger_job.py
```

## Scripts

- **build.py** - Builds Docker image and pushes to Artifact Registry
- **trigger_job.py** - Triggers Cloud Run Job via REST API
- **deploy.sh** - Full deployment automation
- **quickstart.sh** - Interactive setup guide

## GPU Job

The `gpu-job/` folder contains the containerized workload:
- `Dockerfile` - NVIDIA CUDA container
- `requirements.txt` - PyTorch + dependencies
- `main.py` - GPU computation script

See [gpu-job/README.md](gpu-job/README.md) for customization.

## Documentation

- **README.md** - Main documentation
- **instructions.md** - Original requirements
- **STRUCTURE.md** - Architecture details
- **FILES.md** - File descriptions

## Common Commands

```bash
# View logs
gcloud logging read "resource.type=cloud_run_job" --limit=50

# List GCS outputs
gsutil ls gs://cpe-final-project-gpu-job-outputs/

# Download results
gsutil cp gs://cpe-final-project-gpu-job-outputs/gpu-batch-job/results_*.json .
```

## Terraform Integration

Scripts automatically read from parent directory's Terraform outputs:
- Project ID
- Region
- Job name
- Docker repository
- GCS bucket

No manual configuration needed after `terraform apply`.
