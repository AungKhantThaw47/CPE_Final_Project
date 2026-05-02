# Chapter 4: Implementation

## 4.1 System Overview

This chapter describes the implementation of an automated Myanmar crisis event monitoring system that transforms raw Burmese-language news articles into structured, geolocated crisis event records displayed on an interactive web dashboard. The system is implemented as a seven-stage data pipeline deployed entirely on Google Cloud Platform (GCP), with each stage containerised as an independent Docker-based Cloud Run service or job.

The pipeline is designed around three core principles. First, full automation: once deployed, the system operates daily without any manual triggering, driven by Cloud Scheduler and event-based triggers via Google Eventarc. Second, human-in-the-loop quality control: a human analyst reviews machine-generated classifications and annotations before they proceed to downstream stages, ensuring data quality. Third, infrastructure-as-code reproducibility: all cloud resources are managed by Terraform, and all container images are built and versioned using SHA-256 content hashing to ensure deterministic, reproducible deployments.

The overall data flow is illustrated in Figure 4.1. Raw articles are crawled from the Democratic Voice of Burma (DVB) Burmese-language news portal, cleaned, classified by a machine learning model, reviewed by a human analyst, annotated and structured by a large language model (LLM), and finally visualised on an interactive geospatial dashboard.

```
DVB Burmese News
      │
      ▼
[Stage 1] Crawler          — Node.js, Cloud Scheduler (daily midnight)
      │  GCS: dvb/{hash}/{date}/
      ▼
[Stage 2] Text Cleaner     — Python, Cloud Run Job
      │  GCS: dvb_cleaned/{hash}/{date}/
      ▼
[Stage 3] Crisis Classifier — Python, Gemma-300M + scikit-learn, Cloud Run Job
      │  GCS: pending_review/{hash}/{date}/
      ▼
[Stage 4] Admin Review     — Flask, Cloud Run Service (human-in-the-loop)
      │  GCS: crisis_articles/{hash}/{date}/
      ▼
[Stage 5] Annotator        — Python, Gemini 3 Flash, Cloud Run Job
      │  GCS: pending_review_annotation/{hash}/{date}/
      ▼
[Stage 4b] Admin Review    — Annotation review (human-in-the-loop)
      │  GCS: annotated_articles/{hash}/{date}/
      ▼
[Stage 6] Extractor        — Python, Gemini 3 Flash, Cloud Run Job
      │  GCS: events/{hash}/{date}/
      ▼
[Stage 7] Dashboard        — HTML/JS, Leaflet.js, Chart.js, Cloud Run Service
```

All intermediate outputs are stored in Google Cloud Storage (GCS), with each stage writing its output under a deterministic content-hash subdirectory. This hash-based path organisation ensures that each unique version of the code produces its own isolated output, preventing data corruption across re-runs and enabling full data lineage tracking via a Neo4j dependency graph.

---

## 4.2 Stage 1: Data Acquisition — DVB News Crawler

### 4.2.1 Overview

The data acquisition stage is implemented as a Node.js web scraper that collects Burmese-language news articles from the Democratic Voice of Burma (DVB) online portal (burmese.dvb.no). The crawler is packaged as a Docker container and deployed as a Cloud Run Job, scheduled to execute automatically every day at midnight (Asia/Bangkok timezone) via Google Cloud Scheduler.

### 4.2.2 Implementation

The crawler is implemented in `crawler_job/DVB_Burmese.crawler.js` using two primary libraries: **Axios** for HTTP requests and **Cheerio** for HTML parsing. The entry point parses a configurable date range from environment variables (`DATE_START`, `DATE_END`) or defaults to scraping the previous day's articles.

The scraping logic follows a recursive pagination strategy. The `scrapePage()` function fetches the DVB news listing page at `https://burmese.dvb.no/categories/news?page=N` and extracts article metadata — title, publication date, and URL — from each listing entry. Pagination continues recursively until articles older than the target start date are encountered, at which point scraping stops. For each article URL, the `fetchPostContents()` function performs a second HTTP request to download the full article body by extracting text from the `div.full_content p` selector.

