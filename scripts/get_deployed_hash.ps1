# Get Deployed Hash Script
# Retrieves CONTENT_HASH from deployed Cloud Run Job or Service
# Usage: .\get_deployed_hash.ps1 -ProjectId "project-id" -Region "region" -ResourceName "resource-name" -ResourceType "job|service"

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory=$true)]
    [string]$Region,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceName,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("job", "service")]
    [string]$ResourceType
)

$ErrorActionPreference = "Stop"

try {
    if ($ResourceType -eq "job") {
        # Get deployed hash from Cloud Run Job
        $deployedHash = gcloud run jobs describe $ResourceName `
            --region=$Region `
            --project=$ProjectId `
            --format="value(template.template.containers[0].env[?name='CONTENT_HASH'].value)" 2>$null
    }
    else {
        # Get deployed hash from Cloud Run Service
        $deployedHash = gcloud run services describe $ResourceName `
            --region=$Region `
            --project=$ProjectId `
            --format="value(spec.template.spec.containers[0].env[?name='CONTENT_HASH'].value)" 2>$null
    }

    if ([string]::IsNullOrEmpty($deployedHash)) {
        Write-Warning "No CONTENT_HASH found in deployed $ResourceType. This may be a first deployment."
        Write-Output ""
    }
    else {
        Write-Output $deployedHash
    }
}
catch {
    Write-Warning "Failed to retrieve deployed hash: $_"
    Write-Output ""
}
