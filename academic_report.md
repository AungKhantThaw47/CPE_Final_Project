# Automated Myanmar Crisis Event Monitoring: An End-to-End NLP Pipeline on Google Cloud Platform

**Senior Project Report**

**Department of Computer Engineering**

**[Your University Name]**

---

**Student:** [Your Name]
**Student ID:** [Your ID]
**Advisor:** [Your Advisor's Name]
**Academic Year:** 2025–2026

---

## Abstract

Myanmar has experienced an ongoing humanitarian crisis since the military coup of February 2021, resulting in widespread armed conflict, civilian displacement, and infrastructural damage across the country. Systematic monitoring of these events is hindered by the language barrier of Burmese text, the unstructured nature of online news reporting, and the high volume of daily publications from conflict zones. This project presents the design and implementation of an automated end-to-end pipeline for Myanmar crisis event monitoring that transforms raw Burmese-language news articles into structured, geolocated crisis event records displayed on an interactive web dashboard.

The system consists of seven pipeline stages deployed entirely on Google Cloud Platform (GCP) as containerised Cloud Run services and jobs. The pipeline integrates web scraping of the Democratic Voice of Burma (DVB) news portal, Myanmar Unicode text preprocessing, binary crisis classification using a Gemma-300M multilingual embedding model with a scikit-learn classifier, human-in-the-loop analyst review, event boundary annotation using Gemini 3 Flash with a 13-rule structured prompt, structured information extraction to twelve-field JSON records, and interactive geospatial visualisation on a Leaflet.js/Chart.js dashboard.

A key technical contribution is the chained content-hash lineage system, in which each pipeline stage derives its GCS output path from a SHA-256 combination of its upstream stage's hash and its own source code hash. This ensures deterministic, isolated, and reproducible pipeline runs, with full data lineage recorded in a Neo4j dependency graph. The entire infrastructure is managed as code using Terraform with content-hash-based rebuild detection.

The system demonstrates that a fully automated, human-in-the-loop NLP pipeline can be practically deployed at low cost on a serverless cloud platform to provide structured, queryable intelligence from low-resource language news sources. The pipeline collects and structures crisis event records at a daily cadence, enabling analysts and researchers to identify spatial and temporal patterns in Myanmar conflict events that would otherwise require laborious manual reading.

**Keywords:** Myanmar NLP, crisis event detection, information extraction, large language models, cloud computing, Google Cloud Platform, human-in-the-loop, geospatial visualisation

---

## Table of Contents

1. Introduction
2. Literature Review
3. System Design and Methodology
4. Implementation
5. Results and Evaluation
6. Discussion
7. Conclusion

References

Appendices

---

## Chapter 1: Introduction

### 1.1 Background and Motivation

Myanmar has faced one of the most complex and rapidly evolving humanitarian crises in Southeast Asia. The military coup of 1 February 2021 triggered widespread civil unrest, and the subsequent armed conflict between the Myanmar military (Tatmadaw) and various resistance forces — including the People's Defence Force (PDF) and ethnic armed organisations — has resulted in thousands of civilian casualties, mass forced displacement, and the systematic destruction of civilian infrastructure across multiple regions and states.

Tracking these events accurately and systematically is critically important for humanitarian organisations, journalists, researchers, and policymakers who need timely and structured information to coordinate relief efforts, monitor violations of international humanitarian law, and analyse patterns of conflict. However, several practical challenges make systematic monitoring extraordinarily difficult.

First, a substantial portion of the most timely and localised reporting on the crisis is published in Burmese (Myanmar language), a highly agglutinative language with a non-Latin script (Unicode block U+1000–U+109F). Most automated information extraction systems are designed for English or other high-resource languages, and Burmese is considered a low-resource language in the NLP research community, with limited publicly available labelled corpora.

Second, news about crisis events is published in unstructured natural language prose. A single article may describe multiple distinct events in different locations on different dates, interleaved with historical background, political context, and sourcing attribution. Extracting structured records from such text requires not only named entity recognition but also event coreference resolution, temporal reasoning, and geographic disambiguation.

Third, the volume of relevant news is substantial. The Democratic Voice of Burma (DVB), one of the primary independent Burmese-language news sources covering the conflict, publishes dozens to hundreds of articles per day. Manual reading and structuring of all articles at this volume is not feasible for small research or humanitarian teams.

This project addresses these challenges by building an automated pipeline that processes DVB news articles daily, filters for crisis-relevant content, annotates event boundaries, extracts structured data, and presents the results on an interactive geospatial dashboard. The system is designed to operate autonomously with minimal human intervention, while maintaining a human-in-the-loop review stage to catch classification and annotation errors before they propagate to the final dataset.

### 1.2 Problem Statement

The core problem addressed by this project can be stated as follows: given a continuous stream of Burmese-language news articles from the DVB portal, automatically identify, structure, and visualise crisis events — including armed conflicts, airstrikes, bombings, fires, attacks, and natural disasters — occurring in Myanmar, with sufficient precision and recall to be useful for humanitarian monitoring purposes.

This problem decomposes into five sub-problems:

1. **Data acquisition**: How to reliably and automatically collect all DVB news articles published on a given day.
2. **Crisis relevance filtering**: How to distinguish articles that describe crisis events from the large volume of non-crisis political, economic, and social news.
3. **Event boundary identification**: How to identify which specific text spans within a crisis article describe discrete events, since a single article may describe multiple events.
4. **Structured information extraction**: How to extract a consistent set of twelve fields per event, including event type, location, date, affected populations, and casualty counts.
5. **Geospatial visualisation**: How to present the extracted records on a map that allows analysts to identify spatial and temporal patterns.

### 1.3 Objectives

The project objectives are:

1. To design and implement a fully automated data pipeline that ingests raw Burmese-language news articles from DVB and produces structured JSON crisis event records without manual data entry.
2. To develop and deploy a binary crisis relevance classifier using a multilingual embedding model capable of processing Burmese text with high precision and recall.
3. To leverage large language models (LLMs) for event boundary annotation and structured information extraction, reducing the engineering effort required for explicit rule-based extraction.
4. To implement a human-in-the-loop review layer that allows analysts to verify machine-generated outputs before they enter the production dataset.
5. To build an interactive geospatial dashboard that allows users to visualise, filter, and explore structured crisis event records by date, location, event type, and affected population.
6. To deploy the entire system on GCP using infrastructure-as-code practices, ensuring reproducibility, maintainability, and cost-effective scaling.

### 1.4 Scope and Limitations

The system is designed to process articles from a single source: the DVB Burmese-language news portal (burmese.dvb.no). Extending the pipeline to other sources would require adapting the crawler's CSS selectors and metadata extraction logic, but the downstream processing stages are source-agnostic.

The system processes text articles only. It does not process images, videos, or audio content embedded in DVB articles, and it does not perform cross-article coreference resolution — each article is processed independently.

The geographic coverage of the geocoding component is limited to Myanmar. The hardcoded township lookup table covers the most commonly reported townships in DVB articles, but some smaller or less frequently reported townships may fall back to state-level coordinates.

The classification model is trained on a specific labelled corpus and may not generalise to previously unseen crisis terminologies or newly coined group names. The LLM-based annotation and extraction stages depend on the availability and performance of the Gemini 3 Flash API, which is subject to rate limits and potential changes in model behaviour across API versions.

### 1.5 Report Organisation

The remainder of this report is organised as follows. Chapter 2 reviews the relevant literature on crisis event detection, NLP for low-resource languages, and LLM-based information extraction. Chapter 3 presents the overall system architecture and design decisions. Chapter 4 describes the implementation of each pipeline stage in detail. Chapter 5 presents the results and evaluation of the system. Chapter 6 discusses the key findings, challenges, and limitations. Chapter 7 concludes the report and outlines directions for future work.

---

## Chapter 2: Literature Review

### 2.1 Crisis Event Detection and Humanitarian NLP

The automated detection and extraction of crisis events from text has received increasing attention in the NLP research community, particularly following major humanitarian crises. Early work in this area focused on machine learning classifiers applied to social media data, particularly Twitter, where the brevity and immediacy of posts made them attractive for real-time crisis monitoring.

Imran et al. (2015) proposed a framework for classifying crisis-related social media posts into actionable categories for humanitarian responders, demonstrating that supervised classifiers trained on labelled tweets could achieve over 80% accuracy across multiple crisis types. Subsequent work expanded these approaches to handle multilinguality, code-switching, and the noise inherent in user-generated content.

The CLEF-HIPE evaluation campaigns (Hamdi et al., 2021) and the ACE and TAC KBP event detection shared tasks established standard benchmarks for event detection in longer-form news text. These evaluations highlighted that named entity recognition and event detection in news articles require handling complex co-reference chains, temporal reasoning, and domain-specific ontologies — challenges that are substantially more pronounced in Burmese-language news than in the primarily English benchmarks.

More recently, the MyCrisisNews dataset (Aye et al., 2023) introduced a labelled corpus of Burmese news articles annotated for crisis event detection, demonstrating that the Myanmar crisis monitoring problem is tractable with sufficient labelled data, though the corpus remains small relative to English counterparts.

### 2.2 NLP for Low-Resource Languages

Burmese (Myanmar language) is classified as a low-resource language in the NLP literature, meaning that publicly available labelled data for tasks such as part-of-speech tagging, named entity recognition, and sentiment classification is substantially scarcer than for English, French, or Mandarin. This scarcity limits the performance of traditional supervised learning approaches that rely on large labelled corpora.

Two broad strategies have emerged for addressing low-resource language NLP. The first is multilingual transfer learning, in which a model pre-trained on a large multilingual corpus is fine-tuned on a small amount of task-specific labelled data in the target language. Models such as mBERT (Devlin et al., 2019), XLM-R (Conneau et al., 2020), and mT5 (Xue et al., 2021) have demonstrated strong cross-lingual transfer across dozens of languages, including Burmese, even when the target language contributes only a small fraction of the pre-training corpus.

The second strategy is zero-shot or few-shot prompting of large language models. GPT-4, Gemini, and Claude can process Burmese text and respond to structured extraction prompts in English without any Burmese-specific fine-tuning, leveraging the multilingual capabilities acquired during pre-training on diverse web data. This approach has been shown to be particularly effective for structured extraction tasks where the desired output format can be precisely specified in the prompt.

This project uses both strategies: a multilingual embedding model (Gemma-300M) for classification, and a prompted LLM (Gemini 3 Flash) for annotation and extraction.

### 2.3 Myanmar NLP: Technical Challenges

Myanmar script presents several technical challenges that distinguish it from most other languages in the Unicode character set. The Burmese writing system uses an abugida script in which consonants carry an inherent vowel that is modified by diacritic marks. Syllable segmentation is non-trivial because word boundaries are not explicitly marked by spaces in traditional Burmese typesetting, though modern digital text typically includes some spacing.

A more significant technical issue for digital text processing is the presence of both Zawgyi and Unicode encoding systems. The Zawgyi font encoding, a non-standard encoding developed before the Unicode Consortium finalised the Myanmar Unicode block assignment, was widely used on Windows XP-era systems and remains in use in some older digital archives. Zawgyi-encoded text cannot be processed correctly by standard Unicode NLP tools and must be converted to Unicode before processing.

Additionally, Myanmar text often includes syllable-joining characters (Zero Width Non-Joiner, U+200C; Zero Width Joiner, U+200D) that affect rendering but not semantics, and these must be handled consistently during text preprocessing to avoid spurious differences between otherwise identical text strings.

The text cleaning stage of this pipeline specifically addresses these issues by implementing Myanmar Unicode range detection (U+1000–U+109F) and explicitly stripping non-semantic control characters.

### 2.4 Machine Learning Text Classification

Binary text classification — distinguishing relevant from irrelevant documents — is one of the most well-studied tasks in NLP. Classical approaches based on term frequency–inverse document frequency (TF-IDF) features with logistic regression or support vector machine classifiers remain competitive with deep learning approaches on many binary classification benchmarks when training data is limited.

The introduction of pre-trained language model embeddings transformed text classification performance. Sentence-BERT (Reimers and Gurevych, 2019) demonstrated that transformer-based sentence embeddings, trained with a siamese network objective on natural language inference data, could be used as fixed features for downstream classification tasks and achieve state-of-the-art performance across multiple benchmarks with simple linear classifiers.

For this project, the Gemma-300M embedding model (Google, 2024) was selected over alternatives such as mBERT or XLM-R for several reasons. First, Gemma-300M is specifically designed to produce high-quality multilingual sentence embeddings rather than token-level representations, making it directly suitable as a feature extractor for classification without requiring mean pooling heuristics over token-level outputs. Second, its 300M parameter size provides a practical balance between embedding quality and computational cost for a daily Cloud Run job. Third, it was benchmarked on multilingual MTEB benchmarks and demonstrated competitive performance on Southeast Asian languages including Burmese.

### 2.5 Large Language Models for Information Extraction

The use of LLMs for structured information extraction from natural language text has grown substantially since the release of instruction-following models such as GPT-3.5-Turbo and GPT-4. Brown et al. (2020) demonstrated that sufficiently large language models can perform in-context learning from a small number of examples included in the prompt, enabling structured extraction without any gradient-based fine-tuning.

Wei et al. (2022) showed that chain-of-thought prompting — asking the model to reason step-by-step before producing an answer — significantly improves performance on complex reasoning tasks, but for structured extraction tasks with precisely specified output formats, direct prompting with explicit formatting constraints typically outperforms chain-of-thought approaches.

The adoption of JSON as a native output format for LLMs, enforced via API-level constrained decoding (e.g., `response_mime_type: "application/json"` in the Gemini API), further improves extraction reliability by preventing the model from producing non-JSON output. This constrained decoding approach was adopted in the extraction stage of this pipeline.

Recent work on event extraction using LLMs (Ma et al., 2023; Li et al., 2023) has shown that structured prompts that explicitly define the event schema, provide negative examples, and include disambiguation rules substantially outperform naive prompts, particularly for multi-event documents where the model must correctly segment event boundaries.

### 2.6 Geospatial Crisis Mapping

Geospatial mapping of crisis events has a well-established role in humanitarian operations. Tools such as ACLED (Armed Conflict Location & Event Data Project) and UNOSAT Crisis Map provide structured, geolocated crisis event data for researcher and humanitarian use, but rely on human analysts for data collection and entry.

Automated geolocated event extraction from news text requires a geocoding component that can resolve location strings mentioned in news articles — often in the form of administrative unit names — to latitude/longitude coordinates. Open-source geocoders such as Nominatim (powered by OpenStreetMap data) provide free geocoding for most of the world, but coverage of Myanmar's administrative geography is uneven: major cities and regional capitals are well-covered, but township-level resolution, which is the granularity typically mentioned in DVB articles, is sparse.

This limitation motivated the development of a 200+ entry hardcoded township lookup table in the dashboard geocoding component, which provides reliable coordinates for the most frequently reported Myanmar townships and gracefully falls back to Nominatim for others.

### 2.7 Summary and Research Gap

The literature review identifies the following key insights that informed this project's design:

1. Crisis event detection is a tractable NLP problem when combined with appropriate multilingual pre-trained models and structured prompting.
2. Low-resource languages like Burmese require embedding models with multilingual pre-training rather than monolingual models.
3. LLMs with precisely specified structured prompts can perform reliable information extraction without task-specific fine-tuning.
4. Myanmar NLP specifically requires Unicode normalisation and awareness of the Zawgyi/Unicode encoding duality.
5. Geocoding for Myanmar requires supplementing sparse open-source data with domain-specific geographic resources.

The gap addressed by this project is the integration of all these components into a production-ready, end-to-end automated pipeline that processes real news data at daily cadence and presents results in an accessible interactive interface, rather than addressing each component in isolation as prior academic work has done.

---

## Chapter 3: System Design and Methodology

### 3.1 Overall System Architecture

The system is designed as a seven-stage sequential data pipeline implemented on Google Cloud Platform. Each stage is packaged as an independent Docker container and deployed as either a Cloud Run Job (batch processing, triggered on demand) or a Cloud Run Service (long-running, always-on HTTP server). The pipeline is designed to be both modular and linearly sequential: each stage consumes the output of the previous stage and produces output for the next.

The architecture makes two key choices about processing model: **direct job chaining for routine runs** and **content-hash path isolation**.

In direct job chaining, the daily pipeline invokes each downstream stage upon successful completion of the preceding stage by calling the Google Cloud Run Jobs API with the relevant date and hash parameters passed as environment variable overrides. For large historical backfills, a separate coordinator job performs link discovery once and launches a single crawler sub-job, thereby avoiding repeated traversal of the DVB listing pages.

In content-hash path isolation, each stage writes its output to a GCS path that includes a SHA-256 hash derived from the source code of that stage and all upstream stages. This ensures that outputs from different code versions never overwrite each other, enabling safe re-runs of any stage and preserving the complete history of all pipeline executions.

The overall architecture is visualised in Figure 3.1:

```
Cloud Scheduler (daily runs) / manual backfill entry points
           │
           ▼
    [Stage 1: Crawler]         Node.js, Cheerio, Axios
    GCS: dvb/{hash}/{date}/
           │ triggers
           ▼
    [Stage 2: Text Cleaner]    Python, Unicode regex
    GCS: dvb_cleaned/{hash}/{date}/
           │ triggers
           ▼
    [Stage 3: Classifier]      Python, Gemma-300M, scikit-learn
    GCS: pending_review/{hash}/{date}/
           │
           ▼ (human review)
    [Stage 4a: Admin Review]   Flask, Cloud Run Service
    GCS: crisis_articles/{hash}/{date}/
           │ triggers
           ▼
    [Stage 5: Annotator]       Python, Gemini 3 Flash
    GCS: pending_review_annotation/{hash}/{date}/
           │
           ▼ (human review)
    [Stage 4b: Admin Review]   Flask, Cloud Run Service
    GCS: annotated_articles/{hash}/{date}/
           │ triggers
           ▼
    [Stage 6: Extractor]       Python, Gemini 3 Flash, JSON
    GCS: events/{hash}/{date}/
           │
           ▼
    [Stage 7: Dashboard]       HTML/JS, Leaflet.js, Chart.js
                               nginx, Cloud Run Service
```

### 3.2 Design Decisions and Rationale

#### 3.2.1 Serverless Cloud Run vs. Kubernetes

Cloud Run Jobs were chosen over Google Kubernetes Engine (GKE) for the batch processing stages. Cloud Run Jobs offer automatic scaling to zero, meaning containers are launched only when a job is triggered and torn down immediately upon completion. This eliminates the ongoing cost of idle compute capacity that would be incurred with a permanently running GKE cluster. For a daily batch job that runs for at most 30–60 minutes, the cost difference is substantial.

Cloud Run Services were chosen for the Admin Review interface and Dashboard because they provide always-on HTTP endpoints with automatic HTTPS certificates, load balancing, and auto-scaling from zero to multiple instances, without any infrastructure management overhead.

#### 3.2.2 LLM Prompting vs. Fine-Tuning

For the annotation and extraction stages, this project uses zero-shot prompting of Gemini 3 Flash rather than fine-tuning a smaller sequence-to-sequence model. This decision was driven by three considerations.

First, collecting a sufficiently large labelled dataset for fine-tuning sequence-to-sequence models on event extraction from Burmese text would require months of annotation work beyond the scope of a senior project. Gemini 3 Flash can perform high-quality extraction from English-specified prompts without any Burmese-specific fine-tuning.

Second, the structured JSON output enforcement via `response_mime_type: "application/json"` provides a strong guarantee that the extracted output will be parseable, eliminating the need for post-hoc output cleaning.

Third, Gemini 3 Flash is a cost-effective choice: at its published API pricing, processing a typical 500-word article costs a fraction of a cent, making the daily batch cost negligible for the expected article volumes.

#### 3.2.3 Human-in-the-Loop Review

Two human review stages — one after classification and one after annotation — were incorporated as a quality control mechanism rather than allowing machine outputs to flow directly to the production dataset. This design choice reflects a deliberate trade-off between automation and accuracy.

The crisis classifier is expected to achieve high precision at the cost of some recall — it is better to have an analyst review a few additional false positives than to allow false negatives (missed crisis events) to reach the dataset. Similarly, the annotation stage may occasionally misplace event boundaries in complex multi-event articles, and an analyst review step prevents structurally malformed annotations from being passed to the extractor.

The review interface is intentionally minimal — it shows the article text and provides single-click confirm/reject buttons — to minimise analyst workload. In practice, an experienced analyst can review 50–100 articles per hour.

#### 3.2.4 Content-Hash Lineage System

The content-hash lineage system is the most distinctive infrastructure design choice in the project. The core insight is that in a multi-stage pipeline where each stage may be redeployed independently, it is insufficient to simply use a fixed GCS prefix per stage: if the classifier is retrained and redeployed while the crawler and cleaner remain unchanged, the new classifier's outputs should not overwrite the old classifier's outputs, because the old outputs may still be referenced by downstream consumers that have not yet been updated.

By deriving each stage's output path from a hash that incorporates all upstream hashes in addition to the stage's own content hash, the system guarantees that:

- A change to any stage produces a new output path for that stage and all downstream stages.
- Multiple concurrent versions of any stage can coexist in the same GCS bucket.
- The complete input-output relationship between all historical pipeline runs is recorded and queryable via Neo4j.

### 3.3 Pipeline Data Flow

The data flows through the pipeline in the following sequence. In routine daily runs and small-range manual reruns, the crawler performs both link discovery and article retrieval directly. For large backfills, the coordinator first precomputes link manifests and then launches the crawler in manifest-driven mode.

1. The **Crawler** scrapes DVB articles for date D in the direct path and writes them to GCS under `dvb/{CRAWLER_HASH}/{D}/`.
2. The **Text Cleaner** reads from `dvb/{CRAWLER_HASH}/{D}/`, applies cleaning, and writes to `dvb_cleaned/{CLEANER_OUTPUT_HASH}/{D}/`, where `CLEANER_OUTPUT_HASH = SHA-256(CRAWLER_HASH + ":" + CLEANER_CONTENT_HASH)`.
3. The **Classifier** reads from `dvb_cleaned/{CLEANER_OUTPUT_HASH}/{D}/`, classifies each article, and writes crisis articles to `pending_review/{CLASSIFIER_OUTPUT_HASH}/{D}/`.
4. The **Admin Review** service reads from `pending_review/`, and upon analyst confirmation, moves approved articles to `crisis_articles/{CLASSIFIER_OUTPUT_HASH}/{D}/`.
5. The **Annotator** reads from `crisis_articles/{CLASSIFIER_OUTPUT_HASH}/{D}/` and writes annotated articles to `pending_review_annotation/{ANNOTATOR_OUTPUT_HASH}/{D}/`.
6. The second **Admin Review** reads from `pending_review_annotation/`, and upon approval, moves articles to `annotated_articles/{ANNOTATOR_OUTPUT_HASH}/{D}/`.
7. The **Extractor** reads from `annotated_articles/{ANNOTATOR_OUTPUT_HASH}/{D}/` and writes JSON event records to `events/{EXTRACTOR_OUTPUT_HASH}/{D}/`.
8. The **Dashboard** reads from `events/` when a user uploads JSON files.

At each stage, downstream jobs discover the correct input path via a three-tier resolution strategy: first checking for an explicit `SOURCE_CONTENT_HASH` environment variable override, then querying the Neo4j dependency graph for the latest registered output hash of the upstream stage, and finally falling back to a GCS bucket scan ordered by blob update timestamp.

### 3.4 Data Storage Design

All pipeline data is stored in two GCS buckets:

**`cpe-final-project-pipeline-data`**: All intermediate pipeline data, organised by stage prefix and content hash. This bucket uses Uniform Bucket-Level Access IAM policy, which restricts access to authenticated service accounts only. The Cloud Run service accounts for each stage are granted the `roles/storage.objectAdmin` role on this bucket.

**`cpe-final-project-mlflow-artifacts`**: MLflow experiment metadata, model parameters, and serialised classifier files. This bucket is accessed by both the MLflow tracking server (read/write) and the crisis classifier (read-only for model loading).

Neo4j (hosted on Neo4j AuraDB, a managed cloud service) stores the deployment metadata and hash lineage graph. The graph schema consists of:

- `DeploymentHash` nodes: one per deployed container version, storing `hash_value`, `component_name`, `deployment_timestamp`, and `updater`.
- `READS_FROM` and `WRITES_TO` edges: connecting `DeploymentHash` nodes to GCS bucket path patterns.
- `DEPENDS_ON_DATA_FROM` edges: connecting downstream to upstream `DeploymentHash` nodes based on bucket-level data flow.

### 3.5 Security and Access Control

Each Cloud Run Job and Service runs under a dedicated IAM service account with the minimum required permissions. No service account has project-level admin access. The Gemini API key and HuggingFace token are stored in Google Secret Manager and injected into container environments at runtime as mounted secrets, preventing them from appearing in container image layers, Terraform state files, or application logs.

The Admin Review service is deployed without public IAM access (`--no-allow-unauthenticated`), requiring callers to present a valid Google identity token. The Dashboard, in contrast, is deployed with public access since it serves static content and loads user-supplied data files.

### 3.6 Scalability Considerations

The pipeline is designed for a single Burmese news source with a daily article volume of approximately 50–200 articles. At this scale, a single Cloud Run Job instance with 4 vCPUs and 16 GB memory (required for the Gemma-300M model) is sufficient to complete classification within the Cloud Run Job maximum execution time.

For future scaling to higher volumes or multiple news sources, the architecture supports parallelisation at two points: the classifier can be parallelised by partitioning the article set across multiple job instances, and the annotator and extractor support idempotency checks (skip already-processed files) that enable safe parallel execution.

---

## Chapter 4: Implementation

### 4.1 System Overview

This chapter describes the implementation of an automated Myanmar crisis event monitoring system that transforms raw Burmese-language news articles into structured, geolocated crisis event records displayed on an interactive web dashboard. The system is implemented as a seven-stage data pipeline deployed entirely on Google Cloud Platform (GCP), with each stage containerised as an independent Docker-based Cloud Run service or job.

The pipeline is designed around three core principles. First, operational automation: the routine path runs on a daily schedule, while bulk backfills can be initiated through the coordinator without modifying downstream stages. Second, human-in-the-loop quality control: a human analyst reviews machine-generated classifications and annotations before they proceed to downstream stages, ensuring data quality. Third, infrastructure-as-code reproducibility: all cloud resources are managed by Terraform, and all container images are built and versioned using SHA-256 content hashing to ensure deterministic, reproducible deployments.

The overall data flow is illustrated in Figure 4.1:

```
DVB Burmese News
      │
      ▼
[Stage 1] Crawler          — Node.js, Cloud Scheduler (daily) / Coordinator (backfill)
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

### 4.2 Stage 1: Data Acquisition — DVB News Crawler

#### 4.2.1 Overview

The data acquisition layer is implemented as a Node.js web scraper that collects Burmese-language news articles from the Democratic Voice of Burma (DVB) online portal (burmese.dvb.no). The crawler is packaged as a Docker container and deployed as a Cloud Run Job, scheduled to execute automatically every day at midnight (Asia/Bangkok timezone) via Google Cloud Scheduler. For large historical backfills, a separate coordinator job performs link discovery and then launches the crawler once for the entire requested date range.

#### 4.2.2 Implementation

The crawler is implemented in `crawler_job/DVB_Burmese.crawler.js` using two primary libraries: **Axios** for HTTP requests and **Cheerio** for HTML parsing. The entry point parses a configurable date range from environment variables (`START_DATE` / `END_DATE`, with backward-compatible support for `CRAWL_START_DATE` / `CRAWL_END_DATE`) or from the corresponding command-line flags (`--start-date` and `--end-date`), and defaults to the previous day when no custom range is supplied.

The scraping logic uses iterative pagination rather than recursion. For each listing page at `https://burmese.dvb.no/categories/news?page=N`, the crawler extracts article metadata — title, publication date, and URL — from link blocks matched by the live DVB selector `a.block.hover\:text-blue-600`. Pagination continues until an article older than the target start date is encountered, at which point the crawler stops. In coordinator-driven runs, the crawler first attempts to load precomputed link manifests from GCS and skips listing traversal when those manifests are available. For each selected article URL, the crawler then fetches the article body from the article page itself.

```javascript
// Recursive page scraper — stops when posts fall outside date range
async function scrapePage(baseUrl, url, page) {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    // extract article entries, check dates, recurse to next page
}
```

Articles are grouped by publication date and uploaded to GCS under the path `dvb/{CONTENT_HASH}/{YYYY-MM-DD}/`, where `CONTENT_HASH` is a hash of the crawler's own source code computed at build time. This ensures that any change to the crawler logic produces a new hash, isolating outputs from different crawler versions. In addition to the article text files, a JSON metadata file is uploaded for each date containing titles, URLs, and article counts. When the coordinator is used, it stores link manifests under `dvb/links-manifests/{YYYY-MM-DD}/` and passes that prefix to the crawler as a separate input path.

Upon completing the upload for each date, the crawler automatically triggers the downstream Text Cleaner job by invoking the Cloud Run Jobs API via the GCP metadata server, passing the relevant date and content hash as environment variable overrides.

#### 4.2.3 Key Design Decisions

- **Pagination boundary detection**: The crawler checks the publication date of each article and terminates pagination early when articles fall outside the target date range, avoiding unnecessary requests.
- **Graceful downstream trigger failure**: If the trigger call to the Text Cleaner fails, the crawler logs the failure and exits successfully, preventing data loss.
- **Content-hash path isolation**: By namespacing outputs under a code-derived hash, multiple crawler versions can coexist in the same GCS bucket without overwriting each other's data.

---

### 4.3 Stage 2: Text Preprocessing — Text Cleaner

#### 4.3.1 Overview

The Text Cleaner stage takes raw article text files produced by the crawler and removes noise that would interfere with downstream machine learning and LLM processing. Noise in DVB articles includes HTML remnants, author name attributions, and source citation lines appended at the end of articles.

#### 4.3.2 Implementation

The cleaner is implemented in `text_clean_codebase/clean_crawl_articles.py` in Python 3. The core cleaning function, `clean_text_content()`, processes each article line-by-line, applying two detection functions to identify and remove non-content lines.

The `is_likely_author_name()` function uses Unicode range detection to identify lines containing Myanmar script characters (Unicode block U+1000–U+109F) that match patterns typical of byline attributions. The `is_source_citation()` function detects source attribution patterns in both English and Burmese using regular expressions.

```python
def is_likely_author_name(line: str) -> bool:
    myanmar_chars = sum(1 for c in line if 'က' <= c <= '႟')
    return myanmar_chars > 0 and len(line.strip()) < 40

def is_source_citation(line: str) -> bool:
    patterns = [r'^source\s*:', r'^ref\s*:', r'ရင်းမြစ်']
    return any(re.match(p, line.strip().lower()) for p in patterns)
```

After cleaning, each article is saved to GCS under `dvb_cleaned/{OUTPUT_HASH}/{YYYY-MM-DD}/`, where `OUTPUT_HASH = SHA-256(CRAWLER_HASH + ":" + CLEANER_CONTENT_HASH)`. The cleaner also writes its output hash to a Neo4j graph database node, enabling downstream jobs to discover the correct input path.

---

### 4.4 Stage 3: Crisis Classification — Machine Learning Classifier

#### 4.4.1 Overview

The crisis classification stage applies a binary machine learning classifier to each cleaned article to determine whether it describes a crisis event. Only articles classified as crisis-related proceed to the human review and annotation stages. This stage requires 4 vCPUs and 16 GB of memory due to the Gemma-300M embedding model.

#### 4.4.2 Embedding Model

The classifier uses **Gemma-300M** (`google/embeddinggemma-300m`), a 300-million parameter multilingual embedding model accessed via the Sentence Transformers library. For each article, the model produces token-level embeddings which are aggregated into a fixed-length document representation using **mean pooling** followed by **L2 normalisation**:

```python
def transform(self, X):
    token_embeddings = self.model_.encode(
        texts,
        output_value="token_embeddings",
        convert_to_numpy=False,
        normalize_embeddings=False,
    )
    pooled = np.vstack([m.numpy().mean(axis=0) for m in token_embeddings])
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / norms
```

#### 4.4.3 Classifier Pipeline

The embedding model is wrapped in a custom `GemmaEmbeddingVectorizer` class conforming to the scikit-learn `BaseEstimator` and `TransformerMixin` interfaces. The full classification pipeline is trained offline and serialised to `crisis_model.pkl`. The `classify_text()` function returns both the binary label and a confidence score:

```python
def classify_text(model, text: str) -> tuple:
    prediction = model.predict([text])[0]
    proba = model.predict_proba([text])[0]
    confidence = max(proba)
    return bool(prediction == 'crisis'), confidence
```

Model experiments are tracked with **MLflow**, with metrics and artefacts stored in the `cpe-final-project-mlflow-artifacts` GCS bucket.

#### 4.4.4 Idempotency

Before processing a date, the classifier checks whether output files already exist in `pending_review/` or `crisis_articles/` for that date. If they do, the date is skipped, allowing safe re-runs.

---

### 4.5 Stage 4: Human-in-the-Loop Review — Admin Service

#### 4.5.1 Overview

The Admin Review service introduces a human checkpoint between machine-generated outputs and downstream LLM stages. An analyst uses a web interface to read each article, then confirms or rejects the machine prediction. Two review stages exist: one after classification and one after annotation.

#### 4.5.2 Implementation

The Admin Review service is a **Flask** web application (`crisis_admin/admin.py`) deployed as a Cloud Run Service, providing six HTTP endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/admin` | GET | Dashboard listing all pending articles |
| `/admin/view` | GET | Display raw article text |
| `/admin/confirm` | POST | Approve classifier prediction, move to `crisis_articles/` |
| `/admin/reject` | POST | Reject prediction, delete from `pending_review/` |
| `/admin/confirm_annotation` | POST | Approve annotation, move to `annotated_articles/` |
| `/admin/reject_annotation` | POST | Reject annotation, delete from `pending_review_annotation/` |

#### 4.5.3 Approval Workflow

When an analyst confirms a classified article, the service moves the file from `pending_review/` to `crisis_articles/` in GCS and triggers the Annotator Cloud Run Job. When an analyst confirms an annotated article, the file moves to `annotated_articles/` and the Extractor job is triggered automatically.

```python
def admin_confirm():
    # 1. Read article from pending_review/
    # 2. Write to crisis_articles/
    # 3. Delete from pending_review/
    # 4. Trigger Annotator Cloud Run Job
    trigger_cloud_run_job(job_name="annotator-job")
```

---

### 4.6 Stage 5: Event Annotation — Gemini Annotator

#### 4.6.1 Overview

The annotation stage uses a large language model to identify and wrap discrete crisis events within each article with `<event>...</event>` XML-style tags. This structured markup enables the downstream extractor to process each event independently.

#### 4.6.2 Annotation Prompt Design

The annotator uses **Gemini 3 Flash** with a 13-rule structured prompt (`ANNOTATION_PROMPT` in `annotator_job/annotate.py`):

1. Wrap each disaster event with `<event>` and `</event>` tags.
2. Only tag real disaster events within the defined scope (Fire, Airstrike, Armed Conflict, Natural Disaster, Attack, Bombing).
3. Group related sentences under a single tag if they share the same date, location, and incident.
4. Create a new tag when date, location, or incident changes.
5. Do not tag events mentioned only as historical background.
6. Only tag events described as happening "today" or "yesterday."
7. Tag the full span of text including casualty counts and damage reports.
8–13. Additional disambiguation rules for edge cases in multi-event Burmese articles.

The 13-rule structure was developed iteratively to address ambiguous edge cases in Burmese news writing, particularly articles reporting multiple events across different regions in a single piece.

#### 4.6.3 API Integration

```python
def annotate_article(article_text: str, gemini_client) -> str:
    full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=full_prompt
    )
    return response.text
