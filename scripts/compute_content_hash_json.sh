#!/bin/bash
# Compute Content Hash Script (JSON output for Terraform)
# Computes deterministic hash of codebase directory content
# Returns JSON for Terraform external data source

set -e

# Read from stdin for Terraform external data source
eval "$(jq -r '@sh "CODEBASE_PATH=\(.codebase_path)"')"

# Verify codebase path exists
if [ ! -d "$CODEBASE_PATH" ]; then
    # Return empty hash instead of failing
    echo '{"content_hash":""}'
    exit 0
fi

# Compute hash of all files in codebase directory
cd "$CODEBASE_PATH"

# Find all files, excluding only temporary build artifacts and dependencies
FILES=$(find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.pytest_cache/*" \
    ! -path "*/venv/*" \
    ! -path "*/.venv/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | sort)

if [ -z "$FILES" ]; then
    # Return empty hash for empty directories
    echo '{"content_hash":""}'
    exit 0
fi

# Compute combined hash of all files (normalize line endings to LF)
CONTENT_HASH=$(echo "$FILES" | while read -r file; do
    # Convert CRLF to LF for consistent hashing across platforms
    tr -d '\r' < "$file"
done | sha256sum | awk '{print $1}')

# Return JSON for Terraform external data source
echo "{\"content_hash\":\"$CONTENT_HASH\"}"
