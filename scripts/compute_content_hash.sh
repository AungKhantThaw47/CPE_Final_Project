#!/bin/bash
# Compute Content Hash Script
# Computes deterministic hash of codebase directory content
# Usage: ./compute_content_hash.sh <codebase_path>

set -e

CODEBASE_PATH="$1"

if [ -z "$CODEBASE_PATH" ]; then
    echo "Error: Codebase path is required"
    echo "Usage: $0 <codebase_path>"
    exit 1
fi

if [ ! -d "$CODEBASE_PATH" ]; then
    echo "Error: Codebase path does not exist: $CODEBASE_PATH"
    exit 1
fi

# Compute hash of all files in codebase directory
# Sort files and compute combined hash for deterministic result
CURRENT_HASH=$(find "$CODEBASE_PATH" -type f \
    ! -name ".build-hash*" \
    ! -name ".dockerignore" \
    ! -name "cloudbuild.yaml" \
    ! -name "Dockerfile" \
    -exec sha256sum {} \; | \
    sort | \
    sha256sum | \
    cut -d' ' -f1)

if [ -z "$CURRENT_HASH" ]; then
    echo "Error: Failed to compute content hash"
    exit 1
fi

echo "$CURRENT_HASH"
