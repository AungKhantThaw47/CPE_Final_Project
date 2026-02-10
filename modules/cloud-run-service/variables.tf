variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the service"
  type        = string
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "description" {
  description = "Description of the service"
  type        = string
  default     = ""
}

variable "container_image" {
  description = "Container image URL"
  type        = string
}

variable "codebase_path" {
  description = "Path to the codebase directory for building the container"
  type        = string
  default     = ""
}

variable "build_image" {
  description = "Whether to build the container image (true) or use pre-built image (false)"
  type        = bool
  default     = true
}

variable "cpu_limit" {
  description = "CPU limit for the service"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for the service"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "allow_public" {
  description = "Allow public access to the service"
  type        = bool
  default     = false
}

variable "environment_variables" {
  description = "Environment variables for the service"
  type        = map(string)
  default     = {}
}

variable "cloud_sql_instances" {
  description = "List of Cloud SQL instance connection names"
  type        = list(string)
  default     = []
}

variable "service_account_roles" {
  description = "IAM roles to grant to the service's service account"
  type        = list(string)
  default     = []
}

variable "github_sha" {
  description = "GitHub commit SHA (provided by CI, empty for local builds)"
  type        = string
  default     = ""
}
