# GPU Batch Execution System on Google Cloud

Production-ready GPU batch execution using Cloud Run Jobs (NO CLI, NO manual console steps).

## Architecture

- **Compute**: Cloud Run Jobs v2 with NVIDIA L4 GPU
- **Storage**: Google Cloud Storage (job outputs)
- **Container**: Docker image in Artifact Registry
- **Infrastructure**: 100% Terraform-managed
- **Execution**: Python REST API triggers

## Key Features

✅ GPU auto-stops after job completion (NO idle billing)  
✅ NO gcloud CLI required  
✅ NO manual console steps  
✅ NO long-running services  
✅ Python-only execution  
✅ Fully reproducible via Terraform  

---

## Project Structure

```
.
├── main.tf                    # Terraform infrastructure
├── variables.tf               # Terraform variables
├── outputs.tf                 # Terraform outputs
├── provider.tf                # Terraform provider config
├── terraform.tfvars.example   # Example configuration
│
├── Dockerfile                 # GPU-ready container
├── job_requirements.txt       # Python deps for container
├── job/
│   └── main.py               # GPU job script (runs in container)
│
├── trigger_job.py            # Job execution trigger (REST API)
├── build.py                  # Docker build & push script
│
└── README.md                 # This file
```

---

## Prerequisites

1. **GCP Project** with billing enabled
2. **Docker** installed locally
3. **Terraform** >= 1.0
4. **Python** >= 3.10
5. **Authentication**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

---

## Setup & Deployment

### Step 1: Configure Terraform

Create `terraform.tfvars`:

```hcl
project_id = "your-gcp-project-id"
region     = "asia-southeast1"  # Must support GPUs
```

### Step 2: Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

This creates:
- Cloud Run Job with GPU (NVIDIA L4)
- Artifact Registry repository
- GCS bucket for outputs
- Service accounts with minimal permissions
- Required IAM bindings

### Step 3: Authenticate Docker to Artifact Registry

```bash
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
```

Or manually:
```bash
docker login -u oauth2accesstoken \
  -p "$(gcloud auth print-access-token)" \
  asia-southeast1-docker.pkg.dev
```

### Step 4: Build and Push Docker Image

```bash
python build.py
```

This:
1. Builds GPU-ready Docker image
2. Pushes to Artifact Registry
3. Updates Cloud Run Job

### Step 5: Execute Job

```bash
python trigger_job.py
```

This:
1. Authenticates via OAuth2
2. Triggers Cloud Run Job via REST API
3. Returns execution metadata
4. Job runs with GPU and auto-stops

---

## How It Works

### 1. Infrastructure (Terraform)

- Creates Cloud Run Job with GPU configuration
- Job is configured with `nvidia-l4` GPU accelerator
- Container gets 4 vCPU, 16GB RAM, 1 GPU
- Service account has permissions for GCS and logging
- NO compute instances created (serverless)

### 2. Container (Docker)

- Based on `nvidia/cuda:12.2.0-runtime-ubuntu22.04`
- Includes Python 3.11 and CUDA toolkit
- PyTorch with CUDA 12.1 support
- Google Cloud Storage client
- Runs `job/main.py` as entrypoint

### 3. Job Execution (job/main.py)

1. Detects GPU availability
2. Prints GPU name and specs
3. Executes matrix multiplication on GPU
4. Saves results to GCS bucket
5. Exits naturally → GPU stops billing

### 4. Job Triggering (trigger_job.py)

- Uses Google Cloud REST API (v2)
- OAuth2 authentication with `google-auth`
- POST to `/v2/projects/{project}/locations/{region}/jobs/{job}:run`
- NO gcloud CLI required
- Returns execution metadata

---

## Monitoring & Results

### View Logs

**Option 1: Cloud Console**
```
https://console.cloud.google.com/run/jobs
```

**Option 2: Python Script** (optional - create `view_logs.py`):
```python
from google.cloud import logging
client = logging.Client()
logger = client.logger("run.googleapis.com/stdout")
for entry in logger.list_entries():
    print(entry.payload)
```

### View Results

