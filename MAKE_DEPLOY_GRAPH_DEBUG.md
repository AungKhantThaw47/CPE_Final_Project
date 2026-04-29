# Analysis: Why pending_review_annotation/ Neo4j Linkage Broke

## Deployment Flow: `make deploy`

```
make deploy
  ├── Terraform plan + apply
  │   └── Creates/updates Cloud Run jobs and services
  └── make post-apply (AUTOMATIC)
      └── bash scripts/terraform_post_action.sh
          └── python3 scripts/terraform_post_action.py
              ├── Get Terraform outputs (job/service configurations)
              ├── Load base_manifest (bootstrap/neo4j/graph_manifest.json)
              ├── build_dynamic_hash_graph()  ← GRAPH GENERATION LOGIC
              │   ├── Reads WRITES_TO relationships from base_manifest
              │   ├── Creates FolderHash nodes for each (component, bucket, path)
              │   ├── Creates PRODUCED_BY edges (folder → deployment hash)
              │   └── Creates DEPENDS_ON_DATA_FROM edges (folder → upstream folder)
              ├── Write generated_graph.json to bootstrap/neo4j/generated/
              └── sync_graph_to_neo4j()
                  └── python3 bootstrap/neo4j/load_graph.py
                      └── Creates Neo4j nodes and relationships from manifest
```

## The Problem: Filtering Before Graph Building

Looking at `build_dynamic_hash_graph()` in `terraform_post_action.py` (lines 300-480):

### 1. **Base Manifest Filtering** (lines 308-327)
The function starts by filtering the base_manifest based on Terraform outputs:

```python
active_graph_keys = set()
for key in (outputs.get("active_graph_keys") or []):
    active_graph_keys.add(key)

# Backward-compatible fallback for older output sets
if not use_global_pruning:
    for name in (outputs.get("jobs") or {}).keys():
        active_graph_keys.add(f"job:{name}")
    for name in (outputs.get("services") or {}).keys():
        active_graph_keys.add(f"service:{name}")

# Filter nodes
filtered_nodes = []
for node in base_manifest.get("nodes", []):
    key = node.get("key", "")
    if use_global_pruning:
        if key.startswith(managed_prefixes) and key not in active_graph_keys:
            continue  # ← SKIP nodes not in outputs
    else:
        if key.startswith(("job:", "service:")) and key not in active_graph_keys:
            continue  # ← SKIP inactive jobs/services

# Filter relationships
filtered_relationships = []
for relationship in base_manifest.get("relationships", []):
    source = relationship.get("from", "")
    target = relationship.get("to", "")
    if source in filtered_node_keys and target in filtered_node_keys:
        filtered_relationships.append(relationship)  # ← SKIP if source/target missing
```

### 2. **The Bottleneck: Component Not in Outputs**

If `dvb-annotator-job` is NOT in the Terraform outputs (`outputs.get("jobs")`), then:

1. `"job:dvb-annotator-job"` is NOT added to `active_graph_keys`
2. The relationship:
   ```
   {
     "from": "job:dvb-annotator-job",
     "to": "bucket:pipeline-data",
     "type": "WRITES_TO",
     "path": "pending_review_annotation/"
   }
   ```
   is SKIPPED because source is not in `filtered_node_keys`
3. **No FolderHash node is created for `pending_review_annotation/`**
4. **No HAS_HASH, PRODUCED_BY, or DEPENDS_ON_DATA_FROM relationships are created**

### 3. **Why outputs Might Be Missing Jobs**

In `terraform_post_action.py` (line 68):
```python
raw_outputs = json.loads(stdout)
outputs = {key: value.get("value") for key, value in raw_outputs.items()}
```

If `terraform output -json` doesn't include `jobs`, then:
- Terraform outputs aren't configured correctly
- OR job definition is missing/incomplete
- OR Cloud Run job failed to deploy

## Root Causes

### Primary: **Incomplete Terraform Outputs**

**Check what outputs exist:**
```bash
cd /Users/akt/workspace/CPE_Final_Project
terraform output -json | python3 -m json.tool | grep -A10 '"jobs"'
```

If `jobs` is missing or empty, dvb-annotator-job won't be in the graph.

### Secondary: **Graph Filtering Logic is Aggressive**

The filtering assumes all active jobs/services are in Terraform outputs. If any job existed before but wasn't re-deployed, it gets excluded.

### Tertiary: **No Validation/Warnings**

When relationships are skipped due to filtering, there's **no warning logged**, making it silent failure.

## Solution Checklist

1. **Verify Terraform outputs include all jobs:**
   ```bash
   terraform output jobs
   terraform output services
   ```

2. **If outputs are incomplete:**
   - Check `outputs.tf` for all job/service output definitions
   - Verify `terraform apply` actually deployed all resources
   - Run: `terraform apply -auto-approve` to redeploy

3. **Force graph resync:**
   ```bash
   # Option 1: Full redeploy (regenerates outputs + graph)
   make deploy AUTO_APPROVE=true
   
   # Option 2: Just rebuild graph from current outputs
   set -a; source .env; set +a
   python3 scripts/terraform_post_action.py
   
   # Option 3: Clean and reload graph from base manifest
   make restart-graph
   ```

4. **Verify graph was rebuilt:**
   ```bash
   ls -lah bootstrap/neo4j/generated/terraform_post_action_graph.json
   # Check modification time
   ```

## Evidence in Codebase

**Base Manifest:**
- `bootstrap/neo4j/graph_manifest.json` line 510-517
- **HAS** the WRITES_TO relationship defined

**Dynamic Graph Builder:**
- `scripts/terraform_post_action.py` lines 354-370
- **FILTERS** relationships based on active jobs/services from outputs

**Graph Loader:**
- `bootstrap/neo4j/load_graph.py` 
- Takes manifest and creates nodes/relationships
- Does NOT validate if relationships make sense (just loads them)

## Timeline

1. **Last successful state:** All folder relationships populated
2. **When broken:** Last `make deploy` where one of:
   - Job definition changed/removed
   - Terraform outputs changed structure
   - Job Cloud Run deployment failed
   - Graph filtering excluded the job
3. **Current state:** `pending_review_annotation/` folder node exists but orphaned (no edges)
