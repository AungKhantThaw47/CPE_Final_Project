# CI/CD Pipeline

GitHub Actions workflow that automates Terraform infrastructure planning and deployment.

## Workflow Diagram

```mermaid
flowchart TD
    subgraph Triggers["Workflow Triggers"]
        TR1["Push to any branch"]
        TR2["Pull Request opened / updated"]
        TR3["workflow_dispatch\n(manual)"]
    end

    subgraph Plan["Job: terraform-plan\n(all events)"]
        P1["Checkout code"]
        P2["Cache Terraform plugins"]
        P3["Setup Terraform v1.14.3"]
        P4["Authenticate to GCP\n(GOOGLE_CREDENTIALS secret)"]
        P5["Setup gcloud CLI"]
        P6["Make scripts executable\nchmod +x scripts/*.sh"]
        P7["terraform fmt -check"]
        P8["terraform init"]
        P9["terraform validate"]
        P10["terraform plan -out=tfplan"]
        P11{"Is Pull Request?"}
        P12["Post plan summary\nas PR comment"]
        P13["Upload tfplan artifact\n(5-day retention)"]
    end

    subgraph Apply["Job: terraform-apply\n(push to main only)"]
        A1["Checkout code"]
        A2["Cache Terraform plugins"]
        A3["Setup Terraform v1.14.3"]
        A4["Authenticate to GCP"]
        A5["Setup gcloud CLI"]
        A6["Configure Docker\nfor Artifact Registry"]
        A7["terraform init"]
        A8["Download tfplan artifact"]
        A9["terraform apply -auto-approve tfplan"]
        A10["terraform output -json"]
    end

    subgraph GCP["GCP Resources Updated"]
        G1["Docker images built\nvia Cloud Build"]
        G2["Cloud Run Jobs deployed"]
        G3["Cloud Run Services deployed"]
        G4["GCS Buckets updated"]
        G5["IAM roles assigned"]
        G6["Cloud Scheduler rules updated"]
    end

    TR1 & TR2 & TR3 --> P1
    P1 --> P2 --> P3 --> P4 --> P5 --> P6
    P6 --> P7 --> P8 --> P9 --> P10
    P10 --> P11
    P11 -->|Yes| P12
    P11 -->|No| P13
    P12 --> P13

    P13 -->|"needs: terraform-plan\nif: push && ref == main"| A1
    A1 --> A2 --> A3 --> A4 --> A5 --> A6
    A6 --> A7 --> A8 --> A9 --> A10
    A9 --> G1 & G2 & G3 & G4 & G5 & G6
```

## Environment Variables & Secrets

| Name | Source | Used In |
|------|--------|---------|
| `GOOGLE_CREDENTIALS` | GitHub Secret | GCP authentication |
| `HF_TOKEN` | GitHub Secret | Hugging Face model downloads |
| `GEMINI_API_KEY` | GitHub Secret | Gemini API (annotator, extractor) |
| `GITHUB_TOKEN` | Built-in | Posting PR comments |
| `TF_VAR_github_sha` | `github.sha` | Content hash for image tagging |
| `TF_VAR_github_username` | `github.actor` | Deployment context labelling |

## Concurrency

The workflow uses a concurrency group keyed on the branch name, cancelling any in-progress run for the same branch when a new commit is pushed:

```
group: ${{ github.workflow }}-${{ github.head_ref || github.ref_name }}
cancel-in-progress: true
```

## Content-Hash Deployment Strategy

Terraform uses a content hash of each job's source directory to decide whether to rebuild and redeploy the Docker image:

- **Local builds**: hash computed from file contents using `scripts/compute_content_hash.sh`
- **GitHub Actions builds**: hash derived from `GITHUB-{first 7 chars of commit SHA}`

This ensures that only changed jobs trigger a new Cloud Build + Cloud Run deployment, minimising build time and cost.
