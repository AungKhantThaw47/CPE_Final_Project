#!/bin/bash
# Get Deployed Hash Script
# Retrieves CONTENT_HASH from deployed Cloud Run Job or Service
# Usage: ./get_deployed_hash.sh <project_id> <region> <resource_name> <resource_type>

set -e

PROJECT_ID="$1"
REGION="$2"
RESOURCE_NAME="$3"
RESOURCE_TYPE="$4"

if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$RESOURCE_NAME" ] || [ -z "$RESOURCE_TYPE" ]; then
    echo "Error: All parameters are required"
    echo "Usage: $0 <project_id> <region> <resource_name> <job|service>"
    exit 1
fi

if [ "$RESOURCE_TYPE" != "job" ] && [ "$RESOURCE_TYPE" != "service" ]; then
    echo "Error: Resource type must be 'job' or 'service'"
    exit 1
fi

if [ "$RESOURCE_TYPE" = "job" ]; then
    DEPLOYED_HASH=$(gcloud run jobs describe "$RESOURCE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(template.template.containers[0].env[?name='CONTENT_HASH'].value)" 2>/dev/null || echo "")
else
    DEPLOYED_HASH=$(gcloud run services describe "$RESOURCE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(spec.template.spec.containers[0].env[?name='CONTENT_HASH'].value)" 2>/dev/null || echo "")
fi

echo "$DEPLOYED_HASH"
