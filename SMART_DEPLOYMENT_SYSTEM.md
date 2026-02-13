# Smart Hash-Based Deployment System

## Overview

This system intelligently manages Cloud Run deployments based on:
1. **Who** is deploying (Local developer vs GitHub CI)
2. **What** has changed (Content hash comparison)

## How It Works

### Key Concepts

1. **CONTENT_HASH**: Pure SHA-256 hash of all files in the codebase directory
   - Deterministic and consistent across environments
   - Always set in environment variables
   - Used to detect actual code changes

2. **LOCAL_HASH**: Set only when deploying from a local machine
   - Format: `{CONTENT_HASH}_{username}`
   - Only set when content has changed from deployed version
   - Cleared automatically on CI deployments

3. **GITHUB_HASH**: Set only when deploying from GitHub CI
   - Format: `SHA-256({CONTENT_HASH}-{github_sha}-{github_username})`
   - Only set when content has changed from deployed version
   - Cleared automatically on local deployments

### Deployment Logic

#### Local Deployment (`terraform apply` from local machine)

When you run `terraform apply` locally:

1. **Hash Calculation**:
   - Calculates CONTENT_HASH from your codebase
   - Fetches currently deployed CONTENT_HASH from Cloud Run
   - Compares the two hashes

2. **If Content Changed** (hashes differ):
   - ✅ Triggers Cloud Build to rebuild container
   - ✅ Sets LOCAL_HASH = `{CONTENT_HASH}_{your_username}`
   - ❌ Clears GITHUB_HASH (removes it from env vars)
   - Updates CONTENT_HASH to new value

3. **If Content Unchanged** (hashes match):
   - ❌ Skips Cloud Build (no rebuild needed)
   - ❌ Clears LOCAL_HASH (no env var set)
   - ❌ Keeps GITHUB_HASH cleared
   - Maintains existing CONTENT_HASH

#### CI Deployment (`terraform apply` from GitHub Actions)

When GitHub Actions runs deployment:

1. **Hash Calculation**:
   - Same calculation process
   - Compares deployed vs calculated CONTENT_HASH

2. **If Content Changed**:
   - ✅ Triggers Cloud Build to rebuild container
   - ✅ Sets GITHUB_HASH = `SHA-256({CONTENT_HASH}-{commit}-{github_user})`
   - ❌ Clears LOCAL_HASH (removes it from env vars)
   - Updates CONTENT_HASH to new value

3. **If Content Unchanged**:
   - ❌ Skips Cloud Build
   - ❌ Clears GITHUB_HASH
   - ❌ Keeps LOCAL_HASH cleared
   - Maintains existing CONTENT_HASH

## Benefits

### 1. **Cost Optimization**
- Cloud Build only runs when code actually changes
- No unnecessary container rebuilds
- Saves time and Cloud Build minutes

### 2. **Clear Deployment Tracking**
- Know exactly who deployed what
- LOCAL_HASH shows local deployments 
- GITHUB_HASH shows CI deployments
- Only one is set at a time

### 3. **Automatic Hash Management**
- No manual hash clearing needed
- Opposite hash automatically cleared on deployment
- Prevents stale hash values

### 4. **Smart Build Triggering**
- Compares deployed vs current content
- Only rebuilds when necessary
- First-time deployments always trigger builds

## Environment Variables in Cloud Run

Your Cloud Run jobs/services will have these environment variables:

```bash
# Always present - shows current codebase hash
CONTENT_HASH=abc123def456...

# Only set after local deployment with changes
LOCAL_HASH=abc123def456_aungk

# Only set after CI deployment with changes  
GITHUB_HASH=789xyz456abc...

# At most one of LOCAL_HASH or GITHUB_HASH is set
# If no changes detected, neither is set
```

## Example Scenarios

### Scenario 1: First Deployment (Local)
```
Deployed CONTENT_HASH: (none - doesn't exist)
Calculated CONTENT_HASH: abc123

Result:
✅ Cloud Build triggered (first deployment)
✅ CONTENT_HASH=abc123
✅ LOCAL_HASH=abc123_aungk
❌ GITHUB_HASH=(not set)
```

### Scenario 2: Code Change (Local)
```
Deployed CONTENT_HASH: abc123
Calculated CONTENT_HASH: def456

Result:
✅ Cloud Build triggered (content changed)
✅ CONTENT_HASH=def456
✅ LOCAL_HASH=def456_aungk
❌ GITHUB_HASH=(cleared)
```

### Scenario 3: No Code Change (Local)
```
Deployed CONTENT_HASH: abc123
Calculated CONTENT_HASH: abc123

Result:
❌ Cloud Build skipped (no changes)
✅ CONTENT_HASH=abc123 (unchanged)
❌ LOCAL_HASH=(not set)
❌ GITHUB_HASH=(cleared if present)
```

