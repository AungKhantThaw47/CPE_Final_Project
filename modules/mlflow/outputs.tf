output "mlflow_url" {
  description = "MLflow tracking server URL"
  value       = google_cloud_run_v2_service.mlflow.uri
}

output "mlflow_service_name" {
  description = "MLflow Cloud Run service name"
  value       = google_cloud_run_v2_service.mlflow.name
}

output "artifacts_bucket" {
  description = "GCS bucket for MLflow artifacts"
  value       = google_storage_bucket.mlflow_artifacts.name
}

output "db_host" {
  description = "MLflow database public IP"
  value       = google_sql_database_instance.mlflow.public_ip_address
}

output "db_name" {
  description = "MLflow database name"
  value       = google_sql_database.mlflow.name
}

output "service_account_email" {
  description = "MLflow service account email"
  value       = google_service_account.mlflow_sa.email
}