Results are saved to GCS:
```
gs://YOUR_PROJECT_ID-gpu-job-outputs/gpu-batch-job/results_TIMESTAMP.json
```

Download:
```bash
gsutil ls gs://YOUR_PROJECT_ID-gpu-job-outputs/gpu-batch-job/
gsutil cp gs://YOUR_PROJECT_ID-gpu-job-outputs/gpu-batch-job/results_*.json .
```

Or via Python:
```python
from google.cloud import storage
client = storage.Client()
bucket = client.bucket("YOUR_PROJECT_ID-gpu-job-outputs")
blob = bucket.blob("gpu-batch-job/results_TIMESTAMP.json")
print(blob.download_as_text())
```

---

## Cost Control

### GPU Billing

- GPU charges **ONLY during job execution**
- Job timeout: 15 minutes maximum
- NO retries (max_retries = 0)
- Job exits → GPU stops → billing stops

### Estimated Costs (asia-southeast1)

- NVIDIA L4 GPU: ~$0.77/hour
- Cloud Run CPU/Memory: ~$0.10/hour
- **Example**: 5-minute job = ~$0.07

### Cost Optimization

1. Use smallest GPU that meets requirements (T4 < L4)
2. Set appropriate timeout
3. Disable retries for one-time jobs
4. Use GCS lifecycle rules to delete old outputs

---

## Validation Checklist

✅ GPU auto-stops after job completion  
✅ NO gcloud CLI required at any step  
✅ Terraform handles infrastructure only  
✅ Python handles execution only  
✅ Results retrievable via GCS  
✅ Logs available in Cloud Logging  
✅ System is production-safe  

---

## Troubleshooting

### Error: "Quota exceeded for GPU"

Request quota increase:
```
https://console.cloud.google.com/iam-admin/quotas
```

Filter: `Cloud Run` → `GPUs per region`

### Error: "Permission denied"

Verify service account IAM:
```bash
terraform state show google_service_account.cloud_run_job_sa
terraform state show google_cloud_run_v2_job_iam_member.invoker_can_run
```

### Error: "Image not found"

Rebuild and push:
```bash
python build.py
terraform apply
```

### Job fails silently

Check logs:
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=gpu-batch-job" --limit 50
```

---

## Advanced Usage

### Custom GPU Computation

Edit `job/main.py`:
```python
def run_gpu_computation():
    # Your custom GPU code here
    model = YourModel().cuda()
    result = model(data)
    return result
```

### Scheduled Execution

Add to `main.tf`:
```hcl
resource "google_cloud_scheduler_job" "trigger_gpu_job" {
  name     = "trigger-gpu-job-daily"
  schedule = "0 2 * * *"  # 2 AM daily
  
  http_target {
    uri         = google_cloud_run_v2_job.gpu_batch_job.uri
    http_method = "POST"
    
    oauth_token {
      service_account_email = google_service_account.job_invoker_sa.email
    }
  }
}
```

### Multiple Jobs

Copy job directory and modify Terraform:
```hcl
module "job_1" {
  source   = "./modules/gpu-job"
  job_name = "job-1"
}

module "job_2" {
  source   = "./modules/gpu-job"
  job_name = "job-2"
}
```

---

## Security Best Practices

1. **Service Account Permissions**: Minimal IAM roles only
2. **Secrets Management**: Use Secret Manager for API keys
3. **Network Security**: Private GCS buckets only
4. **Audit Logging**: Enabled automatically
5. **No Public Access**: Jobs require authentication

---

## Cleanup

Remove all resources:
```bash
terraform destroy
```

This deletes:
- Cloud Run Job
- Artifact Registry repository
- GCS bucket (if empty)
- Service accounts
- IAM bindings

**Note**: Docker images in Artifact Registry are deleted automatically.

---

## References

- [Cloud Run Jobs Documentation](https://cloud.google.com/run/docs/create-jobs)
- [GPU Support on Cloud Run](https://cloud.google.com/run/docs/configuring/services/gpu)
- [Cloud Run API Reference](https://cloud.google.com/run/docs/reference/rest/v2)
- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

---

## License

MIT
