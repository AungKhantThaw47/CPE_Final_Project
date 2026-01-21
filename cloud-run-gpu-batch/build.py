#!/usr/bin/env python3
"""
Docker Image Build and Push Script

Builds Docker image and pushes to Google Artifact Registry.
NO gcloud CLI required - uses docker commands only.

Usage:
    python build.py

Prerequisites:
    1. Docker installed and running
    2. Authenticated to Artifact Registry:
       docker login -u oauth2accesstoken -p "$(gcloud auth print-access-token)" \
         REGION-docker.pkg.dev

Or configure Docker credential helper:
    gcloud auth configure-docker REGION-docker.pkg.dev
"""

import os
import sys
import subprocess
import json


def run_command(cmd, check=True):
    """Execute shell command and return output."""
    print(f"\n▶️  {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    if check and result.returncode != 0:
        print(f"\n❌ Command failed with exit code {result.returncode}")
        sys.exit(1)
    
    return result


def load_terraform_outputs():
    """Load configuration from Terraform outputs."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True,
            text=True,
            check=True,
            cwd=".."  # Run in parent directory where terraform files are
        )
        outputs = json.loads(result.stdout)
        
        return {
            "project_id": outputs["project_id"]["value"],
            "region": outputs["region"]["value"],
            "docker_repository": outputs["docker_repository"]["value"],
            "docker_image_full_path": outputs["docker_image_full_path"]["value"],
        }
    except Exception as e:
        print(f"❌ Could not load terraform outputs: {e}")
        print("Make sure Terraform has been applied first.")
        sys.exit(1)


def build_image(image_tag):
    """Build Docker image."""
    print("=" * 60)
    print("BUILDING DOCKER IMAGE")
    print("=" * 60)
    
    # Change to parent directory for build context
    import os
    original_dir = os.getcwd()
    os.chdir("..")
    
    try:
        run_command([
            "docker", "build",
            "-t", image_tag,
            "--platform", "linux/amd64",
            "-f", "cloud-run-gpu-batch/gpu-job/Dockerfile",
            "cloud-run-gpu-batch"
        ])
    finally:
        os.chdir(original_dir)
    
    print(f"\n✅ Image built: {image_tag}")


def push_image(image_tag):
    """Push Docker image to Artifact Registry."""
    print("\n" + "=" * 60)
    print("PUSHING IMAGE TO ARTIFACT REGISTRY")
    print("=" * 60)
    
    run_command(["docker", "push", image_tag])
    
    print(f"\n✅ Image pushed: {image_tag}")


def main():
    """Main build and push flow."""
    print("🐳 Docker Image Build & Push")
    print()
    
    # Load configuration
    print("Loading configuration from Terraform...")
    config = load_terraform_outputs()
    
    image_tag = config["docker_image_full_path"]
    
    print(f"\nProject ID: {config['project_id']}")
    print(f"Region: {config['region']}")
    print(f"Repository: {config['docker_repository']}")
    print(f"Image Tag: {image_tag}")
    
    # Build image
    build_image(image_tag)
    
    # Push image
    push_image(image_tag)
    
    print("\n" + "=" * 60)
    print("✅ BUILD & PUSH COMPLETE")
    print("=" * 60)
    print(f"\nImage: {image_tag}")
    print("\nNext steps:")
    print("1. Run: terraform apply (to update Cloud Run Job with new image)")
    print("2. Run: python trigger_job.py (to execute the job)")


if __name__ == "__main__":
    main()
