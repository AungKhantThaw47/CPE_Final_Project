# Hash Modules Documentation

Reusable hashing modules for PowerShell and Bash, providing consistent cross-platform content hashing functionality.

## Overview

These modules provide cryptographic hashing utilities for:
- Computing SHA256/MD5 hashes of strings, files, and directories
- Normalizing line endings for cross-platform consistency
- Filtering files with customizable exclusion patterns
- Comparing and storing hashes

## Files

- **Hash-Module.psm1** - PowerShell module
- **hash_module.sh** - Bash script module
- **example_hash_usage.ps1** - PowerShell usage examples
- **example_hash_usage.sh** - Bash usage examples

---

## PowerShell Module (Hash-Module.psm1)

### Installation

```powershell
# Import the module
Import-Module .\scripts\Hash-Module.psm1

# Or with full path
Import-Module "D:\workspace\CPE_Final_Project\scripts\Hash-Module.psm1"
```

### Functions

#### Get-StringHash
Computes SHA256 hash of a string.

```powershell
$hash = Get-StringHash -Content "Hello, World!"
# Returns: dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f
```

#### Get-FileHash
Computes SHA256 hash of a file with optional line ending normalization.

```powershell
# With normalization (default)
$hash = Get-FileHash -FilePath "C:\path\to\file.txt"

# Without normalization (preserves CRLF)
$hash = Get-FileHash -FilePath "C:\path\to\file.txt" -NormalizeLineEndings $false
```

#### Get-DirectoryContentHash
Computes SHA256 hash of all files in a directory.

```powershell
$result = Get-DirectoryContentHash -DirectoryPath "C:\path\to\dir"
Write-Host "Hash: $($result.Hash)"
Write-Host "Files: $($result.FileCount)"

# With custom exclusions
$result = Get-DirectoryContentHash `
    -DirectoryPath "C:\path\to\dir" `
    -ExclusionPatterns @("*.log", "*\temp\*")

# With verbose output
$result = Get-DirectoryContentHash `
    -DirectoryPath "C:\path\to\dir" `
    -Verbose
```

**Returns:**
```powershell
@{
    Hash = "abc123..."
    FileCount = 42
    ProcessedFiles = @("file1.txt", "file2.py", ...)
}
```

#### Compare-Hashes
Compares two hash strings (case-insensitive).

```powershell
$match = Compare-Hashes -Hash1 $hash1 -Hash2 $hash2
# Returns: $true or $false
```

#### Save-HashToFile & Read-HashFromFile
Store and retrieve hashes from files.

```powershell
# Save
Save-HashToFile -Hash $myHash -FilePath "hash.txt"

# Read
$storedHash = Read-HashFromFile -FilePath "hash.txt"
```

#### Get-DefaultExclusionPatterns
Gets default file exclusion patterns.

```powershell
$patterns = Get-DefaultExclusionPatterns
# Returns: @(".build-hash*", "*.log", "*\node_modules\*", ...)
```

#### Get-FilteredFiles
Filters a file list using exclusion patterns.

```powershell
$files = Get-ChildItem -Recurse -File
$filtered = Get-FilteredFiles -Files $files
```

#### Get-Md5Hash
Fast MD5 hashing (less secure, useful for quick comparisons).

```powershell
$md5 = Get-Md5Hash -Content "Quick test"
```

---

## Bash Module (hash_module.sh)

### Installation

```bash
# Source the module
source ./scripts/hash_module.sh

# Or with full path
source /path/to/hash_module.sh
```

### Functions

#### hash_string
Computes SHA256 hash of a string.

```bash
hash=$(hash_string "Hello, World!")
# Returns: dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f
```

#### hash_file
Computes SHA256 hash of a file.

```bash
# With normalization (default)
hash=$(hash_file "/path/to/file.txt")

# Without normalization
hash=$(hash_file "/path/to/file.txt" false)
```

#### hash_directory_content
Computes SHA256 hash of all files in a directory.

```bash
# Basic usage
result=$(hash_directory_content "/path/to/dir")

# Parse JSON result
hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
file_count=$(echo "$result" | grep -oP '"file_count":\s*\K[0-9]+')

# With custom exclusions
custom_patterns="*.log
*.tmp
test_*"
result=$(hash_directory_content "/path/to/dir" "$custom_patterns")

# With verbose output
result=$(hash_directory_content "/path/to/dir" "" "true" "true")
```

**Returns JSON:**
```json
{
  "hash": "abc123...",
  "file_count": 42
}
```

#### compare_hashes
Compares two hash strings.

```bash
if compare_hashes "$hash1" "$hash2"; then
    echo "Hashes match"
else
    echo "Hashes differ"
fi
```

#### save_hash_to_file & read_hash_from_file
Store and retrieve hashes.

