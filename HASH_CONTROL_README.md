# Deployment Hash Control System

## Overview

This system prevents unnecessary Cloud Run deployments by comparing the hash of the codebase content with the currently deployed environment variable. Deployment occurs **ONLY if there is a real content difference**.

## Core Concept

Three environment variables are maintained inside each Cloud Run Job/Service:

- `CONTENT_HASH` → Pure hash of files inside the codebase directory (deterministic)
- `LOCAL_HASH` → Hash of (content_hash + local username)
- `GITHUB_HASH` → Hash of (content_hash + github commit + github username)

Only `CONTENT_HASH` controls deployment decisions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Compute Current Hash                               │
│  ────────────────────────────────────────                   │
│  find codebase/ -type f | sha256sum | sha256sum             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Get Deployed Hash from Cloud Run                   │
│  ──────────────────────────────────────────                 │
│  gcloud run jobs describe ... --format="env.CONTENT_HASH"   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Compare Hashes                                      │
│  ───────────────────────                                     │
│  if [ "$CURRENT" = "$DEPLOYED" ]; then                       │
│    echo "Skip deployment"                                    │
│  else                                                        │
│    terraform apply                                           │
│  fi                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Local Deployment

### PowerShell (Windows)

```powershell
# Deploy all resources
.\scripts\deploy_local.ps1

# Deploy specific resource with hash checking
.\scripts\deploy_local.ps1 -ResourceName "dvb-crawler-job" -ResourceType "job"

# Skip hash check (force deployment)
.\scripts\deploy_local.ps1 -SkipHashCheck
```

### Bash (Linux/Mac)

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Compute content hash
CURRENT_HASH=$(./scripts/compute_content_hash.sh ./Codebase_Container/crawler_job)

# Get deployed hash
DEPLOYED_HASH=$(./scripts/get_deployed_hash.sh "cpe-final-project" "asia-southeast1" "dvb-crawler-job" "job")

# Compare and deploy if needed
if ./scripts/compare_hashes.sh "$CURRENT_HASH" "$DEPLOYED_HASH"; then
    echo "No deployment needed"
else
    terraform apply \
        -var="content_hash=$CURRENT_HASH" \
        -var="local_username=$(whoami)"
fi
```

## CI Deployment (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Setup gcloud
        uses: google-github-actions/setup-gcloud@v1
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Compute current hash for dvb-crawler-job
        id: compute_hash
        run: |
          CURRENT_HASH=$(./scripts/compute_content_hash.sh ./Codebase_Container/crawler_job)
          echo "current_hash=$CURRENT_HASH" >> $GITHUB_OUTPUT
      
      - name: Get deployed hash
        id: deployed_hash
        run: |
          DEPLOYED_HASH=$(./scripts/get_deployed_hash.sh \
            "${{ secrets.GCP_PROJECT_ID }}" \
            "asia-southeast1" \
            "dvb-crawler-job" \
            "job" || echo "")
          echo "deployed_hash=$DEPLOYED_HASH" >> $GITHUB_OUTPUT
      
      - name: Compare hashes
        id: compare
        run: |
          if [ "${{ steps.compute_hash.outputs.current_hash }}" = "${{ steps.deployed_hash.outputs.deployed_hash }}" ]; then
            echo "should_deploy=false" >> $GITHUB_OUTPUT
            echo "Hashes match. Skipping deployment."
          else
            echo "should_deploy=true" >> $GITHUB_OUTPUT
            echo "Hashes differ. Deploying."
          fi
      
      - name: Terraform Init
        if: steps.compare.outputs.should_deploy == 'true'
        run: terraform init
      
      - name: Terraform Apply
        if: steps.compare.outputs.should_deploy == 'true'
        env:
          TF_VAR_content_hash: ${{ steps.compute_hash.outputs.current_hash }}
          TF_VAR_github_sha: ${{ github.sha }}
          TF_VAR_github_username: ${{ github.actor }}
        run: |
          terraform apply -auto-approve
```

## Terraform Variables

The following variables control the hash system:

```hcl
variable "content_hash" {
  description = "Pure hash of codebase files (deterministic, no metadata)"
  type        = string
  default     = ""
}

variable "local_username" {
  description = "Local username for local deployments"
  type        = string
  default     = ""
}

variable "github_username" {
  description = "GitHub username for CI deployments"
  type        = string
  default     = ""
}

variable "github_sha" {
  description = "GitHub commit SHA (provided by CI)"
  type        = string
  default     = ""
}
```

## Environment Variables in Cloud Run

Each Cloud Run Job/Service will have these environment variables:

```bash
BUILD_HASH=LOCAL-a1b2c3d  # or GITHUB-a1b2c3d
CONTENT_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
LOCAL_HASH=5f4dcc3b5aa765d61d8327deb882cf99d4da3cf451e1e4b843fe39b7b7889b1c  # Only in local deployments
GITHUB_HASH=7d793037a0760186574b0282f2f435e7b3a0c0d7c7894c7f5e8297b5e2d8c7e1  # Only in CI deployments
```

## Critical Rules

1. **Never rely on Terraform state** to detect changes
2. **Always compare against live deployed Cloud Run** environment variable
3. CI runner instances are **stateless** and must not cause forced redeploy
4. Deployment must be **deterministic**
5. No timestamp-based triggers
6. No random triggers
7. No implicit null_resource rebuilds

## Troubleshooting

### Hash mismatch on every deployment

Check that file sorting is deterministic:
```powershell
# PowerShell
Get-ChildItem -Recurse | Sort-Object FullName
```

### CONTENT_HASH not found in Cloud Run

This is normal for first deployments. The script will proceed with deployment.

### Deployment still occurs when no changes made

Verify that infrastructure files are excluded from hash calculation:
- `.build-hash*`
- `.dockerignore`
- `cloudbuild.yaml`
- `Dockerfile`

## Benefits

✅ **No unnecessary Cloud Run revisions**  
✅ **No redundant Docker image builds**  
✅ **Deterministic deployments**  
✅ **Clean separation of CI logic and Terraform**  
✅ **Production-grade infrastructure control**

## File Structure

```
scripts/
├── compute_content_hash.ps1    # Windows hash computation
├── compute_content_hash.sh     # Unix hash computation
├── get_deployed_hash.ps1       # Windows retrieval of deployed hash
├── get_deployed_hash.sh        # Unix retrieval of deployed hash
├── compare_hashes.ps1          # Windows hash comparison
├── compare_hashes.sh           # Unix hash comparison
└── deploy_local.ps1            # Complete local deployment workflow
```

## Example Output

```
============================================
Local Deployment with Hash Control
============================================

Project ID: cpe-final-project
Region: asia-southeast1
Username: developer

Step 1: Computing current content hash...
Current content hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Step 2: Retrieving deployed hash from Cloud Run...
Deployed content hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Step 3: Comparing hashes...
Hashes match. No deployment needed.
  Current:  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  Deployed: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

No deployment needed. Exiting.
```
