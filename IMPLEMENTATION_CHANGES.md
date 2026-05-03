# Infrastructure Changes: Workflow-Only Orchestration & Dashboard Service

**Date:** May 2, 2026  
**Status:** ✅ Implemented

---

## Summary of Changes

### 1. **Removed Job-to-Job Chaining IAM** (main.tf)

**What was removed:**
- Resource: `google_cloud_run_v2_job_iam_member "crawler_triggers_cleaner"`
- This IAM binding allowed the crawler job to directly invoke the text-cleaner job
- Reason: Eliminated architectural redundancy; pipeline orchestration now delegated exclusively to Cloud Workflows

**Impact:**
- ✅ Simplified IAM model (single source of truth for job sequencing)
- ✅ Eliminated implicit pipeline coupling via job service accounts
- ✅ All pipeline stage ordering now controlled by `workflow.yaml` and `manual_workflow.yaml`
- ⚠️ Jobs can no longer trigger each other independently (intentional — use workflows instead)

**How to run jobs now:**
```bash
# Daily pipeline (automated via scheduler)
gcloud workflows run daily-pipeline --project cpe-final-project --location asia-southeast1

# Manual pipeline with date range
gcloud workflows run manual-pipeline \
  --data='{"crawl_start_date": "2026-05-01", "crawl_end_date": "2026-05-02"}' \
  --project cpe-final-project \
  --location asia-southeast1

# Individual job (if needed for debugging)
gcloud run jobs execute dvb-crawler-job --project cpe-final-project --location asia-southeast1 --wait
```

---

### 2. **Added Dashboard Cloud Run Service** (main.tf & Dockerfile)

**New service configuration:**
```hcl
crisis-dashboard = {
  codebase_path   = "${path.root}/Codebase_Container/FrontEnd_Dashboard"
  container_image = "asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/crisis-dashboard:latest"
  description     = "Crisis events interactive dashboard — Leaflet.js geospatial visualization"
  build_image     = true
  cpu_limit       = "1"
  memory_limit    = "512Mi"
  min_instances   = 0
  max_instances   = 2
  port            = 8080
  allow_public    = true
  environment_variables = {
    EVENTS_API_URL       = "https://events-api-PLACEHOLDER/events"
    GOOGLE_CLOUD_PROJECT = "cpe-final-project"
    GCP_REGION           = "asia-southeast1"
  }
}
```

**Dashboard Dockerfile updates:**
- Serves `crisis-dashboard.html` as `index.html` via nginx
- Includes supporting HTML assets (`project-poster.html`, `poster-canva.html`)
- Listens on port 8080 (Cloud Run standard)
- Accepts `EVENTS_API_URL` environment variable for runtime API endpoint configuration

**Features:**
- ✅ Publicly accessible geospatial dashboard
- ✅ Queries events-api for real-time crisis events
- ✅ Auto-scaling (0–2 instances based on traffic)
- ✅ Static asset serving optimized for nginx

---

## Deployment Steps

### Step 1: Deploy Infrastructure
```bash
cd /Users/akt/workspace/CPE_Final_Project
terraform plan -out tfplan
terraform apply tfplan
```

### Step 2: Capture Output URLs
After `terraform apply`, capture the public URLs:
```bash
terraform output services | grep -A10 crisis-dashboard
terraform output services | grep -A10 events-api
```

Example output:
```
"crisis-dashboard" = {
  "console_url" = "https://console.cloud.google.com/run/detail/asia-southeast1/crisis-dashboard?project=cpe-final-project"
  "public_url" = "https://crisis-dashboard-xxxxx-xx.a.run.app"
}
"events-api" = {
  "public_url" = "https://events-api-xxxxx-xx.a.run.app"
}
```

### Step 3: Update Dashboard Configuration

The dashboard is initialized with a placeholder API URL. Update it with the real events-api endpoint:

**Option A: Via Cloud Run Console**
1. Navigate to Cloud Run → `crisis-dashboard` → Edit & Deploy
2. Set environment variable:
   ```
   EVENTS_API_URL=https://events-api-xxxxx-xx.a.run.app/events
   ```
3. Deploy

**Option B: Via gcloud CLI**
```bash
gcloud run services update crisis-dashboard \
  --set-env-vars EVENTS_API_URL=https://events-api-xxxxx-xx.a.run.app/events \
  --region asia-southeast1 \
  --project cpe-final-project
```

**Option C: Automated (Terraform)**
Add to `terraform.tfvars`:
```hcl
dashboard_api_url = "https://events-api-xxxxx-xx.a.run.app/events"
```

