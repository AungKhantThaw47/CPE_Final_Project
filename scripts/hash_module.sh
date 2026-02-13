#!/bin/bash
# Hash Module for Bash
# Provides reusable hashing functions for content-based operations
# Usage: source ./hash_module.sh

# Computes SHA256 hash of a string
# Arguments:
#   $1 - Content string to hash
# Returns:
#   Hexadecimal hash string via stdout
hash_string() {
    local content="$1"
    
    if [ -z "$content" ]; then
        echo "Error: Content is required" >&2
        return 1
    fi
    
    echo -n "$content" | sha256sum | cut -d' ' -f1
}

# Computes SHA256 hash of a file
# Arguments:
#   $1 - File path to hash
#   $2 - Normalize line endings (true/false, default: true)
# Returns:
#   Hexadecimal hash string via stdout
hash_file() {
    local file_path="$1"
    local normalize="${2:-true}"
    
    if [ ! -f "$file_path" ]; then
        echo "Error: File not found: $file_path" >&2
        return 1
    fi
    
    if [ "$normalize" = "true" ]; then
        # Normalize CRLF to LF for consistent cross-platform hashing
        tr -d '\r' < "$file_path" | sha256sum | cut -d' ' -f1
    else
        sha256sum "$file_path" | cut -d' ' -f1
    fi
}

# Gets the default file exclusion patterns for content hashing
# Returns:
#   Array-like string of patterns (one per line)
get_default_exclusion_patterns() {
    cat <<EOF
node_modules
__pycache__
.pytest_cache
venv
.venv
.git
.terraform
*.tfstate
*.tfstate.backup
.DS_Store
dist
build
.build-hash
*.log
*.tmp
EOF
}

# Builds find command exclusion arguments from patterns
# Arguments:
#   $1 - Pattern list (one per line)
# Returns:
#   Find command arguments via stdout
build_find_exclusions() {
    local patterns="$1"
    local exclusions=""
    
    while IFS= read -r pattern; do
        [ -z "$pattern" ] && continue
        
        # Handle wildcard patterns
        if [[ "$pattern" == "*."* ]]; then
            # File extension pattern (e.g., *.log)
            exclusions="$exclusions ! -name '${pattern#\*.}'"
        else
            # Directory or file name pattern
            exclusions="$exclusions ! -path '*/${pattern}/*' ! -name '${pattern}'"
        fi
    done <<< "$patterns"
    
    echo "$exclusions"
}

# Computes SHA256 hash of directory contents
# Arguments:
#   $1 - Directory path
#   $2 - Custom exclusion patterns (optional, newline-separated)
#   $3 - Normalize line endings (true/false, default: true)
#   $4 - Verbose mode (true/false, default: false)
# Returns:
#   JSON object with hash, file_count via stdout
hash_directory_content() {
    local dir_path="$1"
    local custom_patterns="$2"
    local normalize="${3:-true}"
    local verbose="${4:-false}"
    
    if [ ! -d "$dir_path" ]; then
        echo "Error: Directory not found: $dir_path" >&2
        return 1
    fi
    
    # Use custom patterns or defaults
    local patterns="${custom_patterns:-$(get_default_exclusion_patterns)}"
    
    # Build find command with exclusions
    local find_cmd="find \"$dir_path\" -type f"
    
    # Add exclusion patterns
    while IFS= read -r pattern; do
        [ -z "$pattern" ] && continue
        
        if [[ "$pattern" == "*."* ]]; then
            # File extension pattern (e.g., *.log)
            local ext="${pattern#\*.}"
            find_cmd="$find_cmd ! -name '*.$ext'"
        else
            # Directory or file name pattern
            find_cmd="$find_cmd ! -path '*/${pattern}/*' ! -name '${pattern}'"
        fi
    done <<< "$patterns"
    
    find_cmd="$find_cmd 2>/dev/null"
    
    if [ "$verbose" = "true" ]; then
        echo "Finding files in: $dir_path" >&2
        echo "Command: $find_cmd" >&2
    fi
    
    # Get sorted file list (lowercase + byte sort for cross-platform consistency)
    # Use LC_COLLATE=C to ensure consistent byte-level sorting across all systems
    local file_list
    file_list=$(eval "$find_cmd" | awk '{print tolower($0) "\t" $0}' | LC_COLLATE=C sort | cut -f2-)
    
    if [ -z "$file_list" ]; then
        echo "Error: No files found in directory after filtering" >&2
        return 1
    fi
    
    local file_count
    file_count=$(echo "$file_list" | wc -l)
    
    if [ "$verbose" = "true" ]; then
        echo "Processing $file_count files..." >&2
    fi
    
    # Compute combined hash
    local combined_hash
    if [ "$normalize" = "true" ]; then
        combined_hash=$(echo "$file_list" | while read -r file; do
            if [ "$verbose" = "true" ]; then
                echo "  Processing: $file" >&2
            fi
            tr -d '\r' < "$file" 2>/dev/null || cat "$file"
        done | sha256sum | cut -d' ' -f1)
    else
        combined_hash=$(echo "$file_list" | while read -r file; do
            if [ "$verbose" = "true" ]; then
                echo "  Processing: $file" >&2
            fi
            cat "$file"
        done | sha256sum | cut -d' ' -f1)
    fi
    
    if [ -z "$combined_hash" ]; then
        echo "Error: Failed to compute directory hash" >&2
        return 1
    fi
    
    # Return JSON-like output
    cat <<EOF
{
  "hash": "$combined_hash",
  "file_count": $file_count
}
EOF
}

