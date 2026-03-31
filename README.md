# CPE Final Project - Cloud Infrastructure & Data Pipeline

Terraform-managed GCP infrastructure for GPU batch processing, MLflow tracking, and web scraping with automated scheduling.

> **Note**: Hash preservation system with smart rebuild detection - only builds when code changes!

## Project Overview

This project provides a complete cloud infrastructure setup with:
- **GPU Batch Jobs**: CUDA-accelerated processing on Cloud Run with NVIDIA L4 GPUs
- **MLflow Tracking Server**: Experiment tracking and model registry
- **Web Crawler**: Automated DVB Burmese news scraper with GCS storage
- **Scheduled Jobs**: Automated data processing pipelines

## Quick Start (Simplified Deployment)

Just run Terraform directly - **all hash values are auto-computed**:

```powershell
# Windows
terraform init
terraform plan
terraform apply
```

```bash
# Linux/Mac  
terraform init
terraform plan
terraform apply
```

**What happens automatically:**
- ✅ **Content hash** computed from each codebase directory
- ✅ **Username** detected for deployment tracking
- ✅ **Hash comparison** - only deploys if code changed
- ✅ **No wrapper scripts needed**

**Documentation:**
- 📘 [CONTENT_HASH_AUTOMATED.md](CONTENT_HASH_AUTOMATED.md) - How content hashing works
- 📘 [DEPLOYMENT_SIMPLIFIED.md](DEPLOYMENT_SIMPLIFIED.md) - Deployment details
- 📘 [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) - What changed

**Helper scripts** in `scripts/` are now optional utilities.

## Project Structure

```
CPE_Final_Project/
│
├── Infrastructure (Root)
│   ├── main.tf                    # Main infrastructure configuration
│   ├── variables.tf               # Configurable variables
│   ├── outputs.tf                 # Infrastructure outputs
│   ├── provider.tf                # GCP provider configuration
│   ├── terraform.tfvars.example   # Configuration template
│   └── shell.nix                  # Nix development environment
│
├── .github/                       # GitHub Actions CI/CD
│   ├── workflows/
│   │   └── terraform-deploy.yml   # Automated deployment workflow
│   └── GITHUB_ACTIONS_SETUP.md    # CI/CD setup guide
│
├── utils/                         # Shared utilities
│   ├── gcs_utils.py               # Python GCS utilities
│   ├── gcs_utils.js               # JavaScript GCS utilities
│   └── README.md                  # Utils documentation
│
├── Codebase_Container/            # Application code
│   ├── mlflow/                    # MLflow service container assets
│   │   ├── Dockerfile             # MLflow container
│   │   └── cloudbuild.yaml        # Cloud Build configuration
│   │
│   ├── crawler_job/               # DVB Burmese news crawler
│   │   ├── DVB_Burmese.crawler.js # Web scraper implementation
│   │   ├── package.json           # Node.js dependencies
│   │   ├── Dockerfile             # Container definition
│   │   └── cloudbuild.yaml        # Cloud Build configuration
│   │
│   ├── cloud_scheduler_function/  # Scheduled data processor
│   │   ├── main.py                # Processor logic
│   │   ├── Dockerfile             # Container definition
│   │   └── cloudbuild.yaml        # Cloud Build configuration
│   │
│   └── gpu_batch_job/             # GPU-accelerated processing
│       ├── main.py                # GPU workload
│       ├── Dockerfile             # CUDA container
│       └── cloudbuild.yaml        # Cloud Build configuration
│
└── modules/                       # Terraform modules
    ├── cloud-scheduler/           # Cloud Run Job + Scheduler module
    │   ├── main.tf                # Job and scheduler resources
    │   ├── variables.tf           # Module inputs
    │   └── outputs.tf             # Module outputs
    │
    ├── cloud-run-service/         # Cloud Run Service module
    │   ├── main.tf                # Service resources
    │   ├── variables.tf           # Module inputs
    │   └── outputs.tf             # Module outputs
```

## Infrastructure Components

### Cloud Run Jobs (Scheduled)
1. **GPU Batch Job** (`gpu-batch-job`)
   - NVIDIA L4 GPU acceleration
   - 4 CPU / 16Gi memory
   - Manual trigger (no scheduler)
   - Results saved to GCS

2. **Daily Data Processor** (`daily-data-processor`)
   - Runs every hour
   - 1 CPU / 512Mi memory
   - Scheduled data processing tasks

