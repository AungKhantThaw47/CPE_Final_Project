#!/usr/bin/env python3

"""Parallel GCS folder rename/move utility for Cloud Run Jobs.

Each Cloud Run task independently scans the source prefix, hashes object names,
and processes only the shard assigned to its task index.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, Optional

from google.cloud import storage


@dataclass(frozen=True)
class GcsLocation:
    bucket: str
    prefix: str


def normalize_prefix(prefix: str) -> str:
    prefix = (prefix or "").strip().lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def parse_gs_uri(value: str, *, default_bucket: Optional[str] = None) -> GcsLocation:
    value = (value or "").strip()
    if not value:
        raise ValueError("GCS location is empty")

    if value.startswith("gs://"):
        remainder = value[5:]
        bucket, _, prefix = remainder.partition("/")
        if not bucket:
            raise ValueError(f"Invalid GCS URI: {value}")
        return GcsLocation(bucket=bucket, prefix=normalize_prefix(prefix))

    if default_bucket:
        return GcsLocation(bucket=default_bucket, prefix=normalize_prefix(value))

    if "/" not in value:
        return GcsLocation(bucket=value, prefix="")

    raise ValueError(
        f"Unsupported GCS location '{value}'. Use gs://bucket/prefix or provide --bucket."
    )


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_task_index() -> int:
    raw_value = os.environ.get("CLOUD_RUN_TASK_INDEX", "0").strip()
    try:
        return int(raw_value)
    except ValueError:
        return 0


def get_task_count() -> int:
    raw_value = os.environ.get("CLOUD_RUN_TASK_COUNT", "1").strip()
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return 1


def get_thread_workers() -> int:
    raw_value = os.environ.get("THREAD_WORKERS", "4").strip()
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return 4


def shard_for_object(object_name: str, task_count: int) -> int:
    digest = hashlib.sha256(object_name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) % task_count


def list_objects(bucket: storage.Bucket, prefix: str) -> list[storage.Blob]:
    return [blob for blob in bucket.list_blobs(prefix=prefix)]


def move_blob(bucket: storage.Bucket, source_blob: storage.Blob, destination_name: str, *, overwrite: bool, apply: bool) -> str:
    destination_blob = bucket.blob(destination_name)
    if destination_blob.exists():
        if not overwrite:
            return f"skip exists gs://{bucket.name}/{destination_name}"
        if apply:
            destination_blob.delete()

    if not apply:
        return f"dry-run gs://{bucket.name}/{source_blob.name} -> gs://{bucket.name}/{destination_name}"

    bucket.copy_blob(source_blob, bucket, destination_name)
    source_blob.delete()
    return f"moved gs://{bucket.name}/{source_blob.name} -> gs://{bucket.name}/{destination_name}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parallel Cloud Run job for renaming a GCS folder prefix.")
    parser.add_argument("--bucket", default=os.environ.get("GCS_BUCKET", "").strip(), help="Bucket name")
    parser.add_argument("--source", default=os.environ.get("SOURCE_PREFIX", "").strip(), help="Source prefix or gs:// URI")
    parser.add_argument("--destination", default=os.environ.get("DESTINATION_PREFIX", "").strip(), help="Destination prefix or gs:// URI")
    parser.add_argument("--apply", action="store_true", default=env_flag("APPLY", default=False), help="Perform the move")
    parser.add_argument("--overwrite", action="store_true", default=env_flag("OVERWRITE", default=False), help="Overwrite destination objects")
    parser.add_argument("--thread-workers", type=int, default=get_thread_workers(), help="Thread workers per task")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.source or not args.destination:
        parser.error("Both --source and --destination are required")

    source = parse_gs_uri(args.source, default_bucket=args.bucket or None)
    destination = parse_gs_uri(args.destination, default_bucket=source.bucket)

    if source.bucket != destination.bucket:
        raise SystemExit("Cross-bucket moves are not supported by this job")

    task_index = get_task_index()
    task_count = get_task_count()

    client = storage.Client()
    bucket = client.bucket(source.bucket)
    blobs = list_objects(bucket, source.prefix)

    print("=" * 72)
    print("Parallel GCS folder rename job")
    print(f"Task: {task_index + 1}/{task_count}")
    print(f"Bucket: gs://{source.bucket}")
    print(f"Source: gs://{source.bucket}/{source.prefix}")
    print(f"Destination: gs://{destination.bucket}/{destination.prefix}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Overwrite existing destination objects: {args.overwrite}")
    print(f"Thread workers: {args.thread_workers}")
    print("=" * 72)

    if not blobs:
        print(f"No objects found under gs://{source.bucket}/{source.prefix}")
        return 0

    assigned = [blob for blob in blobs if shard_for_object(blob.name, task_count) == task_index]
    print(f"Discovered {len(blobs)} object(s); assigned {len(assigned)} to this task")

    if not assigned:
        print("No assigned objects for this task shard.")
        return 0

    completed = 0
    with ThreadPoolExecutor(max_workers=args.thread_workers) as executor:
        futures = []
        for blob in assigned:
            relative_name = blob.name[len(source.prefix):]
            if not relative_name:
                continue
            destination_name = f"{destination.prefix}{relative_name}"
            futures.append(
                executor.submit(
                    move_blob,
                    bucket,
                    blob,
                    destination_name,
                    overwrite=args.overwrite,
                    apply=args.apply,
                )
            )

        for future in as_completed(futures):
            message = future.result()
            print(message)
            if message.startswith("moved "):
                completed += 1

    if args.apply:
        print(f"Task complete: moved {completed} object(s) in shard {task_index + 1}/{task_count}.")
    else:
        print(f"Dry run complete for shard {task_index + 1}/{task_count}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
