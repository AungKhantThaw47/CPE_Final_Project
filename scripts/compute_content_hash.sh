#!/bin/bash
# Compute Content Hash Script
# Computes deterministic hash of codebase directory content
# Usage: ./compute_content_hash.sh <codebase_path>

set -e

# Force C locale for consistent sorting across all systems
export LC_ALL=C
export LC_COLLATE=C

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

# Compute hash of all files in codebase directory (normalize line endings)
# Sort files and compute combined hash for deterministic result
# Use lowercase + LC_COLLATE=C to ensure consistent byte-level sorting across all systems
CURRENT_HASH=$(find "$CODEBASE_PATH" -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.pytest_cache/*" \
    ! -path "*/venv/*" \
    ! -path "*/.venv/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    ! -name "package-lock.json" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | LC_COLLATE=C sort | cut -f2- | while read -r file; do
    # Convert CRLF to LF for consistent hashing across platforms
    tr -d '\r' < "$file"
done | sha256sum | cut -d' ' -f1)

if [ -z "$CURRENT_HASH" ]; then
    echo "Error: Failed to compute content hash"
    exit 1
fi

echo "$CURRENT_HASH"