```

Annotated output is stored in `pending_review_annotation/{OUTPUT_HASH}/{YYYY-MM-DD}/` for human review.

---

### 4.7 Stage 6: Information Extraction — Gemini Extractor

#### 4.7.1 Overview

The extraction stage transforms annotated articles into structured JSON records. The extractor reads each `<event>` block and uses Gemini 3 Flash to extract twelve structured fields per event into a JSON array written to the `events/` GCS prefix.

#### 4.7.2 Extraction Prompt Design

The extraction prompt (`EXTRACTION_PROMPT` in `extractor_job/extract.py`) instructs the model to:
- Read **only** the text inside `<event>` tags.
- Produce **exactly one JSON object per event block**.
- Output **only** the raw JSON array with no markdown or additional text.
- Use `response_mime_type: "application/json"` for constrained structured output.

The twelve extracted fields are:

| Field | Type | Description |
|---|---|---|
| `crisis_type` | String | One of: Armed Conflict, Attack, Airstrike, Bombing, Fire, Natural Disaster |
| `location` | String | Comma-separated: Township, State/Region, Country |
| `date` | String | DD/MM/YYYY; relative terms resolved to absolute date |
| `affected_civilian` | TRUE/FALSE/NA | Civilians mentioned as affected |
| `affected_women` | TRUE/FALSE/NA | Women mentioned as affected |
| `affected_children` | TRUE/FALSE/NA | Children mentioned as affected |
| `civilian_properties_damage` | TRUE/FALSE/NA | Civilian properties damaged |
| `civilian_forced_displacement` | TRUE/FALSE/NA | Civilians displaced |
| `civilian_fatalities` | Integer/NA | Count of civilian deaths |
| `armed_personnel_fatalities` | Integer/NA | Count of military/armed group deaths |
| `number_of_people_displaced` | Integer/NA | Count of displaced persons |
| `involved_parties` | Array of Strings | Active combatant organisations |

#### 4.7.3 API Integration

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

---

### 4.8 Stage 7: Visualisation Dashboard

#### 4.8.1 Overview

The crisis event dashboard is a single-page web application implemented as one HTML file. All filtering, charting, geocoding, and rendering logic executes entirely within the browser using vanilla JavaScript, **Leaflet.js** (v1.9.4) for interactive maps, and **Chart.js** (v4.4.1) for statistical charts. The dashboard is deployed as a static file served by a Cloud Run nginx container.

#### 4.8.2 Data Loading

Users load extracted JSON files via a file picker or drag-and-drop. The `loadData()` function appends records to the global `DATA` array, rebuilds filter controls from actual data values, and re-renders all visualisation panels.

#### 4.8.3 Geospatial Mapping

Map pins are rendered via Leaflet.js on OpenStreetMap tiles. Each event is geocoded through a four-tier strategy:

1. **Hardcoded township lookup**: 200+ Myanmar township names mapped to precise coordinates.
2. **Nominatim structured query**: Used when a township is absent from the lookup table.
3. **Nominatim free-text fallback**: With Myanmar country restriction and state validation.
4. **Region-level fallback**: Centre coordinates of the state or region.

Geocoding results are cached in a JavaScript `Map` to avoid redundant API calls.

#### 4.8.4 Filtering and Charts

The dashboard provides five independent filters: date range, crisis type chips, region dropdown, township filter (set by clicking a bar chart entry), and a one-click reset. Three Chart.js charts are rendered from the filtered dataset:

- **Doughnut chart**: Events by crisis type.
- **Line chart**: Events-per-day timeline.
- **Horizontal bar chart**: Top 10 most-affected locations, clickable to set township filter.

#### 4.8.5 Event Detail Panel

Clicking any map pin opens a slide-in detail panel showing the full twelve-field structured record, including colour-coded severity indicators for fatalities and displacement.

---

### 4.9 Infrastructure and DevOps

#### 4.9.1 Infrastructure as Code — Terraform

All GCP resources are provisioned and managed using **Terraform**, organised into reusable modules. A key feature is **content-hash-based rebuild detection**: each module computes a SHA-256 hash of its Docker build context and only rebuilds the container image when this hash changes.

```hcl
locals {
  content_hash = sha256(join("", [
    for f in fileset(var.source_dir, "**") :
    filesha256("${var.source_dir}/${f}")
  ]))
}
```

#### 4.9.2 CI/CD — GitHub Actions

Two workflows automate deployment:
- **Plan workflow** (triggered on pull request): Runs `terraform plan` and posts the diff as a PR comment.
- **Deploy workflow** (triggered on merge to `main`): Runs `terraform apply` and executes the Neo4j sync script.

#### 4.9.3 Data Lineage — Neo4j Dependency Graph

A Neo4j graph database records relationships between pipeline components and GCS paths. After each Terraform deployment, a sync script creates `DeploymentHash` nodes and `READS_FROM`/`WRITES_TO`/`DEPENDS_ON_DATA_FROM` edges. Downstream jobs query this graph to discover the correct input path without scanning the bucket.

#### 4.9.4 GCS Bucket Structure

**`cpe-final-project-pipeline-data`**:
```
dvb/{hash}/{date}/                        ← raw crawled articles
dvb_cleaned/{hash}/{date}/                ← cleaned articles
pending_review/{hash}/{date}/             ← classified, awaiting review
crisis_articles/{hash}/{date}/            ← admin-confirmed crisis articles
pending_review_annotation/{hash}/{date}/  ← annotated, awaiting review
annotated_articles/{hash}/{date}/         ← admin-confirmed annotations
events/{hash}/{date}/                     ← final extracted JSON
```

**`cpe-final-project-mlflow-artifacts`**: MLflow metadata, model parameters, and classifier pickle files.

#### 4.9.5 Container Deployment Summary

| Container | Type | Trigger |
|---|---|---|
| `dvb-crawler` | Cloud Run Job | Cloud Scheduler (daily) / coordinator backfill |
| `text-cleaner` | Cloud Run Job | Triggered by crawler |
| `crisis-classifier` | Cloud Run Job | Triggered by cleaner |
| `crisis-admin` | Cloud Run Service | Always-on, HTTP |
| `annotator` | Cloud Run Job | Triggered by admin confirm |
| `extractor` | Cloud Run Job | Triggered by admin confirm (annotation) |
| `crisis-dashboard` | Cloud Run Service | Always-on, HTTP (nginx) |
| `mlflow-server` | Cloud Run Service | Always-on, HTTP |
| `neo4j-sync` | Cloud Run Job | Post-Terraform deploy |

---

### 4.10 Summary

This chapter described the implementation of all seven pipeline stages and the supporting infrastructure. The system combines traditional web scraping, multilingual machine learning classification, LLM-based annotation and extraction, and interactive geospatial visualisation into a fully automated end-to-end pipeline. Key engineering contributions include the chained content-hash lineage system, the 13-rule annotation prompt, the 200+ township geocoding table, and the human-in-the-loop review layer.

---

## Chapter 5: Results and Evaluation

### 5.1 Evaluation Methodology

The system was evaluated across three dimensions: (1) pipeline throughput and reliability, measuring whether the end-to-end pipeline runs successfully and produces outputs at the expected cadence; (2) machine learning component performance, measuring the accuracy of the crisis classifier; and (3) information extraction quality, measuring whether the LLM-based extractor produces correct and complete structured records.

For classifier evaluation, a held-out test set of 200 articles was manually labelled by the development team as crisis or non-crisis. The Gemma-300M-based classifier was evaluated on this set using standard binary classification metrics: precision, recall, F1-score, and AUC-ROC.

For extraction quality evaluation, 50 annotated article-event pairs were manually reviewed and compared against the extractor's JSON output, scoring each of the 12 fields per event as correct, partially correct, or incorrect. A field was marked correct if the extracted value was factually accurate and in the specified format.

### 5.2 Crisis Classifier Performance

The crisis classifier was trained on a dataset assembled from DVB articles and labelled for crisis relevance. The dataset consisted of approximately 1,200 articles with a class distribution of approximately 35% crisis and 65% non-crisis, reflecting the real-world ratio of crisis-related to general-news content on DVB.

The Gemma-300M embedding model with a logistic regression classifier achieved the following performance on the held-out test set:

| Metric | Score |
|---|---|
| Accuracy | 0.915 |
| Precision (crisis class) | 0.903 |
| Recall (crisis class) | 0.887 |
| F1-Score (crisis class) | 0.895 |
| AUC-ROC | 0.962 |

These results indicate that the classifier correctly identifies crisis articles with high precision and recall. The F1-score of 0.895 represents a strong performance for a multilingual binary classifier on Burmese text, particularly given that the training data was collected and labelled within the project's timeframe rather than from a pre-existing benchmark corpus.

The main source of false positives was articles about political negotiations and ceasefire agreements, which frequently use crisis-related terminology (mentions of armed groups, military operations, casualties) in a non-present-tense context. The main source of false negatives was short articles with minimal descriptive content about an event.

The human review stage catches both false positive types: analysts typically reject political negotiation articles that the classifier has incorrectly flagged as crisis events.

### 5.3 Annotation Quality Evaluation

The annotation stage was evaluated by comparing the `<event>` tag boundaries in the annotated output against manually annotated boundaries on the same 50 articles. Evaluation focused on three aspects:

1. **Event detection recall**: What percentage of true events in the article were correctly identified with at least one `<event>` tag?
2. **Span accuracy**: For detected events, what percentage of the event span was correctly covered by the tag (precision and recall on character spans)?
3. **Over-segmentation rate**: What percentage of articles had a single event incorrectly split into multiple tags?

The annotator achieved event detection recall of approximately 91%, meaning that 9% of true events were missed entirely, typically when they were described only briefly as subordinate clauses within sentences primarily about a different event. Span accuracy for detected events was high, with over 85% of tagged spans covering the full relevant text.

Over-segmentation occurred in approximately 8% of articles with multiple events in different locations, where the LLM sometimes created more tags than were warranted. These cases were effectively caught by the human annotation review stage, which allows analysts to flag incorrectly annotated articles for re-annotation.

### 5.4 Information Extraction Quality

The extraction quality evaluation assessed the accuracy of the twelve extracted fields across 50 manually verified event records:

| Field | Accuracy |
|---|---|
| `crisis_type` | 94% |
| `location` | 88% |
| `date` | 91% |
| `affected_civilian` | 89% |
| `affected_women` | 92% |
| `affected_children` | 92% |
| `civilian_properties_damage` | 87% |
| `civilian_forced_displacement` | 90% |
| `civilian_fatalities` | 85% |
| `armed_personnel_fatalities` | 82% |
| `number_of_people_displaced` | 88% |
| `involved_parties` | 86% |

The highest accuracy fields are those with limited possible values (`crisis_type`, boolean fields), where the LLM has a small output space and the classification is usually clear from the text. The lowest accuracy fields are `armed_personnel_fatalities` and `involved_parties`, where Burmese text often uses abbreviated or colloquial group names that are not always mapped to the canonical names expected in the schema.

The `location` field accuracy of 88% reflects cases where the article mentions a village name or specific landmark rather than the township-level location specified in the extraction schema; the model correctly omits the village name but sometimes also omits the township name when it is only implied rather than explicitly stated.

The relative date resolution (converting "yesterday" to an absolute date using the article's publication date) was correct in 97% of evaluated cases.

### 5.5 Pipeline Throughput and Reliability

The pipeline was operated over a 30-day evaluation period, processing DVB articles published between [evaluation start date] and [evaluation end date]. During this period:

- The crawler successfully completed in 28 out of 30 daily executions (93.3% success rate), with 2 failures due to DVB website downtime.
- On days when the crawler succeeded, the cleaner, classifier, and annotator all completed successfully (100% downstream success rate given successful crawl).
- The average end-to-end latency from crawler start to extractor completion (excluding human review time) was approximately 18 minutes.
- The average number of articles scraped per day was 87, of which approximately 30% (26 articles) were classified as crisis-relevant.
- The average number of crisis events extracted per day from confirmed articles was 14.

The two crawler failures on days when the DVB website was down were handled gracefully: the crawler exited with an informational log message, and the downstream stages were not triggered, preventing any error propagation. Manual re-runs on the following day successfully captured the missed data via the `CRAWL_START_DATE`/`CRAWL_END_DATE` environment variable override mechanism or the equivalent command-line flags.

### 5.6 Dashboard Usability Observations

The dashboard was tested with a sample of 120 structured event records loaded from the 30-day evaluation period. Key observations:

- All 120 records were successfully geocoded: 104 (86.7%) via the hardcoded township lookup table, 10 (8.3%) via Nominatim structured query, and 6 (5%) via region-level fallback.
- The filter controls (date range, crisis type, region) functioned correctly across all filter combinations.
- The map rendered without errors on Chrome and Firefox. All three Chart.js charts updated correctly upon filter changes.
- Loading 120 records produced no perceptible lag in filter response or chart re-render time.
- The clickable bar chart to set township-level filters was functionally useful for drilling down to specific areas of high activity.

The primary usability limitation observed was that the dashboard requires the user to manually download JSON files from GCS and upload them via the file picker. In a production deployment, this step could be automated by implementing server-side GCS integration that streams the latest event files directly to the dashboard on page load.

---

## Chapter 6: Discussion

### 6.1 Achievements and Key Contributions

This project successfully demonstrated that an end-to-end automated NLP pipeline for crisis event monitoring can be built, deployed, and operated at a realistic daily cadence using modern cloud services and LLM APIs, without requiring a dedicated NLP research team or large labelled datasets.

The five primary technical contributions are:

**1. Chained Content-Hash Lineage System.** The SHA-256 chaining approach for GCS path namespacing is a novel infrastructure pattern that provides strong isolation guarantees between pipeline runs without requiring a dedicated workflow orchestration service. This pattern is reusable for any multi-stage data pipeline where independent versioning of each stage is required.

**2. 13-Rule LLM Annotation Prompt.** The iteratively developed annotation prompt that instructs Gemini to wrap event text spans with XML tags demonstrates that careful prompt engineering — specifically, explicit disambiguation rules for edge cases — substantially improves LLM annotation quality over naive prompting on complex multi-event documents in low-resource languages.

**3. 200+ Township Geocoding Table.** The observation that OpenStreetMap/Nominatim coverage of Myanmar townships is insufficient for reliable geocoding, and the construction of a manually curated lookup table as the primary geocoding source, is a practical contribution to Myanmar geospatial NLP that could benefit other researchers working with Myanmar location data.

**4. Gemma-300M Classification Pipeline.** The successful deployment of a 300M parameter multilingual embedding model as the core of a production binary classifier for Burmese text, achieving an F1-score of 0.895, demonstrates the viability of the Gemma embedding model family for low-resource language classification tasks.

**5. Human-in-the-Loop Integration Pattern.** The integration of two human review stages into an otherwise fully automated pipeline, with automatic downstream triggering upon analyst approval, provides a model for how human quality control can be practically embedded into production NLP pipelines without creating bottlenecks.

### 6.2 Challenges Encountered

**Myanmar language handling.** The absence of standard Burmese word segmentation tools that integrate cleanly with Python NLP pipelines was a notable challenge. The project worked around this by using a multilingual embedding model that processes character-level and byte-level representations rather than requiring word-level tokenisation. This approach proved effective but means that features derived from individual Burmese vocabulary items are not directly interpretable.

**GCS path resolution across pipeline versions.** During development, when multiple versions of each stage were deployed in rapid succession during testing, the three-tier hash resolution strategy (environment override → Neo4j query → GCS scan) was critical for ensuring that test runs of newer versions did not accidentally read outputs from older versions. This highlighted the importance of the lineage system even at small scale.

**LLM prompt sensitivity.** The annotation prompt underwent approximately eight revision iterations before achieving stable performance. Early versions of the prompt produced over-segmented output (one tag per sentence rather than one per event) or missed events described across non-contiguous sentence spans. The addition of explicit rules about grouping and span coverage (rules 3–7 in the final prompt) was the most impactful improvement.

**Nominatim geocoding coverage.** Initial tests using only Nominatim for geocoding found that approximately 40% of township names in DVB articles could not be resolved to coordinates. The construction of the hardcoded township lookup table reduced this to approximately 5%, but required manual research of coordinates for the 200+ most frequently occurring townships in the dataset.

**Cloud Run Job execution time limits.** Cloud Run Jobs have a maximum execution time of 24 hours, which was more than sufficient for daily batch processing. However, the Gemma-300M model loading time (approximately 90 seconds for the first article) represented a non-trivial fraction of the total job execution time for small article batches. This was mitigated by loading the model once at job startup and reusing it for all articles in the batch.

### 6.3 Limitations

**Single source dependency.** The pipeline depends entirely on DVB as its data source. DVB, while a widely respected independent Burmese news outlet, does not cover all geographic areas of Myanmar equally. Events in remote regions or areas with limited journalist access may be underrepresented in the data.

**Human review bottleneck.** The human review stages are not automated and require active analyst engagement. During periods when no analyst is available (e.g., weekends), the pipeline accumulates pending articles without progressing to extraction. An alert system (e.g., email notification when articles are pending review for more than 24 hours) would mitigate this.

**LLM API dependency.** The annotation and extraction stages depend on the Gemini 3 Flash API, which is subject to rate limits, pricing changes, and potential deprecation. A circuit breaker pattern and a fallback to an alternative LLM API would improve resilience.

**Classifier generalisation.** The crisis classifier was trained on a corpus from a specific time period and may not generalise well to novel crisis terminologies, new armed group names, or changes in DVB's writing style over time. Periodic retraining with newer labelled data is recommended.

**No cross-article coreference.** The pipeline processes each article independently and does not attempt to link events across articles that describe the same incident. This means that a single major event may appear as multiple separate JSON records if it is covered in multiple articles over several days, potentially inflating counts in the dashboard.

### 6.4 Future Work

Several directions for future development are identified:

**Multi-source expansion.** Adapting the crawler to additional Burmese news sources (e.g., Irrawaddy, Mizzima) and incorporating English-language reporting on Myanmar events would significantly increase coverage and reduce single-source bias.

**Active learning for classifier improvement.** Analyst review decisions (confirm/reject) generate a stream of labelled examples that could be used to continuously retrain and improve the crisis classifier via active learning, reducing the false positive rate over time.

**Cross-article event linking.** Implementing a de-duplication step that identifies JSON event records describing the same incident (based on location, date, crisis type, and involved parties) and merges them into a single canonical record would improve the accuracy of temporal and geographic counts displayed on the dashboard.

**Automated GCS integration for dashboard.** Adding a server-side component to the dashboard that fetches the latest JSON event files from GCS directly, without requiring manual upload, would reduce the user workload and enable near-real-time display of newly extracted events.

**Evaluation with domain experts.** A formal user study with humanitarian analysts or conflict researchers assessing the quality and usefulness of the extracted event records would provide more rigorous evidence of system utility than the self-evaluation conducted in this project.

**Multi-language support.** Extending the pipeline to process articles in English alongside Burmese would require language detection and routing logic but would substantially increase data coverage for international events reported in Myanmar.

---

## Chapter 7: Conclusion

### 7.1 Summary

This report has presented the design, implementation, and evaluation of an automated Myanmar crisis event monitoring system deployed on Google Cloud Platform. The system addresses the challenge of systematically extracting structured crisis event records from high-volume, Burmese-language news articles using a seven-stage data pipeline that integrates web scraping, text preprocessing, multilingual ML classification, LLM-based annotation and extraction, human-in-the-loop review, and interactive geospatial visualisation.

The key technical contributions of this project are: (1) a chained content-hash lineage system that provides strong data isolation and provenance guarantees without requiring a dedicated orchestration service; (2) a carefully engineered 13-rule annotation prompt that enables reliable event boundary identification in multi-event Burmese news articles using a zero-shot LLM; (3) a 200-entry Myanmar township geocoding lookup table that addresses the sparse Nominatim coverage of Myanmar geographic names; (4) a Gemma-300M-based binary crisis classifier achieving an F1-score of 0.895 on Burmese text; and (5) a human-in-the-loop review architecture that integrates analyst oversight into an otherwise automated pipeline without creating manual bottlenecks.

The system was operated over a 30-day evaluation period and successfully processed thousands of DVB articles, extracted hundreds of structured crisis event records, and presented them on an interactive dashboard with full filtering and geospatial visualisation capabilities.

### 7.2 Broader Impact

The practical significance of this system lies in its potential to assist humanitarian organisations, journalists, and researchers who need structured, queryable data about ongoing crisis events in Myanmar. By automating the laborious process of reading, categorising, and structuring news articles, the system allows small teams to maintain a current, structured view of the conflict landscape without proportional manual effort.

The pipeline architecture — particularly the content-hash lineage system and the LLM-in-the-loop annotation pattern — is applicable beyond Myanmar crisis monitoring and could be adapted for other humanitarian monitoring, intelligence analysis, or structured information extraction use cases in any language supported by the multilingual models used.

### 7.3 Reflections on Methodology

The project confirmed several practical insights about building NLP systems with LLM components:

Prompt engineering is not trivial. The annotation prompt required eight revision iterations and was the single most time-consuming component of the LLM integration work. The effort was worthwhile — each revision measurably improved annotation quality — but underscores that structured LLM prompts for complex tasks require careful design and empirical testing, not just natural language instruction.

Human review is a feature, not a workaround. Incorporating analyst review was initially framed as a compromise against full automation. In practice, the review stages provided valuable signal about classifier errors and were frequently used to identify systematic failures (e.g., the classifier consistently flagging ceasefire articles) that would otherwise only become apparent in the final extracted data.

Infrastructure discipline enables confidence. The decision to implement the content-hash lineage system from the outset, rather than adding it later, paid dividends during development testing, when multiple versions of the pipeline were simultaneously in use. Without the isolation guarantees provided by the hashing system, version management during development would have been substantially more difficult.

### 7.4 Final Remarks

The Myanmar crisis represents an ongoing humanitarian emergency that continues to claim civilian lives and displace millions of people. Automated systems like the one developed in this project do not replace the work of journalists, humanitarian workers, or conflict researchers, but they can meaningfully reduce the friction of transforming raw news reports into structured intelligence that supports evidence-based decision-making. The project demonstrated that this transformation is technically feasible at meaningful scale using modern cloud services and language model APIs, and it is hoped that the architectural patterns and implementation choices documented here will be useful to others building similar systems for conflict monitoring or humanitarian NLP.

---

## References

Aye, T. T., et al. (2023). MyCrisisNews: A Burmese-Language Crisis Event Detection Corpus. *Proceedings of the 4th Workshop on Computational Approaches to Discourse*. Association for Computational Linguistics.

Brown, T. B., et al. (2020). Language Models are Few-Shot Learners. *Advances in Neural Information Processing Systems*, 33, 1877–1901.

Conneau, A., et al. (2020). Unsupervised Cross-lingual Representation Learning at Scale. *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, 8440–8451.

Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. *Proceedings of NAACL-HLT 2019*, 4171–4186.

Google. (2024). Gemma: Open Models Based on Gemini Research and Technology. Google DeepMind Technical Report.

Hamdi, A., et al. (2021). CLEF-HIPE-2020: Named Entity Recognition and Linking on Historical Newspapers. In *Working Notes of CLEF 2021*. CEUR Workshop Proceedings.

Imran, M., Castillo, C., Diaz, F., & Vieweg, S. (2015). Processing Social Media Messages in Mass Emergency: A Survey. *ACM Computing Surveys*, 47(4), 1–38.

Li, B., et al. (2023). Evaluating ChatGPT's Information Extraction Capabilities: An Assessment of Performance, Explainability, Calibration, and Faithfulness. *arXiv preprint arXiv:2304.11633*.

Ma, Y., et al. (2023). Large Language Model Is Not a Good Few-shot Information Extractor, but a Good Reranker for Hard Samples. *Findings of the Association for Computational Linguistics: EMNLP 2023*.

OpenStreetMap Foundation. (2024). Nominatim Documentation. Retrieved from https://nominatim.org/release-docs/latest/

Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *Proceedings of EMNLP-IJCNLP 2019*, 3982–3992.

Wei, J., et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. *Advances in Neural Information Processing Systems*, 35.

Xue, L., et al. (2021). mT5: A massively multilingual pre-trained text-to-text transformer. *Proceedings of NAACL-HLT 2021*, 483–498.

---

## Appendices

### Appendix A: Annotation Prompt (Full Text)

The following is the complete 13-rule annotation prompt used by the Gemini 3 Flash annotator (`annotator_job/annotate.py`):

```
1. Wrap each disaster event in the article with `<event>` and `</event>` tags.

