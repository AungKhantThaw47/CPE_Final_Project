# Quick Start Guide - Hash Control System Testing

## Prerequisites

- Terraform installed
- gcloud CLI installed and authenticated
- PowerShell (Windows) or Bash (Linux/Mac)
- Access to GCP project with Cloud Run enabled

## Test 1: Verify Hash Computation

### Windows (PowerShell)

```powershell
# Test hash computation for crawler job
.\scripts\compute_content_hash.ps1 -CodebasePath ".\Codebase_Container\crawler_job"

# Should output a 64-character hex string
# Example: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### Linux/Mac (Bash)

```bash
# Make script executable
chmod +x scripts/compute_content_hash.sh

# Test hash computation
./scripts/compute_content_hash.sh ./Codebase_Container/crawler_job
```

**Expected Result:** A consistent 64-character SHA256 hash

---

## Test 2: First Deployment (No Deployed Hash)

```powershell
# Windows
.\scripts\deploy_local.ps1 `
    -ResourceName "dvb-crawler-job" `
    -ResourceType "job"
```

**Expected Behavior:**
1. Computes current hash
2. Finds no deployed hash
3. Proceeds with Terraform deployment
4. Sets CONTENT_HASH, LOCAL_HASH environment variables in Cloud Run

---

## Test 3: Second Deployment (No Changes)

Run the same command again:

```powershell
.\scripts\deploy_local.ps1 `
    -ResourceName "dvb-crawler-job" `
    -ResourceType "job"
```

**Expected Behavior:**
1. Computes current hash
2. Retrieves deployed hash from Cloud Run
3. Hashes match → **Deployment skipped**
4. Output: "No deployment needed. Exiting."

---

## Test 4: Deployment with Code Changes

1. Make a change to any file in the codebase:
   ```powershell
   # Add a comment to a Python file
   Add-Content -Path ".\Codebase_Container\crawler_job\main.py" -Value "# Test change"
   ```

2. Run deployment again:
   ```powershell
   .\scripts\deploy_local.ps1 `
       -ResourceName "dvb-crawler-job" `
       -ResourceType "job"
   ```

**Expected Behavior:**
1. Computes new hash (different from deployed)
2. Hashes differ → **Deployment proceeds**
3. New CONTENT_HASH updated in Cloud Run

---

## Test 5: Verify Environment Variables in Cloud Run

```powershell
# Check environment variables in deployed job
gcloud run jobs describe dvb-crawler-job `
    --region=asia-southeast1 `
    --format="yaml(template.template.containers[0].env)"
```

**Expected Output:**
```yaml
env:
- name: BUILD_HASH
  value: LOCAL-a1b2c3d
- name: CONTENT_HASH
  value: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- name: LOCAL_HASH
  value: 5f4dcc3b5aa765d61d8327deb882cf99d4da3cf451e1e4b843fe39b7b7889b1c
- name: GCS_BUCKET
  value: cpe-final-project-crawler-data
```

---

## Test 6: Manual Hash Comparison

```powershell
# Compute current hash
$current = .\scripts\compute_content_hash.ps1 -CodebasePath ".\Codebase_Container\crawler_job"

# Get deployed hash
$deployed = .\scripts\get_deployed_hash.ps1 `
    -ProjectId "cpe-final-project" `
    -Region "asia-southeast1" `
    -ResourceName "dvb-crawler-job" `
    -ResourceType "job"

# Compare
.\scripts\compare_hashes.ps1 -CurrentHash $current -DeployedHash $deployed

# Exit code 0 = match, Exit code 1 = different
Write-Host "Exit Code: $LASTEXITCODE"
```

---

## Test 7: Force Deployment (Skip Hash Check)

```powershell
# Deploy without hash checking
.\scripts\deploy_local.ps1 -SkipHashCheck
```

**Expected Behavior:**
- Skips all hash comparison steps
- Proceeds directly to Terraform apply
- Useful for infrastructure changes or troubleshooting

---

## Test 8: Deploy All Resources

```powershell
# Deploy all jobs and services
.\scripts\deploy_local.ps1
```

**Expected Behavior:**
- Deploys all resources defined in main.tf
- Each resource gets its own CONTENT_HASH based on its codebase
- No hash checking (deploys everything)

---

## Test 9: GitHub Actions Simulation

Simulate CI environment:

```powershell
# Set environment variables like GitHub Actions would
$env:TF_VAR_content_hash = "$(.\scripts\compute_content_hash.ps1 -CodebasePath '.\Codebase_Container\crawler_job')"
$env:TF_VAR_github_sha = "abc123def456"
$env:TF_VAR_github_username = "github-actions"

