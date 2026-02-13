#!/bin/bash
# Get current username for deployment tracking
# Returns JSON for Terraform external data source

set -e

USERNAME="${USER:-${USERNAME:-unknown}}"

# Return JSON for Terraform external data source
echo "{\"username\":\"$USERNAME\"}"
