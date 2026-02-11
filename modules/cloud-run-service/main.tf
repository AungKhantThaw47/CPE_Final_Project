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
    external = {
      source  = "hashicorp/external"
      version = "~> 2.0"
    }
  }
}

# Check git status and find the last commit that changed the codebase directory
data "external" "git_status" {
  program = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0 ? [
    "PowerShell", "-Command", <<-EOT
      Set-Location '${replace(path.root, "/", "\\")}'
      
      # Get current git commit (use github_sha if provided, otherwise HEAD)
      $targetCommit = '${var.github_sha}'
      if ([string]::IsNullOrEmpty($targetCommit)) {
        try {
          $targetCommit = (git rev-parse --short HEAD 2>$null)
          if (-not $targetCommit) { $targetCommit = "nogit" }
        } catch {
          $targetCommit = "nogit"
        }
      } else {
        # Shorten the full GitHub SHA
        $targetCommit = $targetCommit.Substring(0, [Math]::Min(7, $targetCommit.Length))
      }
      
      # Get relative path to codebase directory
      $codebasePath = '${replace(var.codebase_path != "" ? var.codebase_path : "${path.module}/service", "/", "\\")}'
      
      # Check if we're in a git repo
      if ($targetCommit -eq "nogit") {
        $hasChanges = "true"
        $lastCommit = "nogit"
      } else {
        # Check for uncommitted changes (only relevant for local, not CI)
        $isCI = '${var.github_sha}' -ne ''
        if (-not $isCI) {
          try {
            $gitChanges = (git status --porcelain $codebasePath 2>$null)
            if ($gitChanges) {
              $hasChanges = "true"
              $lastCommit = $targetCommit
              $result = @{
                has_changes = $hasChanges
                git_commit = $lastCommit
              }
              $result | ConvertTo-Json -Compress
              exit 0
            }
          } catch {
            $hasChanges = "true"
            $lastCommit = $targetCommit
            $result = @{
              has_changes = $hasChanges
              git_commit = $lastCommit
            }
            $result | ConvertTo-Json -Compress
            exit 0
          }
        }
        
        # Find the last commit that actually changed the codebase directory
        try {
          # Check if current commit changed the codebase (excluding .build-hash)
          $commitDiff = (git diff-tree --no-commit-id --name-only -r $targetCommit -- $codebasePath 2>$null | Where-Object { $_ -notlike '*/.build-hash' })
          if ($commitDiff) {
            # Current commit has real changes
            $lastCommit = $targetCommit
          } else {
            # No real changes or only .build-hash changed - find last commit that changed non-.build-hash files
            # Use git log with path and grep to filter out .build-hash commits
            $allCommits = (git log --format=%h -n 50 $targetCommit -- $codebasePath 2>$null)
            $lastCommit = $targetCommit
            foreach ($c in $allCommits) {
              $cDiff = (git diff-tree --no-commit-id --name-only -r $c -- $codebasePath 2>$null | Where-Object { $_ -notlike '*/.build-hash' })
              if ($cDiff) {
                $lastCommit = $c
                break
              }
            }
          }
          $hasChanges = "false"
        } catch {
          $hasChanges = "false"
          $lastCommit = $targetCommit
        }
      }
      
      # Output JSON for Terraform
      $result = @{
        has_changes = $hasChanges
        git_commit = $lastCommit
      }
      $result | ConvertTo-Json -Compress
    EOT
  ] : ["sh", "-c", <<-EOT
    cd '${path.root}' || exit 1
    
    # Get current git commit (use github_sha if provided, otherwise HEAD)
    target_commit='${var.github_sha}'
    if [ -z "$target_commit" ]; then
      target_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")
    else
      # Shorten the full GitHub SHA
      target_commit=$(echo "$target_commit" | cut -c1-7)
    fi
    
    # Get relative path to codebase directory
    codebase_path='${var.codebase_path != "" ? var.codebase_path : "${path.module}/service"}'
    
    # Check if we're in a git repo
    if [ "$target_commit" = "nogit" ]; then
      has_changes="true"
      last_commit="nogit"
    else
      # Check for uncommitted changes (only relevant for local, not CI)
      is_ci='${var.github_sha != "" ? "true" : "false"}'
      if [ "$is_ci" = "false" ]; then
        git_changes=$(git status --porcelain "$codebase_path" 2>/dev/null || echo "")
        if [ -n "$git_changes" ]; then
          has_changes="true"
          last_commit="$target_commit"
          echo "{\"has_changes\":\"$has_changes\",\"git_commit\":\"$last_commit\"}"
          exit 0
        fi
      fi
      
      # Find the last commit that actually changed the codebase directory
      # Exclude .build-hash from change detection
      commit_diff=$(git diff-tree --no-commit-id --name-only -r "$target_commit" -- "$codebase_path" 2>/dev/null | grep -v '\.build-hash$' || echo "")
      if [ -n "$commit_diff" ]; then
        # Current commit has real changes
        last_commit="$target_commit"
      else
        # No real changes or only .build-hash changed - find last commit with real changes
        last_commit="$target_commit"
        for commit in $(git log --format=%h -n 50 "$target_commit" -- "$codebase_path" 2>/dev/null); do
          c_diff=$(git diff-tree --no-commit-id --name-only -r "$commit" -- "$codebase_path" 2>/dev/null | grep -v '\.build-hash$' || echo "")
          if [ -n "$c_diff" ]; then
            last_commit="$commit"
            break
          fi
        done
      fi
      has_changes="false"
    fi
    
    # Output JSON for Terraform
    echo "{\"has_changes\":\"$has_changes\",\"git_commit\":\"$last_commit\"}"
  EOT
  ]
}

