variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "cpe-final-project"
}

variable "region" {
  description = "GCP Region (must support GPUs)"
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "asia-southeast1-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# ============================================
# Cloud Run Job Configuration
# ============================================

variable "job_name" {
  description = "Name of the Cloud Run Job"
  type        = string
  default     = "gpu-batch-job"
}

variable "docker_repository_id" {
  description = "Artifact Registry repository ID for Docker images"
  type        = string
  default     = "gpu-jobs"
}

variable "image_name" {
  description = "Docker image name"
  type        = string
  default     = "gpu-job-runner"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "service_account_id" {
  description = "Service account ID for Cloud Run Job"
  type        = string
  default     = "gpu-job-runner"
}

variable "gpu_type" {
  description = "GPU accelerator type"
  type        = string
  default     = "nvidia-l4"
}

# ============================================
# MLflow Configuration
# ============================================

variable "mlflow_db_password" {
  description = "Password for MLflow PostgreSQL database"
  type        = string
  sensitive   = true
  default     = "changeme123"
}

variable "mlflow_public_access" {
  description = "Allow public access to MLflow tracking server"
  type        = bool
  default     = true
}

variable "github_sha" {
  description = "GitHub commit SHA (provided by CI via TF_VAR_github_sha, empty for local builds)"
  type        = string
  default     = ""
}

# ============================================
# Deployment Hash Control System
# ============================================

variable "content_hash" {
  description = "Pure hash of codebase files (deterministic, no metadata)"
  type        = string
  default     = ""
}

variable "local_username" {
  description = "Local username for local deployments"
  type        = string
  default     = ""
}

variable "github_username" {
  description = "GitHub username for CI deployments"
  type        = string
  default     = ""
}
