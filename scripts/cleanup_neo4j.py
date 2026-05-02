#!/usr/bin/env python3
"""Delete stale Neo4j edges: bad DEPENDS_ON_DATA_FROM → coordinator and null-key FolderHash nodes."""
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
        result = json.loads(resp.read())
        return result.get("counters", {})

print("Deleting DEPENDS_ON_DATA_FROM edges pointing at coordinator...")
c = run("MATCH (a)-[r:DEPENDS_ON_DATA_FROM]->(b {key:'job:dvb-coordinator-job'}) DELETE r")
print(f"  {c}")

print("Deleting null-key FolderHash nodes...")
c = run("MATCH (n:FolderHash) WHERE n.key IS NULL DETACH DELETE n")
print(f"  {c}")

print("Done.")
