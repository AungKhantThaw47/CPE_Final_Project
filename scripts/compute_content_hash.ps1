# Compute Content Hash Script
# Computes deterministic hash of codebase directory content
# Usage: .\compute_content_hash.ps1 -CodebasePath "path/to/codebase"

param(
    [Parameter(Mandatory=$true)]
    [string]$CodebasePath
)

$ErrorActionPreference = "Stop"

# Verify codebase path exists
if (-not (Test-Path $CodebasePath)) {
    Write-Error "Codebase path does not exist: $CodebasePath"
    exit 1
}

# Compute hash of all files in codebase directory
# Sort files and compute combined hash for deterministic result
# Use ordinal byte-level sorting for cross-platform consistency
try {
    $files = Get-ChildItem -Path $CodebasePath -Recurse -File | 
             Where-Object { 
                 $_.Name -notlike ".build-hash*" -and
                 $_.Name -notlike "*.log" -and
                 $_.Name -notlike "*.tmp" -and
                 $_.Name -ne "package-lock.json" -and
                 $_.FullName -notlike "*\node_modules\*" -and
                 $_.FullName -notlike "*\__pycache__\*" -and
                 $_.FullName -notlike "*\.pytest_cache\*" -and
                 $_.FullName -notlike "*\venv\*" -and
                 $_.FullName -notlike "*\.venv\*"
             }

    # Convert to array with lowercase sort keys and sort using ordinal comparison
    # This matches the bash approach with tolower() + LC_COLLATE=C sort
    $fileList = [System.Collections.Generic.List[PSCustomObject]]::new()
    foreach ($file in $files) {
        $fileList.Add([PSCustomObject]@{
            Path = $file.FullName
            SortKey = $file.FullName.ToLowerInvariant().Replace('\', '/')
        })
    }
    $fileList.Sort({
        param($x, $y)
        [string]::CompareOrdinal($x.SortKey, $y.SortKey)
    })
    $fileArray = $fileList | ForEach-Object { $_.Path }

    if ($fileArray.Count -eq 0) {
        Write-Error "No files found in codebase directory"
        exit 1
    }

    # Create a hash of all file contents (normalize line endings to LF)
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    $combinedBytes = [System.Collections.Generic.List[byte]]::new()

    foreach ($filePath in $fileArray) {
        try {
            # Try to read as text and normalize line endings (CRLF -> LF)
            $content = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::UTF8)
            $normalizedContent = $content.Replace("`r`n", "`n")
            $fileBytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedContent)
            $combinedBytes.AddRange($fileBytes)
        } catch {
            # If text read fails (binary file), read as binary without normalization
            $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
            $combinedBytes.AddRange($fileBytes)
        }
    }

    $hashBytes = $hashAlgorithm.ComputeHash($combinedBytes.ToArray())
    $contentHash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()

    Write-Output $contentHash
}
catch {
    Write-Error "Failed to compute content hash: $_"
    exit 1
}
