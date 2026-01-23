output "scheduler_job_name" {
  description = "Name of the Cloud Scheduler job"
  value       = google_cloud_scheduler_job.job.name
}

output "cloud_run_job_name" {
  description = "Name of the Cloud Run job"
  value       = google_cloud_run_v2_job.scheduled_job.name
}

output "service_account_email" {
  description = "Email of the service account used by the job"
  value       = google_service_account.scheduler_sa.email
}

output "schedule" {
  description = "Cron schedule of the job"
  value       = google_cloud_scheduler_job.job.schedule
}
