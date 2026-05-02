#!/bin/bash
export PATH=/home/mma/google-cloud-sdk/bin:/usr/bin:/bin
REGION=asia-southeast1
GCLOUD=/home/mma/google-cloud-sdk/bin/gcloud

echo "Listing all executions..."
EXECUTIONS=$($GCLOUD run jobs executions list --region=$REGION --format="value(metadata.name)" --limit=1000 2>/dev/null | sort -u)
TOTAL=$(echo "$EXECUTIONS" | grep -c .)
echo "Found $TOTAL executions to cancel"

while IFS= read -r exec_name; do
  [ -z "$exec_name" ] && continue
  $GCLOUD run jobs executions cancel "$exec_name" --region=$REGION --quiet 2>/dev/null \
    && echo "Cancelled: $exec_name" \
    || echo "Skip (already done): $exec_name"
done <<< "$EXECUTIONS"

echo "All done."
