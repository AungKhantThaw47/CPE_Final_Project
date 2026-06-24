# Codebase Summary

This repository contains a Terraform-managed Google Cloud Platform deployment for a DVB Burmese crisis-news data pipeline. It builds Cloud Run jobs and services, stores intermediate data in GCS, writes extracted events to Firestore, and keeps a Neo4j graph of deployment hashes and data dependencies.

## Main Areas

- `main.tf`, `variables.tf`, `outputs.tf`, `provider.tf`: Root Terraform configuration for GCP APIs, Artifact Registry, GCS buckets, Firestore, Cloud Run jobs, Cloud Run services, Workflows, IAM, and deployment outputs.
- `modules/cloud-scheduler`: Terraform module for Cloud Run jobs, optional Cloud Scheduler triggers, image builds, environment variables, IAM, and content-hash tracking.
- `modules/cloud-run-service`: Terraform module for always-on Cloud Run HTTP services.
- `Codebase_Container`: Application code for the jobs and services that Terraform builds into containers.
- `workflow.yaml` and `manual_workflow.yaml`: Google Cloud Workflows definitions for daily and date-range pipeline orchestration.
- `scripts`: Local and CI helper scripts for Terraform post-actions, hashing, pipeline execution, debugging, Neo4j cleanup, and system restart tasks.
- `bootstrap/neo4j`: Base graph manifest, generated graph artifacts, and Python loaders for Neo4j.
- `queries`: Cypher queries used to inspect pipeline structure, deployment hashes, lineage, and history.
- `utils`: Shared Python and JavaScript helpers for GCS, Firestore schema handling, and Neo4j access.
- `diagrams`: Mermaid, SVG, and markdown diagrams for the architecture, data pipeline, workflows, CI/CD, and infrastructure modules.

## Runtime Components

Cloud Run jobs:

- `dvb-coordinator-job`: Discovers DVB article links for a date range and fans out crawler executions.
- `dvb-crawler-job`: Crawls DVB article content and writes raw article data to GCS.
- `dvb-text-cleaner-job`: Cleans crawled text and writes cleaned content back to GCS.
- `crisis-classifier-job`: Classifies cleaned articles as crisis-related or not.
- `dvb-annotator-job`: Uses Gemini to annotate crisis articles.
- `dvb-extractor-job`: Extracts structured crisis events and writes them to Firestore.
- `gcs-folder-rename-job`: Internal utility job for moving or renaming GCS prefixes.

Cloud Run services:

- `mlflow`: MLflow tracking server with GCS artifact storage.
- `crisis-admin`: Admin portal for reviewing crisis articles and triggering annotation/extraction work.
- `events-api`: API for reading extracted Firestore event data.
- `crisis-dashboard`: Frontend dashboard for crisis event visualization.

Optional/reference code:

- `gpu_batch_job`: GPU batch job code kept for future re-enable.
- `cloud_scheduler_function`: Older scheduled processor container.
- `test_GCS_annotation_sample`: Small tracked sample text files for annotation testing.

## Data Flow

1. Coordinator discovers article URLs for a date range.
2. Crawler fetches article text and metadata into the shared pipeline GCS bucket.
3. Text cleaner normalizes article content.
4. Classifier identifies crisis-related articles.
5. Annotator adds structured annotations to crisis articles.
6. Extractor writes event records to Firestore.
7. Events API and dashboard expose the extracted data.
8. Terraform post-actions update generated Neo4j graph artifacts and can sync the graph when Neo4j environment variables are configured.

## Generated or Local-Only Files

The following are intentionally not source files and can be regenerated:

- `.terraform/`: Created by `terraform init`.
- `.venv/`, `venv/`, `env/`: Local Python virtual environments.
- `__pycache__/`, `*.pyc`: Python bytecode caches.
- `tfplan`, `tfplan.*`: Terraform plan output.
- `.env`, `terraform.tfvars`: Local configuration and secrets.
- `node_modules/`: Local Node.js dependencies.

These paths are covered by `.gitignore`.
