#!/usr/bin/env python3
"""
Build and push Docker image using Cloud Build API (no gcloud CLI)
"""
import os
import sys
import json
import tarfile
import tempfile
from pathlib import Path
from google.cloud import storage
from google.cloud.devtools import cloudbuild_v1
from google.api_core import retry

def create_source_tarball(source_dir: Path, output_path: Path):
    """Create a tarball of the source directory."""
    print(f"Creating source tarball from {source_dir}...")
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=".")
    print(f"Created tarball: {output_path} ({output_path.stat().st_size} bytes)")

def upload_source_to_gcs(bucket_name: str, local_file: Path, destination_blob: str):
    """Upload source tarball to GCS."""
    print(f"Uploading to gs://{bucket_name}/{destination_blob}...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(str(local_file))
    print(f"Uploaded to gs://{bucket_name}/{destination_blob}")
    return f"gs://{bucket_name}/{destination_blob}"

def submit_build(project_id: str, image_tag: str, source_gcs_url: str):
    """Submit build to Cloud Build."""
    print(f"Submitting build to Cloud Build...")
    client = cloudbuild_v1.CloudBuildClient()
    
    build = cloudbuild_v1.Build(
        source=cloudbuild_v1.Source(
            storage_source=cloudbuild_v1.StorageSource(
                bucket=source_gcs_url.replace("gs://", "").split("/")[0],
                object_=source_gcs_url.split("/", 3)[-1]
            )
        ),
        steps=[
            cloudbuild_v1.BuildStep(
                name="gcr.io/cloud-builders/docker",
                args=[
                    "build",
                    "--platform", "linux/amd64",
                    "--provenance=false",
                    "-t", image_tag,
                    "-f", "gpu-job/Dockerfile",
                    "."
                ]
            )
        ],
        images=[image_tag]
    )
    
    operation = client.create_build(project_id=project_id, build=build)
    print(f"Build submitted. Waiting for completion...")
    print(f"Build ID: {operation.metadata.build.id}")
    
    # Wait for build to complete
    result = operation.result(timeout=1800)  # 30 minute timeout
    
    if result.status == cloudbuild_v1.Build.Status.SUCCESS:
        print(f"✓ Build succeeded!")
        print(f"Image pushed: {image_tag}")
        return True
    else:
        print(f"✗ Build failed with status: {result.status}")
        print(f"Logs: {result.log_url}")
        return False

def main():
    # Read configuration from Terraform outputs
    os.chdir(Path(__file__).parent.parent)  # Go to project root
    
    result = os.popen("terraform output -json").read()
    outputs = json.loads(result)
    
    project_id = outputs["project_id"]["value"]
    bucket_name = outputs["storage_bucket"]["value"]
    image_url = outputs["image_url"]["value"]
    
    print(f"Project: {project_id}")
    print(f"Image: {image_url}")
    print(f"Bucket: {bucket_name}")
    
    # Create source directory path
    source_dir = Path(__file__).parent / "gpu-job"
    
    # Create temporary tarball
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    try:
        # Step 1: Create tarball
        create_source_tarball(source_dir.parent, tmp_path)
        
        # Step 2: Upload to GCS
        blob_name = f"build-sources/{source_dir.parent.name}-{os.urandom(8).hex()}.tar.gz"
        source_url = upload_source_to_gcs(bucket_name, tmp_path, blob_name)
        
        # Step 3: Submit build
        success = submit_build(project_id, image_url, source_url)
        
        sys.exit(0 if success else 1)
        
    finally:
        # Cleanup
        if tmp_path.exists():
            tmp_path.unlink()

if __name__ == "__main__":
    main()
