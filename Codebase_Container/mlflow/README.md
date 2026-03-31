# MLflow Service

This directory contains the MLflow Cloud Run service container assets.

## Files

- `Dockerfile`: Builds the MLflow server image
- `cloudbuild.yaml`: Cloud Build config for Artifact Registry image builds
- `.dockerignore`: Build context exclusions

The Terraform root module points the `mlflow` Cloud Run service at this directory via `codebase_path`.