locals {
  # Use provided codebase_path or fallback to default location
  codebase_directory = var.codebase_path != "" ? var.codebase_path : "${path.module}/service"

  # OS detection (check for Windows drive letter like C:, D:)
  is_windows = length(regexall("^[A-Za-z]:", abspath(path.root))) > 0

  # Generate hash of all files in the codebase directory, excluding .build-hash*
  codebase_files = [
    for file in fileset(local.codebase_directory, "**") :
    file if !startswith(file, ".build-hash") && fileexists("${local.codebase_directory}/${file}")
  ]

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
  build_env    = data.external.git_status.result.has_changes == "true" ? "LOCAL" : "GITHUB"
  # Use git commit from last change to codebase (LOCAL prefix only for uncommitted changes)
  build_hash   = data.external.git_status.result.has_changes == "true" ? "LOCAL-${substr(local.codebase_hash, 0, 7)}" : "GITHUB-${data.external.git_status.result.git_commit}"

  # Sanitize service name for service account IDs (replace underscores with hyphens)
  sa_safe_service_name = replace(var.service_name, "_", "-")

  # Build commands for each OS
  windows_build_command = <<-EOT
    if (Test-Path '${replace(path.root, "/", "\\")}\\utils') {
      Copy-Item -Recurse -Force '${replace(path.root, "/", "\\")}\\utils' '${replace(local.codebase_directory, "/", "\\")}\'
    }
    
    cd '${replace(local.codebase_directory, "/", "\\")}'
    gcloud builds submit `
      --project=${var.project_id} `
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
      --project=${var.project_id} \
      --config cloudbuild.yaml \
      --substitutions=_IMAGE_TAG=${var.container_image}
    
    if [ -d '${local.codebase_directory}/utils' ]; then
      rm -rf '${local.codebase_directory}/utils'
    fi
  EOT
}

# Generate .build-hash file for the service
# GitHub build hash (committed to git)
resource "local_file" "build_hash_github" {
  filename = "${local.codebase_directory}/.build-hash.github"
  content  = data.external.git_status.result.has_changes == "true" ? "GITHUB-${data.external.git_status.result.git_commit}" : local.build_hash
}

# Local build hash (in .gitignore, only created when there are local changes)
resource "local_file" "build_hash_local" {
  count    = data.external.git_status.result.has_changes == "true" ? 1 : 0
  filename = "${local.codebase_directory}/.build-hash.local"
  content  = local.build_hash
}

# Build service image (only if build_image is true)
resource "null_resource" "service_image_build" {
  count = var.build_image ? 1 : 0

  triggers = {
    codebase_hash = local.codebase_hash
    build_hash    = local.build_hash
  }

  depends_on = [local_file.build_hash_github, local_file.build_hash_local]

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
