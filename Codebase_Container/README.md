# Codebase Container

`Codebase_Container/` contains the application code that Terraform builds and deploys as Cloud Run jobs and Cloud Run services. Each deployable folder is intended to be self-contained with its own `Dockerfile` and dependency file.

## Jobs

- `coordinator_job`: Node.js DVB link discovery and crawler fan-out.
- `crawler_job`: Node.js DVB article crawler.
- `text_clean_codebase`: Python text cleaning job for crawled articles.
- `crisis_classifier_job`: Python crisis classification job.
- `annotator_job`: Python Gemini-based article annotation job.
- `extractor_job`: Python event extraction job that writes structured output.
- `gcs_folder_rename_job`: Python utility job for moving GCS prefixes.
- `gpu_batch_job`: GPU batch workload kept as optional/reference code.
- `cloud_scheduler_function`: Older scheduled processor container kept for compatibility/reference.

## Services

- `mlflow`: MLflow tracking server container.
- `crisis_admin`: Flask-style admin portal for article review and job triggers.
- `events_api`: API service that reads extracted events from Firestore.
- `FrontEnd_Dashboard`: Static/dashboard frontend container.

## Test And Sample Files

- `test_GCS_annotation_sample`: Small tracked sample articles for annotation testing.
- Some folders include local test scripts such as `test_pipeline_article.py` or `test_gcs.py`.

## How Terraform Uses These Folders

Root `main.tf` registers deployable jobs in `locals.jobs` and services in `locals.services`. Each entry points `codebase_path` at one folder in this directory. The Terraform modules use that path to compute content hashes, build container images, and deploy Cloud Run resources.

When adding a new component:

1. Create a new folder with a clear name.
2. Add the application entry point.
3. Add a `Dockerfile`.
4. Add `requirements.txt` for Python or `package.json` for Node.js.
5. Register the folder in `main.tf`.
6. Run `make fmt`, `make validate`, and `make plan` from the repository root.

See `../HOW_TO_USE.md` for deployment and pipeline commands.
