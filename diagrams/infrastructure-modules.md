# Infrastructure Modules

Terraform module structure and the relationship between root-level resources and reusable modules.

## Module Dependency Diagram

```mermaid
graph TD
    subgraph Root["Root Module (main.tf)"]
        R_APIS["google_project_service\nEnable GCP APIs"]
        R_AR["google_artifact_registry_repository\nDocker registry"]
        R_SA["google_service_account\n(per job / service)"]
        R_IAM["google_project_iam_member\n(per role)"]
        R_BUCKETS["GCS Buckets\n(5 buckets)"]
        R_JOBS["locals.jobs\nJob definitions map"]
        R_SERVICES["locals.services\nService definitions map"]
        R_EA["google_eventarc_trigger\n(annotator + extractor)"]
        R_WF["google_workflows_workflow\n(orchestration)"]
    end

    subgraph ModScheduler["modules/cloud-scheduler"]
        MS_JOB["google_cloud_run_v2_job\nCloud Run Job"]
        MS_SA["google_service_account"]
        MS_SCHED["google_cloud_scheduler_job\n(optional)"]
        MS_BUILD["null_resource\nCloud Build trigger"]
    end

    subgraph ModService["modules/cloud-run-service"]
        MV_SVC["google_cloud_run_v2_service\nCloud Run Service"]
        MV_SA["google_service_account"]
        MV_IAM["google_cloud_run_v2_service_iam_member\n(public access)"]
        MV_BUILD["null_resource\nCloud Build trigger"]
    end

    subgraph ModMLflow["Codebase_Container/mlflow"]
        ML_SVC["MLflow Tracking Server\n(extends cloud-run-service)"]
        ML_IMG["Dockerfile\nMLflow 3.8.1 + GCS backend"]
    end

    subgraph Utils["utils/"]
        U_PY["gcs_utils.py\nPython GCS helpers"]
        U_JS["gcs_utils.js\nNode.js GCS helpers"]
    end

    R_APIS -->|"depends_on"| R_AR
    R_APIS -->|"depends_on"| R_BUCKETS
    R_AR -->|"image registry"| ModScheduler
    R_AR -->|"image registry"| ModService

    R_JOBS -->|"for_each"| ModScheduler
    R_SERVICES -->|"for_each"| ModService

    R_SA --> R_IAM
    R_IAM --> ModScheduler
    R_IAM --> ModService

    R_BUCKETS --> R_EA
    R_EA -->|"triggers"| MV_SVC

    ModMLflow -->|"uses"| ModService

    ModScheduler --> MS_JOB
    ModScheduler --> MS_SA
    ModScheduler --> MS_SCHED
    ModScheduler --> MS_BUILD

    ModService --> MV_SVC
    ModService --> MV_SA
    ModService --> MV_IAM
    ModService --> MV_BUILD

    Utils -.->|"imported by"| ModScheduler
    Utils -.->|"imported by"| ModService
```

## Module Input/Output Summary

### `modules/cloud-scheduler`

Provisions a **Cloud Run Job** with an optional **Cloud Scheduler** trigger and a **Cloud Build** step to build and push the Docker image.

| Input Variable | Description |
|----------------|-------------|
| `codebase_path` | Path to the job's source directory (for Docker build) |
| `container_image` | Full Artifact Registry image URI |
| `enable_scheduler` | Whether to create a Cloud Scheduler rule |
| `schedule` | Cron expression (e.g. `0 * * * *`) |
| `enable_gpu` | Attach NVIDIA L4 GPU accelerator |
| `cpu_limit` | vCPU limit |
| `memory_limit` | Memory limit (e.g. `512Mi`, `16Gi`) |
| `timeout` | Job execution timeout |
| `environment_variables` | Map of env vars injected into the container |
| `service_account_roles` | IAM roles granted to the job's service account |

### `modules/cloud-run-service`

Provisions a **Cloud Run Service** (always-on HTTP) with optional public access and a **Cloud Build** step.

| Input Variable | Description |
|----------------|-------------|
| `codebase_path` | Path to the service's source directory |
| `container_image` | Full Artifact Registry image URI |
| `cpu_limit` | vCPU limit |
| `memory_limit` | Memory limit |
| `min_instances` | Minimum number of running instances |
| `max_instances` | Maximum number of running instances |
| `port` | HTTP port the container listens on |
| `allow_public` | Whether to grant unauthenticated access |
| `environment_variables` | Map of env vars injected into the container |
| `service_account_roles` | IAM roles granted to the service's service account |
| `cloud_sql_instances` | List of Cloud SQL connection strings (optional) |

### `Codebase_Container/mlflow`

Contains the MLflow Cloud Run container assets used by the root module's `mlflow` service entry.

## Directory Structure

```
CPE_Final_Project/
├── main.tf                    # Root module — orchestrates all resources
├── variables.tf               # Input variables with defaults
├── outputs.tf                 # Exported values (URLs, bucket names, etc.)
├── provider.tf                # GCP provider + GCS backend for Terraform state
├── modules/
│   ├── cloud-scheduler/       # Reusable Cloud Run Job + Scheduler module
│   └── cloud-run-service/     # Reusable Cloud Run Service module
├── Codebase_Container/
│   ├── mlflow/               # MLflow server container assets
│   ├── crawler_job/           # dvb-crawler-job source (Node.js)
│   ├── gpu_batch_job/         # gpu-batch-job source (Python + PyTorch)
│   ├── cloud_scheduler_function/ # daily-data-processor source (Python)
│   ├── text_clean_codebase/   # dvb-text-cleaner-job source (Python)
│   ├── crisis_classifier_job/ # crisis-classifier-job source (Python + HF)
│   ├── extractor_job/         # dvb-extractor source (Python + Gemini)
│   ├── annotator_job/         # dvb-annotator source (Python + Gemini)
│   └── crisis_admin/          # crisis-admin source (Python)
├── utils/
│   ├── gcs_utils.py           # Shared Python GCS helpers
│   └── gcs_utils.js           # Shared Node.js GCS helpers
└── scripts/
    ├── terraform_compute_hash.sh     # Unix Terraform hash adapter
    ├── terraform_compute_hash.ps1    # Windows Terraform hash adapter
    ├── get_deployed_content_hash.sh  # Unix deployed hash lookup
    ├── get_deployed_content_hash.ps1 # Windows deployed hash lookup
    ├── get_username.sh               # Unix username lookup
    ├── get_username.ps1              # Windows username lookup
    ├── hash_module.sh                # Shared Unix hash helpers
    └── Hash-Module.psm1              # Shared PowerShell hash helpers
```
