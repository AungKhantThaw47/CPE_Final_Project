#!/bin/bash
# Detailed hash debugging - shows EXACTLY what we're hashing

export LC_ALL=C
export LC_COLLATE=C

CODEBASE_PATH="$1"

echo "==================================="
echo "DEBUG: Hash Computation Details"
echo "==================================="
echo "Codebase path: $CODEBASE_PATH"
echo "LC_ALL: $LC_ALL"
echo "LC_COLLATE: $LC_COLLATE"
echo ""

cd "$CODEBASE_PATH"

echo "=== FILE LIST (sorted) ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    ! -name "package-lock.json" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | LC_COLLATE=C sort | cut -f2- | tee /tmp/file_list.txt

echo ""
echo "=== FILE COUNT ==="
wc -l < /tmp/file_list.txt

echo ""
echo "=== INDIVIDUAL FILE HASHES ==="
while read -r file; do
    hash=$(tr -d '\r' < "$file" 2>/dev/null | sha256sum | cut -d' ' -f1)
    size=$(wc -c < "$file" 2>/dev/null)
    echo "$file : $hash (${size} bytes)"
done < /tmp/file_list.txt

echo ""
echo "=== COMBINED HASH ==="
while read -r file; do
    tr -d '\r' < "$file" 2>/dev/null || cat "$file"
done < /tmp/file_list.txt | sha256sum | cut -d' ' -f1

rm -f /tmp/file_list.txt
