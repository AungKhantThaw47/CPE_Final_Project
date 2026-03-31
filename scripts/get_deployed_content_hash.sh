#!/bin/bash
# Bash script to get deployed CONTENT_HASH from Cloud Run service/job

# Read JSON input from Terraform using Python to avoid jq dependency
input_json="$(cat)"
readarray -t input_values < <(printf '%s' "$input_json" | python3 -c 'import json, sys
payload = json.load(sys.stdin)
print(payload.get("project_id", ""))
print(payload.get("region", ""))
print(payload.get("resource_name", ""))
print(payload.get("resource_type", ""))')

project_id="${input_values[0]}"
region="${input_values[1]}"
resource_name="${input_values[2]}"
resource_type="${input_values[3]}"

extract_hashes() {
    python3 -c 'import json, sys
resource_type = sys.argv[1]
try:
    doc = json.load(sys.stdin)
except Exception:
    print("")
    print("")
    print("")
    raise SystemExit(0)

if resource_type == "service":
    env_list = (
        doc.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [{}])[0]
        .get("env", [])
    )
else:
    env_list = (
        doc.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [{}])[0]
        .get("env", [])
    )

env_map = {
    item.get("name"): item.get("value", "")
    for item in env_list
    if isinstance(item, dict)
}

print(env_map.get("CONTENT_HASH", ""))
print(env_map.get("LOCAL_HASH", ""))
print(env_map.get("GITHUB_HASH", ""))' "$1"
}

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
        readarray -t extracted < <(printf '%s' "$json_output" | extract_hashes "service")
        deployed_content_hash="${extracted[0]}"
        deployed_local_hash="${extracted[1]}"
        deployed_github_hash="${extracted[2]}"
    fi
else
    # Cloud Run Job - parse JSON
    json_output=$(gcloud run jobs describe "$resource_name" \
        --region="$region" \
        --project="$project_id" \
        --format=json 2>/dev/null || echo "")
    
    if [ -n "$json_output" ]; then
        readarray -t extracted < <(printf '%s' "$json_output" | extract_hashes "job")
        deployed_content_hash="${extracted[0]}"
        deployed_local_hash="${extracted[1]}"
        deployed_github_hash="${extracted[2]}"
    fi
fi

# Output JSON result with all three hashes
python3 - "$deployed_content_hash" "$deployed_local_hash" "$deployed_github_hash" <<'PY'
import json
import sys

print(json.dumps({
    "deployed_content_hash": sys.argv[1],
    "deployed_local_hash": sys.argv[2],
    "deployed_github_hash": sys.argv[3],
}))
PY