Then update [main.tf](main.tf#L330) line 330:
```hcl
EVENTS_API_URL = var.dashboard_api_url
```

### Step 4: Test the Full Stack

```bash
# 1. Check dashboard is live
curl https://crisis-dashboard-xxxxx-xx.a.run.app

# 2. Trigger manual pipeline
gcloud workflows run manual-pipeline \
  --data='{"crawl_start_date": "2026-05-01", "crawl_end_date": "2026-05-02"}' \
  --project cpe-final-project \
  --location asia-southeast1

# 3. Wait for extractor to write to Firestore (~10 min total)
# 4. Visit dashboard URL and verify events display
```

---

## Architecture Diagram: After Changes

```
Cloud Scheduler (daily @ 00:00 Bangkok)
        ↓
    ┌─────────────────────────────────────────────┐
    │  Cloud Workflows: daily-pipeline            │
    │  (workflow.yaml)                            │
    ├─────────────────────────────────────────────┤
    │  1. Run dvb-crawler-job       (20 min)       │
    │  2. Run dvb-text-cleaner-job  (10 min)       │
    │  3. Run crisis-classifier-job (60 min)       │
    │  4. [HUMAN REVIEW via crisis-admin]         │
    │  5. Run dvb-annotator-job     (10 min)       │
    │  6. [HUMAN REVIEW via crisis-admin]         │
    │  7. Run dvb-extractor-job     (10 min)       │
    └─────────────────────────────────────────────┘
                     ↓
            Firestore Collection: "events"
                     ↓
        ┌──────────────────────────┐
        │  events-api              │ ← Query endpoint
        │  (Cloud Run Service)     │
        └──────────────────────────┘
                     ↑
        ┌──────────────────────────┐
        │  crisis-dashboard        │ ← Queries events-api
        │  (Cloud Run Service)     │   Displays on Leaflet.js map
        │  Public: https://...     │
        └──────────────────────────┘
```

---

## Post-Deployment Verification Checklist

- [ ] `terraform apply` completes without errors
- [ ] `crisis-dashboard` service deployed and publicly accessible
- [ ] Manual pipeline runs successfully with test date range
- [ ] Dashboard displays mock events after pipeline completes
- [ ] Dashboard API URL env var updated to real events-api endpoint
- [ ] Admin portal (`crisis-admin`) allows triggering annotator/extractor jobs
- [ ] Firestore events collection populated after extractor job runs

---

## Rollback (if needed)

To revert to job-to-job chaining:
```bash
git checkout HEAD -- main.tf Codebase_Container/FrontEnd_Dashboard/Dockerfile
terraform apply -auto-approve
```

---

## Next Steps (Not Yet Implemented)

1. **Dashboard HTML Enhancement:**
   - Add environment variable substitution for `EVENTS_API_URL` in `crisis-dashboard.html`
   - Currently uses placeholder; inject at runtime via nginx

2. **Events API Authentication:**
   - Consider adding authentication between dashboard and events-api (service-to-service auth)
   - Current config: public access both services

3. **Workflow Status Monitoring:**
   - Add Cloud Logging sink for workflow execution history
   - Implement alerting for failed pipeline stages

4. **Manual Stage Triggers:**
   - Implement Cloud Run service endpoints in `crisis-admin` to programmatically trigger annotator/extractor jobs
   - Ensure proper audit logging of human-approved transitions

---

## Files Modified

1. **[main.tf](main.tf)**
   - Removed: `google_cloud_run_v2_job_iam_member "crawler_triggers_cleaner"` (lines 476–484)
   - Added: `crisis-dashboard` service to `local.services` (lines 321–344)
   - Added: Explanatory comment for workflow-only orchestration

2. **[Codebase_Container/FrontEnd_Dashboard/Dockerfile](Codebase_Container/FrontEnd_Dashboard/Dockerfile)**
   - Added: Support for multiple static HTML files
   - Added: Environment variable `EVENTS_API_URL` with default fallback
   - Updated: nginx startup command with explicit daemon mode

---

## Support Commands

```bash
# View current dashboard service logs
gcloud run services logs read crisis-dashboard --region asia-southeast1 --limit 50

# View workflow execution history
gcloud workflows executions list --workflow daily-pipeline --location asia-southeast1

# Monitor Firestore writes
gcloud firestore documents list --collection events

# Redeploy specific service only
terraform apply -target="module.services[\"crisis-dashboard\"]"
```
