#!/bin/bash
# Compute Content Hash using Hash Module
# Returns JSON with content_hash for Terraform external data source
# Usage: Called by Terraform data.external resource

set -e

# Force C locale for consistent sorting across all systems
export LC_ALL=C
export LC_COLLATE=C

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source hash module
source "$SCRIPT_DIR/hash_module.sh"

# Read JSON input from Terraform (stdin)
INPUT=$(cat)

# Parse codebase_path from JSON input
CODEBASE_PATH=$(echo "$INPUT" | grep -oP '"codebase_path":\s*"\K[^"]+' || echo "")

if [ -z "$CODEBASE_PATH" ] || [ ! -d "$CODEBASE_PATH" ]; then
    # Return error as valid JSON
    echo '{"content_hash":"","error":"Invalid or missing codebase_path"}'
    exit 0
fi

# Compute hash using hash module
RESULT=$(hash_directory_content "$CODEBASE_PATH" 2>&1)

# Check if hash computation succeeded
if [ $? -eq 0 ]; then
    HASH=$(echo "$RESULT" | grep -oP '"hash":\s*"\K[^"]+' || echo "")
    FILE_COUNT=$(echo "$RESULT" | grep -oP '"file_count":\s*\K[0-9]+' || echo "0")
    
    if [ -n "$HASH" ]; then
        # Return success JSON
        echo "{\"content_hash\":\"$HASH\",\"file_count\":\"$FILE_COUNT\"}"
    else
        # Return error JSON
        echo '{"content_hash":"","error":"Failed to extract hash from result"}'
    fi
else
    # Return error JSON
    ERROR_MSG=$(echo "$RESULT" | head -1 | sed 's/"/\\"/g')
    echo "{\"content_hash\":\"\",\"error\":\"$ERROR_MSG\"}"
fi
