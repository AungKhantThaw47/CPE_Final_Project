# Compute Content Hash using Hash Module
# Returns JSON with content_hash for Terraform external data source
# Usage: Called by Terraform data.external resource

$ErrorActionPreference = "Stop"

# Read JSON input from stdin (Terraform passes JSON via stdin)
$inputJson = @($input)[0]
if (-not $inputJson) {
    # Try reading from console if pipeline is empty
    $reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput())
    $inputJson = $reader.ReadToEnd()
    $reader.Close()
}

if (-not $inputJson) {
    Write-Output (@{
        content_hash = ""
        error = "No input provided"
    } | ConvertTo-Json -Compress)
    exit 0
}

try {
    $queryData = $inputJson | ConvertFrom-Json
    $codebasePath = $queryData.codebase_path
} catch {
    Write-Output (@{
        content_hash = ""
        error = "Failed to parse input JSON: $($_.Exception.Message)"
    } | ConvertTo-Json -Compress)
    exit 0
}

if (-not $codebasePath -or -not (Test-Path $codebasePath)) {
    # Return error as valid JSON
    Write-Output (@{
        content_hash = ""
        error = "Invalid or missing codebase_path: $codebasePath"
    } | ConvertTo-Json -Compress)
    exit 0
}

# Import hash module
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module "$ScriptDir\Hash-Module.psm1" -Force

try {
    # Compute hash using the hash module
    $result = Get-DirectoryContentHash -DirectoryPath $codebasePath
    
    # Return JSON for Terraform
    Write-Output (@{
        content_hash = $result.Hash
        file_count = $result.FileCount.ToString()
    } | ConvertTo-Json -Compress)
    
} catch {
    # Return error as valid JSON
    Write-Output (@{
        content_hash = ""
        error = $_.Exception.Message
    } | ConvertTo-Json -Compress)
}
