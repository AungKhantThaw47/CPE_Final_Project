#!/usr/bin/env bash

set -euo pipefail

TF_BIN="${TF:-terraform}"
PROJECT_ID="${PROJECT_ID:-}"
CONFIRM="${CONFIRM:-false}"
FIRESTORE_COLLECTION="${FIRESTORE_COLLECTION:-events}"

if [[ "${CONFIRM,,}" != "true" ]]; then
  echo "Refusing destructive restart. Re-run with CONFIRM=true"
  echo "Example: make system-restart CONFIRM=true"
  exit 1
fi

if ! command -v "$TF_BIN" >/dev/null 2>&1; then
  echo "Missing Terraform binary: $TF_BIN" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Missing required tool: gcloud" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing required tool: python3" >&2
  exit 1
fi

if [[ -z "$PROJECT_ID" ]]; then
  if command -v "$TF_BIN" >/dev/null 2>&1; then
    PROJECT_ID="$($TF_BIN output -raw project_id 2>/dev/null || true)"
  fi
fi

if [[ -z "$PROJECT_ID" ]]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "Unable to resolve PROJECT_ID. Set PROJECT_ID or configure Terraform output/gcloud project." >&2
  exit 1
fi

PIPELINE_BUCKET="$($TF_BIN output -raw gcs_output_bucket 2>/dev/null || true)"
MLFLOW_BUCKET="$($TF_BIN output -raw mlflow_artifacts_bucket 2>/dev/null || true)"

# Fallbacks for older or partial states.
if [[ -z "$PIPELINE_BUCKET" ]]; then
  PIPELINE_BUCKET="${PROJECT_ID}-pipeline-data"
fi
if [[ -z "$MLFLOW_BUCKET" ]]; then
  MLFLOW_BUCKET="${PROJECT_ID}-mlflow-artifacts"
fi

echo "============================================================"
echo "SYSTEM RESTART (destructive)"
echo "Project: $PROJECT_ID"
echo "Buckets to clean: $PIPELINE_BUCKET, $MLFLOW_BUCKET"
echo "Firestore collection to clean: $FIRESTORE_COLLECTION"
echo "Neo4j target: ${NEO4J_URI:-<not-set>} / db=${NEO4J_DATABASE:-neo4j}"
echo "============================================================"

clean_bucket() {
  local bucket="$1"

  if [[ -z "$bucket" ]]; then
    return 0
  fi

  if ! gcloud storage ls "gs://$bucket" >/dev/null 2>&1; then
    echo "Bucket not found or inaccessible, skipping: gs://$bucket"
    return 0
  fi

  echo "Cleaning objects in gs://$bucket ..."
  gcloud storage rm --recursive "gs://$bucket/**" >/dev/null 2>&1 || true

  # Remove potential hidden/metadata entries if any remain.
  gcloud storage rm --recursive "gs://$bucket/*" >/dev/null 2>&1 || true

  echo "Bucket cleaned: gs://$bucket"
}

clean_bucket "$PIPELINE_BUCKET"
clean_bucket "$MLFLOW_BUCKET"

export PROJECT_ID FIRESTORE_COLLECTION
python3 - <<'PY'
import os
import sys

project_id = os.environ.get("PROJECT_ID", "").strip()
collection_name = os.environ.get("FIRESTORE_COLLECTION", "events").strip() or "events"

if not project_id:
  print("PROJECT_ID is missing; skipping Firestore cleanup.")
  raise SystemExit(0)

try:
  from google.cloud import firestore
except Exception as exc:
  print(
    "google-cloud-firestore is required for Firestore cleanup. "
    "Install it with: python3 -m pip install google-cloud-firestore",
    file=sys.stderr,
  )
  print(f"Import error: {exc}", file=sys.stderr)
  raise SystemExit(1)


def delete_doc_recursive(doc_ref) -> int:
  deleted = 0
  for subcollection in doc_ref.collections():
    deleted += delete_collection_recursive(subcollection)
  doc_ref.delete()
  return deleted + 1


def delete_collection_recursive(collection_ref) -> int:
  deleted = 0
  for doc in collection_ref.stream():
    deleted += delete_doc_recursive(doc.reference)
  return deleted


client = firestore.Client(project=project_id)
target_collection = client.collection(collection_name)
deleted_count = delete_collection_recursive(target_collection)
print(
  f"Firestore cleanup complete: deleted {deleted_count} document(s) "
  f"from collection '{collection_name}' in project '{project_id}'."
)
PY

python3 - <<'PY'
import base64
import json
import os
import ssl
import sys
from urllib import parse, request, error

neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
neo4j_user = os.environ.get("NEO4J_USER", "").strip()
neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
neo4j_db = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
skip_ssl = os.environ.get("NEO4J_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes", "on"}

if not (neo4j_uri and neo4j_user and neo4j_password):
    print("Neo4j env vars are missing; skipping hash node cleanup.")
    raise SystemExit(0)

parsed = parse.urlparse(neo4j_uri)
if parsed.scheme in {"http", "https"}:
    base_uri = neo4j_uri.rstrip("/")
elif parsed.scheme in {"neo4j+s", "bolt+s", "neo4j+ssc", "bolt+ssc"}:
    base_uri = f"https://{parsed.hostname}"
elif parsed.scheme in {"neo4j", "bolt"}:
    host = parsed.hostname or "localhost"
    if host in {"localhost", "127.0.0.1"}:
        base_uri = f"http://{host}:7474"
    else:
        base_uri = f"http://{host}"
else:
    print(f"Unsupported Neo4j URI scheme: {parsed.scheme}", file=sys.stderr)
    raise SystemExit(1)

endpoint = f"{base_uri}/db/{parse.quote(neo4j_db)}/query/v2"
auth = base64.b64encode(f"{neo4j_user}:{neo4j_password}".encode("utf-8")).decode("ascii")
ssl_context = ssl._create_unverified_context() if skip_ssl else None

queries = [
    "MATCH (n:DeploymentHash) DETACH DELETE n",
    "MATCH (n:FolderHash) DETACH DELETE n",
]

for q in queries:
    payload = json.dumps({"statement": q, "parameters": {}, "includeCounters": True}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=30, context=ssl_context) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"Neo4j HTTP error: {exc.code} {exc.reason}\n{details}", file=sys.stderr)
        raise SystemExit(1)
    except error.URLError as exc:
        print(f"Neo4j connection error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if body.strip():
        data = json.loads(body)
        if isinstance(data, dict) and data.get("errors"):
            first = data["errors"][0]
            print(f"Neo4j query failed: {first.get('code')} {first.get('message')}", file=sys.stderr)
            raise SystemExit(1)

print("Neo4j hash cleanup complete: deleted DeploymentHash and FolderHash nodes.")
PY

echo "System restart cleanup complete."
