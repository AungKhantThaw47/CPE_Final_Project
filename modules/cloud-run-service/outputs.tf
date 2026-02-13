output "service_name" {
  description = "The name of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.name
}

output "service_url" {
  description = "The URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.uri
}

output "service_account_email" {
  description = "Email of the service account used by the service"
  value       = google_service_account.service_sa.email
}

# ============================================
# Deployment Hash Control System Outputs
# ============================================

output "content_hash" {
  description = "Pure hash of codebase files (deterministic, controls deployment decisions)"
  value       = local.content_hash_value
}

output "local_hash" {
  description = "Local deployment hash format: LOCAL_{content_hash}_{local_username}"
  value       = local.local_hash
}

output "github_hash" {
  description = "GitHub deployment hash format: GITHUB_{content_hash}_{github_commit_hash}_{github_username}"
  value       = local.github_hash
}

output "current_use" {
  description = "Current deployment source: Local or Github"
  value       = local.current_use
}
