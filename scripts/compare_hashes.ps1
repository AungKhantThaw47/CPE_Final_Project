# Compare Hashes Script
# Compares current content hash with deployed hash to determine if deployment is needed
# Usage: .\compare_hashes.ps1 -CurrentHash "hash1" -DeployedHash "hash2"
# Returns: 0 if hashes match (no deployment needed), 1 if different (deployment needed)

param(
    [Parameter(Mandatory=$true)]
    [string]$CurrentHash,
    
    [Parameter(Mandatory=$false)]
    [string]$DeployedHash = ""
)

$ErrorActionPreference = "Stop"

# If no deployed hash exists, deployment is needed (first deployment)
if ([string]::IsNullOrEmpty($DeployedHash)) {
    Write-Host "No deployed hash found. First deployment required."
    exit 1
}

# Compare hashes
if ($CurrentHash -eq $DeployedHash) {
    Write-Host "Hashes match. No deployment needed."
    Write-Host "  Current:  $CurrentHash"
    Write-Host "  Deployed: $DeployedHash"
    exit 0
}
else {
    Write-Host "Hashes differ. Deployment required."
    Write-Host "  Current:  $CurrentHash"
    Write-Host "  Deployed: $DeployedHash"
    exit 1
}
