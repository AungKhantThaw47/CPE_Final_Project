# 🚀 Terraform Single-Command Deployment - Quick Reference

## The Magic Command

```bash
terraform apply
```

That's it! This builds your Docker image and deploys everything.

---

## First Time Setup (One-time)

```bash
# 1. Authenticate
gcloud auth application-default login

# 2. Set your project
gcloud config set project cpe-final-project

# 3. Initialize Terraform
terraform init

# 4. Deploy everything (including Docker build)
terraform apply
```

---

## Daily Workflow

### Update Code and Redeploy
```bash
# Edit your files:
# - cloud-run-gpu-batch/gpu-job/main.py
# - cloud-run-gpu-batch/gpu-job/Dockerfile
# - cloud-run-gpu-batch/gpu-job/requirements.txt

# Then just run:
terraform apply
```

It automatically detects changes and rebuilds!

### Force Rebuild
```bash
terraform apply -var="image_tag=v2"
```

### View What Changed
```bash
terraform plan
```

### Destroy Everything
```bash
terraform destroy
```

---

## What Happens During `terraform apply`

```
[1/8] Enabling Google Cloud APIs...           ✓
[2/8] Creating Artifact Registry...            ✓
[3/8] Building Docker image (Cloud Build)...   ✓  ← NEW!
[4/8] Pushing image to registry...             ✓  ← NEW!
[5/8] Creating GCS bucket...                   ✓
[6/8] Creating service accounts...             ✓
[7/8] Setting up IAM permissions...            ✓
[8/8] Deploying Cloud Run GPU job...           ✓
```

---

## Monitoring Build Progress

### View in Console
https://console.cloud.google.com/cloud-build/builds

### View in Terminal
```bash
gcloud builds list --limit=5
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")
```

---

## Troubleshooting

### Build Failed?
```bash
# Check latest build logs
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")
```

### Not Authenticated?
```bash
gcloud auth application-default login
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
```

### Wrong Project?
```bash
gcloud config set project cpe-final-project
```

### Need to Clean Up?
```bash
terraform destroy -auto-approve
```

---

## Variables You Can Customize

Create `terraform.tfvars`:
```hcl
project_id = "your-project-id"
region     = "us-central1"
image_tag  = "v1.0.0"
job_name   = "my-gpu-job"
gpu_type   = "nvidia-l4"
```

Or pass inline:
```bash
terraform apply -var="project_id=my-project" -var="image_tag=v2.0"
```

---

## Pro Tips

### 1. Auto-approve (skip confirmation)
```bash
terraform apply -auto-approve
```

### 2. Specific resource targeting
```bash
terraform apply -target=null_resource.docker_image_build
```

### 3. View outputs
```bash
terraform output
```

### 4. Check current state
```bash
terraform show
```

### 5. Format your .tf files
```bash
terraform fmt
```

---

## File Structure (What Gets Built)

```
cloud-run-gpu-batch/
├── gpu-job/
│   ├── Dockerfile         ← Monitored for changes
│   ├── main.py           ← Monitored for changes
│   └── requirements.txt  ← Monitored for changes
```

When any of these files change, the next `terraform apply` will rebuild the image automatically!

---

## Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| Artifact Registry | `gpu-jobs` | Stores Docker images |
| Docker Image | `gpu-job-runner:latest` | GPU workload container |
| Cloud Run Job | `gpu-batch-job` | GPU computation |
| Storage Bucket | `{project}-gpu-job-outputs` | Job results |
| Service Account | `gpu-job-runner` | Job execution |
| Service Account | `gpu-job-runner-invoker` | Job triggering |

---

## Cost Optimization

- 💰 GPU only runs when job is active
- 💰 Auto-stops after completion
- 💰 Cloud Build: First 120 build-minutes/day are free
- 💰 No idle compute costs

---

## Support

📖 Documentation: `DEPLOYMENT.md`
📝 Changes: `CHANGELOG.md`
📦 Project Structure: `README.md`
