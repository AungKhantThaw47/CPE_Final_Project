# 🚀 Single Command Deployment

## Quick Start

**Deploy everything with one command:**

```bash
cd /Users/akt/workspace/CPE_Final_Project
make deploy-all
```

That's it! This single command handles:

1. ✅ **check-tools** — Verify terraform, gcloud, python3 are installed
2. ✅ **fmt** — Format all Terraform files
3. ✅ **validate** — Validate Terraform configuration syntax
4. ✅ **plan** — Create execution plan (tfplan)
5. ✅ **apply** — Auto-approve and apply changes
6. ✅ **post-apply** — Generate deployment summary
7. ✅ **output** — Display service URLs and configuration

---

## What Gets Deployed

**New/Updated:**
- ✨ `crisis-dashboard` Cloud Run Service (Leaflet.js frontend)
- ✨ Dashboard Dockerfile with static asset serving

**Removed:**
- ❌ Job-to-job chaining IAM (`crawler_triggers_cleaner`)

**Existing (Unchanged):**
- 8 Cloud Run Jobs
- 2 Cloud Run Services (mlflow, crisis-admin, events-api)
- Firestore database
- GCS buckets
- Cloud Workflows (daily + manual)
- Cloud Scheduler

---

## After Deployment

The command output will show:

```
╔════════════════════════════════════════════════════════════════╗
║         🚀 DEPLOYING INFRASTRUCTURE (AUTO-APPROVE)            ║
╚════════════════════════════════════════════════════════════════╝

... (Terraform applies changes) ...

╔════════════════════════════════════════════════════════════════╗
║                    ✅ DEPLOYMENT COMPLETE                      ║
╚════════════════════════════════════════════════════════════════╝

📋 Deployment Summary:
════════════════════════════════════════════════════════════════
(JSON output of all services and URLs)

Next steps:
  1. Capture service URLs: make output
  2. Update dashboard API: see DEPLOYMENT_CHECKLIST.md
  3. Test pipeline: gcloud workflows run daily-pipeline --location asia-southeast1
```

---

## Common Options

**If you only have environment variables (no terraform.tfvars):**
```bash
# Just run it — make will use .env and TF_VAR_* env vars
make deploy-all
```

**If you need to use a different var file:**
```bash
make deploy-all TF_VARS_FILE=my-custom.tfvars
```

**If you need a different environment file:**
```bash
make deploy-all ENV_FILE=production.env
```

---

## Troubleshooting

**If checks fail:**
```bash
# Manually verify tools
which terraform gcloud python3

# Or run check only
make check-tools
```

**If validation fails:**
```bash
# Review errors
make validate
```

**If apply fails:**
```bash
# See the plan that was generated
cat tfplan

# Or re-run just planning
make plan
```

**To see all logs from previous deployment:**
```bash
make output
```

---

## Alternative: Interactive Mode

If you prefer step-by-step execution:

```bash
make check-tools    # Verify tools
make fmt            # Format code
make validate       # Validate
make plan           # Review plan
make deploy         # Apply (interactive approval)
```

Or use:
```bash
make deploy AUTO_APPROVE=false  # Manual approval at apply step
```

---

## Comparison

| Command | What It Does |
|---------|-------------|
| `make deploy-all` | ✅ Everything (fmt → validate → plan → apply) |
| `make deploy` | Plan + Apply (needs AUTO_APPROVE) |
| `make apply` | Just apply existing tfplan |
| `make plan` | Just create tfplan |
| `make validate` | Just check syntax |

---

## What if deployment fails?

### Option 1: Rollback via git
```bash
git checkout HEAD -- main.tf Codebase_Container/FrontEnd_Dashboard/Dockerfile
make deploy-all
```

### Option 2: Destroy and retry
```bash
make destroy AUTO_APPROVE=true
make deploy-all
```

### Option 3: Fix and retry
```bash
# Fix the issue, then
make deploy-all
```

---

## Environment Variables Needed

Before running `make deploy-all`, ensure these are set in `.env`:

```bash
TF_VAR_project_id="cpe-final-project"
TF_VAR_region="asia-southeast1"
TF_VAR_neo4j_uri="bolt://..."
TF_VAR_neo4j_user="..."
TF_VAR_neo4j_password="..."
TF_VAR_hf_token="..."
TF_VAR_gemini_api_key="..."
TF_VAR_daily_notify_email="..."
TF_VAR_notify_webhook_url="..."
```

---

## Detailed Deployment Flow

```
User: make deploy-all
         │
         ├─→ check-tools (verify terraform, gcloud, python3)
         │
         ├─→ fmt (format *.tf files)
         │
         ├─→ validate (check syntax)
         │
         ├─→ plan (create tfplan)
         │   └─→ init (if needed)
         │
         ├─→ apply -auto-approve (execute tfplan)
         │
         ├─→ post-apply (run terraform_post_action.sh)
         │
         ├─→ output -json (display services/URLs)
         │
         └─→ ✅ DONE
```

---

## After Successful Deployment

1. **Check output:**
   ```bash
   make output
   ```

2. **Update dashboard API URL** (see DEPLOYMENT_CHECKLIST.md):
   ```bash
   EVENTS_API_URL=$(terraform output -json services | jq -r '.events_api.public_url')
   gcloud run services update crisis-dashboard \
     --set-env-vars EVENTS_API_URL="${EVENTS_API_URL}/events"
   ```

3. **Test the pipeline:**
   ```bash
   gcloud workflows run daily-pipeline --location asia-southeast1
   ```

4. **View dashboard:**
   ```bash
   DASHBOARD_URL=$(terraform output -json services | jq -r '.crisis_dashboard.public_url')
   open "$DASHBOARD_URL"
   ```

---

## Time Estimate

- **Total deployment time:** 5–10 minutes
  - Format: ~1s
  - Validate: ~2s
  - Plan: ~10s
  - Apply: ~4–9 min (Docker builds, service creation)

---

That's it! 🎉 One command deploys your entire infrastructure.
