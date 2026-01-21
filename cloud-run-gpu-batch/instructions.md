# Role
You are a senior cloud platform engineer.
Your task is to design and implement a GPU-based batch execution system on Google Cloud.
You MUST follow all constraints strictly.

---

## Hard Constraints (DO NOT VIOLATE)

1. ❌ Do NOT use gcloud CLI
2. ❌ Do NOT use manual console steps
3. ❌ Do NOT use Compute Engine, GKE, or Vertex AI
4. ❌ Do NOT create long-running services
5. ✅ Use ONLY:
   - Python scripts
   - Terraform
6. ✅ GPU workload must auto-stop after completion
7. ✅ GPU cost must stop when Python script exits

---

## Target Architecture

- Google Cloud Run **Jobs** (NOT services)
- GPU accelerator (NVIDIA L4 or T4)
- Python-based execution
- Docker container
- Terraform-managed infrastructure
- Python-based job execution trigger (REST API)

---

## Functional Requirements

### Execution
- A Python script must run once
- It must use GPU (CUDA-visible)
- It must terminate automatically
- When terminated, the infrastructure must stop billing

### Outputs
- Results must be retrievable via:
  - Cloud Logging OR
  - Google Cloud Storage (preferred)

---

## Infrastructure Requirements (Terraform)

Terraform must provision:

1. Required APIs:
   - run.googleapis.com
   - artifactregistry.googleapis.com
   - iam.googleapis.com
   - cloudscheduler.googleapis.com (optional)

2. Artifact Registry (Docker)
3. Service Account for Cloud Run Job
4. IAM permissions:
   - storage.objectAdmin (if using GCS)
   - run.invoker
5. Cloud Run Job (v2)
   - GPU enabled
   - Memory and CPU limits defined
   - Timeout defined
   - Retry disabled (max_retries = 0)

Terraform MUST NOT:
- Build Docker images
- Execute jobs
- Use null_resource with local-exec

---

## Container Requirements

- Base image MUST support NVIDIA CUDA
- Python version >= 3.10
- Must install required ML libraries (e.g., torch)
- Entrypoint MUST exit after work is done
- No infinite loops
- No servers
- No sleep-based logic

---

## Python Job Code Requirements

The job Python script MUST:

1. Detect GPU availability
2. Print GPU name
3. Execute a GPU-eligible computation
4. Save output to Google Cloud Storage OR log stdout
5. Exit naturally (no force kill)

Example expectations:
- torch.cuda.is_available() == True
- torch.cuda.get_device_name(0) printed

---

## Job Execution (NO CLI)

Job execution MUST be triggered using:

- Python script
- REST API call to Cloud Run Jobs endpoint
- OAuth2 using google-auth

Example behavior:
- Python script sends POST request to:
  /apis/run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run
- Receives execution metadata
- Does NOT wait for job completion

---

## Optional Automation

If scheduling is required:
- Use Cloud Scheduler
- Terraform-managed
- HTTP POST with OAuth service account

---

## Cost Control Rules

- GPU must exist ONLY during execution
- No idle GPU resources
- No always-on containers
- No retries unless explicitly required

---

## Deliverables Expected From You

You MUST produce:

1. Terraform files:
   - main.tf
   - variables.tf
   - outputs.tf

2. Dockerfile (GPU-ready)

3. Python job script:
   - main.py

4. Python execution trigger:
   - trigger_job.py

5. Clear comments explaining WHY each piece exists

---

## Style Rules

- Be explicit
- Be concise
- No assumptions
- No skipped steps
- No CLI references
- No UI references

---

## Final Validation Checklist

Before answering, ensure:
- GPU auto-stops after job ends
- No CLI is required at any step
- Terraform handles infra only
- Python handles execution only
- System is production-safe

Failure to meet ANY requirement is unacceptable.