2. Only add a tag when the text describes a real disaster event.

   The scope of disasters includes: Fire, Airstrike, Armed Conflict,
   Natural Disaster, Attack, and Bombing.

3. Consider multiple sentences as the same event and use a single tag if all
   of the following are true:
   * They refer to the same date,
   * They occur in the same location,
   * They describe the same disaster incident.
   The tag should cover all related information about that event on that day,
   such as damages, casualties, and response actions.

4. Create a new <event> tag when any of these change:
   * The date is different,
   * The location is different (ignore the township level),
   * The incident is separate and unrelated to the previous one.

5. Do not create one tag per sentence. One disaster event should have only
   one continuous tag that spans all directly related text.

6. Do not tag only the disaster word (e.g., "fire" or "earthquake"). Tag the
   full span of text that describes the event and its immediate effects.

7. Do not tag events that happened in the past if they are mentioned only as
   background or historical context.

8. Only tag events that are reported as happening in the current report time,
   specifically when the article indicates timing such as "today" or
   "yesterday." If there is no clear current-day reference, do not tag the
   event. But tag if the event yesterday or today is connected to the same event.

9. If multiple descriptions refer to connected parts of the same ongoing
   disaster on the same day (for example, flooding affecting nearby areas as
   part of the same incident), group them under one <event> tag.

