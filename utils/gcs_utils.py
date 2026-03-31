"""
Shared GCS (Google Cloud Storage) utility functions for all components
"""

import os
import json
from datetime import datetime
import torch
from google.cloud import storage


def save_results_to_gcs(results_data, confirm_save=True):
    """
    Save computation results to Google Cloud Storage.
    
    Args:
        results_data (dict): Results data to save
        confirm_save (bool): If True, actually save to GCS. If False, only simulate/validate.
    
    Returns:
        dict: Upload status information
    """
    print("\n" + "=" * 60)
    print("SAVING RESULTS TO GCS")
    print("=" * 60)
    
    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        print("⚠️  GCS_BUCKET environment variable not set")
        print("⚠️  Skipping GCS upload")
        return {"status": "skipped", "reason": "GCS_BUCKET not set"}
    
    # Create unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_name = os.environ.get("JOB_NAME", "unknown-job")
    filename = f"{job_name}/results_{timestamp}.json"
    
    # Add metadata
    results_data["timestamp"] = datetime.now().isoformat()
    results_data["job_name"] = job_name
    results_data["cuda_available"] = torch.cuda.is_available()
    
    if torch.cuda.is_available():
        results_data["gpu_name"] = torch.cuda.get_device_name(0)
        results_data["gpu_count"] = torch.cuda.device_count()
    
    # Prepare JSON payload
    json_payload = json.dumps(results_data, indent=2)
    
    if not confirm_save:
        print("🔍 DRY RUN MODE - Not actually saving to GCS")
        print(f"Would save to: gs://{bucket_name}/{filename}")
        print(f"Payload size: {len(json_payload)} bytes")
        print(f"Preview:\n{json_payload[:200]}...")
        return {
            "status": "dry_run",
            "bucket": bucket_name,
            "filename": filename,
            "size_bytes": len(json_payload)
        }
    
    try:
        # Initialize GCS client (uses service account from Cloud Run)
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Upload to GCS
        blob = bucket.blob(filename)
        blob.upload_from_string(
            json_payload,
            content_type="application/json"
        )
        
        folder_name = os.path.dirname(filename)
        file_url = f"gs://{bucket_name}/{filename}"
        folder_url = f"gs://{bucket_name}/{folder_name}/" if folder_name else f"gs://{bucket_name}/"

        print(f"✅ Results saved to {file_url}")
        print(f"   Saved folder: {folder_url}")
        
        return {
            "status": "success",
            "bucket": bucket_name,
            "folder": folder_name,
            "filename": filename,
            "size_bytes": len(json_payload),
            "url": file_url
        }
        
    except Exception as e:
        print(f"❌ Error saving to GCS: {e}")
        print(f"   Bucket: {bucket_name}")
        raise
