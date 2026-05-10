#!/usr/bin/env python3
"""Query Neo4j and print a relationship summary for the pipeline graph."""
import ssl, base64, json
from urllib import request, parse

NEO4J_URI      = "neo4j+s://4a6a2b6a.databases.neo4j.io"
NEO4J_USER     = "4a6a2b6a"
NEO4J_PASSWORD = "5C_VdJn2ERjV_4ftwy3a0tWyLmv4cd93V871d-uxELM"
NEO4J_DATABASE = "4a6a2b6a"

def run(statement, params=None):
    base = f"https://{parse.urlparse(NEO4J_URI).hostname}"
    endpoint = f"{base}/db/{parse.quote(NEO4J_DATABASE)}/query/v2"
    payload = json.dumps({"statement": statement, "parameters": params or {}}).encode()
    auth = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()
    req = request.Request(endpoint, data=payload, method="POST", headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    ctx = ssl._create_unverified_context()
    with request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read())

def rows(result):
    data = result.get("data", {})
    fields = data.get("fields", [])
    return [dict(zip(fields, row)) for row in data.get("values", [])]

SEP = "=" * 65

# ── 1. Null-key nodes (stale/corrupt) ────────────────────────────
print(f"\n{SEP}")
print("NULL-KEY NODES (corrupt — should be empty)")
print(SEP)
for r in rows(run("MATCH (n) WHERE n.key IS NULL RETURN labels(n) AS lbl, count(*) AS cnt")):
    print(f"  labels={r['lbl']}  count={r['cnt']}")
else:
    null_count = rows(run("MATCH (n) WHERE n.key IS NULL RETURN count(n) AS c"))[0]['c']
    print(f"  {null_count} null-key node(s) found")

# ── 2. Coordinator node + all its relationships ───────────────────
print(f"\n{SEP}")
print("DVB-COORDINATOR-JOB — ALL RELATIONSHIPS")
print(SEP)
q = """
MATCH (n {key:'job:dvb-coordinator-job'})-[r]-(m)
WHERE m.key IS NOT NULL
RETURN n.key AS node,
       CASE WHEN startNode(r)=n THEN '→' ELSE '←' END AS dir,
       type(r) AS rel, m.key AS other
ORDER BY rel, other
"""
for r in rows(run(q)):
    arrow = f"--[{r['rel']}]-->" if r['dir'] == '→' else f"<--[{r['rel']}]--"
    print(f"  {r['node']} {arrow} {r['other']}")

# ── 3. Check SPAWNS edge ──────────────────────────────────────────
print(f"\n{SEP}")
print("SPAWNS RELATIONSHIP CHECK")
print(SEP)
spawns = rows(run("MATCH (a)-[:SPAWNS]->(b) RETURN a.key AS from, b.key AS to"))
if spawns:
    for r in spawns:
        print(f"  {r['from']} --[SPAWNS]--> {r['to']}")
else:
    print("  ✗ No SPAWNS relationships found")

# ── 4. Expected node check ────────────────────────────────────────
print(f"\n{SEP}")
print("EXPECTED NODES")
print(SEP)
expected = [
    "project:cpe-final-project",
    "job:dvb-coordinator-job",
    "job:dvb-crawler-job",
    "job:dvb-text-cleaner-job",
    "job:crisis-classifier-job",
    "workflow:daily-pipeline",
    "workflow:manual-coordinator",
    "bucket:pipeline-data",
    "source:dvb-news",
    "registry:artifact-registry",
    "scheduler:daily-pipeline-trigger",
]
found = {r['key'] for r in rows(run("MATCH (n) WHERE n.key IN $keys RETURN n.key AS key", {"keys": expected}))}
for key in expected:
    status = "✓" if key in found else "✗ MISSING"
    print(f"  {status}  {key}")

# ── 5. Suspicious DEPENDS_ON_DATA_FROM targeting coordinator ─────
print(f"\n{SEP}")
print("DEPENDS_ON_DATA_FROM → coordinator (should be empty)")
print(SEP)
q = """
MATCH (a)-[:DEPENDS_ON_DATA_FROM]->(b {key:'job:dvb-coordinator-job'})
RETURN a.key AS from
"""
deps = rows(run(q))
if deps:
    for r in deps:
        print(f"  ✗  {r['from']} --[DEPENDS_ON_DATA_FROM]--> job:dvb-coordinator-job")
else:
    print("  ✓ None")

# ── 6. Workflow ORCHESTRATES check ───────────────────────────────
print(f"\n{SEP}")
print("WORKFLOW ORCHESTRATES")
print(SEP)
q = """
MATCH (w:Workflow)-[r:ORCHESTRATES]->(j)
RETURN w.key AS workflow, j.key AS job, r.step_order AS step
ORDER BY w.key, r.step_order
"""
for r in rows(run(q)):
    print(f"  {r['workflow']} --[ORCHESTRATES step {r['step']}]--> {r['job']}")

# ── 7. FolderHash DERIVED_FROM chain ─────────────────────────────
print(f"\n{SEP}")
print("DERIVED_FROM CHAIN (all working folder hashes)")
print(SEP)
q = """
WITH [
    'dvb/',
    'dvb_cleaned/',
    'pending_review/',
    'crisis_articles/',
    'pending_review_annotation/',
    'annotated_articles/',
    'events/'
] AS working_paths
MATCH (fh:FolderHash)
WHERE fh.folder_path IN working_paths
OPTIONAL MATCH (fh)-[:PRODUCED_BY]->(prod:DeploymentHash)
OPTIONAL MATCH (fh)-[:DERIVED_FROM]->(src:FolderHash)
RETURN DISTINCT
    fh.folder_path AS target,
    src.folder_path AS source,
    fh.hash_value AS hash,
    prod.component_key AS producer,
    fh.updated_at AS updated
ORDER BY target, updated DESC, hash DESC
"""
for r in rows(run(q)):
        producer = r['producer'] or "(none)"
        source = r['source'] or "(none)"
        print(f"  {r['target']:<26} ← DERIVED_FROM {source:<22}  {(r['hash'] or '')[:12]}...  {producer}")

print(f"\n{SEP}\nDone.\n")
