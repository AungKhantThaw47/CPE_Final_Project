output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "zone" {
  description = "GCP Zone"
  value       = var.zone
}

# ============================================
# Cloud Run Job Outputs
# ============================================

output "job_name" {
  description = "Cloud Run Job name"
  value       = google_cloud_run_v2_job.gpu_batch_job.name
}

output "job_url" {
  description = "Cloud Run Job execution URL"
  value       = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.gpu_batch_job.name}:run"
}

output "docker_repository" {
  description = "Artifact Registry Docker repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}"
}

output "docker_image_full_path" {
  description = "Full Docker image path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/${var.image_name}:${var.image_tag}"
}

output "gcs_bucket_name" {
  description = "GCS bucket for job outputs"
  value       = google_storage_bucket.job_outputs.name
}

output "service_account_email" {
  description = "Service account email for job execution"
  value       = google_service_account.cloud_run_job_sa.email
}

output "invoker_service_account_email" {
  description = "Service account email for job invocation"
  value       = google_service_account.job_invoker_sa.email
}