```javascript
// Recursive page scraper — stops when posts fall outside date range
async function scrapePage(baseUrl, url, page) {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    // extract article entries, check dates, recurse to next page
}
```

Articles are grouped by publication date and uploaded to GCS under the path `dvb/{CONTENT_HASH}/{YYYY-MM-DD}/`, where `CONTENT_HASH` is an MD5 hash of the crawler's own source code computed at build time. This ensures that any change to the crawler logic produces a new hash, isolating outputs from different crawler versions. In addition to the article text files, a JSON metadata file is uploaded for each date containing titles, URLs, and article counts.

Upon completing the upload for each date, the crawler automatically triggers the downstream Text Cleaner job by invoking the Cloud Run Jobs API via the GCP metadata server, passing the relevant date and content hash as environment variable overrides. This chained triggering mechanism eliminates the need for any external orchestration service.

### 4.2.3 Key Design Decisions

- **Pagination boundary detection**: The crawler checks the publication date of each article and terminates pagination early when articles fall outside the target date range, avoiding unnecessary requests.
- **Graceful downstream trigger failure**: If the trigger call to the Text Cleaner fails (e.g., due to a network error or job quota), the crawler logs the failure and exits successfully, preventing data loss. The cleaner can be triggered manually as a fallback.
- **Content-hash path isolation**: By namespacing outputs under a code-derived hash, multiple crawler versions can coexist in the same GCS bucket without overwriting each other's data.

---

## 4.3 Stage 2: Text Preprocessing — Text Cleaner

### 4.3.1 Overview

The Text Cleaner stage takes raw article text files produced by the crawler and removes noise that would interfere with downstream machine learning and LLM processing. Noise in DVB articles includes HTML remnants, author name attributions, and source citation lines appended at the end of articles.

### 4.3.2 Implementation

The cleaner is implemented in `text_clean_codebase/clean_crawl_articles.py` in Python 3. The core cleaning function, `clean_text_content()`, processes each article line-by-line, applying two detection functions to identify and remove non-content lines.

The `is_likely_author_name()` function uses Unicode range detection to identify lines containing Myanmar script characters (Unicode block U+1000–U+109F) that match patterns typical of byline attributions. The `is_source_citation()` function detects source attribution patterns in both English (e.g., "Source:", "Ref:") and Burmese using regular expressions.

```python
def is_likely_author_name(line: str) -> bool:
    # Detects Myanmar script author names using Unicode range U+1000-U+109F
    myanmar_chars = sum(1 for c in line if 'က' <= c <= '႟')
    return myanmar_chars > 0 and len(line.strip()) < 40

def is_source_citation(line: str) -> bool:
    # Detects source attribution patterns in English and Burmese
    patterns = [r'^source\s*:', r'^ref\s*:', r'ရင်းမြစ်']
    return any(re.match(p, line.strip().lower()) for p in patterns)
```

After cleaning, each article is saved to GCS under `dvb_cleaned/{OUTPUT_HASH}/{YYYY-MM-DD}/`, where `OUTPUT_HASH` is a SHA-256 hash derived from both the upstream crawler hash and the cleaner's own content hash, computed as:

```
OUTPUT_HASH = SHA-256( CRAWLER_HASH + ":" + CLEANER_CONTENT_HASH )
```

This chained hashing scheme propagates provenance through the pipeline. Any change to either the crawler or cleaner produces a unique output path, preserving the outputs of all previous runs.

Upon completion, the cleaner writes a `_COMPLETE` marker file to GCS and records its output hash to a Neo4j graph database node, enabling downstream jobs to discover the correct input path by querying Neo4j rather than scanning the bucket.

---

## 4.4 Stage 3: Crisis Classification — Machine Learning Classifier

### 4.4.1 Overview

The crisis classification stage applies a binary machine learning classifier to each cleaned article to determine whether it describes a crisis event. Only articles classified as crisis-related proceed to the human review and annotation stages. This stage is the most computationally intensive in the pipeline, requiring 4 vCPUs and 16 GB of memory due to the Gemma-300M embedding model.

### 4.4.2 Embedding Model

