# ============================================
# MLflow Tracking Server Module
# ============================================

locals {
  mlflow_bucket = "${var.project_id}-mlflow-artifacts"
  mlflow_db_name = "mlflow"
  is_windows  = substr(pathexpand("~"), 0, 1) != "/"
}

# Build MLflow Docker image
resource "null_resource" "mlflow_image_build" {
  triggers = {
    dockerfile = filemd5("${path.module}/Dockerfile")
  }

  provisioner "local-exec" {
    command = local.is_windows ? (
      "cd ${path.module} && gcloud builds submit --tag ${var.mlflow_image}"
    ) : (
      "cd ${path.module} && gcloud builds submit --tag ${var.mlflow_image}"
    )
  }
}

# GCS bucket for MLflow artifacts
resource "google_storage_bucket" "mlflow_artifacts" {
  name                        = local.mlflow_bucket
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# Cloud SQL instance for MLflow backend store
resource "google_sql_database_instance" "mlflow" {
  name                = "${var.project_id}-mlflow-20260122105040"
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = false

  settings {
    tier = var.db_tier
    
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "all"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled = false
    }
  }
}

resource "google_sql_database" "mlflow" {
  name     = local.mlflow_db_name
  instance = google_sql_database_instance.mlflow.name
}

resource "google_sql_user" "mlflow" {
  name     = var.db_username
  instance = google_sql_database_instance.mlflow.name
  password = var.db_password
}

# Service account for MLflow server
resource "google_service_account" "mlflow_sa" {
  account_id   = "mlflow-server"
  display_name = "MLflow Tracking Server"
}

resource "google_storage_bucket_iam_member" "mlflow_sa_storage" {
  bucket = google_storage_bucket.mlflow_artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.mlflow_sa.email}"
}

resource "google_project_iam_member" "mlflow_sa_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.mlflow_sa.email}"
}

# MLflow Cloud Run service
resource "google_cloud_run_v2_service" "mlflow" {
  name                = var.service_name
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.mlflow_sa.email
    timeout         = "300s"
    
    containers {
      image = var.mlflow_image
      
      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
        tcp_socket {
          port = 8080
        }
      }

      env {
        name  = "BACKEND_STORE_URI"
        value = "postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.mlflow.public_ip_address}:5432/${local.mlflow_db_name}"
      }
      env {
        name  = "ARTIFACT_ROOT"
        value = "gs://${local.mlflow_bucket}/artifacts"
      }
      env {
        name  = "WERKZEUG_TRUSTED_HOSTS"
        value = "*"
      }
      env {
        name  = "MLFLOW_HTTP_REQUEST_TRUSTED_HOSTS"
        value = "*"
      }
    }
  }

  depends_on = [
    null_resource.mlflow_image_build,
    google_sql_database.mlflow,
    google_sql_user.mlflow,
    google_storage_bucket.mlflow_artifacts
  ]
}

# IAM policy for MLflow access
resource "google_cloud_run_v2_service_iam_member" "mlflow_access" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = var.region
  role     = "roles/run.invoker"
  member   = var.allow_public_access ? "allUsers" : "serviceAccount:${google_service_account.mlflow_sa.email}"
}
