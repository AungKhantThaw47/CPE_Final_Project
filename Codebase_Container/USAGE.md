# Using Codebase_Container with Terraform

## Overview

All application codebases are now centralized in `Codebase_Container/`. The Terraform modules have been updated to accept a `codebase_path` variable, allowing you to specify different codebase locations.

## Example Usage

### Using Cloud Scheduler Module with Different Codebases

```hcl
# Example 1: Crawler Scheduled Job
module "crawler_scheduler" {
  source = "./modules/cloud-scheduler"
  
  project_id        = var.project_id
  region            = var.region
  job_name          = "crawler-job"
  job_description   = "Daily web crawler"
  schedule          = "0 2 * * *"  # Daily at 2 AM
  container_image   = "asia-southeast1-docker.pkg.dev/${var.project_id}/myrepo/crawler:latest"
  
  # Point to crawler codebase
  codebase_path     = "${path.root}/Codebase_Container/crawler_codebase/default"
  
  environment_variables = {
    CRAWL_TARGET = "https://example.com"
    OUTPUT_PATH  = "/data/output"
  }
}

# Example 2: Text Cleaning Scheduled Job
module "text_clean_scheduler" {
  source = "./modules/cloud-scheduler"
  
  project_id        = var.project_id
  region            = var.region
  job_name          = "text-clean-job"
  job_description   = "Weekly text cleaning"
  schedule          = "0 3 * * 0"  # Weekly on Sunday at 3 AM
  container_image   = "asia-southeast1-docker.pkg.dev/${var.project_id}/myrepo/text-clean:latest"
  
  # Point to text cleaning codebase
  codebase_path     = "${path.root}/Codebase_Container/text_clean_codebase/default"
  
  environment_variables = {
    INPUT_BUCKET  = "gs://my-bucket/input"
    OUTPUT_BUCKET = "gs://my-bucket/output"
  }
}

# Example 3: Custom Cloud Scheduler Function
module "custom_scheduler" {
  source = "./modules/cloud-scheduler"
  
  project_id        = var.project_id
  region            = var.region
  job_name          = "custom-function"
  job_description   = "Custom scheduled function"
  schedule          = "*/30 * * * *"  # Every 30 minutes
  container_image   = "asia-southeast1-docker.pkg.dev/${var.project_id}/myrepo/custom:latest"
  
  # Point to cloud scheduler function codebase
  codebase_path     = "${path.root}/Codebase_Container/cloud_scheduler_function"
}
```

## Benefits

1. **Centralized Management**: All application logic in one location
2. **Flexibility**: Easy to switch between different codebases
3. **Reusability**: Same codebase can be used by multiple jobs
4. **Organization**: Clear separation between infrastructure and application code

## Migration Notes

If you have existing Terraform configurations, update them to use the new `codebase_path` variable:

**Before:**
```hcl
module "my_job" {
  source = "./modules/cloud-scheduler"
  # ... other variables
}
```

**After:**
```hcl
module "my_job" {
  source = "./modules/cloud-scheduler"
  codebase_path = "${path.root}/Codebase_Container/your_codebase"
  # ... other variables
}
```

## Default Behavior

If `codebase_path` is not specified, the module will default to `${path.module}/function` for backward compatibility.
