# Content Hash System - Now Fully Automated

## ✅ Complete: Content Hashes Auto-Computed

All resources now have their `content_hash` automatically computed from their codebase files.

## Current Content Hashes

| Resource | Content Hash (first 32 chars) | Codebase Path |
|----------|-------------------------------|---------------|
| **Jobs** |||
| gpu-batch-job | `5693b960cdd891e2f49c5a11d38e2a31` | `Codebase_Container/gpu_batch_job` |
| daily-data-processor | `15db9b2ebb8df65ac1738233678dd652` | `Codebase_Container/cloud_scheduler_function` |
| dvb-crawler-job | `5f3d5b132a3bfa529e23eaf023d688f8` | `Codebase_Container/crawler_job` |
| dvb-text-cleaner-job | `3333223b2a9dccd6d62c8fd20e802721` | `Codebase_Container/text_clean_codebase` |
| **Services** |||
| mlflow | `4636e129869425f8f14b537fb68b4922` | `modules/mlflow` |

## How It Works

### 1. Data Sources Compute Hashes
```terraform
# Compute content hash for each job codebase
data "external" "job_content_hash" {
  for_each = local.job_codebases
  program  = local.is_windows_env ? 
    ["PowerShell", "-File", "${path.root}/scripts/compute_content_hash_json.ps1"] : 
    ["bash", "${path.root}/scripts/compute_content_hash_json.sh"]
  query = {
    codebase_path = each.value
  }
}
```

### 2. Modules Receive Auto-Computed Hashes
```terraform
module "jobs" {
  for_each = local.jobs
  
  # Auto-computed from codebase files
  content_hash = data.external.job_content_hash[each.key].result.content_hash
  local_username = local.actual_local_username  # Also auto-detected
  github_username = local.actual_github_username
}
```

### 3. Hash Changes Trigger Deployment
When you modify code in any codebase:
- ✅ Content hash changes automatically
- ✅ Terraform detects the change
- ✅ Only affected resources are updated

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────┐
│  terraform apply                                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├─► Compute content hashes (data sources)
                 │   ├─> gpu-batch-job:        5693b960...
                 │   ├─> daily-data-processor: 15db9b2e...
                 │   ├─> dvb-crawler-job:      5f3d5b13...
                 │   ├─> dvb-text-cleaner-job: 3333223b...
                 │   └─> mlflow:               4636e129...
                 │
                 ├─► Compare with deployed hashes
                 │   └─> CONTENT_HASH env var in Cloud Run
                 │
                 └─► Update only if hash changed
                     └─> Triggers rebuild + redeployment
```

## What Gets Computed

Each codebase hash includes all files except:
- `.build-hash*` (temporary build files)
- `.dockerignore`
- `cloudbuild.yaml`
- `Dockerfile`

**Why exclude these?** Changes to build configuration shouldn't trigger redeployment if the actual code hasn't changed.

## Testing Hash Computation

```powershell
# Compute hash for specific codebase
.\scripts\compute_content_hash_json.ps1 -CodebasePath "Codebase_Container\crawler_job"

# Output:
# {"content_hash":"5f3d5b132a3bfa529e23eaf023d688f8fc8725ae0c7bde919eef824254aab9c3"}
```

## Terraform Plan Shows Hash Changes

```bash
terraform plan
```

Output when code changes:
```diff
~ module.jobs["dvb-crawler-job"].google_cloud_run_v2_job.scheduled_job
    ~ template {
      ~ containers {
        ~ env {
          ~ value = "old_hash..." -> "5f3d5b13..." # CONTENT_HASH
        }
      }
    }
```

## Hash Variables in Outputs

After running `terraform apply`, check outputs:

```powershell
terraform output -json | ConvertFrom-Json | 
  Select-Object -ExpandProperty jobs | 
  Select-Object -ExpandProperty value | 
  Format-Table
```

Each resource shows:
- **`content_hash`** ✓ Auto-computed from codebase
- **`local_hash`** ✓ Auto-computed from username
- **`github_hash`** (empty for local, set in CI/CD)

## Comparison Logic

Terraform modules use `content_hash` as trigger:

```terraform
resource "null_resource" "scheduler_job_image_build" {
  triggers = {
    content_hash = local.content_hash_value  # Auto-computed
    container_image = var.container_image
  }
  
  # Only rebuilds when content_hash changes
  provisioner "local-exec" {
    command = "gcloud builds submit..."
  }
}
```

## Benefits

### 1. Automatic Change Detection
- ✅ Edit any file in `Codebase_Container/crawler_job/`
- ✅ Run `terraform apply`
- ✅ Only that job rebuilds and redeploys

### 2. Skip Unnecessary Deployments
- ✅ No code changes = no deployment
- ✅ Saves build time and costs
- ✅ Prevents unnecessary service restarts

### 3. Audit Trail
- ✅ Every deployment has unique content hash
- ✅ View deployed hash: `gcloud run jobs describe <job> --format="yaml(template.template.containers[0].env)"`
- ✅ Compare with local: `terraform output`

### 4. No Manual Hash Management
- ✅ No scripts to run before deploying
- ✅ No `-var` flags to remember
- ✅ Just `terraform apply`

## Example Workflow

### 1. Edit Code
```bash
# Modify crawler logic
code Codebase_Container/crawler_job/DVB_Burmese.crawler.js
```

### 2. Deploy
```powershell
terraform apply
```

Terraform automatically:
1. ✅ Computes new hash for `dvb-crawler-job`
2. ✅ Compares with deployed hash
3. ✅ Detects change
4. ✅ Triggers Cloud Build
5. ✅ Updates Cloud Run Job
6. ✅ Sets new `CONTENT_HASH` environment variable

### 3. Verify
```powershell
# Check deployed hash
terraform output -json | jq '.jobs.value["dvb-crawler-job"].content_hash'
```

## CI/CD Integration

For GitHub Actions, hashes are still auto-computed:

```yaml
- name: Deploy to Cloud Run
  env:
    # Username and content_hash auto-computed by Terraform
    TF_VAR_github_sha: ${{ github.sha }}      # Add commit SHA
    TF_VAR_github_username: ${{ github.actor }} # Add actor
  run: |
    terraform apply -auto-approve
```

## Migration from Manual System

### Before (Manual):
```powershell
$hash = .\scripts\compute_content_hash.ps1 -CodebasePath "..."
terraform apply -var="content_hash=$hash"
```

### Now (Automatic):
```powershell
terraform apply
```

## Troubleshooting

### Hash computation fails
```powershell
# Test hash script directly
.\scripts\compute_content_hash_json.ps1 -CodebasePath "Codebase_Container\crawler_job"
```

### Check computed vs deployed
```powershell
# Local (computed by Terraform)
terraform output -json | jq '.jobs.value["dvb-crawler-job"].content_hash'

# Deployed (in Cloud Run)
gcloud run jobs describe dvb-crawler-job --region asia-southeast1 --format="value(template.template.containers[0].env.CONTENT_HASH.value)"
```

### Force redeployment (bypass hash check)
```powershell
# Manually trigger rebuild by changing container image tag
terraform apply -var="image_tag=v2"
```

## Summary

✅ **Content hashes are fully automated**
- Computed automatically from codebase files
- No manual scripts or `-var` flags needed
- Changes detected and deployed automatically

✅ **All three hash types working**
- `content_hash` ✓ Auto-computed from files
- `local_hash` ✓ Auto-computed from username  
- `github_hash` ✓ Set via CI/CD env vars

✅ **Simple workflow**
```powershell
terraform apply  # That's it!
```
