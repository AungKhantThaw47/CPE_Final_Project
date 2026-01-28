# ============================================
# Cloud Run Jobs Outputs
# ============================================

output "jobs" {
  description = "Cloud Run Jobs with trigger commands and URLs"
  value = {
    for job_key, job_config in local.jobs : job_key => {
      # Trigger command
      trigger_command = "gcloud run jobs execute ${module.jobs[job_key].job_name} --region ${var.region}"
      
      # Console URLs
      console_url = "https://console.cloud.google.com/run/jobs/details/${var.region}/${module.jobs[job_key].job_name}?project=${var.project_id}"
      
      # Docker info
      docker_image_url = job_config.container_image
      docker_registry  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}"
      
      # Connected resources
      gcs_buckets = [for k, v in job_config.environment_variables : v if k == "GCS_BUCKET"]
      cloud_sql   = []  # Add if needed in future
      
      # Schedule info
      schedule = lookup(job_config, "schedule", null)
    }
  }
}

# ============================================
# Cloud Run Services Outputs
# ============================================

output "services" {
  description = "Cloud Run Services with URLs and connected resources"
  value = {
    for svc_key, svc_config in local.services : svc_key => {
      # Public URL (if service exists)
      public_url = lookup(module.services, svc_key, null) != null ? module.services[svc_key].service_url : null
      
      # Console URL
      console_url = "https://console.cloud.google.com/run/detail/${var.region}/${svc_key}?project=${var.project_id}"
      
      # Docker info
      docker_image_url = svc_config.container_image
      docker_registry  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}"
      
      # Connected resources
      cloud_sql_instances = lookup(svc_config, "cloud_sql_instances", [])
      gcs_buckets        = []  # Extract from env vars if needed
      
      # Access info
      allow_public = lookup(svc_config, "allow_public", false)
    }
  }
}

# ============================================
# Shared Resources
# ============================================

output "docker_repository" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}"
}

output "gcs_output_bucket" {
  description = "GCS bucket for job outputs"
  value       = google_storage_bucket.job_outputs.name
}

output "mlflow_artifacts_bucket" {
  description = "GCS bucket for MLflow artifacts"
  value       = google_storage_bucket.mlflow_artifacts.name
}
