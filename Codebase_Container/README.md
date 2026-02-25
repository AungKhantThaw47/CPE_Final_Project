# Codebase Container

This directory contains all application logic codebases for different Cloud Run jobs and scheduled tasks.

## Structure

```
Codebase_Container/
├── crawler_codebase/          # Web crawler application
│   └── default/
│       └── main.py
├── text_clean_codebase/       # Text cleaning application
│   └── default/
│       └── main.py
└── cloud_scheduler_function/  # Cloud Scheduler function
    ├── Dockerfile
    ├── main.py
    └── requirements.txt
```

## Adding New Codebases

When adding a new codebase to this container:

1. Create a new folder with a descriptive name (e.g., `data_processing_function`)
2. Include the necessary files for your application:
   - `Dockerfile` - Container image definition
   - `main.py` - Application entry point
   - `requirements.txt` - Python dependencies
3. Update Terraform configuration to reference the new codebase location

## Usage with Terraform

### Cloud Scheduler Module

To use a codebase from this container with the cloud-scheduler module:

```hcl
module "my_scheduled_job" {
  source = "./modules/cloud-scheduler"
  
  project_id       = var.project_id
  region           = var.region
  job_name         = "my-job"
  schedule         = "0 2 * * *"
  container_image  = "gcr.io/my-project/my-image:latest"
  
  # Specify the codebase path
  codebase_path    = "${path.root}/Codebase_Container/cloud_scheduler_function"
}
```

### Example: Using Different Codebases

```hcl
# Crawler job
module "crawler_job" {
  source        = "./modules/cloud-scheduler"
  codebase_path = "${path.root}/Codebase_Container/crawler_codebase/default"
  # ... other variables
}

# Text cleaning job
module "text_clean_job" {
  source        = "./modules/cloud-scheduler"
  codebase_path = "${path.root}/Codebase_Container/text_clean_codebase/default"
  # ... other variables
}
```

## Best Practices

1. **Isolation**: Each codebase should be self-contained with its own dependencies
2. **Documentation**: Add a README.md in each codebase folder explaining its purpose
3. **Naming**: Use clear, descriptive names for codebase folders
4. **Structure**: Follow a consistent structure across all codebases for maintainability
