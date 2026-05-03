# Quick Start: Deploy Updated Infrastructure

## Pre-Deployment Checklist

- [x] Terraform syntax validated ✓
- [ ] `.env` file configured with required variables
- [ ] GCP credentials authenticated (`gcloud auth application-default login`)
- [ ] terraform.tfvars configured or environment variables set

## Required Environment Variables

```bash
# Copy to .env or set directly
export TF_VAR_project_id="cpe-final-project"
export TF_VAR_region="asia-southeast1"
export TF_VAR_neo4j_uri="bolt://your-neo4j-host:7687"
export TF_VAR_neo4j_user="your-neo4j-user"
export TF_VAR_neo4j_password="your-neo4j-password"
export TF_VAR_neo4j_database="neo4j"
export TF_VAR_hf_token="your-huggingface-token"
export TF_VAR_gemini_api_key="your-gemini-api-key"
export TF_VAR_daily_notify_email="your-email@example.com"
export TF_VAR_notify_webhook_url="https://your-webhook-url"
```

## Deployment Commands

### 1. Initialize Terraform (first time only)
```bash
cd /Users/akt/workspace/CPE_Final_Project
terraform init
```

### 2. Plan Infrastructure Changes
```bash
# Review what will be created/modified
terraform plan -out tfplan
```

**Expected output:**
- Adding Cloud Run service: `crisis-dashboard`
- Removing IAM resource: `crawler_triggers_cleaner`
- No changes to jobs or other services

### 3. Apply Changes
```bash
# Option A: Interactive approval
terraform apply tfplan

# Option B: Auto-approve (CI/CD)
terraform apply -auto-approve tfplan
```

**Expected duration:** 5–10 minutes

### 4. Capture Output URLs

After apply succeeds:
```bash
# Get all service URLs
terraform output services

# Extract just the dashboard URL
terraform output -json services | jq '.crisis-dashboard.public_url'
terraform output -json services | jq '.events-api.public_url'
```

Save these URLs — you'll need them for the next step.

---

## Post-Deployment Configuration

### Step 1: Update Dashboard API Endpoint

Replace `PLACEHOLDER` with actual events-api URL:

```bash
# Get the actual events-api URL
EVENTS_API_URL=$(terraform output -json services | jq -r '.events_api.public_url')
echo "Events API URL: ${EVENTS_API_URL}/events"

# Update dashboard environment variable
gcloud run services update crisis-dashboard \
  --set-env-vars EVENTS_API_URL="${EVENTS_API_URL}/events" \
  --region asia-southeast1 \
  --project cpe-final-project
```

### Step 2: Verify Dashboard is Live

```bash
# Get dashboard URL
DASHBOARD_URL=$(terraform output -json services | jq -r '.crisis_dashboard.public_url')
echo "Dashboard: $DASHBOARD_URL"

# Test with curl
curl -s "$DASHBOARD_URL" | head -20

# Or open in browser
open "$DASHBOARD_URL"
```

### Step 3: Test Daily Pipeline Trigger

```bash
# Execute the workflow (simulates scheduler)
gcloud workflows run daily-pipeline \
  --project cpe-final-project \
  --location asia-southeast1

# Monitor execution
gcloud workflows executions list \
  --workflow daily-pipeline \
  --location asia-southeast1 \
  --limit 1
```

### Step 4: Verify Pipeline Completes

Monitor logs:
```bash
# Watch crawler job
gcloud run jobs logs read dvb-crawler-job \
  --limit 50 \
  --region asia-southeast1

# Check Cloud Logging for workflow status
gcloud logging read \
  'resource.type="cloud_workflows" AND resource.labels.workflow_name="daily-pipeline"' \
  --limit 20 \
  --format=json | jq '.[] | {timestamp: .timestamp, message: .textPayload}'
```

### Step 5: Verify Firestore Population

After pipeline completes (~30–40 min):
```bash
# List events in Firestore
gcloud firestore documents list \
  --collection events \
  --project cpe-final-project

# Or from gcloud console
open "https://console.cloud.google.com/firestore/data/events?project=cpe-final-project"
```

### Step 6: Test Dashboard Display

1. Visit dashboard URL (from Step 2)
2. Wait for page to load (Leaflet map should appear)
3. If events are in Firestore, map markers should display
4. Test clicking markers to view event details

---

## Troubleshooting

### Dashboard Service Not Deploying

```bash
# Check for build errors
gcloud builds log <BUILD_ID> --stream

# Manually rebuild image
docker build -t crisis-dashboard Codebase_Container/FrontEnd_Dashboard/
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/crisis-dashboard:latest
```

### Events API Not Accessible from Dashboard

```bash
# Check if events-api service exists
gcloud run services list --region asia-southeast1

# Check events-api logs for errors
gcloud run services logs read events-api --limit 50

# Test API directly
curl https://events-api-xxxxx-xx.a.run.app/events
```

### Workflow Not Running

```bash
# Check workflow definition
gcloud workflows describe daily-pipeline --location asia-southeast1

# Manually trigger and monitor
gcloud workflows run daily-pipeline --location asia-southeast1
gcloud workflows executions describe <EXECUTION_ID> --workflow daily-pipeline --location asia-southeast1
```

### Firestore Events Not Populating

```bash
# Check extractor job logs
gcloud run jobs logs read dvb-extractor-job --limit 100

# Verify extractor has datastore.user role
gcloud projects get-iam-policy cpe-final-project \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/datastore.user"
```

---

## Rollback

If any issues arise, revert changes:

```bash
# Option 1: Destroy and re-apply previous version
git checkout HEAD~1 -- main.tf
terraform apply -auto-approve

# Option 2: Destroy just the dashboard service
terraform destroy -target='module.services["crisis-dashboard"]'
```

---

## Summary of Architecture Changes

| Component | Before | After | Status |
|-----------|--------|-------|--------|
| Orchestration | Job-to-job chaining + Workflows (redundant) | Workflows only (single source of truth) | ✅ Simplified |
| Dashboard Service | Missing (not deployed) | Nginx serving static assets on port 8080 | ✅ Added |
| IAM Coupling | Tight (jobs interdependent) | Loose (jobs independent, workflow orchestrates) | ✅ Improved |
| Frontend Access | None (no service deployed) | Public HTTPS endpoint | ✅ Enabled |
| API Integration | N/A | Dashboard queries events-api for real-time updates | ✅ Connected |

---

## Next Validation Steps

After successful deployment:

1. [ ] Dashboard accessible at public URL
2. [ ] Workflow executes without errors
3. [ ] Firestore events populated after extractor run
4. [ ] Dashboard displays events on map
5. [ ] Admin portal can trigger annotator/extractor jobs

---

**For detailed implementation notes, see:** [IMPLEMENTATION_CHANGES.md](IMPLEMENTATION_CHANGES.md)
