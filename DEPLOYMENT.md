# Single-Command Deployment Guide

This Terraform configuration now automatically builds and deploys your Docker image using Cloud Build.

## Prerequisites

1. **Google Cloud SDK** installed and authenticated:
   ```bash
   gcloud auth application-default login
   ```

2. **Terraform** installed (version >= 1.0)

3. **Required GCP permissions**:
   - Cloud Build Editor
   - Artifact Registry Administrator
   - Cloud Run Admin
   - Service Account Admin
   - Storage Admin

## Single-Command Deployment

Simply run:

```bash
terraform apply
```

This will:
1. Enable all required Google Cloud APIs
2. Create Artifact Registry repository
3. **Build your Docker image using Cloud Build**
4. **Push the image to Artifact Registry**
5. Create Cloud Storage bucket for outputs
6. Create service accounts with proper IAM permissions
7. Deploy the Cloud Run GPU job

## What Happens During Build

The Terraform configuration includes a `null_resource` that:
- Automatically triggers Cloud Build when:
  - Dockerfile changes
  - main.py changes
  - requirements.txt changes
  - image_tag variable changes
- Uses `gcloud builds submit` to build and push the image
- Waits for the build to complete before deploying the Cloud Run job

## Updating the Image

If you modify any of the following files:
- `cloud-run-gpu-batch/gpu-job/Dockerfile`
- `cloud-run-gpu-batch/gpu-job/main.py`
- `cloud-run-gpu-batch/gpu-job/requirements.txt`

Just run `terraform apply` again, and it will automatically rebuild and redeploy.

## Force Rebuild

To force a rebuild without changing files, update the `image_tag` variable:

```bash
terraform apply -var="image_tag=v2"
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## Troubleshooting

### Build Fails
- Check Cloud Build logs in GCP Console
- Verify `cloudbuild.googleapis.com` API is enabled
- Ensure you have Cloud Build permissions

### Authentication Issues
```bash
gcloud auth application-default login
gcloud config set project cpe-final-project
```

### Windows Path Issues
The configuration uses `${path.module}` which works cross-platform. If you encounter issues, ensure you're running from the project root directory.

## Variables

You can customize deployment with variables:

```bash
terraform apply \
  -var="project_id=your-project-id" \
  -var="region=us-central1" \
  -var="image_tag=v1.0.0"
```

Or create a `terraform.tfvars` file:

```hcl
project_id = "your-project-id"
region     = "us-central1"
image_tag  = "v1.0.0"
```
