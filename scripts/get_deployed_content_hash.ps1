# PowerShell script to get deployed CONTENT_HASH from Cloud Run service/job
param(
    [string]$project_id,
    [string]$region,
    [string]$resource_name,
    [string]$resource_type  # "service" or "job"
)

try {
    if ($resource_type -eq "service") {
        # Cloud Run Service - get as JSON and parse
        $json = gcloud run services describe $resource_name `
            --region=$region `
            --project=$project_id `
            --format=json 2>$null | ConvertFrom-Json
        
        $envVars = $json.spec.template.spec.containers[0].env
    } else {
        # Cloud Run Job - get as JSON and parse  
        $json = gcloud run jobs describe $resource_name `
            --region=$region `
            --project=$project_id `
            --format=json 2>$null | ConvertFrom-Json
        
        $envVars = $json.spec.template.spec.template.spec.containers[0].env
    }
    
    # Find CONTENT_HASH in environment variables
    $contentHashEnv = $envVars | Where-Object { $_.name -eq "CONTENT_HASH" }
    
    if ($null -eq $contentHashEnv -or [string]::IsNullOrWhiteSpace($contentHashEnv.value)) {
        # Resource doesn't exist yet or has no CONTENT_HASH - return empty hash
        Write-Output '{"deployed_content_hash":""}'
    } else {
        $hash = $contentHashEnv.value.Trim()
        Write-Output "{`"deployed_content_hash`":`"$hash`"}"
    }
} catch {
    # Return empty hash on any error
    Write-Output '{"deployed_content_hash":""}'
}
