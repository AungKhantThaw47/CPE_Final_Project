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
  codebase_directory = var.codebase_path != "" ? var.codebase_path : "${path.module}/service"

  # OS detection (check for Windows drive letter like C:, D:)
  is_windows = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0
  
  # Sanitize service name for resource lookups (replace underscores with hyphens)
  sa_safe_service_name = replace(var.service_name, "_", "-")
}

# ============================================
# Compute Content Hash from Codebase
# ============================================
data "external" "content_hash" {
  program = local.is_windows ? ["PowerShell", "-File", "${path.root}/scripts/compute_content_hash_json.ps1"] : ["bash", "${path.root}/scripts/compute_content_hash_json.sh"]
  query = {
    codebase_path = local.codebase_directory
  }
}

# ============================================
# Get Currently Deployed Content Hash
# ============================================
data "external" "deployed_hash" {
  program = local.is_windows ? ["PowerShell", "-File", "${path.root}/scripts/get_deployed_content_hash.ps1"] : ["bash", "${path.root}/scripts/get_deployed_content_hash.sh"]
  query = {
    project_id    = var.project_id
    region        = var.region
    resource_name = local.sa_safe_service_name
    resource_type = "service"
  }
}

locals {
  # ============================================
  # Deployment Hash Control System
  # ============================================
  
  # CONTENT_HASH: Pure hash of codebase files (computed from codebase_path)
  content_hash_value = data.external.content_hash.result.content_hash
  
  # Currently deployed content hash (empty string if service doesn't exist yet)
  deployed_content_hash = data.external.deployed_hash.result.deployed_content_hash
  
  # Determine if content has changed
  content_has_changed = local.deployed_content_hash == "" || local.deployed_content_hash != local.content_hash_value
  
  # Determine deployment mode
  is_local_deployment = var.github_sha == ""
  is_ci_deployment    = var.github_sha != ""
  
  # LOCAL_HASH: Set only for local deployments when content changed
  local_hash_value = local.is_local_deployment && local.content_has_changed && var.local_username != "" ? "${local.content_hash_value}_${var.local_username}" : ""
  
  # GITHUB_HASH: Set only for CI deployments when content changed
  github_hash_value = local.is_ci_deployment && local.content_has_changed && var.github_username != "" ? sha256("${local.content_hash_value}-${var.github_sha}-${var.github_username}") : ""

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

# Build service image (only if build_image is true AND content has changed)
# Triggered only when deployed content_hash differs from calculated content_hash
resource "null_resource" "service_image_build" {
  count = var.build_image && local.content_has_changed ? 1 : 0

  triggers = {
    # Trigger rebuild when content_hash changes from deployed version
    content_hash = local.content_hash_value
    # Also trigger on image tag changes
    container_image = var.container_image
    # Track deployed hash to detect changes
    deployed_hash = local.deployed_content_hash
  }

  # Build Docker image via Cloud Build
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
