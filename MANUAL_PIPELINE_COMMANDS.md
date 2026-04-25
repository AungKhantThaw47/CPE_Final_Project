# Manual Pipeline Commands

This guide documents the commands to manually run and monitor the data pipeline.

## Prerequisites

- Google Cloud CLI authenticated
- Correct project selected
- Workflow and jobs already deployed

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

## Run Daily Pipeline (Cloud Workflows)

The deployed daily workflow name is `daily-pipeline` in region `asia-southeast1`.

Start a manual execution:

```bash
gcloud workflows execute daily-pipeline \
  --location=asia-southeast1
```

List recent executions:

```bash
gcloud workflows executions list daily-pipeline \
  --location=asia-southeast1 \
  --limit=10
```

## Run Manual Date-Range Pipeline

Use the separate workflow `manual-pipeline` for ad-hoc custom date ranges.

```bash
gcloud workflows execute manual-pipeline \
  --location=asia-southeast1 \
  --data='{"crawl_start_date":"20-03-2026","crawl_end_date":"22-03-2026"}'
```

Optional notification recipient override:

```bash
gcloud workflows execute manual-pipeline \
  --location=asia-southeast1 \
  --data='{"crawl_start_date":"20-03-2026","crawl_end_date":"22-03-2026","notify_email":"ops@example.com"}'
```

Date format must be `DD-MM-YYYY`.

Describe a specific execution:

```bash
gcloud workflows executions describe EXECUTION_ID \
  --workflow=manual-pipeline \
  --location=asia-southeast1
```

## Run Individual Jobs Manually (Cloud Run Jobs)

Run crawler:

```bash
gcloud run jobs execute dvb-crawler-job \
  --region=asia-southeast1 \
  --wait
```

Run cleaner:

```bash
gcloud run jobs execute dvb-text-cleaner-job \
  --region=asia-southeast1 \
  --wait
```

Run classifier:

```bash
gcloud run jobs execute crisis-classifier-job \
  --region=asia-southeast1 \
  --wait
```

## Helpful Monitoring Commands

Read recent logs for one job:

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=dvb-crawler-job" \
  --limit=50 \
  --format=json
```

Check workflow-scheduler trigger:

```bash
gcloud scheduler jobs describe daily-pipeline-scheduler \
  --location=asia-southeast1
```

## Notes

- Daily workflow execution follows this order: crawler -> cleaner -> classifier -> notify.
- Manual workflow execution follows this order: crawler -> cleaner -> classifier -> notify.
- Annotation and extraction happen after admin transitions via job execution:
  - `pending_review -> crisis_articles` then run `dvb-annotator-job` to produce `pending_review_annotation`
  - `pending_review_annotation -> annotated_articles` then run `dvb-extractor-job` to produce `events`
- If you want to force an upstream hash for consumers, set `SOURCE_CONTENT_HASH` in job environment overrides when invoking jobs via API or workflow changes.
