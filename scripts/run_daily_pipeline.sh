#!/bin/bash

##############################################################################
# run_daily_pipeline.sh
#
# Spawn a gcloud command for each day in a date range.
# Replaces {DATE} placeholder in the command with each day (DD-MM-YYYY).
#
# Usage:
#   ./scripts/run_daily_pipeline.sh START_DATE END_DATE COMMAND
#
# Arguments:
#   START_DATE      - Start date in DD-MM-YYYY format (e.g., 20-03-2026)
#   END_DATE        - End date in DD-MM-YYYY format (e.g., 22-03-2026)
#   COMMAND         - Command template with {DATE} placeholder (quoted)
#
# Examples:
#   # Execute same date for both start and end of date-range pipeline
#   ./scripts/run_daily_pipeline.sh 20-03-2026 22-03-2026 \
#     'gcloud workflows execute manual-pipeline --location=asia-southeast1 --data="{\"crawl_start_date\":\"{DATE}\",\"crawl_end_date\":\"{DATE}\"}"'
#
##############################################################################

set -euo pipefail

# Helper: Print with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Helper: Parse DD-MM-YYYY to YYYY-MM-DD for date arithmetic
date_to_unix() {
    local date_str="$1"  # DD-MM-YYYY
    date -j -f "%d-%m-%Y" "$date_str" "+%s" 2>/dev/null || date -d "$date_str" "+%s"
}

# Helper: Convert unix timestamp back to DD-MM-YYYY
unix_to_date() {
    local unix_ts="$1"
    date -j -f "%s" "$unix_ts" "+%d-%m-%Y" 2>/dev/null || date -d "@$unix_ts" "+%d-%m-%Y"
}

# Parse arguments
if [[ $# -lt 3 ]]; then
    cat >&2 <<'EOF'
Usage: ./run_daily_pipeline.sh START_DATE END_DATE COMMAND

Arguments:
  START_DATE   - Start date in DD-MM-YYYY format (e.g., 20-03-2026)
  END_DATE     - End date in DD-MM-YYYY format (e.g., 22-03-2026)
  COMMAND      - Command template with {DATE} placeholder (in quotes)

Example:
  ./run_daily_pipeline.sh 20-03-2026 22-03-2026 \
    'gcloud workflows execute manual-pipeline \
      --location=asia-southeast1 \
      --data="{\"crawl_start_date\":\"{DATE}\",\"crawl_end_date\":\"{DATE}\"}"'
EOF
    exit 1
fi

START_DATE="$1"
END_DATE="$2"
COMMAND_TEMPLATE="$3"

# Validate date format
if ! [[ "$START_DATE" =~ ^[0-9]{2}-[0-9]{2}-[0-9]{4}$ ]]; then
    log "ERROR: START_DATE '$START_DATE' does not match DD-MM-YYYY format"
    exit 1
fi
if ! [[ "$END_DATE" =~ ^[0-9]{2}-[0-9]{2}-[0-9]{4}$ ]]; then
    log "ERROR: END_DATE '$END_DATE' does not match DD-MM-YYYY format"
    exit 1
fi

log "Starting date-range command spawner"
log "  Date range:   $START_DATE to $END_DATE"
log "  Mode:         fire-and-forget (no waiting)"
log "  Command:      $COMMAND_TEMPLATE"
log ""

# Generate date range
current_date="$START_DATE"
end_unix=$(date_to_unix "$END_DATE")
current_unix=$(date_to_unix "$START_DATE")

# Track running jobs for parallel execution
job_count=0
pids=()

while [[ $current_unix -le $end_unix ]]; do
    current_date=$(unix_to_date "$current_unix")
    
    # Substitute {DATE} in command template
    cmd="${COMMAND_TEMPLATE//{DATE}/$current_date}"
    
    log "Spawning: $cmd"
    
    # Execute asynchronously (fire and forget)
    eval "$cmd" >/dev/null 2>&1 &
    
    # Move to next day
    current_unix=$((current_unix + 86400))
done

log "All commands spawned!"
