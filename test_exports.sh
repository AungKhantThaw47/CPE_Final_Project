#!/bin/bash
# Test if exports in sourced files work

set -e

echo "=== Test 1: Direct export in this script ==="
export LC_ALL=C
export LC_COLLATE=C
echo "LC_ALL: $LC_ALL"
echo "LC_COLLATE: $LC_COLLATE"

echo ""
echo "=== Test 2: After sourcing hash_module.sh ==="
source "scripts/hash_module.sh"
echo "LC_ALL: $LC_ALL"
echo "LC_COLLATE: $LC_COLLATE"

echo ""
echo "=== Test 3: Compute hash using module ==="
RESULT=$(hash_directory_content "Codebase_Container/crawler_job" 2>&1)
echo "$RESULT" | grep -oP '"hash":\s*"\K[^"]+'