```bash
# Save
save_hash_to_file "$my_hash" "hash.txt"

# Read
stored_hash=$(read_hash_from_file "hash.txt")
```

#### get_default_exclusion_patterns
Gets default exclusion patterns (one per line).

```bash
patterns=$(get_default_exclusion_patterns)
echo "$patterns"
```

#### md5_hash_string & md5_hash_file
Fast MD5 hashing.

```bash
md5=$(md5_hash_string "Quick test")
md5=$(md5_hash_file "/path/to/file.txt")
```

#### verify_hash_dependencies
Checks if required commands are available.

```bash
if verify_hash_dependencies; then
    echo "All dependencies available"
fi
```

---

## Default Exclusion Patterns

Both modules exclude these patterns by default:
- `.build-hash*` - Build hash tracking files
- `*.log` - Log files
- `*.tmp` - Temporary files
- `node_modules/` - Node.js dependencies
- `__pycache__/` - Python cache
- `.pytest_cache/` - Pytest cache
- `venv/`, `.venv/` - Python virtual environments
- `.git/` - Git repository data
- `.terraform/` - Terraform state
- `*.tfstate*` - Terraform state files
- `.DS_Store` - macOS metadata
- `dist/`, `build/` - Build output directories

---

## Usage Examples

### Example 1: Hash a Project Directory

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1

$result = Get-DirectoryContentHash -DirectoryPath ".\Codebase_Container\text_clean_codebase"
Write-Host "Project Hash: $($result.Hash)"
Write-Host "Files: $($result.FileCount)"
```

**Bash:**
```bash
source ./scripts/hash_module.sh

result=$(hash_directory_content "./Codebase_Container/text_clean_codebase")
echo "Project Hash: $(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')"
```

### Example 2: Compare Local vs Deployed Code

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1

$localHash = (Get-DirectoryContentHash -DirectoryPath ".\app").Hash
$deployedHash = Read-HashFromFile -FilePath ".deployed-hash"

if (Compare-Hashes -Hash1 $localHash -Hash2 $deployedHash) {
    Write-Host "Code is up to date"
} else {
    Write-Host "Changes detected - deployment needed"
}
```

**Bash:**
```bash
source ./scripts/hash_module.sh

result=$(hash_directory_content "./app")
local_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
deployed_hash=$(read_hash_from_file ".deployed-hash")

if compare_hashes "$local_hash" "$deployed_hash"; then
    echo "Code is up to date"
else
    echo "Changes detected - deployment needed"
fi
```

### Example 3: Track Build Artifacts

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1

# Compute hash before build
$preHash = (Get-DirectoryContentHash -DirectoryPath ".\src").Hash

# ... perform build ...

# Save hash after successful build
Save-HashToFile -Hash $preHash -FilePath ".build-hash"
```

**Bash:**
```bash
source ./scripts/hash_module.sh

# Compute hash before build
result=$(hash_directory_content "./src")
pre_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')

# ... perform build ...

# Save hash after successful build
save_hash_to_file "$pre_hash" ".build-hash"
```

---

## Running Examples

### PowerShell
```powershell
.\scripts\example_hash_usage.ps1
```

### Bash
```bash
chmod +x ./scripts/example_hash_usage.sh
./scripts/example_hash_usage.sh
```

---

## Cross-Platform Consistency

Both modules normalize line endings (CRLF → LF) by default to ensure consistent hashes across Windows, Linux, and macOS for text files. Binary files are hashed as-is.

### To disable normalization:

**PowerShell:**
```powershell
$hash = Get-FileHash -FilePath "file.txt" -NormalizeLineEndings $false
$result = Get-DirectoryContentHash -DirectoryPath "dir" -NormalizeLineEndings $false
```

**Bash:**
```bash
hash=$(hash_file "file.txt" false)
result=$(hash_directory_content "dir" "" false)
```

---

## Performance Considerations

- **SHA256** is secure but slower - use for production/deployment tracking
- **MD5** is faster but less secure - use for quick local comparisons
- **Directory hashing** scales with file count and size
- **Exclusion patterns** significantly improve performance by skipping large dependency directories

---

## Integration with Existing Scripts

### Update existing scripts to use modules:

**Before:**
```powershell
$files = Get-ChildItem -Recurse -File | Where-Object { $_.Name -notlike "*.log" }
$hash = ($files | Get-Content -Raw | Out-String | `
    ForEach-Object { [System.Text.Encoding]::UTF8.GetBytes($_) } | `
    ForEach-Object { (Get-FileHash -InputStream ([System.IO.MemoryStream]::new($_))).Hash })
```

**After:**
```powershell
Import-Module .\scripts\Hash-Module.psm1
$result = Get-DirectoryContentHash -DirectoryPath "."
$hash = $result.Hash
```

---

## License

Part of CPE_Final_Project. See main README for license information.

## Support

For issues or questions, refer to the project documentation or examine the example scripts.
