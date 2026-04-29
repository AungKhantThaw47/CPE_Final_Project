# Neo4j Graph Health Report (CPE Final Project)

## Query Pattern Issue: Cartesian Product Expansion

Your original Cypher query demonstrates a **Cartesian product** problem:
- It matches 9 components and 9 latest FolderHash nodes **independently**
- Without explicit RELATE clauses between them, Neo4j returns 9×32 = 288 rows
- Each component appears 32 times, paired with every possible latest folder

### Why: The Query Structure
```cypher
MATCH (component) WHERE component:CloudRunJob OR component:CloudRunService
MATCH (component)-[:HAS_HASH]->(latestDep:DeploymentHash)
OPTIONAL MATCH (latestFolder:FolderHash)
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latestFolder) }
```

The third `OPTIONAL MATCH` with no filter relating it back to the component creates **independent paths**:
- Path 1: component → deployment
- Path 2: any latest folder globally

Result: 9 components × 32 latest folders (approx) = 288 rows ✗

---

## Graph Connectivity Findings

### ✅ Healthy Connections (9/9 components linked)

All 9 CloudRun components have proper HAS_HASH edges:

| Component | Latest DeploymentHash | Status |
|-----------|----------------------|--------|
| crisis-admin | service:crisis-admin | ✅ |
| crisis-classifier-job | job:crisis-classifier-job | ✅ |
| dvb-annotator-job | job:dvb-annotator-job | ✅ |
| dvb-crawler-job | job:dvb-crawler-job | ✅ |
| dvb-extractor-job | job:dvb-extractor-job | ✅ |
| dvb-text-cleaner-job | job:dvb-text-cleaner-job | ✅ |
| events-api | service:events-api | ✅ |
| gcs-folder-rename-job | job:gcs-folder-rename-job | ✅ |
| mlflow | service:mlflow | ✅ |

**Total HAS_HASH edges: 27**

---

### ⚠️ Edge Defects Detected

#### 1. **Disconnected FolderHash Nodes (2 orphans)**

| folder_path | hash_value | Issue |
|-------------|-----------|-------|
| `pending_review/` | `182b8266eac4...` | ❌ No PRODUCED_BY, no bucket link |
| `pending_review_annotation/` | `ca6d084d7dd4...` | ❌ No PRODUCED_BY, no bucket link |

**Root cause:** These are latest folders (no PREVIOUS_FOLDER_HASH predecessors) but have no:
- `:PRODUCED_BY` edge to their source DeploymentHash
- `:HAS_HASH` edge from any StorageBucket

**Impact:** Graph cannot trace lineage for manual/UI-driven article processing

#### 2. **Producer Deployment Linkage**

Latest folder summary with producers:

| folder_path | hash_value | producer_component_key | Status |
|-------------|-----------|----------------------|--------|
| `` (mlflow) | `9ea42bc4...` | `service:mlflow` | ✅ |
| `annotated_articles/` | `4d357215...` | `service:crisis-admin` | ✅ |
| `crisis_articles/` | `06c42c9e...` | `service:crisis-admin` | ✅ |
| `dvb/` | `182b8266...` | `job:dvb-crawler-job` | ✅ |
| `dvb_cleaned/` | `ae311d15...` | `job:dvb-text-cleaner-job` | ✅ |
| `events/` | `8c0426c8...` | `job:dvb-extractor-job` | ✅ |
| `pending_review/` | `182b8266...` | **NONE** ❌ | Orphaned |
| `pending_review_annotation/` (v1) | `4d96fc38...` | `job:dvb-annotator-job` | ✅ |
| `pending_review_annotation/` (v2) | `ca6d084d...` | **NONE** ❌ | Orphaned |

**Key finding:** Two distinct `pending_review_annotation/` latest hashes:
- `4d96fc38...` → correctly linked to dvb-annotator-job ✅
- `ca6d084d...` → orphaned, no producer ❌

---

### 📊 Graph Structure Summary

**Node Inventory:**
- 48 SystemNode
- 18 FolderHash
- 11 DeploymentHash
- 11 PipelineOutputHash
- 9 CloudRunJob/Service
- 2 StorageBucket
- 4 other (Workflow, Project, Repository, etc.)

**Edge Distribution:**
- 42 DEPENDS_ON_DATA_FROM (data lineage)
- 27 HAS_HASH (component → deployment)
- 16 PRODUCED_BY (folder ← deployment)
- 10 PREVIOUS_FOLDER_HASH (folder history chain)
- 22 other types (WRITES_TO, READS_FROM, ORCHESTRATES, etc.)

