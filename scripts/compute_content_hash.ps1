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
try {
    $files = Get-ChildItem -Path $CodebasePath -Recurse -File | 
             Where-Object { 
                 $_.Name -notlike ".build-hash*" -and
                 $_.Name -notlike "*.log" -and
                 $_.Name -notlike "*.tmp"
             } | Sort-Object FullName

    if ($files.Count -eq 0) {
        Write-Error "No files found in codebase directory"
        exit 1
    }

    # Create a hash of all file contents (normalize line endings to LF)
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    $combinedBytes = [System.Collections.Generic.List[byte]]::new()

    foreach ($file in $files) {
        try {
            # Try to read as text and normalize line endings (CRLF -> LF)
            $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
            $normalizedContent = $content.Replace("`r`n", "`n")
            $fileBytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedContent)
            $combinedBytes.AddRange($fileBytes)
        } catch {
            # If text read fails (binary file), read as binary without normalization
            $fileBytes = [System.IO.File]::ReadAllBytes($file.FullName)
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
