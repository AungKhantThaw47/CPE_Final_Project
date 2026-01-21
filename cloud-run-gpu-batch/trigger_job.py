#!/usr/bin/env python3
"""
Cloud Run Job Trigger Script

This script triggers a Cloud Run Job via REST API (NO gcloud CLI).
Uses OAuth2 authentication with google-auth.

Usage:
    python trigger_job.py

Environment variables (optional):
    PROJECT_ID - GCP project ID (default: from terraform output)
    REGION - GCP region (default: from terraform output)
    JOB_NAME - Cloud Run Job name (default: from terraform output)
    SERVICE_ACCOUNT_KEY - Path to service account JSON key file
"""

import os
import sys
import json
import requests
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account


def load_terraform_outputs():
    """
    Load Terraform outputs to get job configuration.
    Reads from terraform output JSON.
    """
    try:
        import subprocess
        
        # Determine the terraform directory
        # If we're in cloud-run-gpu-batch subdirectory, go up one level
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir.endswith("cloud-run-gpu-batch"):
            tf_dir = os.path.dirname(script_dir)
        else:
            tf_dir = script_dir
            
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True,
            text=True,
            check=True,
            cwd=tf_dir
        )
        outputs = json.loads(result.stdout)
        
        return {
            "project_id": outputs["project_id"]["value"],
            "region": outputs["region"]["value"],
            "job_name": outputs["job_name"]["value"],
        }
    except Exception as e:
        print(f"⚠️  Could not load terraform outputs: {e}")
        return None


def get_credentials():
    """
    Get Google Cloud credentials for API authentication.
    Uses Application Default Credentials or service account key file.
    """
    key_file = os.environ.get("SERVICE_ACCOUNT_KEY")
    
    if key_file and os.path.exists(key_file):
        print(f"Using service account key: {key_file}")
        credentials = service_account.Credentials.from_service_account_file(
            key_file,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    else:
        print("Using Application Default Credentials")
        credentials, project = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    
    return credentials


def trigger_job(project_id, region, job_name):
    """
    Trigger Cloud Run Job via REST API.
    
    API Reference:
    https://cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run
    """
    print("=" * 60)
    print("TRIGGERING CLOUD RUN JOB")
    print("=" * 60)
    print(f"Project ID: {project_id}")
    print(f"Region: {region}")
    print(f"Job Name: {job_name}")
    
    # Get OAuth2 credentials
    credentials = get_credentials()
    credentials.refresh(Request())
    access_token = credentials.token
    
    # Construct API endpoint
    # Format: /v2/projects/{project}/locations/{location}/jobs/{job}:run
    url = (
        f"https://{region}-run.googleapis.com/v2/"
        f"projects/{project_id}/locations/{region}/jobs/{job_name}:run"
    )
    
    print(f"\nAPI Endpoint: {url}")
    
    # Prepare request headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    # Request body (empty for basic execution)
    payload = {}
    
    print("\nSending POST request...")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Job triggered successfully!")
            print(f"\nExecution Name: {result.get('name', 'N/A')}")
            print(f"Execution UID: {result.get('uid', 'N/A')}")
            
            # Extract execution name for monitoring
            execution_name = result.get('name', '')
            if execution_name:
                print(f"\nMonitor execution at:")
                print(f"https://console.cloud.google.com/run/jobs/executions/details/{region}/{execution_name}")
            
            return result
        else:
            print(f"\n❌ Failed to trigger job")
            print(f"Response: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        sys.exit(1)


def main():
    """
    Main execution flow.
    """
    print("🚀 Cloud Run Job Trigger (REST API)")
    print()
    
    # Get configuration from environment or terraform
    project_id = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION")
    job_name = os.environ.get("JOB_NAME")
    
    # If not provided, try to load from terraform outputs
    if not all([project_id, region, job_name]):
        print("Loading configuration from Terraform outputs...")
        tf_config = load_terraform_outputs()
        
        if tf_config:
            project_id = project_id or tf_config["project_id"]
            region = region or tf_config["region"]
            job_name = job_name or tf_config["job_name"]
        else:
            print("\n❌ Missing configuration. Set environment variables:")
            print("   PROJECT_ID, REGION, JOB_NAME")
            print("\nOr run from directory with terraform state.")
            sys.exit(1)
    
    # Trigger the job
    result = trigger_job(project_id, region, job_name)
    
    print("\n" + "=" * 60)
    print("✅ TRIGGER COMPLETE")
    print("=" * 60)
    print("\nThe job is now executing with GPU.")
    print("GPU will automatically stop when the job completes.")
    print("\nTo view logs:")
    print(f"1. Go to Cloud Console > Cloud Run > Jobs")
    print(f"2. Select '{job_name}'")
    print(f"3. View execution logs")
    print("\nTo view results:")
    print(f"Check GCS bucket: {project_id}-gpu-job-outputs")


if __name__ == "__main__":
    main()
