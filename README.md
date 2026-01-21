# CPE Final Project

## Project Structure

```
CPE_Final_Project/
│
├── Infrastructure (Root)
│   ├── main.tf                    # Terraform infrastructure
│   ├── variables.tf               # Configuration variables
│   ├── outputs.tf                 # Outputs
│   ├── provider.tf                # Provider configuration
│   ├── terraform.tfvars           # Your settings
│   ├── terraform.tfvars.example   # Template
│   ├── shell.nix                  # Nix development environment
│   └── requirements.txt           # Local dev tools
│
└── Cloud Run GPU Batch System
    └── cloud-run-gpu-batch/
        ├── gpu-job/               # GPU workload container
        │   ├── Dockerfile         # CUDA container
        │   ├── requirements.txt   # PyTorch + dependencies
        │   ├── main.py           # GPU job script
        │   └── README.md         # Customization guide
        │
        ├── trigger_job.py        # Job execution (REST API)
        ├── build.py              # Docker build & push
        ├── deploy.sh             # Full deployment
        ├── quickstart.sh         # Quick start guide
        │
        └── Documentation
            ├── README.md         # Main guide
            ├── instructions.md   # Requirements
            ├── STRUCTURE.md      # Architecture
            └── FILES.md          # File descriptions
```

## Quick Start

### ⚡ Single-Command Deployment (NEW!)

The entire project can now be built and deployed with a single command:

**Windows:**
```bash
terraform init
terraform apply
```

**Or use the provided script:**
```bash
deploy_all.bat
```

**Linux/Mac:**
```bash
./deploy_all.sh
```

This will automatically:
- ✅ Enable all required Google Cloud APIs
- ✅ Create Artifact Registry repository
- ✅ **Build your Docker image using Cloud Build**
- ✅ **Push the image to Artifact Registry**
- ✅ Create Cloud Storage bucket for outputs
- ✅ Create service accounts with proper IAM
- ✅ Deploy the Cloud Run GPU job

### Traditional Manual Deployment (Optional)

If you prefer the step-by-step approach:

#### 1. Configure Infrastructure

```bash
# Edit terraform configuration
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID
```

#### 2. Deploy Infrastructure

```bash
terraform init
terraform apply
```

#### 3. Build and Deploy GPU Job (Manual Alternative)

```bash
cd cloud-run-gpu-batch
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
python build.py
```

#### 4. Trigger Job

```bash
python trigger_job.py
```

## Components

### Infrastructure (Root Level)
- **Terraform**: Cloud Run Job, Artifact Registry, IAM, GCS bucket
- **Nix Shell**: Development environment with all tools
- **Requirements**: Local Python packages for development

### GPU Batch System (cloud-run-gpu-batch/)
- **GPU Job**: Containerized CUDA workload
- **Automation**: Build, deploy, and trigger scripts
- **Documentation**: Complete setup and usage guides

## Development

Enter development environment:
```bash
nix-shell
```

This provides:
- Terraform
- Google Cloud SDK (gcloud)
- Python 3.12
- Node.js, Go
- All required CLI tools

## Architecture

- **Compute**: Cloud Run Jobs v2 with GPU (NVIDIA L4)
- **Storage**: Google Cloud Storage for outputs
- **Container**: Docker in Artifact Registry
- **Trigger**: Python REST API (NO CLI)
- **Cost**: GPU auto-stops after job completion

## Documentation

See [cloud-run-gpu-batch/README.md](cloud-run-gpu-batch/README.md) for detailed documentation.