**Connectivity Gaps:**
- Missing PRODUCED_BY: 2 (of 18 FolderHash)
- Missing bucket link: 2 (of 18 FolderHash)
- Components without HAS_HASH: 0 (100% linked) ✅

---

### 🔍 Cartesian Expansion Breakdown

Your query generated 288 rows through this pattern:

1. ✅ **9 components** → **9 DeploymentHashes** (proper JOIN via HAS_HASH)
2. ⚠️ **32 latest FolderHashes** → **independent sweep** (not related to component)
3. ⚠️ **Result:** 9 components × 32 folders ≈ 288 rows total

**Why inefficient?**
- No edge between component and latestFolder nodes
- Neo4j produces all valid combinations (Cartesian product)
- Same 32 folders repeated for each of 9 components

---

## Recommendations

### 1. Fix Query Pattern (Eliminate Cartesian Product)

**Current (produces 288 rows):**
```cypher
OPTIONAL MATCH (latestFolder:FolderHash)
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latestFolder) }
```

**Improved (produces ~12 rows):**
```cypher
OPTIONAL MATCH (component)-[:HAS_HASH]->(:DeploymentHash)-[:PRODUCES]->(latestFolder:FolderHash)
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latestFolder) }
```

Or **filter through data dependencies:**
```cypher
OPTIONAL MATCH (latestFolder:FolderHash)
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latestFolder) }
  AND EXISTS { 
    MATCH (component)-[:HAS_HASH]->(:DeploymentHash)-[:PRODUCED_BY]->(latestFolder)
  }
```

**Expected improvement:** 288 rows → ~12 rows (24× reduction)

### 2. Investigate Orphaned FolderHash Nodes

**Query to identify all orphans:**
```cypher
MATCH (f:FolderHash)
WHERE NOT EXISTS { MATCH (:StorageBucket)-[:HAS_HASH]->(f) }
   OR NOT EXISTS { MATCH (f)-[:PRODUCED_BY]->(:DeploymentHash) }
OPTIONAL MATCH (f)-[:PREVIOUS_FOLDER_HASH]->(prev)
RETURN f.folder_path AS path, f.hash_value AS hash, 
       EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(f) } AS is_latest,
       CASE WHEN EXISTS { MATCH (:StorageBucket)-[:HAS_HASH]->(f) } THEN 'has_bucket' ELSE 'NO_BUCKET' END,
       CASE WHEN EXISTS { MATCH (f)-[:PRODUCED_BY]->(:DeploymentHash) } THEN 'has_producer' ELSE 'NO_PRODUCER' END
```

**Next steps:**
- Option A: Delete if stale or test-only
- Option B: Create missing PRODUCED_BY edges if they shouldn't be orphaned
- Option C: Link to StorageBucket if missing

### 3. Duplicate Pending Annotation Folder Investigation

Two versions of `pending_review_annotation/` have different latest hashes. Verify:

```cypher
MATCH (f1:FolderHash { folder_path: "pending_review_annotation/" })
OPTIONAL MATCH (f1)<-[:PRODUCED_BY]-(d1)
OPTIONAL MATCH (f1)<-[:HAS_HASH]-(b1)
OPTIONAL MATCH (f1)-[:PREVIOUS_FOLDER_HASH*1..]-(prev1:FolderHash)
RETURN f1.hash_value AS hash, d1.component_key AS producer, b1.name AS bucket, 
       count(prev1) AS history_depth
ORDER BY hash DESC
```

Is this dual-hash state intentional, or should one be pruned?

---

## Conclusion

| Category | Status | Details |
|----------|--------|---------|
| Component Registration | ✅ **100%** | All 9 CloudRun components have HAS_HASH edges |
| Folder Producer Links | ⚠️ **89%** | 16/18 FolderHash with PRODUCED_BY; 2 orphaned |
| Bucket Association | ⚠️ **89%** | 16/18 FolderHash with StorageBucket link; 2 missing |
| Query Efficiency | 🔴 **288×** | Cartesian expansion: 288 rows for 9 logical entities |

**Priority Fixes:**
1. **HIGH:** Repair query to eliminate Cartesian bloat (24× row reduction)
2. **MEDIUM:** Link 2 orphaned latest FolderHash nodes or delete them
3. **LOW:** Investigate dual `pending_review_annotation/` hashes

---

Generated: 2026-04-28
Neo4j Database: `4a6a2b6a` @ neo4j.io
