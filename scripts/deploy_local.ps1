# Local Deployment Script with Hash Control
# Compares content hash before deploying to prevent unnecessary deployments
# Usage: .\deploy_local.ps1 [-ResourceName "job-name"] [-ResourceType "job|service"] [-SkipHashCheck]

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceName = "",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("job", "service", "")]
    [string]$ResourceType = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipHashCheck = $false,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Local Deployment with Hash Control" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Load project configuration from terraform.tfvars or use defaults
if ([string]::IsNullOrEmpty($ProjectId)) {
    if (Test-Path "$rootDir\terraform.tfvars") {
        $tfvarsContent = Get-Content "$rootDir\terraform.tfvars" -Raw
        if ($tfvarsContent -match 'project_id\s*=\s*"([^"]+)"') {
            $ProjectId = $Matches[1]
        }
    }
    if ([string]::IsNullOrEmpty($ProjectId)) {
        $ProjectId = "cpe-final-project"
    }
}

if ([string]::IsNullOrEmpty($Region)) {
    if (Test-Path "$rootDir\terraform.tfvars") {
        $tfvarsContent = Get-Content "$rootDir\terraform.tfvars" -Raw
        if ($tfvarsContent -match 'region\s*=\s*"([^"]+)"') {
            $Region = $Matches[1]
        }
    }
    if ([string]::IsNullOrEmpty($Region)) {
        $Region = "asia-southeast1"
    }
}

Write-Host "Project ID: $ProjectId" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Username: $env:USERNAME" -ForegroundColor Yellow
Write-Host ""

# Hash Check Logic (only if ResourceName and ResourceType are provided)
if (-not $SkipHashCheck -and -not [string]::IsNullOrEmpty($ResourceName) -and -not [string]::IsNullOrEmpty($ResourceType)) {
    Write-Host "Step 1: Computing current content hash..." -ForegroundColor Cyan
    
    # Determine codebase path based on resource name
    $codebasePath = ""
    $jobPaths = @{
        "gpu-batch-job" = "$rootDir\Codebase_Container\gpu_batch_job"
        "daily-data-processor" = "$rootDir\Codebase_Container\cloud_scheduler_function"
        "dvb-crawler-job" = "$rootDir\Codebase_Container\crawler_job"
        "dvb-text-cleaner-job" = "$rootDir\Codebase_Container\text_clean_codebase"
    }
    $servicePaths = @{
        "mlflow" = "$rootDir\modules\mlflow"
    }
    
    if ($ResourceType -eq "job" -and $jobPaths.ContainsKey($ResourceName)) {
        $codebasePath = $jobPaths[$ResourceName]
    }
    elseif ($ResourceType -eq "service" -and $servicePaths.ContainsKey($ResourceName)) {
        $codebasePath = $servicePaths[$ResourceName]
    }
    else {
        Write-Error "Unknown resource: $ResourceName (type: $ResourceType)"
        exit 1
    }
    
    if (-not (Test-Path $codebasePath)) {
        Write-Error "Codebase path not found: $codebasePath"
        exit 1
    }
    
    $currentHash = & "$scriptDir\compute_content_hash.ps1" -CodebasePath $codebasePath
    Write-Host "Current content hash: $currentHash" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Step 2: Retrieving deployed hash from Cloud Run..." -ForegroundColor Cyan
    $deployedHash = & "$scriptDir\get_deployed_hash.ps1" `
        -ProjectId $ProjectId `
        -Region $Region `
        -ResourceName $ResourceName `
        -ResourceType $ResourceType
    
    if (-not [string]::IsNullOrEmpty($deployedHash)) {
        Write-Host "Deployed content hash: $deployedHash" -ForegroundColor Green
    }
    else {
        Write-Host "Deployed content hash: (none - first deployment)" -ForegroundColor Yellow
    }
    Write-Host ""
    
    Write-Host "Step 3: Comparing hashes..." -ForegroundColor Cyan
    & "$scriptDir\compare_hashes.ps1" -CurrentHash $currentHash -DeployedHash $deployedHash
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "No deployment needed. Exiting." -ForegroundColor Green
        exit 0
    }
    
    Write-Host ""
    Write-Host "Step 4: Proceeding with Terraform deployment..." -ForegroundColor Cyan
}
elseif ($SkipHashCheck) {
    Write-Host "Skipping hash check (--SkipHashCheck flag provided)" -ForegroundColor Yellow
    Write-Host ""
}
else {
    Write-Host "No specific resource target. Deploying all resources." -ForegroundColor Yellow
    Write-Host "(Use -ResourceName and -ResourceType to enable hash checking)" -ForegroundColor Yellow
    Write-Host ""
}

# Run Terraform with hash control variables
Write-Host "Initializing Terraform..." -ForegroundColor Cyan
Set-Location $rootDir
terraform init

Write-Host ""
Write-Host "Planning Terraform changes..." -ForegroundColor Cyan

# Compute content hashes for all resources if not targeting specific resource
$contentHash = ""
if (-not [string]::IsNullOrEmpty($ResourceName) -and -not [string]::IsNullOrEmpty($codebasePath)) {
    $contentHash = & "$scriptDir\compute_content_hash.ps1" -CodebasePath $codebasePath
}

# Note: For full deployments, content_hash is computed by Terraform itself
# For targeted deployments, we pass the computed hash

terraform plan `
    -var="local_username=$env:USERNAME" `
    $(if ($contentHash) { "-var=content_hash=$contentHash" } else { "" })

Write-Host ""
Write-Host "Applying Terraform changes..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to cancel, or wait 5 seconds to continue..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

terraform apply `
    -var="local_username=$env:USERNAME" `
    $(if ($contentHash) { "-var=content_hash=$contentHash" } else { "" }) `
    -auto-approve

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "Deployment failed!" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    exit 1
}
