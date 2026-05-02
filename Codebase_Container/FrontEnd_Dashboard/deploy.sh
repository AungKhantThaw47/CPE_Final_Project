#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  Deploy Myanmar Crisis Dashboard to GCS static website hosting
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

# ── CONFIGURE THESE ──────────────────────────────────────────────
DASHBOARD_BUCKET="myanmar-crisis-dashboard"      # bucket for the HTML file (new bucket)
CRISIS_BUCKET="YOUR_CRISIS_BUCKET_NAME"          # existing bucket that holds extracted JSON
PROJECT_ID="YOUR_GCP_PROJECT_ID"
REGION="asia-southeast1"
# ─────────────────────────────────────────────────────────────────

HTML_FILE="crisis-dashboard (1).html"

echo "=== Step 1: Create dashboard hosting bucket ==="
gsutil mb -p "$PROJECT_ID" -l "$REGION" -b on "gs://$DASHBOARD_BUCKET" 2>/dev/null || echo "Bucket already exists, continuing."

echo "=== Step 2: Make bucket public (static website) ==="
gsutil iam ch allUsers:objectViewer "gs://$DASHBOARD_BUCKET"

echo "=== Step 3: Configure as static website ==="
gsutil web set -m index.html "gs://$DASHBOARD_BUCKET"

echo "=== Step 4: Upload dashboard HTML as index.html ==="
gsutil -h "Cache-Control:no-cache,max-age=0" cp "$HTML_FILE" "gs://$DASHBOARD_BUCKET/index.html"

echo "=== Step 5: Set CORS on the crisis data bucket ==="
cat > /tmp/cors.json <<'EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Length"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set /tmp/cors.json "gs://$CRISIS_BUCKET"
echo "CORS set on gs://$CRISIS_BUCKET"

echo ""
echo "=== DONE ==="
echo "Dashboard URL: https://storage.googleapis.com/$DASHBOARD_BUCKET/index.html"
echo ""
echo "Next steps:"
echo "  1. Open crisis-dashboard (1).html and set:"
echo "       GCS_BUCKET = \"$CRISIS_BUCKET\""
echo "       GCS_PREFIX = \"extracted_json/\"   (adjust to match your extractor output path)"
echo "  2. Re-upload: gsutil cp \"$HTML_FILE\" gs://$DASHBOARD_BUCKET/index.html"
echo "  3. When data arrives in gs://$CRISIS_BUCKET/extracted_json/, the dashboard auto-loads it."
