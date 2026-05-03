# CPE Final Project — Conclusion Report

**Project:** CPE Senior Project — DVB Burmese Crisis News Pipeline  
**Platform:** Google Cloud Platform (asia-southeast1)  
**Infrastructure:** Terraform + Cloud Run Jobs + Cloud Workflows  
**Report Date:** 2026-05-02

---

## 1. Project Overview

This system is an automated pipeline that collects, cleans, classifies, and extracts structured event data from DVB (Democratic Voice of Burma) Burmese-language news articles. The output feeds a crisis monitoring dashboard for human review and downstream analysis.

The pipeline runs daily via Cloud Scheduler and can also be triggered manually for custom date ranges. All infrastructure is defined as code in Terraform and deployed to GCP.

---

## 2. System Architecture

### 2.1 Infrastructure Components

| Component | Technology | Purpose |
|---|---|---|
| Cloud Run Jobs | Node.js / Python | All compute workloads |
| Cloud Run Services | Python Flask / FastAPI | Admin portal, Events API, MLflow |
| Cloud Workflows | GCP Workflows YAML | Orchestrates job sequencing |
| Cloud Scheduler | Cron | Triggers daily pipeline at 05:00 Bangkok time |
| GCS Bucket (`pipeline-data`) | Google Cloud Storage | All intermediate and final data |
| GCS Bucket (`mlflow-artifacts`) | Google Cloud Storage | ML experiment artifacts |
| Artifact Registry | Docker | Container image storage |
| Firestore | GCP Firestore (Native) | Structured event records |
| MLflow | Cloud Run Service | Experiment tracking |
| Neo4j (AuraDB) | Graph Database | System topology and version tracking |
| Terraform | IaC | Entire infrastructure definition |
| GitHub Actions | CI/CD | Automated deploy on push to main |

### 2.2 GCS Data Layout

Data flows through versioned folder paths in `pipeline-data`. Each job writes under its own `CONTENT_HASH` (a SHA-256 of its container image, injected by Terraform at deploy time):

```
pipeline-data/
├── dvb/links-manifests/{date}/         ← coordinator manifests (unversioned)
│   └── links-manifest.json             ← pre-discovered article links
├── dvb/{CRAWLER_HASH}/{date}/          ← raw articles (crawler writes, versioned)
│   ├── DVB_Burmese_{date}.json         ← article metadata + links
│   ├── DVB_{date}_{content_hash}.txt   ← article full text
│   └── processed/{md5}.json            ← dedup markers
├── dvb_cleaned/{date}/                 ← cleaned text (text-cleaner writes)
├── pending_review/{date}/              ← classified articles (crisis-classifier writes)
├── crisis_articles/{date}/             ← human-reviewed articles (crisis-admin writes)
├── pending_review_annotation/{date}/   ← annotated articles (annotator writes)
├── annotated_articles/{date}/          ← final annotations (annotator writes)
└── events/{date}/                      ← extracted events (extractor writes)
```

---

## 3. Pipeline Flows

### 3.1 Daily Pipeline (Automated)

Triggered by Cloud Scheduler every day at 05:00 (Asia/Bangkok). Orchestrated by `workflow.yaml` (Cloud Workflows).

```
Cloud Scheduler
    └─► Cloud Workflow: daily-pipeline
            ├─► [1] dvb-crawler-job      — scrapes yesterday's DVB articles, uploads raw text + metadata to GCS
            ├─► [2] dvb-text-cleaner-job — reads dvb/, removes author names, writes dvb_cleaned/
            └─► [3] crisis-classifier-job — reads dvb_cleaned/, classifies for crisis relevance, writes pending_review/
                    └─► Webhook notification on completion
```

In this path the crawler runs independently: it traverses DVB listing pages, fetches article content, and triggers the text cleaner directly after saving each date's output.

### 3.2 Manual Pipeline (Backfill / Date Range)

Triggered by calling `manual_workflow.yaml` with `crawl_start_date` and `crawl_end_date` arguments (DD-MM-YYYY). Same sequence as daily, but the crawler receives `START_DATE` / `END_DATE` env vars and processes the full specified range.

