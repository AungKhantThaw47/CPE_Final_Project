# ✅ Single Command Deployment Ready

## 🚀 Deploy Now

```bash
cd /Users/akt/workspace/CPE_Final_Project
make deploy-all
```

That's it! No additional steps needed.

---

## What This Command Does

```
make deploy-all
    ↓
check-tools (verify terraform, gcloud, python3 installed)
    ↓
fmt (format all *.tf files)
    ↓
validate (check Terraform syntax)
    ↓
plan (create execution plan → tfplan)
    ↓
apply -auto-approve (deploy infrastructure)
    ↓
post-apply (run post-deployment scripts)
    ↓
output (display all service URLs)
    ↓
✅ DONE
```

---

## Expected Output

```
╔════════════════════════════════════════════════════════════════╗
║         🚀 DEPLOYING INFRASTRUCTURE (AUTO-APPROVE)            ║
╚════════════════════════════════════════════════════════════════╝

... (Terraform creates resources) ...

╔════════════════════════════════════════════════════════════════╗
║                    ✅ DEPLOYMENT COMPLETE                      ║
╚════════════════════════════════════════════════════════════════╝

📋 Deployment Summary:
════════════════════════════════════════════════════════════════
(JSON output of services, URLs, and configuration)

Next steps:
  1. Capture service URLs: make output
  2. Update dashboard API: see DEPLOYMENT_CHECKLIST.md
  3. Test pipeline: gcloud workflows run daily-pipeline --location asia-southeast1
```

---

## What Gets Deployed

| Component | Status | Details |
|-----------|--------|---------|
| **New:** crisis-dashboard | ✨ Added | Cloud Run Service with Leaflet.js frontend |
| **Updated:** Dashboard Dockerfile | ✨ Enhanced | Support for static assets + env var injection |
| **Removed:** crawler_triggers_cleaner IAM | ❌ Deleted | Job-to-job coupling eliminated |
| **8 Cloud Run Jobs** | ✅ Unchanged | Crawler, Cleaner, Classifier, Annotator, Extractor, etc. |
| **3 Cloud Run Services** | ✅ Unchanged | MLflow, Crisis-Admin, Events-API |
| **Firestore Database** | ✅ Unchanged | Events collection |
| **GCS Buckets** | ✅ Unchanged | Pipeline data + MLflow artifacts |
| **Cloud Workflows** | ✅ Unchanged | Daily + Manual pipelines |
| **Cloud Scheduler** | ✅ Unchanged | Daily trigger |

---

## Time Required

- **Total:** 5–10 minutes
  - Format/Validate/Plan: ~3 seconds
  - Infrastructure apply: ~4–9 minutes
  - Output display: ~1 second

---

## Prerequisites

Ensure these are set in your `.env` file or as environment variables:

```bash
TF_VAR_project_id="cpe-final-project"
TF_VAR_region="asia-southeast1"
TF_VAR_neo4j_uri="bolt://your-host:7687"
TF_VAR_neo4j_user="your-user"
TF_VAR_neo4j_password="your-password"
TF_VAR_neo4j_database="neo4j"
TF_VAR_hf_token="your-hf-token"
TF_VAR_gemini_api_key="your-gemini-key"
TF_VAR_daily_notify_email="your-email@example.com"
TF_VAR_notify_webhook_url="https://your-webhook"
```

---

## Post-Deployment Steps

After `make deploy-all` completes successfully:

### 1. **Update Dashboard API URL**
```bash
# Get the events-api URL
EVENTS_API_URL=$(terraform output -json services | jq -r '.events_api.public_url')

# Update dashboard service
gcloud run services update crisis-dashboard \
  --set-env-vars EVENTS_API_URL="${EVENTS_API_URL}/events" \
  --region asia-southeast1 \
  --project cpe-final-project
```

### 2. **Test the Workflow**
```bash
gcloud workflows run daily-pipeline \
  --location asia-southeast1 \
  --project cpe-final-project
```

### 3. **View Deployed Services**
```bash
# Get all URLs
make output

# Or direct commands
terraform output -json services | jq '.crisis_dashboard.public_url'
terraform output -json services | jq '.events_api.public_url'
```

### 4. **Access Dashboard**
```bash
DASHBOARD_URL=$(terraform output -json services | jq -r '.crisis_dashboard.public_url')
open "$DASHBOARD_URL"  # macOS
xdg-open "$DASHBOARD_URL"  # Linux
start "$DASHBOARD_URL"  # Windows
```

---

## Verify Deployment

```bash
# Check Cloud Run Services
gcloud run services list --region asia-southeast1

# Check Firestore
gcloud firestore databases list

# Check GCS Buckets
gsutil ls

# Check workflow definitions
gcloud workflows list --location asia-southeast1

# View service logs
gcloud run services logs read crisis-dashboard --limit 50
gcloud run services logs read events-api --limit 50
```

---

## If Something Goes Wrong

### Option 1: Clean Rollback
```bash
git checkout HEAD -- main.tf Codebase_Container/FrontEnd_Dashboard/Dockerfile
make deploy-all
```

### Option 2: Destroy Everything & Redeploy
```bash
make destroy AUTO_APPROVE=true
make deploy-all
```

### Option 3: Fix & Retry
```bash
# Fix the issue, then
make deploy-all
```

---

## Alternative: Step-by-Step Deployment

If you prefer to see each step:

```bash
make check-tools    # ~2 seconds
make fmt            # ~1 second
make validate       # ~2 seconds
make plan           # ~10 seconds (review changes)
make deploy         # ~5-9 minutes (apply)
make output         # Display results
```

---

## Files Modified

- ✅ [Makefile](Makefile) — Added `deploy-all` target
- ✅ [main.tf](main.tf) — Crisis-dashboard service + removed job-chaining IAM
- ✅ [Codebase_Container/FrontEnd_Dashboard/Dockerfile](Codebase_Container/FrontEnd_Dashboard/Dockerfile) — Enhanced for static assets
- ✅ [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) — Full deployment guide
- ✅ [DEPLOY_SINGLE_COMMAND.md](DEPLOY_SINGLE_COMMAND.md) — Single command guide
- ✅ [IMPLEMENTATION_CHANGES.md](IMPLEMENTATION_CHANGES.md) — Technical details of changes

---

## Summary

| Before | After |
|--------|-------|
| Complex multi-step deployment | ✨ Single command: `make deploy-all` |
| No dashboard service | ✨ Crisis-dashboard deployed |
| Redundant job-chaining IAM | ✅ Removed (workflows orchestrate) |
| Manual variable tracking | ✅ Automated via Makefile |

---

## Ready to Deploy?

```bash
cd /Users/akt/workspace/CPE_Final_Project
make deploy-all
```

**Enjoy! 🎉**
