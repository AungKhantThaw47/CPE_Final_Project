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
