# System Architecture

High-level view of all GCP resources provisioned by Terraform for the CPE Final Project.

## Architecture Diagram

```mermaid
graph TD
    subgraph Developer["👨‍💻 Developer / CI-CD"]
        GH["GitHub Repository"]
        GHA[".github/workflows\nterraform-deploy.yml"]
        POST["terraform_post_action.py\npost-apply summary + graph sync"]
    end

    subgraph GCP["☁️ Google Cloud Platform (asia-southeast1)"]

        subgraph Registry["Artifact Registry"]
            AR["Docker Repository\ncpe-docker-repo"]
        end

        subgraph Schedulers["Cloud Scheduler (Cron)"]
            SCHED1["daily-data-processor\n0 * * * * (every hour)"]
        end

        subgraph Jobs["Cloud Run Jobs (On-Demand / Scheduled)"]
            J1["dvb-crawler-job\n1 CPU · 512 MB\nNode.js"]
            J2["dvb-text-cleaner-job\n1 CPU · 512 MB\nPython"]
            J3["crisis-classifier-job\n4 CPU · 16 GB\nPython + HF"]
            J4["gpu-batch-job\n4 CPU · 16 GB · L4 GPU\nPython + PyTorch"]
            J5["daily-data-processor\n1 CPU · 512 MB\nPython"]
        end

        subgraph Services["Cloud Run Services (Always-On HTTP)"]
            S1["mlflow\n2 CPU · 4 GB\n0–2 instances"]
            S2["crisis-admin\n1 CPU · 512 MB\n0–1 instances"]
            S3["dvb-annotator\n1 CPU · 512 MB\n0–3 instances"]
            S4["dvb-extractor\n1 CPU · 512 MB\n0–3 instances"]
        end

        subgraph Storage["Cloud Storage Buckets"]
            B1["crawler-data\n90-day retention"]
            B2["cleaned-crawler-data\n90-day retention"]
            B3["crisis-crawler-data\n180-day retention"]
            B4["llm-extraction\n(long-term)"]
            B5["gpu-job-outputs\n30-day retention"]
            B6["mlflow-artifacts\n90-day retention"]
            B7["terraform-state\n(indefinite)"]
        end

        subgraph Events["Admin-driven transitions and optional Eventarc Triggers"]
            EA1["Admin job trigger\ncrisis_articles/ → annotator"]
            EA2["Admin job trigger\nannotated_articles/ → extractor"]
        end

        IAM["IAM Service Accounts\n(per job/service)"]
        CB["Cloud Build\n(Docker image builds)"]
    end

    subgraph Graph["External Graph Database"]
        NEO["Neo4j\nsystem dependency graph"]
        HASH["DeploymentHash nodes\ncontent hash + updater"]
    end

    GH --> GHA
    GHA --> CB
    GHA --> POST
    CB --> AR
    AR --> J1 & J2 & J3 & J4 & J5
    AR --> S1 & S2 & S3 & S4

    SCHED1 -->|triggers| J5

    J1 -->|writes raw articles| B1
    J2 -->|reads raw, writes cleaned| B2
    J3 -->|reads cleaned, writes crisis| B3
    J4 -->|writes results| B5

    B3 -->|admin move to crisis_articles/| EA1
    EA1 -->|invokes (run dvb-annotator-job)| S3
    S3 -->|writes annotated| B3

    B3 -->|admin move to annotated_articles/| EA2
    EA2 -->|invokes (run dvb-extractor-job)| S4
    S4 -->|writes extracted| B4

    S2 -->|reads crisis articles| B3
    S1 -->|stores artifacts| B6

    IAM -.->|grants roles| J1 & J2 & J3 & J4 & J5
    IAM -.->|grants roles| S1 & S2 & S3 & S4

    J1 -.->|content hash node| HASH
    J2 -.->|content hash node| HASH
    J3 -.->|content hash node| HASH
    J4 -.->|content hash node| HASH
    J5 -.->|content hash node| HASH
    S1 -.->|content hash node| HASH
    S2 -.->|content hash node| HASH
    S3 -.->|content hash node| HASH
    S4 -.->|content hash node| HASH
    POST -->|updates generated graph| NEO
    HASH --> NEO
```

## Component Summary

| Component | Type | Runtime | Resources |
|-----------|------|---------|-----------|
| `dvb-crawler-job` | Cloud Run Job | Node.js | 1 CPU, 512 MB |
| `dvb-text-cleaner-job` | Cloud Run Job | Python | 1 CPU, 512 MB |
| `crisis-classifier-job` | Cloud Run Job | Python + Hugging Face | 4 CPU, 16 GB |
| `gpu-batch-job` | Cloud Run Job | Python + PyTorch | 4 CPU, 16 GB, NVIDIA L4 |
| `daily-data-processor` | Cloud Run Job (scheduled) | Python | 1 CPU, 512 MB |
| `mlflow` | Cloud Run Service | MLflow 3.8.1 | 2 CPU, 4 GB, 0–2 instances |
| `crisis-admin` | Cloud Run Service | Python | 1 CPU, 512 MB, 0–1 instances |
| `dvb-annotator` | Cloud Run Service | Python + Gemini API | 1 CPU, 512 MB, 0–3 instances |
| `dvb-extractor` | Cloud Run Service | Python + Gemini API | 1 CPU, 512 MB, 0–3 instances |

## Graph Sync Notes

After Terraform apply, `scripts/terraform_post_action.py` generates a Neo4j graph manifest and can auto-sync it to the configured external Neo4j database.

The graph tracks:
- system topology
- bucket-based data dependencies
- one `DeploymentHash` node per service or job content hash
- deployment metadata such as `deployment_source` and `updater`
