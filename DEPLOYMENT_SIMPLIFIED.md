# Simplified Deployment Guide

## Quick Start

Just run Terraform directly - hash values are computed automatically:

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

That's it! No scripts required.

## How It Works

The Terraform configuration automatically:

1. **Detects your username** using data sources
2. **Computes `local_hash`** from username (for deployment tracking)
3. **Sets `content_hash`** via variable (empty by default, can be overridden)
4. **Sets `github_hash`** for CI/CD (empty for local deployments)

## What Got Simplified

### Before:
```powershell
# Required wrapper script that computed hashes and passed -var arguments
.\scripts\deploy_local.ps1
```

### After:
```powershell
# Direct Terraform usage - everything auto-computed
terraform apply
```

## Auxiliary Scripts (Optional)

Scripts are now **optional helpers** for advanced use cases:

### Individual Hash Computation
```powershell
# Compute hash for specific codebase (for manual inspection)
.\scripts\compute_content_hash.ps1 -CodebasePath "./Codebase_Container/crawler_job"
```

### Content Hash Override (Advanced)
```powershell
# Pass specific content_hash if you want deterministic rebuilds
$hash = .\scripts\compute_content_hash.ps1 -CodebasePath "./Codebase_Container/dvb-crawler-job"
terraform apply -var="content_hash=$hash"
```

### Deployment with Hash Checking (Advanced)
```powershell
# Old script still works for hash-based deployment decisions
.\scripts\deploy_local.ps1 -ResourceName "dvb-crawler-job" -ResourceType "job"
```

## Variable Overrides (Optional)

All hash variables can still be overridden:

```powershell
terraform apply \
  -var="content_hash=abc123..." \
  -var="local_username=myuser" \
  -var="github_username=myhandle" \
  -var="github_sha=commit789"
```

But you don't need to - defaults work automatically.

## What Shows in Outputs

Running `terraform output -json` shows:

```json
{
  "jobs": {
    "dvb-crawler-job": {
      "content_hash": "",                    // Empty by default (override with -var)
      "local_hash": "415af8d8a1...",        // Auto-computed ✓
      "github_hash": ""                      // Empty for local (set via CI/CD)
    }
  }
}
```

## CI/CD (GitHub Actions)

For GitHub Actions, set environment variables:

```yaml
- name: Deploy to Cloud Run
  env:
    TF_VAR_github_sha: ${{ github.sha }}
    TF_VAR_github_username: ${{ github.actor }}
    TF_VAR_content_hash: ${{ steps.hash.outputs.hash }}  # If needed
  run: |
    terraform init
    terraform apply -auto-approve
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  terraform apply (no arguments needed)              │
└────────────────┬────────────────────────────────────┘
                 │
                 ├─► data.external.username
                 │   └─> scripts/get_username.ps1
                 │       Returns: { "username": "aungk" }
                 │
                 ├─► local.actual_local_username
                 │   └─> var.local_username != "" ? var : data.username
                 │
                 └─► Modules receive auto-computed values
                     ├─> local_username   ✓ auto
                     ├─> content_hash     (empty or -var override)
                     └─> github_username  (empty or env var)
```

## Benefits

✅ **Simple**: `terraform apply` just works  
✅ **No scripts required**: Direct Terraform usage  
✅ **Scripts are auxiliary**: Use them when you need them  
✅ **Override capable**: Full control via `-var` when needed  
✅ **CI/CD friendly**: Works with environment variables  
✅ **Backward compatible**: Old scripts still work  

## Summary

**Primary workflow**: `terraform apply`  
**Scripts**: Optional helpers for advanced scenarios  
**Overrides**: Available via `-var` flags when needed