The classifier uses **Gemma-300M** (google/embeddinggemma-300m), a 300-million parameter multilingual embedding model from Google, accessed via the Sentence Transformers library. Gemma-300M is selected for its ability to produce high-quality semantic embeddings for Burmese text without requiring a language-specific tokeniser, as it supports multilingual Unicode input natively.

For each article, the model produces token-level embeddings which are aggregated into a fixed-length document representation using **mean pooling**:

```python
def transform(self, X):
    token_embeddings = self.model_.encode(
        texts,
        output_value="token_embeddings",
        convert_to_numpy=False,
        normalize_embeddings=False,
    )
    pooled = np.vstack([m.numpy().mean(axis=0) for m in token_embeddings])
    # L2 normalise
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / norms
```

The resulting embedding vectors are L2-normalised before being passed to the downstream classifier, improving numerical stability and classification accuracy.

### 4.4.3 Classifier Pipeline

The embedding model is wrapped in a custom `GemmaEmbeddingVectorizer` class that conforms to the scikit-learn `BaseEstimator` and `TransformerMixin` interfaces, making it composable with other scikit-learn components. The full classification pipeline is trained offline and serialised to a pickle file (`crisis_model.pkl`) that is loaded at job startup.

The `classify_text()` function calls `predict()` and `predict_proba()` on the loaded pipeline, returning both the binary label (`crisis` / `non-crisis`) and a confidence score:

```python
def classify_text(model, text: str) -> tuple:
    prediction = model.predict([text])[0]
    proba = model.predict_proba([text])[0]
    confidence = max(proba)
    is_crisis = bool(prediction == 'crisis')
    return is_crisis, confidence
```

Articles classified as crisis-related are uploaded to `pending_review/{OUTPUT_HASH}/{YYYY-MM-DD}/` for human review. Non-crisis articles are discarded. Model experiments are tracked with **MLflow**, with metrics and artefacts stored in the `cpe-final-project-mlflow-artifacts` GCS bucket.

### 4.4.4 Idempotency

Before processing a date, the classifier checks whether output files already exist in both `pending_review/` and `crisis_articles/` for that date. If they do, the date is skipped. This idempotency guarantee allows the job to be safely re-run without duplicating data.

---

## 4.5 Stage 4: Human-in-the-Loop Review — Admin Service

### 4.5.1 Overview

The Admin Review service introduces a human checkpoint between machine-generated outputs and the downstream LLM stages. An analyst uses a web interface to read each article, and then either confirms or rejects the classifier's or annotator's prediction. This two-stage review — one after classification, one after annotation — ensures that erroneous outputs from the ML model and the LLM do not propagate to the final dataset.

### 4.5.2 Implementation

The Admin Review service is implemented as a **Flask** web application (`crisis_admin/admin.py`) deployed as a Cloud Run Service. It provides six HTTP endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/admin` | GET | Dashboard listing all pending articles |
| `/admin/view` | GET | Display raw article text |
| `/admin/confirm` | POST | Approve classifier prediction, move to `crisis_articles/` |
| `/admin/reject` | POST | Reject classifier prediction, delete from `pending_review/` |
| `/admin/confirm_annotation` | POST | Approve annotation, move to `annotated_articles/` |
| `/admin/reject_annotation` | POST | Reject annotation, delete from `pending_review_annotation/` |

### 4.5.3 Approval Workflow

When an analyst confirms a classified article, the service moves the file from `pending_review/{hash}/{date}/` to `crisis_articles/{hash}/{date}/` in GCS and then triggers the Annotator Cloud Run Job via the Google Cloud Run Jobs API, passing the article's content hash as a job environment variable. This cascading trigger mechanism ensures that annotation begins immediately after approval without any manual intervention.

Similarly, when an analyst confirms an annotated article, the file is moved to `annotated_articles/{hash}/{date}/` and the Extractor job is triggered automatically.

```python
def admin_confirm():
    # 1. Read article from pending_review/
    # 2. Write to crisis_articles/
    # 3. Delete from pending_review/
    # 4. Trigger Annotator Cloud Run Job
    trigger_cloud_run_job(job_name="annotator-job", env_overrides={
        "SOURCE_CONTENT_HASH": source_hash,
        "PROCESS_DATE": date_str
    })
