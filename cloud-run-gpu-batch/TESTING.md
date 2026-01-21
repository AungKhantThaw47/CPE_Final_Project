# Testing Guide

## Local Testing (Before Deployment)

### Test 1: Validate Terraform Configuration

```bash
terraform init
terraform validate
terraform plan
```

**Expected**: No errors, plan shows resources to be created.

### Test 2: Check Docker Build

```bash
docker build -t test-gpu-job --platform linux/amd64 .
```

**Expected**: Build completes successfully.

### Test 3: Validate Python Scripts

```bash
python -m py_compile trigger_job.py
python -m py_compile build.py
python -m py_compile job/main.py
```

**Expected**: No syntax errors.

---

## Deployment Testing

### Test 4: Deploy Infrastructure

```bash
terraform apply
```

**Expected**: All resources created successfully.

**Verify**:
```bash
terraform output
```

Should show:
- job_name
- job_url
- docker_repository
- gcs_bucket_name
- service_account_email

### Test 5: Build and Push Docker Image

```bash
python build.py
```

**Expected**: 
- Image builds successfully
- Image pushes to Artifact Registry

**Verify**:
```bash
gcloud artifacts docker images list \
  --location=asia-southeast1 \
  --repository=gpu-jobs
```

---

## Job Execution Testing

### Test 6: Trigger Job via Python

```bash
python trigger_job.py
```

**Expected**:
- Returns 200 status code
- Prints execution name and UID
- Provides monitoring link

### Test 7: Monitor Job Execution

**Via Console**:
```
https://console.cloud.google.com/run/jobs
```

**Via gcloud** (optional for verification):
```bash
gcloud run jobs executions list \
  --job=gpu-batch-job \
  --region=asia-southeast1
```

**Expected**: Execution shows "Succeeded" status after ~2-5 minutes.

### Test 8: Verify GPU Detection

**Check logs for**:
```
✅ CUDA is available
✅ GPU 0: NVIDIA L4
```

**Via Console**:
1. Go to Cloud Run > Jobs > gpu-batch-job
2. Click on latest execution
3. View Logs

**Expected**: Logs show GPU detected and computation completed.

### Test 9: Verify Results in GCS

```bash
PROJECT_ID=$(terraform output -raw project_id)
gsutil ls gs://${PROJECT_ID}-gpu-job-outputs/gpu-batch-job/
```

**Expected**: JSON file with results.

**Download and view**:
```bash
gsutil cat gs://${PROJECT_ID}-gpu-job-outputs/gpu-batch-job/results_*.json
```

**Expected JSON structure**:
```json
{
  "device": "cuda",
  "matrix_size": 5000,
  "computation_time_seconds": 1.234,
  "result_shape": [5000, 5000],
  "gpu_name": "NVIDIA L4",
  "cuda_available": true
}
```

---

## Performance Testing

### Test 10: Verify GPU Auto-Stop

1. Trigger job: `python trigger_job.py`
2. Wait for completion (~2-5 minutes)
3. Check billing: https://console.cloud.google.com/billing

**Expected**: GPU billing stops after job completes.

### Test 11: Test Multiple Executions

```bash
for i in {1..3}; do
  echo "Execution $i"
  python trigger_job.py
  sleep 30
done
```

**Expected**: Each execution runs independently, no conflicts.

### Test 12: Verify Timeout

Modify `job/main.py` to add sleep:
```python
import time
time.sleep(1000)  # Force timeout
```

Rebuild and trigger:
```bash
python build.py
python trigger_job.py
```

**Expected**: Job fails after 15 minutes (timeout setting).

---

## Error Testing

### Test 13: Missing Permissions

Remove IAM binding temporarily:
```bash
terraform state rm google_cloud_run_v2_job_iam_member.invoker_can_run
```

Try to trigger:
```bash
python trigger_job.py
```

**Expected**: 403 Permission Denied error.

**Fix**:
```bash
terraform apply
```

### Test 14: Invalid Image

Modify image tag in variables.tf:
```hcl
image_tag = "nonexistent-tag"
```

Apply and trigger:
```bash
terraform apply
python trigger_job.py
```

**Expected**: Job execution fails with image pull error.

**Fix**: Rebuild and push correct image.

---

## Load Testing

### Test 15: Concurrent Execution

```python
# concurrent_test.py
import concurrent.futures
import subprocess

def trigger_job():
    result = subprocess.run(["python", "trigger_job.py"], capture_output=True)
    return result.returncode == 0

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(trigger_job) for _ in range(5)]
    results = [f.result() for f in futures]
    
print(f"Success: {sum(results)}/{len(results)}")
```

**Expected**: All executions succeed (Cloud Run handles concurrency).

---

## Cleanup Testing

### Test 16: Verify Clean Destruction

```bash
terraform destroy
```

**Expected**: All resources deleted.

**Verify**:
```bash
# Check Cloud Run Jobs
gcloud run jobs list --region=asia-southeast1

# Check Artifact Registry
gcloud artifacts repositories list --location=asia-southeast1

# Check GCS buckets
gsutil ls | grep gpu-job-outputs
```

**Expected**: No resources remain.

---

## Continuous Testing Checklist

Before each deployment:

- [ ] Terraform validate passes
- [ ] Docker build succeeds
- [ ] Python scripts have no syntax errors
- [ ] Service account has correct permissions
- [ ] Docker image pushed to Artifact Registry
- [ ] Job triggers successfully via REST API
- [ ] GPU is detected in logs
- [ ] Results saved to GCS
- [ ] Job completes and exits cleanly
- [ ] GPU billing stops after completion

---

## Automated Test Script

```bash
#!/bin/bash
# test_suite.sh

set -e

echo "Running test suite..."

# Test 1: Terraform
echo "Test 1: Terraform validation"
terraform validate

# Test 2: Docker build
echo "Test 2: Docker build"
docker build -t test-build .

# Test 3: Python syntax
echo "Test 3: Python syntax"
python -m py_compile trigger_job.py
python -m py_compile build.py
python -m py_compile job/main.py

# Test 4: Trigger job
echo "Test 4: Job execution"
python trigger_job.py

# Test 5: Wait and check results
echo "Test 5: Checking results (waiting 5 minutes)..."
sleep 300

PROJECT_ID=$(terraform output -raw project_id)
RESULTS=$(gsutil ls gs://${PROJECT_ID}-gpu-job-outputs/gpu-batch-job/ | tail -1)

if [ -z "$RESULTS" ]; then
    echo "❌ No results found in GCS"
    exit 1
fi

echo "✅ Results found: $RESULTS"

# Test 6: Verify GPU in results
gsutil cat "$RESULTS" | grep -q "cuda_available.*true"
if [ $? -eq 0 ]; then
    echo "✅ GPU detected in results"
else
    echo "❌ GPU not detected in results"
    exit 1
fi

echo "✅ All tests passed!"
```

Save as `test_suite.sh` and run:
```bash
chmod +x test_suite.sh
./test_suite.sh
```
