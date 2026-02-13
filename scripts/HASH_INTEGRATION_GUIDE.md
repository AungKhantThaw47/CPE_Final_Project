# Hash Modules - Quick Integration Guide

This guide shows how to migrate existing hash computation scripts to use the new reusable hash modules.

## Migration Examples

### Example 1: Updating compute_content_hash.ps1

**Before (inline hashing):**
```powershell
param([Parameter(Mandatory=$true)][string]$CodebasePath)

$files = Get-ChildItem -Path $CodebasePath -Recurse -File | 
         Where-Object { 
             $_.Name -notlike ".build-hash*" -and
             $_.Name -notlike "*.log" -and
             # ... more filters ...
         } | Sort-Object FullName

$hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
$combinedBytes = [System.Collections.Generic.List[byte]]::new()

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file.FullName)
    $normalizedContent = $content.Replace("`r`n", "`n")
    $fileBytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedContent)
    $combinedBytes.AddRange($fileBytes)
}

$hashBytes = $hashAlgorithm.ComputeHash($combinedBytes.ToArray())
$hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
Write-Output $hash
```

**After (using module):**
```powershell
param([Parameter(Mandatory=$true)][string]$CodebasePath)

# Import hash module
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module "$ScriptDir\Hash-Module.psm1" -Force

# Compute hash using module
$result = Get-DirectoryContentHash -DirectoryPath $CodebasePath
Write-Output $result.Hash
```

**Benefits:** ~50 lines → ~7 lines, better error handling, reusable

---

### Example 2: Updating compute_content_hash.sh

**Before (inline hashing):**
```bash
#!/bin/bash
set -e

CODEBASE_PATH="$1"

CURRENT_HASH=$(find "$CODEBASE_PATH" -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -name "*.log" \
    2>/dev/null | sort | while read -r file; do
    tr -d '\r' < "$file"
done | sha256sum | cut -d' ' -f1)

echo "$CURRENT_HASH"
```

**After (using module):**
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/hash_module.sh"

CODEBASE_PATH="$1"

result=$(hash_directory_content "$CODEBASE_PATH")
hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
echo "$hash"
```

**Benefits:** Cleaner, more maintainable, consistent with PowerShell version

---

## Common Patterns

### Pattern 1: Simple File Hash

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1
$hash = Get-FileHash -FilePath "myfile.txt"
```

**Bash:**
```bash
source ./scripts/hash_module.sh
hash=$(hash_file "myfile.txt")
```

### Pattern 2: Directory Hash with Custom Exclusions

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1
$patterns = @("*.pyc", "*.pyo", "*\__pycache__\*")
$result = Get-DirectoryContentHash -DirectoryPath "./src" -ExclusionPatterns $patterns
```

**Bash:**
```bash
source ./scripts/hash_module.sh
patterns="*.pyc
*.pyo
__pycache__"
result=$(hash_directory_content "./src" "$patterns")
```

### Pattern 3: Compare Local vs Remote Hash

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1

$localHash = (Get-DirectoryContentHash -DirectoryPath "./app").Hash
$remoteHash = (Invoke-RestMethod "https://api.example.com/hash").hash

if (Compare-Hashes -Hash1 $localHash -Hash2 $remoteHash) {
    Write-Host "No deployment needed"
    exit 0
} else {
    Write-Host "Deploying changes..."
    # Deploy code
    Save-HashToFile -Hash $localHash -FilePath ".last-deployed-hash"
}
```

**Bash:**
```bash
source ./scripts/hash_module.sh

result=$(hash_directory_content "./app")
local_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')
remote_hash=$(curl -s "https://api.example.com/hash" | grep -oP '"hash":\s*"\K[^"]+')

if compare_hashes "$local_hash" "$remote_hash"; then
    echo "No deployment needed"
    exit 0
else
    echo "Deploying changes..."
    # Deploy code
    save_hash_to_file "$local_hash" ".last-deployed-hash"
fi
```

### Pattern 4: Git Integration

**PowerShell:**
```powershell
Import-Module .\scripts\Hash-Module.psm1

# Hash current codebase
$currentHash = (Get-DirectoryContentHash -DirectoryPath "./src").Hash

# Get git commit hash
$gitCommit = git rev-parse HEAD

# Create combined tracking object
$tracking = @{
    content_hash = $currentHash
    git_commit = $gitCommit
    timestamp = (Get-Date -Format "o")
} | ConvertTo-Json