### Scenario 4: CI Deployment After Local
```
Deployed: CONTENT_HASH=abc123, LOCAL_HASH=abc123_aungk
Calculated: CONTENT_HASH=xyz789

Result:
✅ Cloud Build triggered (content changed)
✅ CONTENT_HASH=xyz789
❌ LOCAL_HASH=(cleared)
✅ GITHUB_HASH=<hash of xyz789+commit+user>
```

### Scenario 5: Local After CI (No Changes)
```
Deployed: CONTENT_HASH=abc123, GITHUB_HASH=...
Calculated: CONTENT_HASH=abc123

Result:
❌ Cloud Build skipped (no changes)
✅ CONTENT_HASH=abc123 (unchanged)
❌ LOCAL_HASH=(not set)
❌ GITHUB_HASH=(cleared)
```

## Implementation Details

### Files Involved

1. **Scripts**:
   - `scripts/get_deployed_content_hash.ps1` - Fetch deployed hash (Windows)
   - `scripts/get_deployed_content_hash.sh` - Fetch deployed hash (Linux/Mac)
   - `scripts/compute_content_hash_json.ps1` - Calculate hash (Windows)
   - `scripts/compute_content_hash_json.sh` - Calculate hash (Linux/Mac)

2. **Modules**:
   - `modules/cloud-run-service/main.tf` - Service deployment logic
   - `modules/cloud-scheduler/main.tf` - Job deployment logic

### Key Terraform Resources

```terraform
# Fetch deployed hash
data "external" "deployed_hash" {
  # Queries Cloud Run for current CONTENT_HASH
}

# Calculate new hash
data "external" "content_hash" {
  # Computes hash from codebase files
}

# Build only if changed
resource "null_resource" "service_image_build" {
  count = var.build_image && local.content_has_changed ? 1 : 0
  # Triggers Cloud Build when hashes differ
}
```

### Logic Flow

```terraform
locals {
  # Compare hashes
  content_has_changed = deployed_hash == "" || deployed_hash != content_hash
  
  # Determine mode
  is_local_deployment = github_sha == ""
  is_ci_deployment = github_sha != ""
  
  # Set appropriate hash
  local_hash_value = is_local && content_changed ? "{hash}_{user}" : ""
  github_hash_value = is_ci && content_changed ? sha256(...) : ""
}
```

## Monitoring Deployments

### Check Current State
```powershell
# View all hashes
terraform output -json | ConvertFrom-Json | 
  ForEach-Object { 
    $_.jobs.value.PSObject.Properties | 
    ForEach-Object { 
      Write-Host $_.Name
      Write-Host "  content_hash: $($_.Value.content_hash)"
      Write-Host "  local_hash:   $($_.Value.local_hash)"
      Write-Host "  github_hash:  $($_.Value.github_hash)"
    }
  }
```

### Verify Deployment Type
```bash
# Check environment variables in Cloud Run
gcloud run jobs describe JOB_NAME \
  --region=REGION \
  --format="value(template.template.containers[0].env)"
```

## Troubleshooting

### Cloud Build Not Triggering
```
Issue: Made code changes but build didn't run

Check:
1. Is CONTENT_HASH actually different?
   terraform plan -var="local_username=yourname"
   
2. Does the deployed service exist?
   gcloud run jobs list
   
3. Is build_image=true in main.tf?
```

### Wrong Hash Set
```
Issue: LOCAL_HASH set but I'm in GitHub Actions

Check:
1. Is TF_VAR_github_sha being passed?
   echo $TF_VAR_github_sha
   
2. Verify deployment context
   terraform plan -var="github_sha=abc123"
```

### Hash Not Clearing
```
Issue: Both LOCAL_HASH and GITHUB_HASH are set

This shouldn't happen with new logic. If it does:
1. Check if you're on latest module version
2. Verify data sources are working:
   terraform refresh
3. Check for state file issues
```

## GitHub Actions Configuration

Make sure your CI sets these variables:

```yaml
- name: Terraform Apply
  env:
    TF_VAR_github_sha: ${{ github.sha }}
    TF_VAR_github_username: ${{ github.actor }}
    # DON'T set TF_VAR_local_username in CI
  run: terraform apply -auto-approve
```

## Best Practices

1. **Always let Terraform manage hashes** - Don't set them manually
2. **CI should only set github_* vars** - Never set local_username in CI
3. **Local should only set local_username** - Never set github_* locally
4. **Review outputs after apply** - Verify correct hash is set
5. **Monitor Cloud Build usage** - Ensure builds only run when needed

## Summary

This system ensures:
- ✅ Builds only run when code actually changes
- ✅ Clear tracking of who deployed what
- ✅ Automatic hash management (no manual cleanup)
- ✅ Cost optimization (no redundant builds)
- ✅ Simple usage (just run terraform apply)
