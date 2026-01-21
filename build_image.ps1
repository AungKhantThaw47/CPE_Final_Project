# PowerShell script to build and push Docker image using Cloud Build
param(
    [string]$Region,
    [string]$ProjectId,
    [string]$RepositoryId,
    [string]$ImageName,
    [string]$ImageTag
)

$imagePath = "$Region-docker.pkg.dev/$ProjectId/$RepositoryId/$ImageName`:$ImageTag"

Write-Host "Building and pushing image: $imagePath"

gcloud builds submit cloud-run-gpu-batch/gpu-job `
    --tag=$imagePath `
    --project=$ProjectId `
    --timeout=20m

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Build completed successfully!"
