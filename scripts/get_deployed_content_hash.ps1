# PowerShell script to get deployed CONTENT_HASH from Cloud Run service/job
# Reads JSON input from stdin (Terraform external data source)

$ErrorActionPreference = "Stop"

try {
    # Read JSON input from stdin
    $inputJson = [Console]::In.ReadToEnd() | ConvertFrom-Json
    
    $project_id = $inputJson.project_id
    $region = $inputJson.region
    $resource_name = $inputJson.resource_name
    $resource_type = $inputJson.resource_type
    
    # Initialize empty values
    $contentHash = ""
    $localHash = ""
    $githubHash = ""
    
    if ($resource_type -eq "service") {
        # Cloud Run Service - get as JSON and parse
        $json = gcloud run services describe $resource_name `
            --region=$region `
            --project=$project_id `
            --format=json 2>$null | ConvertFrom-Json
        
        if ($null -ne $json) {
            $envVars = $json.spec.template.spec.containers[0].env
            
            # Find hashes in environment variables
            $contentHashEnv = $envVars | Where-Object { $_.name -eq "CONTENT_HASH" }
            $localHashEnv = $envVars | Where-Object { $_.name -eq "LOCAL_HASH" }
            $githubHashEnv = $envVars | Where-Object { $_.name -eq "GITHUB_HASH" }
            
            # Extract values
            $contentHash = if ($null -eq $contentHashEnv) { "" } else { $contentHashEnv.value }
            $localHash = if ($null -eq $localHashEnv) { "" } else { $localHashEnv.value }
            $githubHash = if ($null -eq $githubHashEnv) { "" } else { $githubHashEnv.value }
        }
    } else {
        # Cloud Run Job - get as JSON and parse  
        $json = gcloud run jobs describe $resource_name `
            --region=$region `
            --project=$project_id `
            --format=json 2>$null | ConvertFrom-Json
        
        if ($null -ne $json) {
            $envVars = $json.spec.template.spec.template.spec.containers[0].env
            
            # Find hashes in environment variables
            $contentHashEnv = $envVars | Where-Object { $_.name -eq "CONTENT_HASH" }
            $localHashEnv = $envVars | Where-Object { $_.name -eq "LOCAL_HASH" }
            $githubHashEnv = $envVars | Where-Object { $_.name -eq "GITHUB_HASH" }
            
            # Extract values
            $contentHash = if ($null -eq $contentHashEnv) { "" } else { $contentHashEnv.value }
            $localHash = if ($null -eq $localHashEnv) { "" } else { $localHashEnv.value }
            $githubHash = if ($null -eq $githubHashEnv) { "" } else { $githubHashEnv.value }
        }
    }
    
    # Return all three hashes as JSON
    Write-Output "{`"deployed_content_hash`":`"$contentHash`",`"deployed_local_hash`":`"$localHash`",`"deployed_github_hash`":`"$githubHash`"}"
} catch {
    # Return empty hashes on any error (e.g., resource doesn't exist yet)
    Write-Output '{"deployed_content_hash":"","deployed_local_hash":"","deployed_github_hash":""}'
}
