# CPE Final Project — Diagrams

This folder contains architecture documentation and Mermaid diagrams for the CPE Final Project: a cloud-native, automated Burmese news processing and crisis-classification platform deployed on Google Cloud Platform (GCP).

## Diagrams Index

| File | Description |
|------|-------------|
| [system-architecture.md](system-architecture.md) | Overall GCP system architecture — all services, jobs, storage buckets, and their relationships |
| [data-pipeline.md](data-pipeline.md) | End-to-end data pipeline — from DVB web scraping through text cleaning, crisis classification, annotation, and extraction |
| [cicd-pipeline.md](cicd-pipeline.md) | GitHub Actions CI/CD workflow — Terraform plan on PR, Terraform apply on merge to `main` |
| [infrastructure-modules.md](infrastructure-modules.md) | Terraform module structure — reusable modules, post-apply automation, and Neo4j graph sync |

## Neo4j Coverage

The documentation and diagrams now include the external Neo4j dependency graph flow:
- generated from Terraform post-action output
- synced automatically after `make apply` or `make deploy` when enabled
- includes content-hash nodes and dependency edges between deployed components

## Rendering Mermaid Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) syntax and can be viewed directly in:
- **GitHub** — renders Mermaid natively in `.md` files
- **VS Code** — install the [Mermaid Preview](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) extension
- **Mermaid Live Editor** — paste diagram source at <https://mermaid.live>
