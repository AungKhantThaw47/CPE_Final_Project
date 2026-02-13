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
                 $_.Name -notlike "*.tmp"
             } | Sort-Object FullName

    if ($files.Count -eq 0) {
        # Return empty hash for empty directories
        Write-Output (@{
            content_hash = ""
        } | ConvertTo-Json -Compress)
        exit 0
    }

    # Create a hash of all file contents
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    $combinedBytes = [System.Collections.Generic.List[byte]]::new()

    foreach ($file in $files) {
        $fileBytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $combinedBytes.AddRange($fileBytes)
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
