variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "service_name" {
  description = "Name of the MLflow Cloud Run service"
  type        = string
  default     = "mlflow-server"
}

variable "mlflow_image" {
  description = "Docker image for MLflow server"
  type        = string
  default     = ""  # Will be set to built image
}

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "mlflow"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "cpu" {
  description = "CPU limit for MLflow container"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit for MLflow container"
  type        = string
  default     = "2048Mi"
}

variable "allow_public_access" {
  description = "Allow public access to MLflow server"
  type        = bool
  default     = true
}
