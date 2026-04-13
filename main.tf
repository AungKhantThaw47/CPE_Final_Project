# ============================================
# Auto-Detect Deployment Context
# ============================================

# Get project details (needed for service account emails)
data "google_project" "project" {
  project_id = var.project_id
}

# Auto-detect username for local deployments
data "external" "username" {
  program = local.is_windows_env ? ["PowerShell", "-File", "${path.root}/scripts/get_username.ps1"] : ["bash", "${path.root}/scripts/get_username.sh"]
}

# OS detection for cross-platform build scripts
locals {
  is_windows_env = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0
  is_windows     = local.is_windows_env
  image_path     = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/${var.image_name}:${var.image_tag}"
  pipeline_data_bucket_name = "${var.project_id}-pipeline-data"

  # Auto-computed deployment context (use var overrides if provided, otherwise auto-detect)
  actual_local_username  = var.local_username != "" ? var.local_username : data.external.username.result.username
  actual_github_username = var.github_username
  actual_github_sha      = var.github_sha

  # Define all jobs in one place
  jobs = {
    # Disabled from infra for now; kept as reference for future re-enable.
    # gpu-batch-job = {
    #   codebase_path    = "${path.root}/Codebase_Container/gpu_batch_job"
    #   container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/${var.image_name}:${var.image_tag}"
    #   description      = "GPU-accelerated batch processing job"
    #   build_image      = true # Build from local Dockerfile
    #   enable_scheduler = false
    #   enable_gpu       = true
    #   gpu_type         = var.gpu_type
    #   cpu_limit        = "4"
    #   memory_limit     = "16Gi"
    #   timeout          = "900s"
    #   environment_variables = {
    #     GCS_BUCKET = google_storage_bucket.pipeline_data.name
    #     JOB_NAME   = var.job_name
    #   }
    #   service_account_roles = [
    #     "roles/storage.objectAdmin",
    #     "roles/logging.logWriter"
    #   ]
    # }

    # daily-data-processor = {
    #   codebase_path    = "${path.root}/Codebase_Container/cloud_scheduler_function"
    #   container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/scheduler-job:latest"
    #   description      = "Daily data processing job"
    #   build_image      = true # Build from local Dockerfile
    #   enable_scheduler = true
    #   schedule         = "0 * * * *"
    #   enable_gpu       = false
    #   cpu_limit        = "1"
    #   memory_limit     = "512Mi"
    #   timeout          = "600s"
    #   environment_variables = {
    #     ENV = "production"
    #   }
    #   service_account_roles = []
    # }

    dvb-crawler-job = {
      codebase_path    = "${path.root}/Codebase_Container/crawler_job"
      container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/dvb-crawler:latest"
      description      = "DVB Burmese news crawler job"
      build_image      = true  # Build from local Dockerfile
      enable_scheduler = false # Triggered by workflow
      schedule         = ""
      enable_gpu       = false
      cpu_limit        = "1"
      memory_limit     = "512Mi"
      timeout          = "600s"
      environment_variables = {
        GCS_BUCKET = google_storage_bucket.pipeline_data.name
        GCP_REGION = var.region
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
    }

    dvb-text-cleaner-job = {
      codebase_path    = "${path.root}/Codebase_Container/text_clean_codebase"
      container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/dvb-text-cleaner:latest"
      description      = "DVB text cleaning job - removes author names and source citations"
      build_image      = true  # Build from local Dockerfile
      enable_scheduler = false # Triggered by workflow
      schedule         = ""
      enable_gpu       = false
      cpu_limit        = "1"
      memory_limit     = "512Mi"
      timeout          = "600s"
      environment_variables = {
        GCS_BUCKET    = google_storage_bucket.pipeline_data.name
        NEO4J_URI     = var.neo4j_uri
        NEO4J_USER    = var.neo4j_user
        NEO4J_PASSWORD = var.neo4j_password
        NEO4J_DATABASE = var.neo4j_database
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
    }

    crisis-classifier-job = {
      codebase_path    = "${path.root}/Codebase_Container/crisis_classifier_job"
      container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/crisis-classifier:latest"
      description      = "Crisis news classifier batch job - classifies cleaned articles daily"
      build_image      = true
      enable_scheduler = false # Triggered by workflow
      schedule         = ""
      enable_gpu       = false
      cpu_limit        = "4"
      memory_limit     = "16Gi"
      timeout          = "3600s" # 1 hour max for large batches
      environment_variables = {
        GCS_BUCKET     = google_storage_bucket.pipeline_data.name
        CRISIS_BUCKET  = google_storage_bucket.pipeline_data.name
        HF_TOKEN       = var.hf_token
        NEO4J_URI      = var.neo4j_uri
        NEO4J_USER     = var.neo4j_user
        NEO4J_PASSWORD = var.neo4j_password
        NEO4J_DATABASE = var.neo4j_database
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
    }

    dvb-annotator-job = {
      codebase_path    = "${path.root}/Codebase_Container/annotator_job"
      container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/dvb-annotator:latest"
      description      = "Crisis article annotator batch job"
      build_image      = true
      enable_scheduler = false
      schedule         = ""
      enable_gpu       = false
      cpu_limit        = "1"
      memory_limit     = "512Mi"
      timeout          = "600s"
      environment_variables = {
        CRISIS_BUCKET  = google_storage_bucket.pipeline_data.name
        GEMINI_API_KEY = var.gemini_api_key
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
    }

    dvb-extractor-job = {
      codebase_path    = "${path.root}/Codebase_Container/extractor_job"
      container_image  = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/dvb-extractor:latest"
      description      = "Crisis event extractor batch job"
      build_image      = true
      enable_scheduler = false
      schedule         = ""
      enable_gpu       = false
      cpu_limit        = "1"
      memory_limit     = "512Mi"
      timeout          = "600s"
      environment_variables = {
        CRISIS_BUCKET     = google_storage_bucket.pipeline_data.name
        EXTRACTION_BUCKET = google_storage_bucket.pipeline_data.name
        GEMINI_API_KEY    = var.gemini_api_key
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
    }

  }

  # Define Cloud Run Services (always-on HTTP services)
  services = {
    mlflow = {
      codebase_path   = "${path.root}/Codebase_Container/mlflow"
      container_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/mlflow-server:latest"
      description     = "MLflow Tracking Server"
      build_image     = true # Build from Dockerfile
      cpu_limit       = "2"
      memory_limit    = "4Gi"
      min_instances   = 0
      max_instances   = 2
      port            = 8080
      allow_public    = var.mlflow_public_access
      environment_variables = {
        BACKEND_STORE_URI               = "sqlite:///mlflow.db" # Use SQLite for simplicity, change to PostgreSQL if needed
        ARTIFACT_ROOT                   = "gs://${var.project_id}-mlflow-artifacts"
        GCS_BUCKET                      = "${var.project_id}-mlflow-artifacts"
        MLFLOW_TRACKING_SERVER_NAME     = "mlflow"
        MLFLOW_SERVER_ENABLE_HOST_CHECK = "false"
      }
      service_account_roles = [
        "roles/storage.objectAdmin"
      ]
      cloud_sql_instances = [] # Add ["${var.project_id}:${var.region}:mlflow-db"] if using Cloud SQL
    }

    crisis-admin = {
      codebase_path   = "${path.root}/Codebase_Container/crisis_admin"
      container_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_id}/crisis-admin:latest"
      description     = "Crisis article admin portal"
      build_image     = true
      cpu_limit       = "1"
      memory_limit    = "512Mi"
      min_instances   = 0
      max_instances   = 1
      port            = 8080
      allow_public    = true
      environment_variables = {
        CRISIS_BUCKET  = google_storage_bucket.pipeline_data.name
        NEO4J_URI      = var.neo4j_uri
        NEO4J_USER     = var.neo4j_user
        NEO4J_PASSWORD = var.neo4j_password
        NEO4J_DATABASE = var.neo4j_database
      }
      service_account_roles = [
        "roles/storage.objectAdmin",
        "roles/logging.logWriter"
      ]
      cloud_sql_instances = []
    }

  }
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
    "cloudscheduler.googleapis.com",
    "eventarc.googleapis.com",
    "workflows.googleapis.com",
    "workflowexecutions.googleapis.com"
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
# Shared GCS Bucket for Pipeline Data
# ============================================
resource "google_storage_bucket" "pipeline_data" {
  name                        = local.pipeline_data_bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type = "Delete"
    }
  }
}

# ============================================
# GCS Bucket for MLflow Artifacts
# ============================================
resource "google_storage_bucket" "mlflow_artifacts" {
  name                        = "${var.project_id}-mlflow-artifacts"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90 # Keep MLflow artifacts longer than job outputs
    }
    action {
      type = "Delete"
    }
  }
}


# ============================================
# Service Accounts
# ============================================
resource "google_service_account" "job_invoker_sa" {
  account_id   = "${var.service_account_id}-invoker"
  display_name = "Cloud Run Job Invoker"
  depends_on   = [google_project_service.apis]
}

# ============================================
# Cloud Run Jobs (using for_each on locals)
# ============================================
module "jobs" {
  source   = "./modules/cloud-scheduler"
  for_each = local.jobs

  project_id      = var.project_id
  region          = var.region
  job_name        = each.key
  job_description = each.value.description

  # Scheduler configuration
  enable_scheduler = each.value.enable_scheduler
  schedule         = lookup(each.value, "schedule", "")
  time_zone        = lookup(each.value, "time_zone", "Asia/Bangkok")

  # GPU configuration
  enable_gpu = each.value.enable_gpu
  gpu_type   = lookup(each.value, "gpu_type", "nvidia-l4")

  # Container and resources
  container_image = each.value.container_image
  codebase_path   = each.value.codebase_path
  build_image     = lookup(each.value, "build_image", true)
  github_sha      = local.actual_github_sha

  # Deployment Hash Control (content_hash computed inside module from codebase_path)
  local_username  = local.actual_local_username
  github_username = local.actual_github_username

  cpu_limit    = each.value.cpu_limit
  memory_limit = each.value.memory_limit
  timeout      = each.value.timeout

  # Environment variables
  environment_variables = each.value.environment_variables

  # IAM roles for the job service account
  job_service_account_roles = each.value.service_account_roles

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.docker_repo,
    google_storage_bucket.pipeline_data
  ]
}

