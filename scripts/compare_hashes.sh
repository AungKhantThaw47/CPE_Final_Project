#!/bin/bash
# Compare Hashes Script
# Compares current content hash with deployed hash to determine if deployment is needed
# Usage: ./compare_hashes.sh <current_hash> <deployed_hash>
# Returns: 0 if hashes match (no deployment needed), 1 if different (deployment needed)

set -e

CURRENT_HASH="$1"
DEPLOYED_HASH="$2"

if [ -z "$CURRENT_HASH" ]; then
    echo "Error: Current hash is required"
    echo "Usage: $0 <current_hash> <deployed_hash>"
    exit 1
fi

# If no deployed hash exists, deployment is needed (first deployment)
if [ -z "$DEPLOYED_HASH" ]; then
    echo "No deployed hash found. First deployment required."
    exit 1
fi

# Compare hashes
if [ "$CURRENT_HASH" = "$DEPLOYED_HASH" ]; then
    echo "Hashes match. No deployment needed."
    echo "  Current:  $CURRENT_HASH"
    echo "  Deployed: $DEPLOYED_HASH"
    exit 0
else
    echo "Hashes differ. Deployment required."
    echo "  Current:  $CURRENT_HASH"
    echo "  Deployed: $DEPLOYED_HASH"
    exit 1
fi
