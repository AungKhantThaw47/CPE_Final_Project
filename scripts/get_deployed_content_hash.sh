#!/bin/bash
# Bash script to get deployed CONTENT_HASH from Cloud Run service/job

# Read JSON input from Terraform
eval "$(jq -r '@sh "project_id=\(.project_id) region=\(.region) resource_name=\(.resource_name) resource_type=\(.resource_type)"')"

# Initialize empty values
deployed_content_hash=""
deployed_local_hash=""
deployed_github_hash=""

if [ "$resource_type" = "service" ]; then
    # Cloud Run Service - parse JSON
    json_output=$(gcloud run services describe "$resource_name" \
        --region="$region" \
        --project="$project_id" \
        --format=json 2>/dev/null || echo "")
    
    if [ -n "$json_output" ]; then
        deployed_content_hash=$(echo "$json_output" | jq -r '.spec.template.spec.containers[0].env[]? | select(.name=="CONTENT_HASH") | .value' 2>/dev/null || echo "")
        deployed_local_hash=$(echo "$json_output" | jq -r '.spec.template.spec.containers[0].env[]? | select(.name=="LOCAL_HASH") | .value' 2>/dev/null || echo "")
        deployed_github_hash=$(echo "$json_output" | jq -r '.spec.template.spec.containers[0].env[]? | select(.name=="GITHUB_HASH") | .value' 2>/dev/null || echo "")
    fi
else
    # Cloud Run Job - parse JSON
    json_output=$(gcloud run jobs describe "$resource_name" \
        --region="$region" \
        --project="$project_id" \
        --format=json 2>/dev/null || echo "")
    
    if [ -n "$json_output" ]; then
        deployed_content_hash=$(echo "$json_output" | jq -r '.spec.template.spec.template.spec.containers[0].env[]? | select(.name=="CONTENT_HASH") | .value' 2>/dev/null || echo "")
        deployed_local_hash=$(echo "$json_output" | jq -r '.spec.template.spec.template.spec.containers[0].env[]? | select(.name=="LOCAL_HASH") | .value' 2>/dev/null || echo "")
        deployed_github_hash=$(echo "$json_output" | jq -r '.spec.template.spec.template.spec.containers[0].env[]? | select(.name=="GITHUB_HASH") | .value' 2>/dev/null || echo "")
    fi
fi

# Output JSON result with all three hashes
jq -n --arg content "$deployed_content_hash" --arg local "$deployed_local_hash" --arg github "$deployed_github_hash" \
    '{"deployed_content_hash":$content,"deployed_local_hash":$local,"deployed_github_hash":$github}'
