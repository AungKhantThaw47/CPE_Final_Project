#!/bin/bash
# Example Usage: Hash Module for Bash
# This script demonstrates how to use the hash_module.sh

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the hash module
source "$SCRIPT_DIR/hash_module.sh"

echo "=== Hash Module - Bash Examples ==="
echo ""

# Verify dependencies first
if ! verify_hash_dependencies; then
    echo "Error: Missing required dependencies"
    exit 1
fi

# Example 1: Hash a string
echo -e "\033[0;32mExample 1: Hashing a string\033[0m"
test_string="Hello, World!"
string_hash=$(hash_string "$test_string")
echo "  String: '$test_string'"
echo "  SHA256: $string_hash"
echo ""

# Example 2: Hash a single file
echo -e "\033[0;32mExample 2: Hashing a file\033[0m"
test_file="$SCRIPT_DIR/../README.md"
if [ -f "$test_file" ]; then
    file_hash=$(hash_file "$test_file")
    echo "  File: $test_file"
    echo "  SHA256: $file_hash"
else
    echo "  Skipped - README.md not found"
fi
echo ""

# Example 3: Hash a directory
echo -e "\033[0;32mExample 3: Hashing a directory\033[0m"
test_dir="$SCRIPT_DIR/../Codebase_Container/text_clean_codebase"
if [ -d "$test_dir" ]; then
    result=$(hash_directory_content "$test_dir")
    dir_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
    file_count=$(echo "$result" | grep -oP '"file_count":\s*\K[0-9]+')
    echo "  Directory: $test_dir"
    echo "  SHA256: $dir_hash"
    echo "  Files processed: $file_count"
else
    echo "  Skipped - Directory not found"
fi
echo ""

# Example 4: Compare two hashes
echo -e "\033[0;32mExample 4: Comparing hashes\033[0m"
hash1=$(hash_string "test123")
hash2=$(hash_string "test123")
hash3=$(hash_string "test456")

if compare_hashes "$hash1" "$hash2"; then
    match1="true"
else
    match1="false"
fi

if compare_hashes "$hash1" "$hash3"; then
    match2="true"
else
    match2="false"
fi

echo "  Hash1 vs Hash2 (same content): $match1"
echo "  Hash1 vs Hash3 (different content): $match2"
echo ""

# Example 5: Save and read hash from file
echo -e "\033[0;32mExample 5: Save and read hash\033[0m"
temp_hash_file="/tmp/test_hash_$$.txt"
test_hash=$(hash_string "SaveMe")
save_hash_to_file "$test_hash" "$temp_hash_file"
read_hash=$(read_hash_from_file "$temp_hash_file")
if compare_hashes "$test_hash" "$read_hash"; then
    matches="true"
else
    matches="false"
fi
echo "  Saved hash: $test_hash"
echo "  Read hash:  $read_hash"
echo "  Hashes match: $matches"
rm -f "$temp_hash_file" 2>/dev/null
echo ""

# Example 6: MD5 hash (faster)
echo -e "\033[0;32mExample 6: MD5 hashing (faster but less secure)\033[0m"
md5_hash=$(md5_hash_string "QuickHash")
echo "  MD5: $md5_hash"
echo ""

# Example 7: Hash file without normalization
echo -e "\033[0;32mExample 7: Hash file without line ending normalization\033[0m"
if [ -f "$test_file" ]; then
    raw_hash=$(hash_file "$test_file" false)
    normalized_hash=$(hash_file "$test_file" true)
    echo "  File: $test_file"
    echo "  Raw hash:        $raw_hash"
    echo "  Normalized hash: $normalized_hash"
else
    echo "  Skipped - README.md not found"
fi
echo ""

# Example 8: Get default exclusion patterns
echo -e "\033[0;32mExample 8: Default exclusion patterns\033[0m"
echo "  Default exclusions:"
get_default_exclusion_patterns | while read -r pattern; do
    [ -n "$pattern" ] && echo "    - $pattern"
done
echo ""

# Example 9: Hash directory with verbose output
echo -e "\033[0;32mExample 9: Hash directory with verbose output\033[0m"
small_dir="$SCRIPT_DIR/../utils"
if [ -d "$small_dir" ]; then
    echo "  Processing: $small_dir"
    result=$(hash_directory_content "$small_dir" "" "true" "false")
    dir_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
    echo "  Result hash: $dir_hash"
else
    echo "  Skipped - utils directory not found"
fi
echo ""

echo "=== All examples completed ==="
