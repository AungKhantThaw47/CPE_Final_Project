# Neo4j Bootstrap

This folder bootstraps an external Neo4j database with a graph model of this system.

## What It Creates

The graph includes:

- Repository and CI/CD workflow nodes
- GCP project, Artifact Registry, Cloud Build, and schedulers
- Cloud Run jobs and services
- Storage buckets
- Eventarc triggers
- Workflow orchestration edges
- Data flow relationships between jobs, services, and buckets

## Files

- `graph_manifest.json`: declarative system graph definition
- `load_graph.py`: loads the manifest into Neo4j
- `requirements.txt`: Python dependency for the Neo4j driver
- `queries/*.cypher`: reusable Cypher queries for pipeline and hash analysis
	- includes `14_upstream_latest_hash_lookup.cypher` for runtime latest-hash resolution

## Setup

```bash
cd bootstrap/neo4j
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Load The Graph

```bash
cp ../../.env.example ../../.env
```

Add these values to `.env`:

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
NEO4J_CLEAN=true
NEO4J_MANIFEST_PATH=bootstrap/neo4j/generated/terraform_post_action_graph.json
NEO4J_AUTO_LOAD=true
```

Then run:

```bash
python3 load_graph.py
```

The loader reads the repository `.env` file by default. To use a different env file, set `BOOTSTRAP_ENV_FILE=/path/to/.env` before running it.

## Terraform Hash Graph

After `terraform apply`, the post-action script generates a merged graph manifest at `bootstrap/neo4j/generated/terraform_post_action_graph.json`.

That generated file extends the base system graph with:

- one `DeploymentHash` node per job or service content hash
- `HAS_HASH` edges from each component to its content hash node
- `PREVIOUS_HASH` edges from each new hash node to the prior active hash node
- `deployment_source`, `updater`, and `deployment_ref` stored on the hash node
- direct `READS_FROM` and `WRITES_TO` edges between content-hash nodes and storage buckets
- `DEPENDS_ON_DATA_FROM` edges between content-hash nodes using the existing bucket-based data flow

## Runtime Hash Contract

The data pipeline uses hash-versioned storage paths:

- Producers write to `prefix/<CONTENT_HASH>/<YYYY-MM-DD>/...`
- Consumers read upstream data using Neo4j first, then fallback if needed

Recommended lookup order in jobs/services:

1. `SOURCE_CONTENT_HASH` override env var
2. Neo4j latest hash via `HAS_HASH`
3. GCS scan fallback by blob `updated` time

Example Neo4j lookup query used by downstream consumers:

```cypher
MATCH (c {key: "job:dvb-text-cleaner-job"})-[:HAS_HASH]->(h:DeploymentHash)
RETURN h.hash_value AS hash_value
LIMIT 1
```

Typical component keys:

- `job:dvb-crawler-job`
- `job:dvb-text-cleaner-job`
- `job:crisis-classifier-job`

If you want Neo4j to ingest the hash-aware graph, point `NEO4J_MANIFEST_PATH` at that generated file as shown above.

With `NEO4J_AUTO_LOAD=true`, `make apply` and `make deploy` now push that generated graph into Neo4j automatically as part of the Terraform post-action.

If you want to generate the manifest without updating Neo4j, set `NEO4J_AUTO_LOAD=false`.

## Example Queries

Show all nodes:

```cypher
MATCH (n:SystemNode)
RETURN n
```

Show the pipeline path from crawler to extractor:

```cypher
MATCH p = (:CloudRunJob {name: "dvb-crawler-job"})-[*1..10]->(:CloudRunJob {name: "dvb-extractor-job"})
RETURN p
```

Show everything that writes to storage:

```cypher
MATCH (a)-[r:WRITES_TO]->(b:StorageBucket)
RETURN a.name, type(r), b.name, r.path
ORDER BY a.name, b.name
```

Show workflow orchestration order:

```cypher
MATCH (:Workflow {name: "daily-pipeline"})-[r:ORCHESTRATES]->(job)
RETURN job.name, r.step_order
ORDER BY r.step_order
```