```
Manual trigger (gcloud / admin)
    └─► Cloud Workflow: manual-pipeline
            ├─► [1] dvb-crawler-job      (with START_DATE, END_DATE overrides)
            ├─► [2] dvb-text-cleaner-job (with PROCESS_DATE override)
            └─► [3] crisis-classifier-job (with PROCESS_DATE override)
```

### 3.3 Coordinator Path (Bulk Backfill via Coordinator)

Used when a human operator needs to backfill a large date range. Triggered via `scripts/run_daily_pipeline.py` or directly with `gcloud run jobs execute dvb-coordinator-job`.

```
run_daily_pipeline.py  (or gcloud CLI)
    └─► dvb-coordinator-job (unversioned)
            ├── Scrapes DVB listing pages for the full date range (link discovery only)
            ├── Writes per-date links-manifest.json to static path:
            │       dvb/links-manifests/{date}/links-manifest.json
            └── Spawns ONE dvb-crawler-job with:
                    CRAWL_START_DATE, CRAWL_END_DATE, LINKS_MANIFEST_PREFIX=dvb/links-manifests
                    └─► dvb-crawler-job (versioned under CRAWLER_HASH)
                            ├── Reads links-manifest.json (skips link traversal)
                            ├── Fetches article content directly
                            ├── Writes articles under its own CONTENT_HASH (dvb/{CRAWLER_HASH}/...)
                            └── Triggers dvb-text-cleaner-job for each processed date
```

### 3.4 Admin Review Pipeline (Human-in-the-loop)

After the daily pipeline completes, human reviewers use the crisis-admin portal to:

```
crisis-admin (Flask portal)
    ├── Reviews articles in pending_review/
    ├── Approves → moves to crisis_articles/
    └── Triggers:
            ├─► dvb-annotator-job     — Gemini API annotation → annotated_articles/
            └─► dvb-extractor-job     — Gemini event extraction → events/ + Firestore
```

The `events-api` Cloud Run Service exposes a read endpoint over Firestore for the frontend dashboard.

---

## 4. Cloud Run Jobs Inventory

| Job Name | Runtime | CPU | Memory | Timeout | Trigger |
|---|---|---|---|---|---|
| `dvb-coordinator-job` | Node.js 20 | 1 | 512Mi | 1800s | Manual / run_daily_pipeline.py |
| `dvb-crawler-job` | Node.js 20 | 2 | 512Mi | 1200s | Workflow / Coordinator |
| `dvb-text-cleaner-job` | Python | 1 | 512Mi | 600s | Workflow / Crawler (inline) |
| `crisis-classifier-job` | Python + HuggingFace | 4 | 16Gi | 3600s | Workflow |
| `dvb-annotator-job` | Python + Gemini | 1 | 512Mi | 600s | crisis-admin portal |
| `dvb-extractor-job` | Python + Gemini | 1 | 512Mi | 600s | crisis-admin portal |
| `gcs-folder-rename-job` | Python | 1 | 512Mi | — | Manual |

Cloud Run Services: `crisis-admin` (Flask), `events-api` (FastAPI/Flask), `mlflow` (MLflow tracking server).

---

## 5. Coordinator / Crawler Separation — Implementation

### 5.1 Rationale

The original crawler performed both link discovery (traversing DVB listing pages) and content fetching in a single job. For large date-range backfills this created hundreds of parallel executions and no clean handoff point.

The coordinator was introduced to separate these responsibilities:

- **Coordinator** — Link discovery only. Traverses DVB listing pages once for the full date range, writes a manifest of discovered article URLs to GCS, then spawns exactly one crawler sub-job.
- **Crawler** — Content fetching only (when driven by coordinator). Reads the pre-built manifest from GCS and fetches article content directly without re-traversing listing pages.

### 5.2 Backward Compatibility

The crawler detects which mode to run in by checking for the `LINKS_MANIFEST_PREFIX` environment variable:

```javascript
// crawler: loadArticlesFromManifests()
async function loadArticlesFromManifests() {
    const manifestPrefix = process.env.LINKS_MANIFEST_PREFIX || "";
    if (!manifestPrefix || !GCS_BUCKET || !gcsStorage) return null;
    // ... reads per-date links-manifest.json from GCS
    // returns null if any date's manifest is missing → falls back to scraping
}
```

