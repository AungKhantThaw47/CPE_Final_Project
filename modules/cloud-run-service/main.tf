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
  codebase_directory = var.codebase_path != "" ? var.codebase_path : "${path.module}/service"

  # Generate hash of all files in the codebase directory
  codebase_files = fileset(local.codebase_directory, "**")

  # Check if root utils folder exists and include it in hash
  root_utils_path   = "${path.root}/utils"
  root_utils_exists = fileexists("${local.root_utils_path}/__init__.py")
  root_utils_files  = local.root_utils_exists ? fileset(local.root_utils_path, "**") : []

  # Combined hash: codebase files + root utils files
  codebase_hash = md5(jsonencode(merge(
    {
      for file in local.codebase_files :
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
  build_hash   = local.is_github_ci ? var.github_sha : "${local.build_env}-${substr(local.codebase_hash, 0, 7)}"

  # Sanitize service name for service account IDs (replace underscores with hyphens)
  sa_safe_service_name = replace(var.service_name, "_", "-")

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

# Generate .build-hash file for the service
resource "local_file" "build_hash" {
  filename = "${local.codebase_directory}/.build-hash"
  content  = local.build_hash

  lifecycle {
    ignore_changes = all
  }
}

# Build service image (only if build_image is true)
resource "null_resource" "service_image_build" {
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

# Service Account for the service
resource "google_service_account" "service_sa" {
  account_id   = "${local.sa_safe_service_name}-svc"
  display_name = "Service Account for ${var.service_name}"
  project      = var.project_id
}

# Grant necessary permissions to the service's service account
resource "google_project_iam_member" "service_permissions" {
  for_each = toset(var.service_account_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.service_sa.email}"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "service" {
  name     = local.sa_safe_service_name
  location = var.region
  project  = var.project_id

  deletion_protection = false

  depends_on = [null_resource.service_image_build]

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    service_account = google_service_account.service_sa.email

    containers {
      image = var.container_image

      ports {
        container_port = var.port
      }

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

      # Cloud SQL volume mount
      dynamic "volume_mounts" {
        for_each = length(var.cloud_sql_instances) > 0 ? [1] : []
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }

    # Cloud SQL volume
    dynamic "volumes" {
      for_each = length(var.cloud_sql_instances) > 0 ? [1] : []
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = var.cloud_sql_instances
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      launch_stage,
      scaling,
    ]
  }
}

# Allow public access if enabled
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.allow_public ? 1 : 0

  name     = google_cloud_run_v2_service.service.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}
