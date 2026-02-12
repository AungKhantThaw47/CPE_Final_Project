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
  description = "Hash of (content_hash + local username) - only set for local deployments"
  value       = local.local_hash_value
}

output "github_hash" {
  description = "Hash of (content_hash + github commit + github username) - only set for CI deployments"
  value       = local.github_hash_value
}
