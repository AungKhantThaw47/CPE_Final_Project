# How To Use This Project

## Prerequisites

- Google Cloud project with billing enabled.
- `gcloud` CLI authenticated to the target project.
- Terraform 1.0 or newer.
- Docker available if you want to build or test containers locally.
- `python3` for Terraform external data and helper scripts.
- Optional: `make`, `jq`, and Neo4j credentials for graph sync.

## Configure Local Settings

Create local config files from the tracked examples:

```bash
cp terraform.tfvars.example terraform.tfvars
cp .env.example .env
```

Edit `terraform.tfvars` for non-sensitive deployment values:

```hcl
project_id  = "your-gcp-project-id"
region      = "asia-southeast1"
zone        = "asia-southeast1-a"
environment = "dev"
```

Put secrets and `TF_VAR_*` values in `.env`:

```dotenv
TF_VAR_project_id=your-gcp-project-id
TF_VAR_region=asia-southeast1
TF_VAR_hf_token=your-huggingface-token
TF_VAR_gemini_api_key=your-gemini-api-key
```

Neo4j is optional. Add these values only when you want automatic graph loading or runtime hash lookup:

```dotenv
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
NEO4J_AUTO_LOAD=true
```

## Deploy Infrastructure

Recommended Make workflow:

```bash
make check-tools
make fmt
make validate
make plan
make apply
```

One-command deployment:

```bash
make deploy-all
```

Direct Terraform workflow:

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=terraform.tfvars -out=tfplan
terraform apply tfplan
```

Show deployed outputs:

```bash
make output
```

## Run The Pipeline

Run the normal daily workflow:

```bash
make daily-pipeline
```

Run the manual coordinator workflow for a date range:

```bash
make manual-coordinator START_DATE=20-03-2026 END_DATE=21-03-2026
```

Run the coordinator Cloud Run job directly:

```bash
make coordinator-range START_DATE=20-03-2026 END_DATE=21-03-2026
```

Run the classifier directly for one processing date:

```bash
make classifier-process PROCESS_DATE=2026-03-20
```

More manual commands are documented in `MANUAL_PIPELINE_COMMANDS.md`.

## Work With Neo4j

Reload the dependency graph from the current manifest:

```bash
make restart-graph
```

Inspect graph state with the Cypher files in `queries/`, for example:

- `queries/01_jobs_and_services.cypher`
- `queries/06_hash_lineage.cypher`
- `queries/18_jobs_services_connections.cypher`

## Clean Local Generated Files

Remove the Terraform plan file:

```bash
make clean
```

Remove common local generated folders:

```bash
rm -rf .terraform .venv venv env
find . -name __pycache__ -type d -prune -exec rm -rf {} +
```

Do not delete `.env`, `terraform.tfvars`, or Terraform state files unless you know where the current deployment state is stored.

## Add Or Change A Service

1. Add or edit the service/job folder under `Codebase_Container/`.
2. Include a `Dockerfile` and dependency file (`requirements.txt` or `package.json`) when needed.
3. Register the component in `locals.jobs` or `locals.services` in `main.tf`.
4. Set required environment variables and IAM roles.
5. Run `make fmt`, `make validate`, and `make plan`.
6. Deploy with `make apply` or `make deploy-all`.

## Destroy Infrastructure

Destroy Terraform-managed resources only when you are sure the environment is disposable:

```bash
make destroy
```

Set `AUTO_APPROVE=true` only for automation:

```bash
make destroy AUTO_APPROVE=true
```
