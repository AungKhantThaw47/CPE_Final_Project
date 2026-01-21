# Project Structure

## Overview

Separated GPU job code from infrastructure management code.

```
CPE_Final_Project/
│
├── Infrastructure (Terraform)
│   ├── main.tf              # Cloud Run Job, APIs, IAM, GCS
│   ├── variables.tf         # Configuration variables
│   ├── outputs.tf           # Job URLs, bucket names
│   ├── provider.tf          # GCP provider config
│   └── terraform.tfvars     # Your project settings
│
├── GPU Job (Container)
│   ├── gpu-job/
│   │   ├── Dockerfile       # CUDA + Python container
│   │   ├── requirements.txt # PyTorch, GCS client
│   │   ├── main.py         # GPU workload script
│   │   └── README.md       # Job customization guide
│   │
│   └── (old folders - can be removed)
│       ├── job/            # OLD - replaced by gpu-job/
│       ├── job_requirements.txt  # OLD
│       └── Dockerfile      # OLD
│
├── Execution Scripts
│   ├── trigger_job.py      # Trigger via REST API (NO CLI)
│   ├── build.py            # Build & push Docker image
│   └── deploy.sh           # Full deployment workflow
│
├── Documentation
│   ├── README.md           # Main project documentation
│   ├── TESTING.md          # Test procedures
│   ├── FILES.md            # File descriptions
│   ├── instructions.md     # Original requirements
│   └── STRUCTURE.md        # This file
│
└── Configuration
    ├── requirements.txt     # Local dev tools (google-auth)
    ├── shell.nix           # Nix development shell
    ├── .gitignore          # Git ignore patterns
    └── terraform.tfvars.example  # Config template
```

## Key Changes

### ✅ Separated GPU Job Code

**Before:**
- Files scattered in root directory
- Dockerfile referenced `job/main.py`
- Requirements file had index URL conflict

**After:**
- All GPU job code in `gpu-job/` folder
- Self-contained with own Dockerfile and requirements
- Fixed PyTorch + PyPI package installation

### ✅ Fixed Docker Build

**Issue:** `--index-url` replaced default PyPI, blocking google-cloud-storage

**Solution:** Changed to `--extra-index-url` to support both:
- PyTorch packages from https://download.pytorch.org/whl/cu121
- Other packages from https://pypi.org

### ✅ Clean Separation of Concerns

| Folder | Purpose | Language |
|--------|---------|----------|
| `gpu-job/` | GPU workload | Python + Docker |
| Root (Terraform) | Infrastructure | HCL |
| Root (Scripts) | Automation | Python + Bash |

## File Mapping

### Old → New

```
job/main.py              → gpu-job/main.py
job_requirements.txt     → gpu-job/requirements.txt
Dockerfile               → gpu-job/Dockerfile
```

### Can Be Removed

```
rm -rf job/
rm job_requirements.txt
rm Dockerfile  # (if exists at root)
```

## Build Command

Updated `build.py` to use new structure:

```bash
docker build -t IMAGE_TAG -f gpu-job/Dockerfile .
```

The `.` context includes:
- `gpu-job/Dockerfile` (build instructions)
- `gpu-job/requirements.txt` (dependencies)
- `gpu-job/main.py` (job script)

## Deployment Workflow

1. **Infrastructure First** (one-time):
   ```bash
   terraform init
   terraform apply -target=google_artifact_registry_repository.docker_repo
   ```

2. **Build & Push Image**:
   ```bash
   python build.py
   ```

3. **Complete Infrastructure**:
   ```bash
   terraform apply
   ```

4. **Run Job**:
   ```bash
   python trigger_job.py
   ```

## Why This Structure?

### ✅ Benefits

1. **Modularity**: GPU job is self-contained
2. **Clarity**: Clear separation between infra and code
3. **Reusability**: Easy to copy `gpu-job/` to other projects
4. **Testing**: Can test GPU code independently
5. **Documentation**: Each component has its own README

### ✅ Best Practices

- GPU-specific code isolated in one folder
- Dependencies managed separately
- Docker context minimized
- Clear build path in automation scripts

## Next Steps

1. Review `gpu-job/README.md` for customization
2. Remove old folders: `job/`, `job_requirements.txt`, root `Dockerfile`
3. Run `python build.py` to test new structure
4. Deploy with `terraform apply`