3. **DVB Crawler Job** (`dvb-crawler-job`)
   - Runs daily at midnight (Asia/Bangkok timezone)
   - Scrapes yesterday's DVB Burmese news
   - Uploads articles and metadata to GCS
   - 1 CPU / 512Mi memory

### Cloud Run Services (Always-On HTTP)
1. **MLflow Tracking Server** (`mlflow`)
   - Experiment tracking and model registry
   - 2 CPU / 4Gi memory
   - Autoscaling 0-5 instances
   - Artifacts stored in GCS
   - Port 8080 (internal by default)

### Storage Buckets
- `{project-id}-gpu-job-outputs` - GPU job results (30-day retention)
- `{project-id}-mlflow-artifacts` - MLflow artifacts (90-day retention)
- `{project-id}-crawler-data` - Crawler output (90-day retention)

## Quick Start

### Prerequisites
- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Terraform >= 1.0
- Docker (for local testing)

### 1. Configure Project

```bash
# Copy tracked examples
cp terraform.tfvars.example terraform.tfvars
cp .env.example .env

# Put non-sensitive settings in terraform.tfvars
# Put secrets and TF_VAR_* values in .env
```

Recommended split:
- `terraform.tfvars`: non-sensitive values like `project_id`, `region`, `zone`, `environment`
- `.env`: sensitive values like `TF_VAR_hf_token` and `TF_VAR_gemini_api_key`

### 2. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy infrastructure
terraform apply
```

This will:
- ✅ Enable required GCP APIs
- ✅ Create Artifact Registry repository
- ✅ Build and push Docker images via Cloud Build
- ✅ Create GCS buckets with lifecycle policies
- ✅ Deploy Cloud Run jobs and services
- ✅ Set up Cloud Scheduler for automated runs
- ✅ Configure IAM permissions

### 3. Verify Deployment

```bash
# Check deployed jobs
gcloud run jobs list --region=asia-southeast1

# Check services
gcloud run services list --region=asia-southeast1

# View scheduler jobs
gcloud scheduler jobs list --location=asia-southeast1
```

## Usage

### Running Jobs Manually

**GPU Batch Job:**
```bash
gcloud run jobs execute gpu-batch-job \
  --region=asia-southeast1 \
  --wait
```

**DVB Crawler (manual run):**
```bash
gcloud run jobs execute dvb-crawler-job \
  --region=asia-southeast1 \
  --wait
```

### Accessing MLflow

**Get MLflow URL:**
```bash
# If public access is enabled
gcloud run services describe mlflow \
  --region=asia-southeast1 \
  --format="value(status.url)"

# For internal access, use Cloud Run proxy:
gcloud run services proxy mlflow --region=asia-southeast1
```

### Viewing Crawler Output

**List crawled files:**
```bash
gsutil ls gs://{project-id}-crawler-data/dvb/
```

**Download specific date:**
```bash
gsutil -m cp -r gs://{project-id}-crawler-data/dvb/2026-01-28/ ./
```

### Monitoring

**View job logs:**
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=dvb-crawler-job" \
  --limit=50 \
  --format=json
```

**Check scheduler status:**
```bash
gcloud scheduler jobs describe dvb-crawler-job \
  --location=asia-southeast1
```

## Development

### Local Testing

**Test crawler locally:**
```bash
cd Codebase_Container/crawler_job
npm install
node DVB_Burmese.crawler.js
```

**Test GPU job locally (requires NVIDIA GPU):**
```bash
cd Codebase_Container/gpu_batch_job
pip install -r requirements.txt
python main.py
```

### Development Environment

Enter Nix development environment with all tools:
```bash
nix-shell
```

Provides:
- Terraform
- Google Cloud SDK
- Python 3.12
- Node.js
- All required CLI tools

### Modifying Jobs

1. Edit code in `Codebase_Container/{job_name}/`
2. Run `terraform apply` to rebuild and redeploy
3. Terraform automatically detects code changes and rebuilds images

## Architecture Details

### DVB Crawler Pipeline
1. **Scheduler**: Triggers job daily at midnight (Asia/Bangkok)
2. **Scraper**: Collects yesterday's articles from DVB Burmese news
3. **Storage**: Uploads to GCS organized by date
   - Articles: `gs://bucket/dvb/YYYY-MM-DD/DVB_YYYY-MM-DD_hash.txt`
   - Metadata: `gs://bucket/dvb/YYYY-MM-DD/DVB_Burmese_YYYY-MM-DD.json`