# Run Terraform
terraform plan

# Check that GITHUB_HASH would be set
```

---

## Test 10: Verify Deterministic Hashing

Run hash computation multiple times:

```powershell
# Run 5 times
1..5 | ForEach-Object {
    .\scripts\compute_content_hash.ps1 -CodebasePath ".\Codebase_Container\crawler_job"
}
```

**Expected Result:** All 5 hashes should be **identical**

---

## Troubleshooting Tests

### Test: Hash Changes When No Files Changed

**Problem:** Hash changes on every run even when no files modified

**Diagnosis:**
```powershell
# Check if file modification times affect hash (they shouldn't)
$hash1 = .\scripts\compute_content_hash.ps1 -CodebasePath ".\Codebase_Container\crawler_job"
Start-Sleep -Seconds 2
$hash2 = .\scripts\compute_content_hash.ps1 -CodebasePath ".\Codebase_Container\crawler_job"

if ($hash1 -eq $hash2) {
    Write-Host "✅ Hashing is deterministic"
} else {
    Write-Host "❌ Hashing is NOT deterministic"
}
```

### Test: Deployed Hash Not Found

**Problem:** Script always says "No deployed hash found"

**Diagnosis:**
```powershell
# Manually check Cloud Run
gcloud run jobs describe dvb-crawler-job `
    --region=asia-southeast1 `
    --format="value(template.template.containers[0].env)"

# Look for CONTENT_HASH in output
```

### Test: Terraform Always Redeploys

**Problem:** Terraform still redeploys even when hashes match

**Diagnosis:**
1. Check if Terraform is ignoring the hash check script
2. Verify script exit codes:
   ```powershell
   .\scripts\compare_hashes.ps1 -CurrentHash "abc" -DeployedHash "abc"
   Write-Host "Exit Code: $LASTEXITCODE"  # Should be 0
   
   .\scripts\compare_hashes.ps1 -CurrentHash "abc" -DeployedHash "def"
   Write-Host "Exit Code: $LASTEXITCODE"  # Should be 1
   ```

---

## Success Criteria

✅ **Test 1:** Hash computes successfully  
✅ **Test 2:** First deployment succeeds  
✅ **Test 3:** Second deployment skips (no changes)  
✅ **Test 4:** Deployment proceeds after code change  
✅ **Test 5:** Environment variables present in Cloud Run  
✅ **Test 6:** Manual comparison works correctly  
✅ **Test 7:** Force deployment bypasses hash check  
✅ **Test 10:** Hashing is deterministic  

---

## Next Steps

1. ✅ Complete all 10 tests
2. ✅ Verify environment variables in Cloud Run
3. ✅ Test with actual code changes
4. ✅ Set up GitHub Actions workflow
5. ✅ Monitor production deployments

---

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Hash changes every time | Non-deterministic sorting | Check file sorting in script |
| Can't retrieve deployed hash | Wrong resource name/type | Verify gcloud command syntax |
| Terraform still redeploys | Not using hash comparison | Ensure deploy script runs comparison first |
| Script fails on Linux | Line endings (CRLF) | Convert to LF: `dos2unix scripts/*.sh` |
| Permission denied | Scripts not executable | Run: `chmod +x scripts/*.sh` |

---

## Performance Metrics

Expected execution times:
- Hash computation: < 5 seconds
- Hash retrieval from Cloud Run: < 3 seconds
- Hash comparison: < 1 second
- Full deployment (if needed): 3-5 minutes
- Skipped deployment: < 10 seconds total

---

## Monitoring

Check deployment history:
```powershell
# View Cloud Run revisions
gcloud run revisions list `
    --service=dvb-crawler-job `
    --region=asia-southeast1 `
    --format="table(name,metadata.annotations.CONTENT_HASH:label=HASH,status.conditions[0].lastTransitionTime:label=DEPLOYED)"
```

This shows which revisions were deployed and their content hashes.