# Grant invoker permission to all jobs
resource "google_cloud_run_v2_job_iam_member" "invoker_can_run" {
  for_each = local.jobs

  name     = module.jobs[each.key].job_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.job_invoker_sa.email}"
}

# Allow crawler SA to trigger the text cleaner job (for direct pipeline chaining)
resource "google_cloud_run_v2_job_iam_member" "crawler_triggers_cleaner" {
  project  = var.project_id
  location = var.region
  name     = module.jobs["dvb-text-cleaner-job"].job_name
  role     = "roles/run.developer"
  member   = "serviceAccount:${module.jobs["dvb-crawler-job"].service_account_email}"

  depends_on = [module.jobs]
}

# Grant Eventarc Event Receiver role to service account
resource "google_project_iam_member" "eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.job_invoker_sa.email}"
}

# Grant Pub/Sub Publisher to GCS service account (required for Eventarc GCS triggers)
resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.project.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# ============================================
# Cloud Run Services (using module)
# ============================================
module "services" {
  source   = "./modules/cloud-run-service"
  for_each = local.services

  project_id   = var.project_id
  region       = var.region
  service_name = each.key
  description  = each.value.description

  # Container and resources
  container_image = each.value.container_image
  codebase_path   = each.value.codebase_path
  build_image     = lookup(each.value, "build_image", true)
  github_sha      = local.actual_github_sha