| Path | LINKS_MANIFEST_PREFIX set? | Crawler behavior |
|---|---|---|
| Daily workflow | No | Normal scraping (scrapePage) |
| Manual workflow | No | Normal scraping with date range |
| Coordinator path | Yes | Reads manifests, skips link traversal |

No changes were needed to the daily or manual workflow YAML files.

### 5.3 Version Tracking Preservation (CONTENT_HASH)

Each job has a `CONTENT_HASH` injected by Terraform — a SHA-256 hash of the job's container image. This is used as a folder prefix in GCS so the text cleaner can look up the correct input path from Neo4j.

A critical constraint when the coordinator spawns the crawler: the coordinator must **not** pass its own `CONTENT_HASH` to the crawler. The text cleaner queries Neo4j for `job:dvb-crawler-job`'s hash to find article data. If the crawler wrote files under the coordinator's hash, the text cleaner would look in the wrong GCS prefix.

The coordinator passes only `LINKS_MANIFEST_PREFIX=dvb/{COORDINATOR_HASH}` so the crawler can find the manifests. The crawler retains its own Terraform-injected `CONTENT_HASH` for article output.

```javascript
// coordinator: spawnCrawlerJob()
env: [
    { name: "CRAWL_START_DATE",      value: startStr },
    { name: "CRAWL_END_DATE",        value: endStr },
    { name: "LINKS_MANIFEST_PREFIX", value: `dvb/${CONTENT_HASH}` }, // coordinator's hash — manifest path only
    { name: "GCS_BUCKET",            value: GCS_BUCKET || "" },
    { name: "GCP_REGION",            value: GCP_REGION },
    // CONTENT_HASH intentionally NOT overridden — crawler keeps its own Terraform-injected value
]
```

### 5.4 Container Structure

Each job is in its own folder with its own `Dockerfile`, `package.json`, and `cloudbuild.yaml`. Both jobs share the `utils/` directory (GCS utilities) which is copied into each container at build time.

```
Codebase_Container/
├── coordinator_job/
│   ├── DVB_Burmese.coordinator.js
│   ├── Dockerfile
│   ├── package.json
│   └── cloudbuild.yaml
└── crawler_job/
    ├── DVB_Burmese.crawler.js
    ├── Dockerfile
    ├── package.json
    └── cloudbuild.yaml
```

---

## 6. Neo4j Graph — System Topology

Neo4j (AuraDB) stores the system topology as a property graph. Two categories of nodes coexist:

- **SystemNodes** — static infrastructure (jobs, services, buckets, workflows, scheduler). Defined in `bootstrap/neo4j/graph_manifest.json` and loaded by `bootstrap/neo4j/load_graph.py`.
- **FolderHash / DeploymentHash nodes** — dynamic versioning nodes generated at deploy time by `scripts/terraform_post_action.py`. Track which container hash wrote which GCS folder, enabling the `DERIVED_FROM` chain.

### 6.1 Key Relationships for the DVB Pipeline

```
scheduler:daily-pipeline-trigger
    --[TRIGGERS]--> workflow:daily-pipeline
        --[ORCHESTRATES step 1]--> job:dvb-crawler-job
        --[ORCHESTRATES step 2]--> job:dvb-text-cleaner-job
        --[ORCHESTRATES step 3]--> job:crisis-classifier-job

workflow:manual-pipeline
    --[ORCHESTRATES step 1]--> job:dvb-crawler-job
    --[ORCHESTRATES step 2]--> job:dvb-text-cleaner-job
    --[ORCHESTRATES step 3]--> job:crisis-classifier-job

job:dvb-coordinator-job
    --[SPAWNS]-->             job:dvb-crawler-job
    --[WRITES_TO]-->          bucket:pipeline-data  (path: dvb/links-manifests/)
    <--[FEEDS]--              source:dvb-news
    <--[RUNS]--               project:cpe-final-project
    <--[HOSTS_IMAGE_FOR]--    registry:artifact-registry

job:dvb-crawler-job
    --[WRITES_TO]-->          bucket:pipeline-data  (path: dvb/)
    <--[FEEDS]--              source:dvb-news
```

### 6.2 DERIVED_FROM Chain (Version Lineage)

The text cleaner creates a `DERIVED_FROM` edge in Neo4j whenever it processes a new batch. This chain tracks data lineage from raw DVB articles through to final extracted events:

