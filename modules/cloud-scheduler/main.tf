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
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

locals {
  # Use provided codebase_path or fallback to default location
  codebase_directory = var.codebase_path != "" ? var.codebase_path : "${path.module}/function"

  # Generate hash of all files in the codebase directory, excluding utils folder
  # Any change triggers rebuild, but Docker cache makes it fast
  codebase_files = fileset(local.codebase_directory, "**")
  codebase_files_filtered = [
    for file in local.codebase_files :
    file if !startswith(file, "utils/") && fileexists("${local.codebase_directory}/${file}")
  ]

  # Check if root utils folder exists and include it in hash
  root_utils_path   = "${path.root}/utils"
  root_utils_exists = fileexists("${local.root_utils_path}/__init__.py")
  root_utils_files  = local.root_utils_exists ? fileset(local.root_utils_path, "**") : []

  # Combined hash: codebase files + root utils files
  codebase_hash = md5(jsonencode(merge(
    {
      for file in local.codebase_files_filtered :
      "codebase/${file}" => filemd5("${local.codebase_directory}/${file}")
    },
    {
      for file in local.root_utils_files :
      "utils/${file}" => filemd5("${local.root_utils_path}/${file}")
    }
  )))

  # Environment detection: GITHUB vs LOCAL
  is_github_ci = var.github_sha != ""
  build_env    = local.is_github_ci ? "GITHUB" : "LOCAL"
  # Use full GitHub commit SHA in CI, shortened MD5 hash for local builds
  build_hash   = local.is_github_ci ? "GITHUB-${var.github_sha}" : "${local.build_env}-${substr(local.codebase_hash, 0, 7)}"

  # Sanitize job name for service account IDs (replace underscores with hyphens)
  sa_safe_job_name = replace(var.job_name, "_", "-")

  # OS detection (check for Windows drive letter like C:, D:)
  is_windows = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0

  # Build commands for each OS
  windows_build_command = <<-EOT
    if (Test-Path '${replace(path.root, "/", "\\")}\\utils') {
      Copy-Item -Recurse -Force '${replace(path.root, "/", "\\")}\\utils' '${replace(local.codebase_directory, "/", "\\")}\'
    }
    
    cd '${replace(local.codebase_directory, "/", "\\")}'
    gcloud builds submit `
      --config cloudbuild.yaml `
      --substitutions=_IMAGE_TAG=${var.container_image}
    
    if (Test-Path '${replace(local.codebase_directory, "/", "\\")}\\utils') {
      Remove-Item -Recurse -Force '${replace(local.codebase_directory, "/", "\\")}\\utils'
    }
  EOT

  unix_build_command = <<-EOT
    if [ -d '${path.root}/utils' ]; then
      cp -r '${path.root}/utils' '${local.codebase_directory}/'
    fi
    
    cd '${local.codebase_directory}'
    gcloud builds submit \
      --config cloudbuild.yaml \
      --substitutions=_IMAGE_TAG=${var.container_image}
    
    if [ -d '${local.codebase_directory}/utils' ]; then
      rm -rf '${local.codebase_directory}/utils'
    fi
  EOT
}

# Generate .build-hash file for the job
resource "local_file" "build_hash" {
  filename = "${local.codebase_directory}/.build-hash"
  content  = local.build_hash

  lifecycle {
    ignore_changes = all
  }
}

# Build scheduler job image (only if build_image is true)
resource "null_resource" "scheduler_job_image_build" {
  count = var.build_image ? 1 : 0

  triggers = {
    codebase_hash = local.codebase_hash
  }

  # Copy utils to build context, build image, then cleanup
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
