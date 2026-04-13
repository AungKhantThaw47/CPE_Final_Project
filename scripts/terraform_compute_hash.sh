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

# Parse codebase_path and utils_path from JSON input (portable across macOS/Linux)
CODEBASE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("codebase_path", ""))
except Exception:
    print("")' 2>/dev/null || echo "")

UTILS_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("utils_path", ""))
except Exception:
    print("")' 2>/dev/null || echo "")

if [ -z "$CODEBASE_PATH" ] || [ ! -d "$CODEBASE_PATH" ]; then
    # Return error as valid JSON
    echo '{"content_hash":"","error":"Invalid or missing codebase_path"}'
    exit 0
fi

# Compute codebase hash using hash module
RESULT=$(hash_directory_content "$CODEBASE_PATH" 2>&1)

# Check if hash computation succeeded
if [ $? -eq 0 ]; then
        CODEBASE_HASH=$(printf '%s' "$RESULT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("hash", ""))
except Exception:
    print("")' 2>/dev/null || echo "")

        CODEBASE_FILE_COUNT=$(printf '%s' "$RESULT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("file_count", 0))
except Exception:
    print("0")' 2>/dev/null || echo "0")
        UTILS_HASH=""
        UTILS_FILE_COUNT="0"
        if [ -n "$UTILS_PATH" ] && [ -d "$UTILS_PATH" ]; then
            UTILS_RESULT=$(hash_directory_content "$UTILS_PATH" 2>&1)
            UTILS_HASH=$(printf '%s' "$UTILS_RESULT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("hash", ""))
except Exception:
    print("")' 2>/dev/null || echo "")

            UTILS_FILE_COUNT=$(printf '%s' "$UTILS_RESULT" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("file_count", 0))
except Exception:
    print("0")' 2>/dev/null || echo "0")
        fi

        # If utils hash is available, combine it with codebase hash so utils changes trigger rebuilds.
        if [ -n "$UTILS_HASH" ]; then
            HASH=$(hash_string "${CODEBASE_HASH}:${UTILS_HASH}")
        else
            HASH="$CODEBASE_HASH"
        fi

        FILE_COUNT=$((CODEBASE_FILE_COUNT + UTILS_FILE_COUNT))
    
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
