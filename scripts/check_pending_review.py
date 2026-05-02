#!/usr/bin/env python3
"""Check Neo4j `pending_review/` chain-tip and validate GCS blobs.

Usage: python3 scripts/check_pending_review.py [--bucket BUCKET] [--folder FOLDER]

Prints Neo4j-provided hash, number of blobs under that prefix, and the latest
GCS hash by blob timestamps if different.
"""
import os
import argparse
import sys
from pathlib import Path
from collections import defaultdict

try:
    from google.cloud import storage
except Exception:
    storage = None

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils import neo4j_utils


def list_hash_prefixes_from_gcs(bucket_name: str, folder: str):
    """Return a mapping hash -> list of blob names and last updated time."""
    if not storage:
        raise RuntimeError("google-cloud-storage is not available in this environment")

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blobs = client.list_blobs(bucket_name, prefix=folder)
    hashes = defaultdict(list)
    for b in blobs:
        # Expect layout: folder/<hash>/...  -> split and take second segment
        parts = b.name.split('/')
        if len(parts) < 2:
            continue
        hash_seg = parts[1]
        hashes[hash_seg].append((b.name, b.updated))

    # compute aggregate info
    result = {}
    for h, entries in hashes.items():
        latest = max(e[1] for e in entries)
        result[h] = {
            "count": len(entries),
            "latest_updated": latest,
            "sample": [e[0] for e in entries[:5]],
        }
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.environ.get("GCS_BUCKET") or os.environ.get("CRISIS_BUCKET"))
    p.add_argument("--folder", default="pending_review/")
    args = p.parse_args()

    if not args.bucket:
        print("ERROR: bucket not specified via --bucket or GCS_BUCKET env var")
        return 2

    print(f"Using bucket: {args.bucket}")
    print(f"Checking folder: {args.folder}")

    # 1) Query Neo4j for latest FolderHash
    neo4j_hash = None
    try:
        neo4j_hash = neo4j_utils.query_latest_folder_hash_from_neo4j_env(args.folder, args.bucket)
    except Exception as e:
        print("Neo4j query error:", e)

    print("Neo4j-provided hash:", neo4j_hash)

    # 2) Inspect GCS for blobs under the Neo4j-provided hash (if present)
    if neo4j_hash:
        prefix = f"{args.folder}{neo4j_hash}/"
        print(f"Probing GCS prefix: gs://{args.bucket}/{prefix}")
        try:
            client = storage.Client()
            blobs = list(client.list_blobs(args.bucket, prefix=prefix))
            print(f"Found {len(blobs)} blobs under Neo4j prefix")
            for b in blobs[:10]:
                print(" -", b.name)
        except Exception as e:
            print("GCS probe error:", e)

    # 3) Scan GCS for latest hash by timestamp
    print("Scanning GCS for available hash prefixes (this may take a moment)...")
    try:
        prefixes = list_hash_prefixes_from_gcs(args.bucket, args.folder)
        if not prefixes:
            print("No hashes found under folder in GCS.")
            return 0

        # pick latest by latest_updated
        latest_hash, info = max(prefixes.items(), key=lambda kv: kv[1]["latest_updated"])
        print(f"GCS-latest hash: {latest_hash} (count={info['count']}, latest={info['latest_updated']})")
        print("Sample blobs:")
        for s in info["sample"]:
            print(" -", s)

        if neo4j_hash != latest_hash:
            print("NOTE: Neo4j hash differs from GCS latest hash.")
        else:
            print("Neo4j hash matches GCS latest hash.")

    except Exception as e:
        print("Error scanning GCS:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
