#!/bin/bash
# Bash script to get deployed CONTENT_HASH from Cloud Run service/job

set -e

# Read JSON input from Terraform
eval "$(jq -r '@sh "project_id=\(.project_id) region=\(.region) resource_name=\(.resource_name) resource_type=\(.resource_type)"')"

if [ "$resource_type" = "service" ]; then
    # Cloud Run Service - parse JSON
    deployed_hash=$(gcloud run services describe "$resource_name" \
        --region="$region" \
        --project="$project_id" \
        --format=json 2>/dev/null | \
        jq -r '.spec.template.spec.containers[0].env[] | select(.name=="CONTENT_HASH") | .value' || echo "")
else
    # Cloud Run Job - parse JSON
    deployed_hash=$(gcloud run jobs describe "$resource_name" \
        --region="$region" \
        --project="$project_id" \
        --format=json 2>/dev/null | \
        jq -r '.spec.template.spec.template.spec.containers[0].env[] | select(.name=="CONTENT_HASH") | .value' || echo "")
fi

# Output JSON result
jq -n --arg hash "$deployed_hash" '{"deployed_content_hash":$hash}'