### GPU Processing
- **GPU Type**: NVIDIA L4 (24GB VRAM)
- **Auto-scaling**: Starts on-demand, stops after completion
- **Cost Optimization**: Pay only for execution time

### MLflow Integration
- **Backend Store**: SQLite (upgradeable to Cloud SQL)
- **Artifact Store**: GCS bucket
- **Tracking**: Experiment metrics, parameters, models
- **Registry**: Model versioning and deployment

## Configuration

### Key Variables (terraform.tfvars)

```hcl
project_id             = "your-project-id"
region                 = "asia-southeast1"
job_name               = "gpu-batch-job"
docker_repository_id   = "gpu-jobs"
image_name             = "gpu-batch-job"
image_tag              = "latest"
service_account_id     = "gpu-job-sa"
gpu_type               = "nvidia-l4"
mlflow_public_access   = false  # Set true for public access
```

### Scheduler Cron Expressions

Modify in [main.tf](main.tf):
- DVB Crawler: `0 0 * * *` (daily at midnight)
- Data Processor: `0 * * * *` (every hour)

## Cost Estimation

Approximate monthly costs (varies by usage):
- **GPU Job**: ~$0.80/hour (L4) × execution hours
- **MLflow**: ~$0.10/hour × running time (scales to 0)
- **Crawler**: ~$0.05/execution
- **Storage**: ~$0.02/GB/month
- **Egress**: ~$0.12/GB

Cost optimization:
- Jobs scale to zero when idle
- GCS lifecycle policies auto-delete old data
- Spot/preemptible instances available for batch jobs

## Troubleshooting

**Build failures:**
```bash
# View Cloud Build logs
gcloud builds list --limit=5

# Check specific build
gcloud builds log BUILD_ID
```

**Job execution errors:**
```bash
# View job execution history
gcloud run jobs executions list \
  --job=dvb-crawler-job \
  --region=asia-southeast1

# Get execution logs
gcloud run jobs executions describe EXECUTION_NAME \
  --job=dvb-crawler-job \
  --region=asia-southeast1
```

**Permission issues:**
```bash
# Verify service account permissions
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:*"
```

## CI/CD with GitHub Actions

This project includes automated deployment via GitHub Actions.

### Features

- **Automated Terraform Plan**: Runs on all pull requests with results commented on PR
- **Automated Deploy**: Deploys to GCP when code is merged to main branch
- **Build Hash Detection**: CI builds generate `.build-hash` with `GITHUB-<hash>` prefix
- **Cloud Build Integration**: Automatically builds and pushes Docker images

### Setup Instructions (10 minutes)

📖 **Complete setup guide**: [.github/GITHUB_ACTIONS_SETUP.md](.github/GITHUB_ACTIONS_SETUP.md)

**Quick Setup:**

1. **Create GCP Service Account**
   ```bash
   gcloud iam service-accounts create github-actions \
     --display-name="GitHub Actions Terraform"
   ```

2. **Grant Permissions**
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/editor"
   ```

3. **Create JSON Key**
   ```bash
   gcloud iam service-accounts keys create github-actions-key.json \
     --iam-account=github-actions@PROJECT_ID.iam.gserviceaccount.com
   ```

4. **Add GitHub Secret**
   - Go to repository **Settings** → **Secrets and variables** → **Actions**
   - Create secret named `GOOGLE_CREDENTIALS`
   - Paste entire contents of `github-actions-key.json`
   - Delete local key file after adding to GitHub

### Workflow Triggers

- **Pull Request**: Plan only (no deployment)
- **Push to main**: Plan + Apply (deploys infrastructure)
- **Manual**: Can trigger via Actions tab

### Build Hash Behavior

| Environment | Build Hash Format | Detection Method |
|------------|-------------------|------------------|
| Local | `LOCAL-abc1234` | `TF_VAR_github_sha` is empty |
| GitHub CI | `GITHUB-abc1234` | `TF_VAR_github_sha=${{ github.sha }}` |

All services detect changes to code AND `utils/` folder content.

## Cleanup

**Destroy all infrastructure:**
```bash
terraform destroy
```

**Delete specific resources:**
```bash
# Delete a job
gcloud run jobs delete dvb-crawler-job --region=asia-southeast1

# Delete a service  
gcloud run services delete mlflow --region=asia-southeast1

# Delete bucket
gsutil -m rm -r gs://{project-id}-crawler-data
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `terraform plan`
5. Submit a pull request
