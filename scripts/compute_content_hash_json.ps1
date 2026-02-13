# Compute Content Hash Script (JSON output for Terraform)
# Computes deterministic hash of codebase directory content
# Returns JSON for Terraform external data source

param(
    [Parameter(Mandatory=$false, ValueFromPipeline=$true)]
    [string]$CodebasePath = "",
    
    [Parameter(Mandatory=$false, ValueFromPipeline=$true)]
    [string]$InputObject = ""
)

$ErrorActionPreference = "Stop"

# Get codebase path from query parameter if not provided directly
if ([string]::IsNullOrEmpty($CodebasePath)) {
    # Try to read from stdin for Terraform external data source
    try {
        $stdinContent = ""
        
        # Read from stdin if redirected
        if ([Console]::IsInputRedirected) {
            $reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput())
            $stdinContent = $reader.ReadToEnd()
            $reader.Close()
        }
        elseif (-not [string]::IsNullOrEmpty($InputObject)) {
            $stdinContent = $InputObject
        }
        
        if (-not [string]::IsNullOrEmpty($stdinContent)) {
            $query = $stdinContent | ConvertFrom-Json
            $CodebasePath = $query.codebase_path
        }
    } catch {
        # If parsing fails, return empty hash
        Write-Output (@{
            content_hash = ""
        } | ConvertTo-Json -Compress)
        exit 0
    }
}

# Verify codebase path exists
if ([string]::IsNullOrEmpty($CodebasePath) -or -not (Test-Path $CodebasePath)) {
    # Return empty hash instead of failing
    Write-Output (@{
        content_hash = ""
    } | ConvertTo-Json -Compress)
    exit 0
}

# Compute hash of all files in codebase directory
try {
    $files = Get-ChildItem -Path $CodebasePath -Recurse -File | 
             Where-Object { 
                 $_.Name -notlike ".build-hash*" -and
                 $_.Name -notlike "*.log" -and
                 $_.Name -notlike "*.tmp" -and
                 $_.FullName -notlike "*\node_modules\*" -and
                 $_.FullName -notlike "*\__pycache__\*" -and
                 $_.FullName -notlike "*\.pytest_cache\*" -and
                 $_.FullName -notlike "*\venv\*" -and
                 $_.FullName -notlike "*\.venv\*"
             } | Sort-Object FullName

    if ($files.Count -eq 0) {
        # Return empty hash for empty directories
        Write-Output (@{
            content_hash = ""
        } | ConvertTo-Json -Compress)
        exit 0
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

    # Return JSON for Terraform external data source
    Write-Output (@{
        content_hash = $contentHash
    } | ConvertTo-Json -Compress)
}
catch {
    # Return empty hash on error
    Write-Output (@{
        content_hash = ""
    } | ConvertTo-Json -Compress)
    exit 0
}
