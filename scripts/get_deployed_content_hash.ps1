# PowerShell script to get deployed CONTENT_HASH from Cloud Run service/job
param(
    [string]$project_id,
    [string]$region,
    [string]$resource_name,
    [string]$resource_type  # "service" or "job"
)

try {
    if ($resource_type -eq "service") {
        $output = gcloud run services describe $resource_name --region=$region --project=$project_id --format="value(template.containers[0].env.filter(name:CONTENT_HASH).value)" 2>$null
    } else {
        $output = gcloud run jobs describe $resource_name --region=$region --project=$project_id --format="value(template.template.containers[0].env.filter(name:CONTENT_HASH).value)" 2>$null
    }
    
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($output)) {
        # Resource doesn't exist yet or has no CONTENT_HASH - return empty hash
        Write-Output '{"deployed_content_hash":""}'
    } else {
        $hash = $output.Trim()
        Write-Output "{`"deployed_content_hash`":`"$hash`"}"
    }
} catch {
    # Return empty hash on any error
    Write-Output '{"deployed_content_hash":""}'
}
