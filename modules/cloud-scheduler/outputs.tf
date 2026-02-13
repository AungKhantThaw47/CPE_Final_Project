output "scheduler_job_name" {
  description = "Name of the Cloud Scheduler job"
  value       = var.enable_scheduler ? google_cloud_scheduler_job.job[0].name : null
}

output "cloud_run_job_name" {
  description = "Name of the Cloud Run job"
  value       = google_cloud_run_v2_job.scheduled_job.name
}

output "job_name" {
  description = "Alias for cloud_run_job_name"
  value       = google_cloud_run_v2_job.scheduled_job.name
}

output "service_account_email" {
  description = "Email of the service account used by the job"
  value       = google_service_account.scheduler_sa.email
}

output "schedule" {
  description = "Cron schedule of the job"
  value       = var.enable_scheduler ? google_cloud_scheduler_job.job[0].schedule : null
}

# ============================================
# Deployment Hash Control System Outputs
# ============================================

output "content_hash" {
  description = "Pure hash of codebase files (deterministic, controls deployment decisions)"
  value       = local.content_hash_value
}
