#!/bin/bash
# Test different sorting/hashing approaches to see which produces 9c7b0f74...

export LC_ALL=C
export LC_COLLATE=C

cd "$1"

echo "=== Approach 1: Current (with lowercase) ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | sort | cut -f2- | while read -r file; do
    tr -d '\r' < "$file" 2>/dev/null || cat "$file"
done | sha256sum | cut -d' ' -f1

echo ""
echo "=== Approach 2: Without lowercase (just LC_COLLATE=C sort) ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | sort | while read -r file; do
    tr -d '\r' < "$file" 2>/dev/null || cat "$file"
done | sha256sum | cut -d' ' -f1

echo ""
echo "=== Approach 3: Without line ending normalization ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | awk '{print tolower($0) "\t" $0}' | sort | cut -f2- | while read -r file; do
    cat "$file"
done | sha256sum | cut -d' ' -f1

echo ""
echo "=== Approach 4: Case-sensitive sort (no tolower) ==="
find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name ".build-hash*" \
    ! -name "*.log" \
    ! -name "*.tmp" \
    2>/dev/null | sort -f | while read -r file; do
    tr -d '\r' < "$file" 2>/dev/null || cat "$file"
done | sha256sum | cut -d' ' -f1
