variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the Cloud Run job and scheduler"
  type        = string
  default     = "asia-southeast1"
}

variable "job_name" {
  description = "Name of the scheduled job"
  type        = string
}

variable "job_description" {
  description = "Description of the Cloud Scheduler job"
  type        = string
  default     = "Scheduled cron job"
}

variable "schedule" {
  description = "Cron schedule expression (e.g., '0 2 * * *' for daily at 2 AM)"
  type        = string
}

variable "time_zone" {
  description = "Time zone for the schedule"
  type        = string
  default     = "Asia/Bangkok"
}

variable "container_image" {
  description = "Container image for the Cloud Run job"
  type        = string
}

variable "cpu_limit" {
  description = "CPU limit for the job"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for the job"
  type        = string
  default     = "512Mi"
}

variable "timeout" {
  description = "Job execution timeout"
  type        = string
  default     = "600s"
}

variable "max_retries" {
  description = "Maximum number of retries for failed jobs"
  type        = number
  default     = 3
}

variable "attempt_deadline" {
  description = "Deadline for job attempts"
  type        = string
  default     = "320s"
}

variable "retry_count" {
  description = "Number of retry attempts for the scheduler"
  type        = number
  default     = 3
}

variable "environment_variables" {
  description = "Environment variables for the job"
  type        = map(string)
  default     = {}
}

variable "job_service_account_roles" {
  description = "IAM roles to grant to the job's service account"
  type        = list(string)
  default     = []
}
variable "github_sha" {
  description = "GitHub commit SHA (provided by CI, empty for local builds)"
  type        = string
  default     = ""
}
variable "codebase_path" {
  description = "Path to the codebase folder containing Dockerfile, main.py, and requirements.txt"
  type        = string
  default     = ""
}

variable "build_image" {
  description = "Whether to build the container image (true) or use pre-built image (false)"
  type        = bool
  default     = true
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

variable "enable_gpu" {
  description = "Enable GPU support for the Cloud Run job"
  type        = bool
  default     = false
}

variable "gpu_type" {
  description = "GPU type for the Cloud Run job (e.g., nvidia-l4, nvidia-tesla-t4)"
  type        = string
  default     = "nvidia-l4"
}

variable "execution_environment" {
  description = "Execution environment generation (EXECUTION_ENVIRONMENT_GEN1 or EXECUTION_ENVIRONMENT_GEN2). Gen2 required for GPU."
  type        = string
  default     = "EXECUTION_ENVIRONMENT_GEN2"
}

variable "enable_scheduler" {
  description = "Enable Cloud Scheduler to automatically trigger the job on a schedule"
  type        = bool
  default     = true
}
