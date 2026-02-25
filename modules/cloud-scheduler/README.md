# Cloud Scheduler Module

This module creates a scheduled cron job using Cloud Scheduler and Cloud Run Jobs.

## Features

- Cloud Run Job with custom container
- Cloud Scheduler with cron expression
- Service accounts with proper IAM permissions
- Automatic retries on failure
- Configurable resources (CPU, memory, timeout)

## Sample Python Function

The included Python function demonstrates:
- API data fetching
- Data processing
- Logging
- Error handling

## Usage

```hcl
module "scheduled_job" {
  source = "./modules/cloud-scheduler"

  project_id  = "your-project-id"
  region      = "asia-southeast1"
  job_name    = "daily-data-processor"
  description = "Daily data processing job"
  
  # Run every day at 2 AM Bangkok time
  schedule  = "0 2 * * *"
  time_zone = "Asia/Bangkok"
  
  container_image = "asia-southeast1-docker.pkg.dev/your-project/gpu-jobs/scheduler-job:latest"
  
  cpu_limit    = "1"
  memory_limit = "512Mi"
  timeout      = "600s"
  
  environment_variables = {
    ENV = "production"
  }
  
  job_service_account_roles = [
    "roles/storage.objectViewer",
  ]
}
```

## Building the Container

```bash
# Build and push the Docker image
./modules/cloud-scheduler/build.sh your-project-id scheduler-job asia-southeast1
```

Or use Cloud Build:

```bash
cd modules/cloud-scheduler/function
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/your-project-id/gpu-jobs/scheduler-job:latest
```

## Cron Schedule Examples

- `*/5 * * * *` - Every 5 minutes
- `0 * * * *` - Every hour
- `0 2 * * *` - Daily at 2 AM
- `0 9 * * 1` - Every Monday at 9 AM
- `0 0 1 * *` - First day of every month at midnight

## Manual Trigger

You can manually trigger the job for testing:

```bash
gcloud scheduler jobs run daily-data-processor --location=asia-southeast1
```

## Outputs

- `scheduler_job_name` - Name of the Cloud Scheduler job
- `cloud_run_job_name` - Name of the Cloud Run job
- `service_account_email` - Service account email
- `schedule` - Cron schedule expression
