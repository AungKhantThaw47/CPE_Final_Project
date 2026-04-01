param(
    [string]$TerraformBinary = $(if ($env:TF) { $env:TF } else { "terraform" })
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "terraform_post_action.py"

if (-not (Get-Command $TerraformBinary -ErrorAction SilentlyContinue)) {
    Write-Error "terraform post-action: missing Terraform binary '$TerraformBinary'"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
    Write-Error "terraform post-action: missing required tool 'python' or 'python3'"
}

if (-not (Test-Path $pythonScript)) {
    Write-Error "terraform post-action: missing helper script '$pythonScript'"
}

$pythonBin = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "python3" }
$env:TF = $TerraformBinary
& $pythonBin $pythonScript