```
dvb/ (FolderHash)
    ←[DERIVED_FROM]── dvb_cleaned/ (FolderHash)
        ←[DERIVED_FROM]── pending_review/ (FolderHash)
            ←[DERIVED_FROM]── crisis_articles/ (FolderHash) × N (one per reviewed batch)
                ←[DERIVED_FROM]── pending_review_annotation/ (FolderHash)
                    ←[DERIVED_FROM]── annotated_articles/ (FolderHash)
                        ←[DERIVED_FROM]── events/ (FolderHash)
```

Each `FolderHash` node carries the folder hash value, update timestamp, and the job that produced it (via `PRODUCED_BY` → `DeploymentHash`).

### 6.3 Graph Verification Results (2026-05-02)

After cleanup, all checks pass:

| Check | Result |
|---|---|
| Null-key FolderHash nodes | 0 (cleaned) |
| All 11 expected SystemNodes present | ✓ |
| `SPAWNS`: coordinator → crawler | ✓ |
| `ORCHESTRATES` chains (daily + manual) | ✓ |
| `DEPENDS_ON_DATA_FROM` → coordinator | None ✓ |
| `DERIVED_FROM` chain integrity | ✓ |

---

## 7. Files Created / Modified in This Work Session

### New Files

| File | Description |
|---|---|
| `Codebase_Container/coordinator_job/DVB_Burmese.coordinator.js` | Coordinator job — link discovery + spawns one crawler sub-job |
| `Codebase_Container/coordinator_job/Dockerfile` | Container definition for coordinator |
| `Codebase_Container/coordinator_job/package.json` | Node.js dependencies (axios, cheerio, @google-cloud/storage, dotenv) |
| `Codebase_Container/coordinator_job/cloudbuild.yaml` | Cloud Build pipeline for coordinator image |
| `Codebase_Container/coordinator_job/.dockerignore` | Docker build exclusions |
| `scripts/run_daily_pipeline.py` | Trigger coordinator for a date range from local machine |
| `scripts/check_neo4j.py` | Neo4j graph health check script |
| `scripts/cleanup_neo4j.py` | One-off cleanup of stale Neo4j edges |
| `scripts/cancel_all_executions.sh` | One-off script to cancel all running Cloud Run executions |

### Modified Files

| File | Change |
|---|---|
| `Codebase_Container/crawler_job/DVB_Burmese.crawler.js` | Added `loadArticlesFromManifests()`, `run()` entry point with manifest-or-scrape branching; reverted Dockerfile ENTRYPOINT |
| `Codebase_Container/crawler_job/Dockerfile` | ENTRYPOINT restored to `["node", "DVB_Burmese.crawler.js"]` |
| `bootstrap/neo4j/graph_manifest.json` | Added `job:dvb-coordinator-job` node and all its relationships; fixed coordinator WRITES_TO path from `dvb/` to `dvb/links-manifests/` |
| `main.tf` | Added `dvb-coordinator-job` resource block (1 CPU, 512Mi, 1800s, `run.invoker` role) |
| `scripts/terraform_post_action.py` | Added `spawner_jobs` exclusion set in both inference functions to prevent coordinator from generating spurious `DEPENDS_ON_DATA_FROM` edges to downstream jobs |

---

## 8. Issues Encountered and Resolved

### Issue 1 — Coordinator missing from Neo4j graph

**Symptom:** `make post-apply` failed with `Relationship source not found: job:dvb-coordinator-job`.  
**Cause:** `terraform_post_action.py` tried to create a `HAS_HASH` relationship for the coordinator but the base node did not exist in `graph_manifest.json`.  
**Fix:** Added the `job:dvb-coordinator-job` SystemNode and all its relationships to `graph_manifest.json`.

### Issue 2 — Wrong CONTENT_HASH passed to crawler

