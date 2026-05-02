#!/bin/bash
# Debug script to check why pending_review_annotation folder linkage broke

set -e

echo "=== Checking Terraform Outputs ==="
echo ""

echo "All available outputs:"
terraform output -json | jq 'keys[]' 2>/dev/null || echo "  (No outputs available)"
echo ""

echo "Jobs output:"
terraform output -json 2>/dev/null | jq '.jobs.value // "NOT FOUND"' || echo "  (jobs output missing)"
echo ""

echo "Services output:"
terraform output -json 2>/dev/null | jq '.services.value // "NOT FOUND"' || echo "  (services output missing)"
echo ""

echo "=== Checking if dvb-annotator-job is in outputs ==="
if terraform output -json 2>/dev/null | jq '.jobs.value | keys[] | select(. == "dvb-annotator-job")' >/dev/null 2>&1; then
    echo "✓ dvb-annotator-job FOUND in terraform output"
    echo ""
    echo "Details:"
    terraform output -json 2>/dev/null | jq '.jobs.value["dvb-annotator-job"]'
else
    echo "✗ dvb-annotator-job NOT FOUND in terraform output"
    echo "This is likely why pending_review_annotation/ relationships were not created!"
fi

echo ""
echo "=== What to do next ==="
echo ""
echo "1. If dvb-annotator-job is missing from outputs:"
echo "   a. Check outputs.tf for the job definition"
echo "   b. Run: terraform apply -auto-approve"
echo "   c. Then run: make deploy AUTO_APPROVE=true"
echo ""
echo "2. If dvb-annotator-job is present:"
echo "   a. Check bootstrap/neo4j/generated/terraform_post_action_graph.json"
echo "   b. Search for 'pending_review_annotation'"
echo "   c. If relationships exist in generated manifest but not in Neo4j:"
echo "      - The graph loader failed silently"
echo "      - Run: make restart-graph"
echo ""