# Compares two hash strings
# Arguments:
#   $1 - First hash
#   $2 - Second hash
# Returns:
#   0 if hashes match, 1 if they don't
compare_hashes() {
    local hash1="$1"
    local hash2="$2"
    
    if [ -z "$hash1" ] || [ -z "$hash2" ]; then
        echo "Error: Both hashes are required" >&2
        return 2
    fi
    
    # Convert to lowercase for case-insensitive comparison
    hash1=$(echo "$hash1" | tr '[:upper:]' '[:lower:]')
    hash2=$(echo "$hash2" | tr '[:upper:]' '[:lower:]')
    
    if [ "$hash1" = "$hash2" ]; then
        return 0
    else
        return 1
    fi
}

# Saves hash to a file
# Arguments:
#   $1 - Hash string
#   $2 - File path
save_hash_to_file() {
    local hash="$1"
    local file_path="$2"
    
    if [ -z "$hash" ] || [ -z "$file_path" ]; then
        echo "Error: Hash and file path are required" >&2
        return 1
    fi
    
    echo -n "$hash" > "$file_path"
    echo "Hash saved to: $file_path" >&2
}

# Reads hash from a file
# Arguments:
#   $1 - File path
# Returns:
#   Hash content via stdout, or empty string if file doesn't exist
read_hash_from_file() {
    local file_path="$1"
    
    if [ -z "$file_path" ]; then
        echo "Error: File path is required" >&2
        return 1
    fi
    
    if [ -f "$file_path" ]; then
        cat "$file_path" | tr -d '\n\r'
    fi
}

# Computes MD5 hash (faster but less secure)
# Arguments:
#   $1 - Content string to hash
# Returns:
#   Hexadecimal MD5 hash string via stdout
md5_hash_string() {
    local content="$1"
    
    if [ -z "$content" ]; then
        echo "Error: Content is required" >&2
        return 1
    fi
    
    # Try different MD5 commands based on OS
    if command -v md5sum &> /dev/null; then
        echo -n "$content" | md5sum | cut -d' ' -f1
    elif command -v md5 &> /dev/null; then
        # macOS
        echo -n "$content" | md5
    else
        echo "Error: No MD5 utility found" >&2
        return 1
    fi
}

# Computes MD5 hash of a file
# Arguments:
#   $1 - File path
# Returns:
#   Hexadecimal MD5 hash string via stdout
md5_hash_file() {
    local file_path="$1"
    
    if [ ! -f "$file_path" ]; then
        echo "Error: File not found: $file_path" >&2
        return 1
    fi
    
    # Try different MD5 commands based on OS
    if command -v md5sum &> /dev/null; then
        md5sum "$file_path" | cut -d' ' -f1
    elif command -v md5 &> /dev/null; then
        # macOS
        md5 -q "$file_path"
    else
        echo "Error: No MD5 utility found" >&2
        return 1
    fi
}

# Verifies that all required commands are available
# Returns:
#   0 if all commands are available, 1 otherwise
verify_hash_dependencies() {
    local missing_deps=()
    
    if ! command -v sha256sum &> /dev/null; then
        missing_deps+=("sha256sum")
    fi
    
    if ! command -v find &> /dev/null; then
        missing_deps+=("find")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo "Error: Missing required dependencies: ${missing_deps[*]}" >&2
        return 1
    fi
    
    return 0
}

# Export functions (not needed in bash, but documents available functions)
# Available functions:
#   - hash_string
#   - hash_file
#   - get_default_exclusion_patterns
#   - build_find_exclusions
#   - hash_directory_content
#   - compare_hashes
#   - save_hash_to_file
#   - read_hash_from_file
#   - md5_hash_string
#   - md5_hash_file
#   - verify_hash_dependencies
