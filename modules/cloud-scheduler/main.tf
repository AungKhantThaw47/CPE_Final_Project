terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

locals {
  # Use provided codebase_path or fallback to default location
  codebase_directory = var.codebase_path != "" ? var.codebase_path : "${path.module}/function"

  # OS detection (check for Windows drive letter like C:, D:)
  is_windows = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0
  
  # Sanitize job name for resource lookups (replace underscores with hyphens)
  sa_safe_job_name = replace(var.job_name, "_", "-")
}

# ============================================
# Compute Content Hash using Hash Module
# ============================================
data "external" "content_hash" {
  program = local.is_windows ? ["PowerShell", "-File", "${path.root}/scripts/terraform_compute_hash.ps1"] : ["bash", "${path.root}/scripts/terraform_compute_hash.sh"]
  query = {
    codebase_path = abspath(local.codebase_directory)
  }
}

locals {
  # Use hash from external module for cross-platform consistency
  content_hash_computed = data.external.content_hash.result.content_hash
}

# ============================================
# Get Currently Deployed Content Hash
# ============================================
data "external" "deployed_hash" {
  program = local.is_windows ? ["PowerShell", "-File", "${path.root}/scripts/get_deployed_content_hash.ps1"] : ["bash", "${path.root}/scripts/get_deployed_content_hash.sh"]
  query = {
    project_id    = var.project_id
    region        = var.region
    resource_name = local.sa_safe_job_name
    resource_type = "job"
  }
}