  # Deployment Hash Control (content_hash computed inside module from codebase_path)
  local_username  = local.actual_local_username
  github_username = local.actual_github_username

  cpu_limit    = each.value.cpu_limit
  memory_limit = each.value.memory_limit

  # Scaling
  min_instances = lookup(each.value, "min_instances", 0)
  max_instances = lookup(each.value, "max_instances", 10)

  # Networking
  port         = lookup(each.value, "port", 8080)
  allow_public = lookup(each.value, "allow_public", false)

  # Environment variables
  environment_variables = lookup(each.value, "environment_variables", {})

  # Cloud SQL
  cloud_sql_instances = lookup(each.value, "cloud_sql_instances", [])

  # IAM roles for the service account
  service_account_roles = lookup(each.value, "service_account_roles", [])

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.docker_repo,
    google_storage_bucket.mlflow_artifacts
  ]
}


# ============================================
# Daily Pipeline Workflow
# ============================================

# Service account for the workflow to invoke Cloud Run Jobs
resource "google_service_account" "workflow_sa" {
  account_id   = "daily-pipeline-workflow"
  display_name = "Daily Pipeline Workflow Service Account"
  project      = var.project_id
}

# Allow workflow SA to run Cloud Run Jobs and read executions
resource "google_project_iam_member" "workflow_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.workflow_sa.email}"
}

# Allow workflow SA to write logs
resource "google_project_iam_member" "workflow_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.workflow_sa.email}"
}

# Cloud Workflows definition
resource "google_workflows_workflow" "daily_pipeline" {
  name            = "daily-pipeline"
  region          = var.region
  project         = var.project_id
  description     = "Orchestrates daily pipeline: crawler → cleaner → classifier → annotator → extractor"
  service_account = google_service_account.workflow_sa.email
  source_contents = file("${path.root}/workflow.yaml")

  depends_on = [google_project_service.apis]
}

# Service account for Cloud Scheduler to invoke the workflow
resource "google_service_account" "workflow_scheduler_sa" {
  account_id   = "workflow-scheduler-sa"
  display_name = "Cloud Scheduler SA for Daily Pipeline Workflow"
  project      = var.project_id
}

# Allow scheduler SA to invoke the workflow
resource "google_project_iam_member" "workflow_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.workflow_scheduler_sa.email}"
}

# Single Cloud Scheduler to trigger the workflow daily
resource "google_cloud_scheduler_job" "daily_pipeline_trigger" {
  name             = "daily-pipeline-trigger"
  description      = "Triggers the daily pipeline workflow at 12:05 AM Bangkok time"
  schedule         = "5 0 * * *"
  time_zone        = "Asia/Bangkok"
  project          = var.project_id
  region           = var.region
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.daily_pipeline.name}/executions"
    body        = base64encode("{}")

    oauth_token {
      service_account_email = google_service_account.workflow_scheduler_sa.email
    }
  }

  depends_on = [
    google_workflows_workflow.daily_pipeline,
    google_project_iam_member.workflow_invoker
  ]
}
