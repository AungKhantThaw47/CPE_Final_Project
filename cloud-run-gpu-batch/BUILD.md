# Building the Docker Image

Due to WSL stack smashing issues with gcloud CLI, build the image using one of these methods:

## Option 1: Python Script (Recommended)
```bash
cd cloud-run-gpu-batch
python3 build_image.py
```

## Option 2: Native Windows Command (from PowerShell)
```powershell
cd cloud-run-gpu-batch
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/gpu-job-runner:latest --project cpe-final-project .
```

## Option 3: Manual Docker Build & Push
```bash
cd cloud-run-gpu-batch
docker build --platform linux/amd64 --provenance=false -t asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/gpu-job-runner:latest -f gpu-job/Dockerfile .
docker push asia-southeast1-docker.pkg.dev/cpe-final-project/gpu-jobs/gpu-job-runner:latest
```

After building the image, run `terraform apply` to create the Cloud Run Job.
