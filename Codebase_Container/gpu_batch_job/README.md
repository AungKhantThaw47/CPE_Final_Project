# GPU Job - Containerized GPU Workload

This folder contains the GPU job code that runs inside Cloud Run Jobs.

## Structure

```
gpu-job/
├── Dockerfile          # Container definition with CUDA support
├── requirements.txt    # Python dependencies (PyTorch + GCS)
├── main.py            # GPU job script (the actual workload)
└── README.md          # This file
```

## What Runs Here

The `main.py` script:
1. Detects GPU availability (CUDA)
2. Prints GPU information
3. Executes matrix multiplication on GPU
4. Saves results to GCS bucket
5. Exits cleanly → GPU stops billing

## Dependencies

- **PyTorch 2.2.0** with CUDA 12.1 support
- **google-cloud-storage** for output storage
- **python-dateutil** for timestamp handling

## Container Image

Built from NVIDIA CUDA 12.2 runtime image with Python 3.11.

## How to Customize

### Change GPU Computation

Edit `main.py`, function `run_gpu_computation()`:

```python
def run_gpu_computation():
    device = torch.device("cuda")
    
    # Your custom GPU code here
    model = YourModel().to(device)
    result = model(data)
    
    return {"result": result.item()}
```

### Add Dependencies

Add to `requirements.txt`:

```
# Your package here
transformers==4.36.0
```

### Test Locally (with GPU)

```bash
# Build image
docker build -t gpu-job-test -f gpu-job/Dockerfile .

# Run with GPU
docker run --gpus all \
  -e GCS_BUCKET=test-bucket \
  -e JOB_NAME=test-job \
  gpu-job-test
```

## Environment Variables

Set by Cloud Run Job (see main.tf):

- `GCS_BUCKET` - Output bucket name
- `JOB_NAME` - Job identifier
- `NVIDIA_VISIBLE_DEVICES` - GPU visibility (set to "all")
- `CUDA_VISIBLE_DEVICES` - CUDA device selection

## Output Format

Results saved to GCS as JSON:

```json
{
  "device": "cuda:0",
  "matrix_size": 5000,
  "computation_time_seconds": 2.5,
  "result_shape": [5000, 5000],
  "result_mean": 0.0012,
  "result_std": 44.721,
  "timestamp": "2026-01-20T10:30:00",
  "job_name": "gpu-batch-job",
  "cuda_available": true,
  "gpu_name": "NVIDIA L4",
  "gpu_count": 1
}
```

## Logs

Stdout/stderr captured in Cloud Logging:
- GPU detection results
- Computation metrics
- GCS upload confirmation
- Exit status

## Cost Optimization

- Keep computation focused and fast
- No initialization delays
- No cleanup loops
- Exit immediately after work completes
- GPU billing stops when container exits
