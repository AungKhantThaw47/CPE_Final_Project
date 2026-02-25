# GitHub Actions CI/CD Setup

This document describes how to set up GitHub Actions for automated Terraform deployment to Google Cloud Platform.

## Overview

The CI/CD pipeline uses:
- **Service Account JSON Key** for authentication (simple and straightforward)
- **GitHub Secrets** to securely store credentials
- **Terraform** for infrastructure management
- **Google Cloud Build** for Docker image builds

## Required GitHub Secret

You need to configure **one secret** in your repository:

### `GOOGLE_CREDENTIALS`
- Service account JSON key file content
- Used for authenticating all GCP operations
- Created from a service account with appropriate permissions

## Setup Instructions (10 minutes)

### Step 1: Create Service Account

Navigate to [GCP IAM Console](https://console.cloud.google.com/iam-admin/serviceaccounts):

```bash
# Set your project ID
export PROJECT_ID="cpe-final-project"

# Create service account
gcloud iam service-accounts create github-actions \
  --project=$PROJECT_ID \
  --display-name="GitHub Actions Terraform" \
  --description="Service account for GitHub Actions CI/CD"
```

### Step 2: Grant Required Permissions

Give the service account necessary roles:

```bash
export SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

**For production**, use more granular permissions:
```bash
# Minimal permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudscheduler.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

### Step 3: Generate JSON Key

Create and download the service account key:

```bash
# Create JSON key file
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=$SA_EMAIL

# The key file is downloaded to: ./github-actions-key.json
```

**⚠️ Security Note**: This file contains sensitive credentials. Handle with care:
- Never commit to Git
- Delete after adding to GitHub secrets
- Rotate keys regularly (every 90 days)

### Step 4: Add Secret to GitHub

1. **Open your GitHub repository**
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Create the secret:
   - **Name**: `GOOGLE_CREDENTIALS`
   - **Value**: Copy the **entire contents** of `github-actions-key.json`
5. Click **Add secret**

**Using command line:**
```bash
# View file content to copy
cat github-actions-key.json

# Or use GitHub CLI
gh secret set GOOGLE_CREDENTIALS < github-actions-key.json
```

### Step 5: Clean Up Key File

```bash
# Securely delete the key file
rm github-actions-key.json

# Verify it's deleted
ls github-actions-key.json 2>/dev/null || echo "✓ Key file deleted"
```

### Step 6: Verify Setup

Push a commit to test the workflow:

```bash
git add .github/
git commit -m "Add GitHub Actions CI/CD"
git push origin main
```

Check the workflow run in **Actions** tab on GitHub.

## Workflow Behavior

### On Pull Request
- ✅ Format check
- ✅ Initialize Terraform
- ✅ Validate configuration
- ✅ Generate plan
- ✅ Comment plan on PR
- ❌ **No deployment**

### On Push to Main
- ✅ All plan steps
- ✅ Apply changes
- ✅ Build Docker images
- ✅ Deploy infrastructure

### Manual Trigger
- Can be triggered from **Actions** tab
- Choose branch to run against

## Build Hash System

The workflow automatically detects CI environment:

```yaml
env:
  TF_VAR_github_sha: ${{ github.sha }}
```

**How it works:**
- Local: `github_sha=""` → Build hash: `LOCAL-abc1234`
- CI: `github_sha="<commit>"` → Build hash: `GITHUB-abc1234`

All `.build-hash` files are generated automatically by Terraform.

## Troubleshooting

### Error: Permission Denied

**Problem**: Service account lacks required permissions

**Solution**: Verify roles are granted:
```bash
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions@"
```

### Error: Invalid Credentials

**Problem**: JSON key not copied correctly

**Solution**: 
1. Verify entire JSON content is in secret (including `{` `}`)
2. No extra whitespace or newlines
3. Re-create key if needed

### Error: Terraform State Locked

**Problem**: Previous run didn't complete

**Solution**:
```bash
terraform force-unlock LOCK_ID
```

### Error: Docker Auth Failed

**Problem**: Cannot push to Artifact Registry

**Solution**: Verify service account has `artifactregistry.writer` role

## Security Best Practices

✅ **Use minimal required permissions**  
✅ **Rotate keys every 90 days**  
✅ **Enable branch protection on main**  
✅ **Require PR reviews before merge**  
✅ **Monitor service account usage**  
✅ **Delete unused keys immediately**  

### Key Rotation

Rotate keys regularly for security:

```bash
# List existing keys
gcloud iam service-accounts keys list \
  --iam-account=$SA_EMAIL

# Delete old key
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=$SA_EMAIL

# Create new key
gcloud iam service-accounts keys create github-actions-key-new.json \
  --iam-account=$SA_EMAIL

# Update GitHub secret with new key
gh secret set GOOGLE_CREDENTIALS < github-actions-key-new.json

# Clean up
rm github-actions-key-new.json
```

## Alternative: Workload Identity Federation

For **keyless authentication** (more secure, no key management):

See [Workload Identity Federation Guide](https://cloud.google.com/blog/products/identity-security/enabling-keyless-authentication-from-github-actions) for setup.

Benefits:
- No service account keys to manage
- Automatic credential rotation
- Lower risk of credential leakage

Trade-off: More complex initial setup

## Monitoring

**View workflow runs:**
- GitHub: **Actions** tab
- See real-time logs and results

**View Cloud Build logs:**
- [GCP Console → Cloud Build](https://console.cloud.google.com/cloud-build)
- See Docker image build progress

**Check deployed resources:**
```bash
# List Cloud Run jobs
gcloud run jobs list --region=asia-southeast1

# List Cloud Run services
gcloud run services list --region=asia-southeast1
```

## Example Workflow Run

```
✅ Terraform Plan (Pull Request)
├─ Format Check: ✓
├─ Init: ✓
├─ Validate: ✓
├─ Plan: ✓ (5 to add, 2 to change)
└─ Comment: Posted to PR #42

✅ Terraform Apply (Merged to main)
├─ Init: ✓
├─ Download Plan: ✓
├─ Apply: ✓
├─ Build gpu-batch-job: GITHUB-def0cfa ✓
├─ Build mlflow: GITHUB-6e9188f ✓
├─ Build crawler: GITHUB-e78a743 ✓
└─ Deploy Complete: ✓
```

## Next Steps

1. ✅ Set up service account and credentials
2. ✅ Add `GOOGLE_CREDENTIALS` secret
3. ✅ Push changes to trigger workflow
4. 📝 Configure branch protection rules
5. 🔄 Set up key rotation schedule
6. 📊 Monitor workflow runs and costs
