# OS detection for cross-platform build scripts
locals {
  is_windows  = substr(pathexpand("~"), 0, 1) != "/"
  image_path  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/${var.image_name}:${var.image_tag}"
  bucket_name = "${var.project_id}-gpu-job-outputs"
}

# ============================================
# Enable Required APIs
# ============================================
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com"
  ])
  
  service            = each.value
  disable_on_destroy = false
}

# ============================================
# Artifact Registry Repository
# ============================================
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.docker_repository_id
  format        = "DOCKER"
  description   = "Docker repository for GPU batch jobs"

  depends_on = [google_project_service.apis]
}

# ============================================
# Docker Image Build
# ============================================
resource "null_resource" "docker_image_build" {
  triggers = {
    dockerfile   = filemd5("${path.module}/cloud-run-gpu-batch/gpu-job/Dockerfile")
    main_py      = filemd5("${path.module}/cloud-run-gpu-batch/gpu-job/main.py")
    requirements = filemd5("${path.module}/cloud-run-gpu-batch/gpu-job/requirements.txt")
    image_tag    = var.image_tag
  }

  provisioner "local-exec" {
    command = local.is_windows ? (
      "powershell -ExecutionPolicy Bypass -File scripts/build_image.ps1 -Region ${var.region} -ProjectId ${var.project_id} -RepositoryId ${var.docker_repository_id} -ImageName ${var.image_name} -ImageTag ${var.image_tag}"
    ) : (
      "bash scripts/build_image.sh --region ${var.region} --project-id ${var.project_id} --repository-id ${var.docker_repository_id} --image-name ${var.image_name} --image-tag ${var.image_tag}"
    )
    working_dir = path.module
  }

  depends_on = [google_artifact_registry_repository.docker_repo]
}

# ============================================
# GCS Bucket for Job Outputs
# ============================================
resource "google_storage_bucket" "job_outputs" {
  name                        = local.bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

# ============================================
# Service Accounts
# ============================================
resource "google_service_account" "cloud_run_job_sa" {
  account_id   = var.service_account_id
  display_name = "Cloud Run GPU Job Service Account"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "job_invoker_sa" {
  account_id   = "${var.service_account_id}-invoker"
  display_name = "Cloud Run Job Invoker"
  depends_on   = [google_project_service.apis]
}

# ============================================
# IAM Permissions
# ============================================
resource "google_storage_bucket_iam_member" "job_sa_storage" {
  bucket = google_storage_bucket.job_outputs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run_job_sa.email}"
}

resource "google_project_iam_member" "job_sa_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run_job_sa.email}"
}

resource "google_project_iam_member" "invoker_sa_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.job_invoker_sa.email}"
}

# ============================================
# Cloud Run Job with GPU
# ============================================
resource "google_cloud_run_v2_job" "gpu_batch_job" {
  name                = var.job_name
  location            = var.region
  deletion_protection = false

  template {
    template {
      timeout                       = "900s"
      service_account               = google_service_account.cloud_run_job_sa.email
      execution_environment         = "EXECUTION_ENVIRONMENT_GEN2"
      gpu_zonal_redundancy_disabled = true

      node_selector {
        accelerator = var.gpu_type
      }

      containers {
        image = local.image_path

        resources {
          limits = {
            cpu    = "4"
            memory = "16Gi"
          }
        }

        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.job_outputs.name
        }
        env {
          name  = "JOB_NAME"
          value = var.job_name
        }
        env {
          name  = "NVIDIA_VISIBLE_DEVICES"
          value = "all"
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket.job_outputs,
    google_service_account.cloud_run_job_sa,
    google_storage_bucket_iam_member.job_sa_storage,
    google_project_iam_member.job_sa_logging,
    null_resource.docker_image_build
  ]

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_job_iam_member" "invoker_can_run" {
  name     = google_cloud_run_v2_job.gpu_batch_job.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.job_invoker_sa.email}"
}

# ============================================
# MLflow Docker Image Build
# ============================================
resource "null_resource" "mlflow_image_build" {
  triggers = {
    dockerfile = filemd5("${path.module}/modules/mlflow/Dockerfile")
  }

  provisioner "local-exec" {
    command = local.is_windows ? (
      "powershell -ExecutionPolicy Bypass -File scripts/build_mlflow.ps1 -Region ${var.region} -ProjectId ${var.project_id}"
    ) : (
      "bash scripts/build_mlflow.sh ${var.region} ${var.project_id}"
    )
    working_dir = path.module
  }

  depends_on = [google_artifact_registry_repository.docker_repo]
}

# ============================================
# MLflow Module
# ============================================
module "mlflow" {
  source = "./modules/mlflow"

  project_id          = var.project_id
  region              = var.region
  mlflow_image        = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/mlflow-server:latest"
  db_password         = var.mlflow_db_password
  allow_public_access = var.mlflow_public_access

  depends_on = [google_project_service.apis, null_resource.mlflow_image_build]
}
