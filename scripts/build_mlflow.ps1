param(
    [string]$Region,
    [string]$ProjectId
)

$ImageName = "mlflow-server"
$ImageTag = "latest"
$ImagePath = "$Region-docker.pkg.dev/$ProjectId/gpu-jobs/$ImageName`:$ImageTag"

Write-Host "Building MLflow image: $ImagePath"

gcloud builds submit modules/mlflow `
    --tag=$ImagePath `
    --project=$ProjectId `
    --timeout=10m

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "MLflow image built successfully: $ImagePath"