**Symptom:** If coordinator passed `CONTENT_HASH` to the crawler override, the text cleaner (which queries Neo4j for `job:dvb-crawler-job`'s hash) would look in the wrong GCS prefix.  
**Cause:** Early implementation of `spawnCrawlerJob()` included `CONTENT_HASH` in the container env overrides.  
**Fix:** Removed `CONTENT_HASH` from the env overrides. Added `LINKS_MANIFEST_PREFIX=dvb/${CONTENT_HASH}` (coordinator's own hash) instead, so the crawler can find manifests without changing its article output path.

### Issue 3 — One coordinator spawned per article

**Symptom:** `scripts/run_daily_pipeline.py` was spawning one coordinator execution per article, generating hundreds of Cloud Run executions.  
**Cause:** The script was written to loop per-day and spawn one coordinator per day; the coordinator was also spawning one crawler per article.  
**Fix:** Refactored both: `run_daily_pipeline.py` now fires one coordinator for the entire date range; the coordinator discovers all links for all dates first, saves manifests, then spawns exactly one crawler sub-job.

### Issue 4 — Stale Cloud Run executions blocking quota

**Symptom:** Hundreds of executions from previous test runs were still running or pending.  
**Fix:** Created and ran `scripts/cancel_all_executions.sh` to cancel all executions via `gcloud run jobs executions cancel`. Required a clean WSL environment (`env -i HOME=/home/mma PATH=...`) to avoid Git Bash path expansion issues.

### Issue 5 — Spurious DEPENDS_ON_DATA_FROM edges in Neo4j

**Symptom:** `check_neo4j.py` showed five downstream jobs (`dvb-text-cleaner-job`, `crisis-classifier-job`, `dvb-annotator-job`, `dvb-extractor-job`, `service:crisis-admin`) with `DEPENDS_ON_DATA_FROM → job:dvb-coordinator-job`. These were incorrect — the coordinator is not a data source for any of these jobs.  
**Cause:** `terraform_post_action.py` uses a bucket-level cross-product inference to generate `DEPENDS_ON_DATA_FROM` edges: all readers of `bucket:pipeline-data` were connected to all writers, including coordinator. Coordinator's `WRITES_TO` path (`dvb/`) overlapped with the path downstream jobs read from.  
**Fix:**
1. Changed coordinator's `WRITES_TO` path in `graph_manifest.json` from `"dvb/"` to `"dvb/links-manifests/"` to reflect that it only writes link manifests, not article data.
2. In `terraform_post_action.py`, introduced a `spawner_jobs` set (jobs that appear as the `from` of a `SPAWNS` relationship) and excluded spawner jobs from the `writers_by_bucket` map used in the bucket-level inference. Applied to both inference functions.
3. Deleted the 5 stale edges from Neo4j directly via Cypher query.

### Issue 6 — Null-key FolderHash nodes

**Symptom:** 2 `FolderHash` nodes had no `key` property, causing the `check_neo4j.py` format string to crash and polluting the graph.  
**Cause:** A stale `dvb/` FolderHash node was created without a key at some prior deploy point (pre-existing bug now fixed in `terraform_post_action.py`).  
**Fix:** Deleted with `MATCH (n:FolderHash) WHERE n.key IS NULL DETACH DELETE n`. The `DERIVED_FROM` edge from `dvb_cleaned/` back to `dvb/` was also removed as it depended on the corrupt node; it will regenerate correctly on the next crawler run.

---

## 9. How to Run the Pipeline

### Daily Pipeline (runs automatically)
No action needed. Cloud Scheduler fires at 05:00 Bangkok time daily.

### Manual Backfill via Workflow
```bash
gcloud workflows run manual-pipeline \
  --location=asia-southeast1 \
  --data='{"crawl_start_date":"01-01-2026","crawl_end_date":"31-01-2026"}'
```

### Manual Backfill via Coordinator (large ranges)
```bash
# From local machine (requires gcloud auth)
python3 scripts/run_daily_pipeline.py 01-01-2026 31-01-2026
```

### Check Neo4j Graph Health
```bash
python3 scripts/check_neo4j.py
```

### Cancel All Running Executions
```bash
# From Linux / WSL
bash scripts/cancel_all_executions.sh
```

---

## 10. Current System State (2026-05-02)

- All Cloud Run jobs deployed and registered in Artifact Registry.
- Neo4j graph is clean: all 11 expected SystemNodes present, SPAWNS and ORCHESTRATES relationships correct, no stale DEPENDS_ON_DATA_FROM edges targeting coordinator, no null-key nodes.
- Daily pipeline operational.
- Coordinator/crawler split functional; backward compatibility with daily/manual workflows maintained.
- Version tracking (CONTENT_HASH / DERIVED_FROM chain) intact.
- All previously running executions cancelled.
