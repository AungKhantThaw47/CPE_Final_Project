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
    
    # Find hashes in environment variables
    $contentHashEnv = $envVars | Where-Object { $_.name -eq "CONTENT_HASH" }
    $localHashEnv = $envVars | Where-Object { $_.name -eq "LOCAL_HASH" }
    $githubHashEnv = $envVars | Where-Object { $_.name -eq "GITHUB_HASH" }
    
    # Extract values (empty string if not found)
    $contentHash = if ($null -eq $contentHashEnv) { "" } else { $contentHashEnv.value }
    $localHash = if ($null -eq $localHashEnv) { "" } else { $localHashEnv.value }
    $githubHash = if ($null -eq $githubHashEnv) { "" } else { $githubHashEnv.value }
    
    # Return all three hashes as JSON
    Write-Output "{`"deployed_content_hash`":`"$contentHash`",`"deployed_local_hash`":`"$localHash`",`"deployed_github_hash`":`"$githubHash`"}"
} catch {
    # Return empty hashes on any error
    Write-Output '{"deployed_content_hash":"","deployed_local_hash":"","deployed_github_hash":""}'
}