locals {
  # ============================================
  # Deployment Hash Control System
  # ============================================
  
  # CONTENT_HASH: Pure hash of codebase files (computed natively in Terraform)
  content_hash_value = local.content_hash_computed
  
  # Currently deployed hashes
  deployed_content_hash = data.external.deployed_hash.result.deployed_content_hash
  deployed_local_hash   = data.external.deployed_hash.result.deployed_local_hash
  deployed_github_hash  = data.external.deployed_hash.result.deployed_github_hash
  
  # Determine if content has changed
  content_has_changed = local.deployed_content_hash == "" || local.deployed_content_hash != local.content_hash_value
  
  # Determine deployment mode
  is_local_deployment = var.github_sha == ""
  is_ci_deployment    = var.github_sha != ""
  
  # LOCAL_HASH logic:
  # - If content changed AND local deploy: set new local hash
  # - If content changed AND CI deploy: clear it (empty string)
  # - If content unchanged: preserve existing value
  local_hash_value = local.content_has_changed ? (
    local.is_local_deployment && var.local_username != "" ? "${local.content_hash_value}_${var.local_username}" : ""
  ) : local.deployed_local_hash
  
  # GITHUB_HASH logic:
  # - If content changed AND CI deploy: set new github hash
  # - If content changed AND local deploy: clear it (empty string)
  # - If content unchanged: preserve existing value
  github_hash_value = local.content_has_changed ? (
    local.is_ci_deployment && var.github_username != "" ? sha256("${local.content_hash_value}-${var.github_sha}-${var.github_username}") : ""
  ) : local.deployed_github_hash

  # Build commands for each OS
  # Build from root directory to include utils folder in context
  windows_build_command = <<-EOT
    cd '${replace(path.root, "/", "\\")}'
    gcloud builds submit `
      --project=${var.project_id} `
      --config '${replace(local.codebase_directory, "/", "\\")}\cloudbuild.yaml' `
      --substitutions=_IMAGE_TAG=${var.container_image}
  EOT

  unix_build_command = <<-EOT
    cd '${path.root}'
    gcloud builds submit \
      --project=${var.project_id} \
      --config '${local.codebase_directory}/cloudbuild.yaml' \
      --substitutions=_IMAGE_TAG=${var.container_image}
  EOT
}

# Build scheduler job image (only if build_image is true AND content has changed)
# Triggered only when deployed content_hash differs from calculated content_hash
resource "null_resource" "scheduler_job_image_build" {
  count = var.build_image && local.content_has_changed ? 1 : 0

  triggers = {
    # Rebuild when deployed_content_hash differs from local content_hash
    deployed_content_hash = local.deployed_content_hash
  }

  # Build Docker image via Cloud Build
  provisioner "local-exec" {
    when        = create
    on_failure  = fail
    command     = local.is_windows ? local.windows_build_command : local.unix_build_command
    interpreter = local.is_windows ? ["PowerShell", "-Command"] : ["sh", "-c"]
  }
}

# Cloud Run Job for the scheduled task
resource "google_cloud_run_v2_job" "scheduled_job" {
  name                = local.sa_safe_job_name
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  depends_on = [null_resource.scheduler_job_image_build]

  lifecycle {
    ignore_changes = [
      launch_stage,
      template[0].template[0].containers[0].resources[0].limits["nvidia.com/gpu"],
    ]
  }

  template {
    template {
      execution_environment         = var.execution_environment
      gpu_zonal_redundancy_disabled = var.enable_gpu ? true : null

      dynamic "node_selector" {
        for_each = var.enable_gpu ? [1] : []
        content {
          accelerator = var.gpu_type
        }
      }

      containers {
        image = var.container_image

        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }

        dynamic "env" {
          for_each = var.environment_variables
          content {
            name  = env.key
            value = env.value
          }
        }

        # Deployment Hash Control System
        # CONTENT_HASH: Pure hash of codebase files (deterministic, controls deployment decisions)
        env {
          name  = "CONTENT_HASH"
          value = local.content_hash_value
        }

        # LOCAL_HASH: Set only for local deployments when content changed
        # Cleared for CI deployments or when no content change
        dynamic "env" {
          for_each = local.local_hash_value != "" ? [1] : []
          content {
            name  = "LOCAL_HASH"
            value = local.local_hash_value
          }
        }

        # GITHUB_HASH: Set only for CI deployments when content changed
        # Cleared for local deployments or when no content change
        dynamic "env" {
          for_each = local.github_hash_value != "" ? [1] : []
          content {
            name  = "GITHUB_HASH"
            value = local.github_hash_value
          }
        }

        dynamic "env" {
          for_each = var.enable_gpu ? [1] : []
          content {
            name  = "NVIDIA_VISIBLE_DEVICES"
            value = "all"
          }
        }
      }

      timeout         = var.timeout
      max_retries     = var.max_retries
      service_account = google_service_account.scheduler_sa.email
    }
  }
}

# Service Account for the job
resource "google_service_account" "scheduler_sa" {
  account_id   = "${local.sa_safe_job_name}-job"
  display_name = "Service Account for ${var.job_name}"
  project      = var.project_id
}

# IAM binding to allow Cloud Scheduler to invoke the job
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  count    = var.enable_scheduler ? 1 : 0
  project  = google_cloud_run_v2_job.scheduled_job.project
  location = google_cloud_run_v2_job.scheduled_job.location
  name     = google_cloud_run_v2_job.scheduled_job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker_sa[0].email}"
}

# Service Account for Cloud Scheduler
resource "google_service_account" "scheduler_invoker_sa" {
  count        = var.enable_scheduler ? 1 : 0
  account_id   = "${local.sa_safe_job_name}-sched"
  display_name = "Cloud Scheduler SA for ${var.job_name}"
  project      = var.project_id
}

# Cloud Scheduler Job
resource "google_cloud_scheduler_job" "job" {
  count            = var.enable_scheduler ? 1 : 0
  name             = var.job_name
  description      = var.job_description
  schedule         = var.schedule
  time_zone        = var.time_zone
  attempt_deadline = var.attempt_deadline
  project          = var.project_id
  region           = var.region

  retry_config {
    retry_count = var.retry_count
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.scheduled_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker_sa[0].email
    }
  }

  depends_on = [
    google_cloud_run_v2_job.scheduled_job,
    google_cloud_run_v2_job_iam_member.scheduler_invoker
  ]
}

# Grant necessary permissions to the job's service account
resource "google_project_iam_member" "job_permissions" {
  for_each = toset(var.job_service_account_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}