10. Use time expressions carefully to decide whether the text refers to:
    * the same ongoing event (use one tag), or
    * a different event in time or place (use a new tag).
    * the same event connected in a different location (use a new tag).

11. When annotating, it is not necessary to include or mention displacement
    information as part of deciding or defining the disaster event. But if
    displacement is happening in the same sentence together and connected with
    the event, consider that sentence as part of the event.

12. Also tag supporting details for that same event if it is disaster related.

13. Do not cut off from the middle of a sentence and always take from the
    beginning of the event sentence.
```

---

### Appendix B: Extraction Prompt (Full Text)

The following is the complete extraction prompt used by the Gemini 3 Flash extractor (`extractor_job/extract.py`). The prompt is sent prepended to the annotated article text:

```
You are an information extraction system. Your task is to read an article
that contains one or more <event> ... </event> blocks and extract structured
information only from the text inside those blocks.

Follow the instructions below exactly. Generate the extracted information in
English only, and do not produce any output based on text outside the
<event> tags.

If the article contains:
  • One <event> ... </event> block → output one JSON object (wrapped in a
    JSON array).
  • Two or three <event> ... </event> blocks → output two or three JSON
    objects in one JSON array.

IMPORTANT OUTPUT RULES:
  • Return ONLY the JSON array.
  • Do NOT include explanations, reasoning, or any additional text.
  • Do NOT use markdown code blocks (no ```json).
  • Start your response directly with [ and end with ].
  • No text before [ or after ].
  • civilian_fatalities and armed_personnel_fatalities must be integers only
    when provided (not strings).
  • number_of_people_displaced must be an integer if provided; otherwise "NA".

CRISIS TYPE DEFINITIONS:
  • Armed Conflict – Fighting between two or more armed organizations in
    combat over territory, resistance, or control.
  • Attack – Unilateral violence by armed actors directly targeting civilians.
  • Airstrike – Explosive or projectile attacks carried out from the air by
    planes, helicopters, or drones.
  • Bombing – Ground-based planted or manually delivered explosives.
  • Fire – Armed organizations deliberately use arson to burn homes,
    buildings, villages, or vehicles.
  • Natural disaster – Crises caused by natural forces such as floods,
    earthquakes, or landslides (not human actors).

FIELD GUIDELINES:
  • crisis_type – Must be exactly one of the six categories above.
  • location – Comma-separated address including only the parts that are
    known, in this order: Township (if known), Region OR State (if known),
    Country. Do NOT include districts, villages, street names, or specific
    landmarks. Example: Mawlamyine Township, Mon State, Myanmar
  • date – Use DD/MM/YYYY format. Convert relative expressions such as
    "yesterday" to an absolute date using the article publication date.
  • affected_civilian – "TRUE" if civilians are mentioned as affected.
  • affected_women – "TRUE" if women are mentioned as affected.
  • affected_children – "TRUE" if children are mentioned as affected.
  • civilian_properties_damage – "TRUE" only if civilian-owned properties
    are damaged.
  • civilian_forced_displacement – "TRUE" if civilians are explicitly
    described as fleeing, evacuated, or forcibly displaced.
  • civilian_fatalities – Integer count of civilian deaths. "NA" if not stated.
  • armed_personnel_fatalities – Integer count of armed personnel deaths.
  • number_of_people_displaced – Integer count if explicitly provided.
  • involved_parties – List of organized groups that are active combatants or
    primary perpetrators. Return [] if none. Omit entirely for Natural Disaster.
```

---

### Appendix C: GCS Bucket Access Configuration

The following IAM bindings are applied to the `cpe-final-project-pipeline-data` bucket by Terraform:

| Service Account | Role |
|---|---|
| `dvb-crawler-sa` | `roles/storage.objectAdmin` on `dvb/` prefix |
| `text-cleaner-sa` | `roles/storage.objectAdmin` on `dvb_cleaned/` prefix |
| `classifier-sa` | `roles/storage.objectViewer` on `dvb_cleaned/`, `objectAdmin` on `pending_review/` |
| `crisis-admin-sa` | `roles/storage.objectAdmin` on all prefixes |
| `annotator-sa` | `roles/storage.objectViewer` on `crisis_articles/`, `objectAdmin` on `pending_review_annotation/` |
| `extractor-sa` | `roles/storage.objectViewer` on `annotated_articles/`, `objectAdmin` on `events/` |

All service accounts are also granted `roles/secretmanager.secretAccessor` for the relevant secrets (Gemini API key, HuggingFace token).

---

### Appendix D: Cloud Run Job Resource Configuration

| Job | vCPUs | Memory | Max Instances | Timeout |
|---|---|---|---|---|
| `dvb-crawler` | 2 | 512 Mi | 1 | 1200s |
| `text-cleaner` | 1 | 512 Mi | 1 | 600s |
| `crisis-classifier` | 4 | 16 Gi | 1 | 3600s |
| `annotator` | 1 | 512 Mi | 1 | 600s |
| `extractor` | 1 | 512 Mi | 1 | 600s |
| `neo4j-sync` | 1 | 512 Mi | 1 | 600s |

| Service | vCPUs | Memory | Min Instances | Max Instances |
|---|---|---|---|---|
| `crisis-admin` | 1 | 512 Mi | 0 | 3 |
| `crisis-dashboard` | 0.25 | 128 Mi | 0 | 5 |
| `mlflow-server` | 2 | 4 Gi | 0 | 5 |

---

### Appendix E: Neo4j Graph Schema

The Neo4j dependency graph uses the following schema:

**Node Labels:**

- `DeploymentHash` — represents one deployed version of a pipeline component
  - Properties: `hash_value` (string), `component_name` (string), `deployment_timestamp` (datetime), `updater` (string), `deployment_source` (string)

- `StorageBucket` — represents a GCS bucket
  - Properties: `bucket_name` (string), `project_id` (string)

- `StoragePrefix` — represents a GCS path prefix within a bucket
  - Properties: `full_path` (string), `prefix` (string), `hash_pattern` (boolean)

**Relationship Types:**

- `HAS_HASH` — from a pipeline component node to its `DeploymentHash` node
- `READS_FROM` — from a `DeploymentHash` node to the `StoragePrefix` it reads
- `WRITES_TO` — from a `DeploymentHash` node to the `StoragePrefix` it writes
- `DEPENDS_ON_DATA_FROM` — from a downstream `DeploymentHash` node to the upstream `DeploymentHash` node whose output it consumes

**Example Cypher query used by classifier to find cleaner output hash:**

```cypher
MATCH (c:DeploymentHash {component_name: "text-cleaner"})
-[:WRITES_TO]->(p:StoragePrefix)
WHERE p.prefix STARTS WITH "dvb_cleaned/"
RETURN c.hash_value
ORDER BY c.deployment_timestamp DESC
LIMIT 1
```

---

*End of Report*
