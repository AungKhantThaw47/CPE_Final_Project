#!/usr/bin/env python3

"""Move a GCS folder prefix to a new prefix.

This utility is intentionally outside the data pipeline. It is meant for
internal maintenance workflows where a folder prefix needs to be renamed or
relocated while preserving the object layout under that prefix.

Behavior:
- Defaults to dry-run.
- Copies each object from source prefix to destination prefix.
- Deletes the source object only after a successful copy.
- Preserves the relative path beneath the source prefix.
"""

from __future__ import annotations

import argparse
import os
import sys
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


def list_objects(bucket: storage.Bucket, prefix: str) -> list[storage.Blob]:
    return list(bucket.list_blobs(prefix=prefix))


def move_prefix(
    client: storage.Client,
    source: GcsLocation,
    destination: GcsLocation,
    *,
    apply: bool,
    overwrite: bool,
) -> int:
    if source.bucket != destination.bucket:
        raise ValueError("Cross-bucket moves are not supported by this utility")

    if not source.prefix:
        raise ValueError("Source prefix must not be empty")

    if source.prefix == destination.prefix:
        print(f"No-op: source and destination are identical: gs://{source.bucket}/{source.prefix}")
        return 0

    bucket = client.bucket(source.bucket)
    source_blobs = list_objects(bucket, source.prefix)

    if not source_blobs:
        print(f"No objects found under gs://{source.bucket}/{source.prefix}")
        return 0

    moved = 0
    for blob in source_blobs:
        relative_name = blob.name[len(source.prefix):]
        if not relative_name:
            continue

        destination_name = f"{destination.prefix}{relative_name}"
        destination_blob = bucket.blob(destination_name)

        if destination_blob.exists(client):
            if not overwrite:
                raise RuntimeError(f"Destination already exists: gs://{source.bucket}/{destination_name}")
            if apply:
                destination_blob.delete()

        print(f"{ 'MOVE' if apply else 'DRY-RUN' }: gs://{source.bucket}/{blob.name} -> gs://{source.bucket}/{destination_name}")

        if not apply:
            continue

        bucket.copy_blob(blob, bucket, destination_name)
        blob.delete()
        moved += 1

    return moved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rename or relocate a GCS folder prefix by copying objects to a new prefix."
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("GCS_BUCKET", "").strip(),
        help="Bucket name (or set GCS_BUCKET). Required unless using full gs:// URIs.",
    )
    parser.add_argument(
        "--source",
        default=os.environ.get("SOURCE_PREFIX", "").strip(),
        help="Source prefix or gs:// URI (or set SOURCE_PREFIX).",
    )
    parser.add_argument(
        "--destination",
        default=os.environ.get("DESTINATION_PREFIX", "").strip(),
        help="Destination prefix or gs:// URI (or set DESTINATION_PREFIX).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=os.environ.get("APPLY", "false").strip().lower() in {"1", "true", "yes", "on"},
        help="Perform the move. Without this flag the script runs in dry-run mode.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=os.environ.get("OVERWRITE", "false").strip().lower() in {"1", "true", "yes", "on"},
        help="Replace destination objects if they already exist.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.source or not args.destination:
        parser.error("Both --source and --destination are required")

    source = parse_gs_uri(args.source, default_bucket=args.bucket or None)
    destination = parse_gs_uri(args.destination, default_bucket=source.bucket)

    if destination.bucket != source.bucket:
        raise SystemExit("Cross-bucket moves are not supported by this utility")

    client = storage.Client()
    print("=" * 72)
    print("GCS folder rename utility")
    print(f"Bucket: gs://{source.bucket}")
    print(f"Source: gs://{source.bucket}/{source.prefix}")
    print(f"Destination: gs://{destination.bucket}/{destination.prefix}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Overwrite existing destination objects: {args.overwrite}")
    print("=" * 72)

    moved = move_prefix(
        client,
        source,
        destination,
        apply=args.apply,
        overwrite=args.overwrite,
    )

    if args.apply:
        print(f"Completed move of {moved} object(s).")
    else:
        print("Dry run complete. Re-run with --apply to perform the move.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())