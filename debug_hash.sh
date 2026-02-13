#!/bin/bash
# Debug script to see what files and content CI sees

export LC_ALL=C
export LC_COLLATE=C

cd "$1"

echo "=== File List (sorted) ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | sort | cut -f2-

echo ""
echo "=== File Count ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | wc -l

echo ""
echo "=== First file hash (for comparison) ==="
first_file=$(find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | sort | cut -f2- | head -1)
echo "File: $first_file"
tr -d '\r' < "$first_file" | sha256sum | cut -d' ' -f1

echo ""
echo "=== Combined hash ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | sort | cut -f2- | while read -r file; do
    tr -d '\r' < "$file" 2>/dev/null || cat "$file"
done | sha256sum | cut -d' ' -f1