$tracking | Out-File "build-info.json"
```

**Bash:**
```bash
source ./scripts/hash_module.sh

# Hash current codebase
result=$(hash_directory_content "./src")
current_hash=$(echo "$result" | grep -oP '"hash":\s*"\K[^"]+')

# Get git commit hash
git_commit=$(git rev-parse HEAD)

# Create combined tracking object
cat > build-info.json <<EOF
{
  "content_hash": "$current_hash",
  "git_commit": "$git_commit",
  "timestamp": "$(date -Iseconds)"
}
EOF
```

---

## Integration Checklist

When migrating an existing script:

- [ ] Import/source the appropriate module at the beginning
- [ ] Replace manual hash computation with module functions
- [ ] Update exclusion pattern lists to use module defaults or custom patterns
- [ ] Replace string comparisons with `Compare-Hashes` function
- [ ] Update file I/O to use `Save-HashToFile` and `Read-HashFromFile`
- [ ] Test with same inputs to verify hash consistency
- [ ] Update documentation/comments
- [ ] Remove old hash computation code

---

## Performance Tips

1. **Use MD5 for development, SHA256 for production:**
   ```powershell
   # Development (faster)
   $hash = Get-Md5Hash -Content $data
   
   # Production (secure)
   $hash = Get-StringHash -Content $data
   ```

2. **Cache directory hashes:**
   ```powershell
   $cacheFile = ".hash-cache"
   if (Test-Path $cacheFile) {
       $cachedHash = Read-HashFromFile -FilePath $cacheFile
       # Use cached hash if git hasn't changed
   }
   ```

3. **Exclude large directories early:**
   ```powershell
   $patterns = Get-DefaultExclusionPatterns
   $patterns += @("*\large_data\*", "*\models\*")
   ```

4. **Use ShowProgress for long operations:**
   ```powershell
   $result = Get-DirectoryContentHash -DirectoryPath $path -ShowProgress
   ```

---

## Testing Your Integration

### PowerShell Test Script:
```powershell
# test_hash_integration.ps1
Import-Module .\scripts\Hash-Module.psm1

$testDir = ".\test_directory"
New-Item -ItemType Directory -Path $testDir -Force | Out-Null
"test content" | Out-File "$testDir\file1.txt"
"test content" | Out-File "$testDir\file2.txt"

$hash1 = (Get-DirectoryContentHash -DirectoryPath $testDir).Hash
$hash2 = (Get-DirectoryContentHash -DirectoryPath $testDir).Hash

if (Compare-Hashes -Hash1 $hash1 -Hash2 $hash2) {
    Write-Host "✓ Hash consistency test passed" -ForegroundColor Green
} else {
    Write-Host "✗ Hash consistency test failed" -ForegroundColor Red
}

Remove-Item $testDir -Recurse -Force
```

### Bash Test Script:
```bash
#!/bin/bash
# test_hash_integration.sh
source ./scripts/hash_module.sh

test_dir="./test_directory"
mkdir -p "$test_dir"
echo "test content" > "$test_dir/file1.txt"
echo "test content" > "$test_dir/file2.txt"

result1=$(hash_directory_content "$test_dir")
hash1=$(echo "$result1" | grep -oP '"hash":\s*"\K[^"]+')

result2=$(hash_directory_content "$test_dir")
hash2=$(echo "$result2" | grep -oP '"hash":\s*"\K[^"]+')

if compare_hashes "$hash1" "$hash2"; then
    echo "✓ Hash consistency test passed"
else
    echo "✗ Hash consistency test failed"
fi

rm -rf "$test_dir"
```

---

## Troubleshooting

### Issue: Different hashes on Windows vs Linux
**Solution:** Ensure line ending normalization is enabled (default)

### Issue: Hash changes but files haven't changed
**Solution:** Check for excluded files being included or temp files being created

### Issue: Module import fails
**PowerShell Solution:**
```powershell
Import-Module ".\scripts\Hash-Module.psm1" -Force -ErrorAction Stop
```

**Bash Solution:**
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/hash_module.sh" || exit 1
```

### Issue: Permission denied on Bash scripts
**Solution:**
```bash
chmod +x ./scripts/*.sh
```

---

## Further Reading

- See [HASH_MODULES_README.md](HASH_MODULES_README.md) for complete API documentation
- Run example scripts for working demonstrations
- Check existing hash computation scripts for migration candidates