```

### 4.5.4 Hash Resolution

The service resolves the correct GCS input path for each article using a three-tier fallback strategy:

1. **Environment variable** (`SOURCE_CONTENT_HASH`) — set explicitly when triggered by the classifier.
2. **Neo4j query** — queries the dependency graph for the hash recorded by the upstream stage.
3. **GCS bucket scan** — falls back to scanning the bucket and selecting the most recently updated hash folder.

This layered resolution ensures the service remains operational even when upstream metadata is unavailable.

---

## 4.6 Stage 5: Event Annotation — Gemini Annotator

### 4.6.1 Overview

The annotation stage takes confirmed crisis articles and uses a large language model to identify and mark discrete crisis events within the text. Each event is wrapped in an XML-style `<event>...</event>` tag that delimits the text span belonging to that event. This structured markup enables the downstream extractor to process each event independently.

### 4.6.2 Annotation Prompt Design

The annotator uses **Gemini 3 Flash** with a carefully engineered 13-rule structured prompt (`ANNOTATION_PROMPT` in `annotator_job/annotate.py`). The prompt instructs the model to:

1. Wrap each disaster event in `<event>` and `</event>` tags.
2. Only tag events that are real disasters within the defined scope: Fire, Airstrike, Armed Conflict, Natural Disaster, Attack, and Bombing.
3. Group related sentences under a **single tag** if they share the same date, location, and incident.
4. Create a **new tag** when the date, location, or incident changes.
5. **Not tag** past events mentioned only as historical background.
6. **Only tag** events described as happening "today" or "yesterday" relative to the article's publication date.
7. Tag the **full span** of text describing an event, including casualty counts, damage reports, and response actions.

The 13-rule structure was developed iteratively to address ambiguous edge cases in Burmese news writing, particularly articles that report multiple events across different regions in a single piece. The rule set explicitly instructs the model not to split a single continuous event across multiple tags and not to merge events from different dates or locations.

### 4.6.3 API Integration

The annotator calls the Gemini API via the `google-genai` Python SDK:

```python
def annotate_article(article_text: str, gemini_client) -> str:
    full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=full_prompt
    )
    return response.text
