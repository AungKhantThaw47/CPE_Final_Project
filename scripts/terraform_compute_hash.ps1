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
    $utilsPath = $queryData.utils_path
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
    # Compute codebase hash
    $result = Get-DirectoryContentHash -DirectoryPath $codebasePath
    $codebaseHash = $result.Hash
    $codebaseFileCount = $result.FileCount

    # Compute utils hash when available so shared utils changes trigger rebuilds
    $utilsHash = $null
    $utilsFileCount = 0
    if ($utilsPath -and (Test-Path $utilsPath)) {
        $utilsResult = Get-DirectoryContentHash -DirectoryPath $utilsPath
        $utilsHash = $utilsResult.Hash
        $utilsFileCount = $utilsResult.FileCount
    }

    if ($utilsHash) {
        $combinedHash = Get-StringHash -Content "$codebaseHash`:$utilsHash"
    } else {
        $combinedHash = $codebaseHash
    }
    
    # Return JSON for Terraform
    Write-Output (@{
        content_hash = $combinedHash
        file_count = ($codebaseFileCount + $utilsFileCount).ToString()
    } | ConvertTo-Json -Compress)
    
} catch {
    # Return error as valid JSON
    Write-Output (@{
        content_hash = ""
        error = $_.Exception.Message
    } | ConvertTo-Json -Compress)
}
