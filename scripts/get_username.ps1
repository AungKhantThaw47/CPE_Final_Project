# Get current username for deployment tracking
# Returns JSON for Terraform external data source

$ErrorActionPreference = "Stop"

$username = $env:USERNAME
if ([string]::IsNullOrEmpty($username)) {
    $username = $env:USER
}
if ([string]::IsNullOrEmpty($username)) {
    $username = "unknown"
}

# Return JSON for Terraform external data source
Write-Output (@{
    username = $username
} | ConvertTo-Json -Compress)