```

The annotated output — the original article text with `<event>` tags inserted — is stored in GCS under `pending_review_annotation/{OUTPUT_HASH}/{YYYY-MM-DD}/` for human review before proceeding to extraction.

---

## 4.7 Stage 6: Information Extraction — Gemini Extractor

### 4.7.1 Overview

The extraction stage transforms annotated articles into structured JSON records. The extractor reads each `<event>` block and uses Gemini 3 Flash to extract twelve structured fields per event. The output is a JSON array — one object per event — written directly to the `events/` GCS prefix, where it can be consumed by the dashboard.

### 4.7.2 Extraction Prompt Design

The extraction prompt (`EXTRACTION_PROMPT` in `extractor_job/extract.py`) instructs the model to:

- Read **only** the text inside `<event>...</event>` tags and completely ignore all text outside them.
- Produce **exactly one JSON object per event block**, never splitting or merging blocks.
- Output **only** the raw JSON array with no markdown, no explanations, and no additional text.
- Use `response_mime_type: "application/json"` in the generation config to enforce structured output.

The twelve extracted fields are defined as follows:

| Field | Type | Description |
|---|---|---|
| `crisis_type` | String | One of: Armed Conflict, Attack, Airstrike, Bombing, Fire, Natural Disaster |
| `location` | String | Comma-separated: Township, State/Region, Country |
| `date` | String | DD/MM/YYYY format; relative terms (e.g., "yesterday") resolved to absolute date |
| `affected_civilian` | TRUE/FALSE/NA | Whether civilians are mentioned as affected |
| `affected_women` | TRUE/FALSE/NA | Whether women are mentioned as affected |
| `affected_children` | TRUE/FALSE/NA | Whether children are mentioned as affected |
| `civilian_properties_damage` | TRUE/FALSE/NA | Whether civilian properties are damaged |
| `civilian_forced_displacement` | TRUE/FALSE/NA | Whether civilians are displaced |
| `civilian_fatalities` | Integer/NA | Count of civilian deaths |
| `armed_personnel_fatalities` | Integer/NA | Count of military/armed group deaths |
| `number_of_people_displaced` | Integer/NA | Count of displaced persons |
| `involved_parties` | Array of Strings | Active combatant organisations (omitted for Natural Disaster) |

### 4.7.3 API Integration

The extractor calls the Gemini REST API directly using the `requests` library rather than the Python SDK, enabling explicit control over request headers and the `response_mime_type` generation config:

```python
def extract_events(article_text: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/" \
          f"gemini-3-flash-preview:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": EXTRACTION_PROMPT + article_text}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    response = requests.post(url, json=payload)
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]
```

### 4.7.4 Output Storage

Extracted JSON files are written to `events/{OUTPUT_HASH}/{YYYY-MM-DD}/{filename}.json`. Each file contains a JSON array, with one object per `<event>` block from the source article. The dashboard reads directly from this path, loading one or more JSON files via the Load JSON interface.

---

## 4.8 Stage 7: Visualisation Dashboard

### 4.8.1 Overview

The crisis event dashboard is a client-side web application implemented as a single HTML file. It requires no backend server — all filtering, charting, geocoding, and rendering logic executes entirely within the user's browser using vanilla JavaScript and two open-source libraries: **Leaflet.js** (v1.9.4) for interactive maps and **Chart.js** (v4.4.1) for statistical charts. The dashboard is deployed as a static file served by a Cloud Run nginx container.

### 4.8.2 Data Loading

On page load, users upload extracted JSON files via a file picker or by dragging and dropping files onto the browser window. The `loadData()` function accepts a JSON array and appends records to the global `DATA` array. After loading, filter controls are rebuilt from the actual data values (crisis types, regions), date range pickers are auto-populated, and the map and charts are re-rendered.

Multiple JSON files can be loaded simultaneously, with records from all files merged into a single dataset for unified filtering and visualisation.

### 4.8.3 Geospatial Mapping

Map pins are rendered using Leaflet.js with OpenStreetMap tiles. Each crisis event is geocoded from its `location` field string to a latitude/longitude coordinate pair using a four-tier resolution strategy:

1. **Hardcoded township lookup**: A lookup table of over 200 Myanmar township names mapped to precise coordinates. This is the primary geocoding source and covers the vast majority of DVB article locations. It was introduced because the Nominatim geocoding API has sparse and inconsistent coverage for Myanmar township names.
2. **Nominatim structured query**: If the township is not in the hardcoded table, a structured Nominatim API query is made using separate `city` and `state` parameters, with results validated against the expected state name.
3. **Nominatim free-text fallback**: A free-text query with Myanmar country restriction (`countrycodes=mm`) and state validation.
4. **Region-level fallback**: Falls back to the centre coordinates of the state or region if no township-level match is found.

Geocoding results are cached in a JavaScript `Map` to avoid redundant API calls across filter operations and data reloads.

### 4.8.4 Filtering and Charts

The dashboard provides five independent filters: date range (from/to), crisis type chips, region dropdown, township-level filter (populated by clicking a bar chart entry), and a one-click reset. Filters are applied client-side against the in-memory `DATA` array on every change, producing a `filtered` array that drives all three visualisation panels simultaneously.

Three Chart.js charts are rendered from the filtered dataset:

- **Doughnut chart**: Breakdown of events by crisis type, colour-coded by category.
- **Line chart**: Events-per-day timeline showing temporal distribution.
- **Horizontal bar chart**: Top 10 most-affected locations, clickable to set a township-level filter.

### 4.8.5 Event Detail Panel

Clicking any map pin opens a slide-in detail panel showing the full structured record for that event, including all 12 extracted fields. The panel includes colour-coded severity indicators for civilian and armed personnel fatalities and displacement counts.

---

## 4.9 Infrastructure and DevOps

### 4.9.1 Infrastructure as Code — Terraform

All GCP resources — Cloud Run Jobs, Cloud Run Services, Cloud Scheduler cron jobs, GCS buckets, IAM service accounts, Artifact Registry repositories, and Secret Manager entries — are provisioned and managed using **Terraform**. The Terraform configuration is organised into reusable modules for each pipeline component.

A key feature of the Terraform setup is **content-hash-based rebuild detection**. Each Cloud Run Job or Service module computes a SHA-256 hash of its Docker build context (source code directory) at `terraform plan` time. Terraform only marks the container image resource as requiring a rebuild when this hash changes, preventing unnecessary Cloud Build executions and reducing deployment time significantly. The hash is computed as:

```hcl
locals {
  content_hash = sha256(join("", [
    for f in fileset(var.source_dir, "**") :
    filesha256("${var.source_dir}/${f}")
  ]))
}
```

### 4.9.2 CI/CD — GitHub Actions

Two GitHub Actions workflows automate the deployment lifecycle:

- **Plan workflow** (triggered on pull request): Runs `terraform plan` and posts the diff as a pull request comment, allowing reviewers to see infrastructure changes before merging.
- **Deploy workflow** (triggered on merge to `main`): Runs `terraform apply` to provision or update all resources, then executes a Neo4j sync script to update the dependency graph with the new deployment state.

### 4.9.3 Data Lineage — Neo4j Dependency Graph

A Neo4j graph database is used to record the relationships between all pipeline components and the GCS bucket paths they read from and write to. After each Terraform deployment, a sync script creates `DeploymentHash` nodes for each container and edges representing data flow between stages. Each node stores the content hash, deployment timestamp, and the GCS prefix patterns for its inputs and outputs.

This graph enables downstream jobs to discover the correct input path by querying: "What is the most recent output hash written by the upstream stage for date X?" This is more reliable than scanning the GCS bucket, particularly when multiple versions of a stage have been deployed.

### 4.9.4 GCS Bucket Structure

The pipeline uses two primary GCS buckets:

**`cpe-final-project-pipeline-data`** — stores all intermediate pipeline data:

```
dvb/{hash}/{date}/                    ← raw crawled articles
dvb_cleaned/{hash}/{date}/            ← cleaned articles
pending_review/{hash}/{date}/         ← classified, awaiting review
crisis_articles/{hash}/{date}/        ← admin-confirmed crisis articles
pending_review_annotation/{hash}/{date}/  ← annotated, awaiting review
annotated_articles/{hash}/{date}/     ← admin-confirmed annotations
events/{hash}/{date}/                 ← final extracted JSON
```

**`cpe-final-project-mlflow-artifacts`** — stores MLflow experiment metadata, model parameters, evaluation metrics, and the serialised classifier pickle file.

### 4.9.5 Container Deployment Summary

The complete system consists of nine Docker containers, all built via Cloud Build and stored in Google Artifact Registry:

| Container | Type | Trigger |
|---|---|---|
| `dvb-crawler` | Cloud Run Job | Cloud Scheduler (daily midnight) |
| `text-cleaner` | Cloud Run Job | Triggered by crawler |
| `crisis-classifier` | Cloud Run Job | Triggered by cleaner |
| `crisis-admin` | Cloud Run Service | Always-on, HTTP |
| `annotator` | Cloud Run Job | Triggered by admin confirm |
| `extractor` | Cloud Run Job | Triggered by admin confirm (annotation) |
| `crisis-dashboard` | Cloud Run Service | Always-on, HTTP (nginx) |
| `mlflow-server` | Cloud Run Service | Always-on, HTTP |
| `neo4j-sync` | Cloud Run Job | Post-Terraform deploy |

---

## 4.10 Summary

This chapter has described the implementation of all seven pipeline stages and the supporting infrastructure. The system combines traditional web scraping, multilingual machine learning classification, large language model-based annotation and extraction, and interactive geospatial visualisation into a fully automated end-to-end pipeline. Key engineering contributions include the chained content-hash lineage system that enables reproducible, isolated pipeline runs; the 13-rule annotation prompt that handles complex multi-event Burmese news articles; the 200+ township geocoding table that resolves the sparse OpenStreetMap coverage for Myanmar; and the human-in-the-loop review layer that ensures data quality before LLM processing. The next chapter presents the evaluation of the system's outputs and performance.
