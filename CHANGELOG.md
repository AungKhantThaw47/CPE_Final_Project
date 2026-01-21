# Changes Made for Single-Command Deployment

## Summary
Your Terraform configuration now automatically builds and pushes the Docker image using Google Cloud Build during `terraform apply`.

## Files Modified

### 1. `main.tf`
**Added:**
- New `null_resource.docker_image_build` resource that:
  - Triggers Cloud Build to build your Docker image
  - Monitors file changes (Dockerfile, main.py, requirements.txt)
  - Automatically rebuilds when any of these files change
  - Uses `gcloud builds submit` command
  - Pushes image to Artifact Registry

**Modified:**
- Added `null_resource.docker_image_build` to Cloud Run job dependencies
- Ensures image is built before deploying the job

### 2. `provider.tf`
**Added:**
- `null` provider (version ~> 3.0) to enable the null_resource

## How It Works

```
terraform apply
    ↓
1. Enable APIs (cloudbuild, artifactregistry, run, iam)
    ↓
2. Create Artifact Registry repository
    ↓
3. Trigger null_resource.docker_image_build
    ↓
4. Execute: gcloud builds submit cloud-run-gpu-batch/ \
      --tag=asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/gpu-job-runner:latest
    ↓
5. Cloud Build:
   - Reads Dockerfile
   - Builds image with CUDA, Python, PyTorch
   - Pushes to Artifact Registry
    ↓
6. Create Cloud Storage bucket
    ↓
7. Create service accounts & IAM bindings
    ↓
8. Deploy Cloud Run GPU Job using the built image
    ↓
✅ Done!
```

## Key Features

### Automatic Rebuild Triggers
The build triggers automatically when:
- `cloud-run-gpu-batch/gpu-job/Dockerfile` changes
- `cloud-run-gpu-batch/gpu-job/main.py` changes
- `cloud-run-gpu-batch/gpu-job/requirements.txt` changes
- `image_tag` variable changes

### Force Rebuild
To force a rebuild without file changes:
```bash
terraform apply -var="image_tag=v2"
```

Or update the variable in `terraform.tfvars`:
```hcl
image_tag = "v2"
```

## Benefits

### Before (Manual Process):
```bash
# Step 1: Deploy infrastructure
terraform apply

# Step 2: Manually build image
cd cloud-run-gpu-batch
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
python build.py

# Step 3: Wait for build
# Step 4: Update job or redeploy
```

### After (Automated):
```bash
# Everything in one command!
terraform apply
```

## No Breaking Changes

- All existing functionality preserved
- Previous manual build methods still work
- Can still use `cloud-run-gpu-batch/build.py` if needed
- Cloud Run job still has `ignore_changes` for manual image updates

## Platform Support

Works on:
- ✅ Windows (PowerShell/CMD)
- ✅ Linux (bash)
- ✅ macOS (zsh/bash)
- ✅ WSL (Windows Subsystem for Linux)

Uses `${path.module}` for cross-platform compatibility.

## Requirements

Ensure you have:
1. `gcloud` CLI installed and authenticated
2. Cloud Build API enabled (done automatically by terraform)
3. Proper IAM permissions:
   - Cloud Build Editor
   - Artifact Registry Writer
   - Storage Admin (for Cloud Build logs)

## Testing

Test the setup:
```bash
# Initialize
terraform init

# Plan (shows what will be created)
terraform plan

# Apply (builds and deploys)
terraform apply
```

Watch Cloud Build progress in GCP Console:
https://console.cloud.google.com/cloud-build/builds

## Troubleshooting

### "gcloud not found"
Install Google Cloud SDK:
https://cloud.google.com/sdk/docs/install

### Authentication errors
```bash
gcloud auth application-default login
gcloud config set project cpe-final-project
```

### Build fails
Check Cloud Build logs:
```bash
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
```

Or view in console:
https://console.cloud.google.com/cloud-build/builds
