# Project Architecture Rules

## Directory Structure

### 1. Shared Utils at Root

**Rule**: All services use shared utilities from the project root `utils/` folder.

**Location**: `D:\workspace\CPE_Final_Project\utils/`

**Rationale**:
- Prevents code duplication across services
- Ensures consistent utility functions
- Simplifies maintenance and updates
- Docker images are built from root with utils included in context

**What to do**:
- ✅ Keep shared utilities in root `utils/` folder
- ✅ All Dockerfiles copy utils: `COPY utils /workspace/utils`
- ✅ Docker builds run from project root (not service directory)
- ✅ cloudbuild.yaml receives root directory as build context

---

## Build and Deployment

### 2. Infrastructure Files Don't Trigger Rebuilds

**Excluded from rebuild triggers**:
- `.build-hash*` files (legacy, no longer used but excluded defensively)
- `.dockerignore` files
- `cloudbuild.yaml` files
- `Dockerfile` files

**Rationale**: Infrastructure optimizations (Docker layer reordering, build config changes) should not trigger expensive container rebuilds. Only application code changes should rebuild images.

### 3. Docker Layer Caching

**Rule**: Dependencies must be copied and installed BEFORE application code in Dockerfiles.

**Standard Dockerfile Structure**:
```dockerfile
# 1. Base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Copy dependency files (least frequently changed)
# Build runs from root, so use full path
COPY Codebase_Container/your_service/requirements.txt .

# 4. Install dependencies (cached layer)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy shared utils from root
COPY utils /workspace/utils

# 6. Copy application code (most frequently changed)
COPY Codebase_Container/your_service/main.py .

# 6. Runtime configuration
CMD ["python", "main.py"]
```

**Rationale**: Maximizes GCP Cloud Build cache effectiveness, reducing build times by ~70% for code-only changes.

---

## Git Workflow

### 4. Deployment Hash Control

**Environment Variables**:
- `CONTENT_HASH` - SHA256 hash of codebase content
- `LOCAL_HASH` - Username of deployer for local builds
- `GITHUB_HASH` - GitHub commit SHA for CI/CD builds

**Purpose**: 
- Tracks deployment provenance in Cloud Run environment variables
- Hash comparison happens BEFORE Terraform apply (external scripts)
- Prevents unnecessary rebuilds when content hasn't changed
- Terraform does NOT independently decide on rebuilds

---

## Best Practices

1. **Keep services self-contained**: Each service manages its own code and dependencies
2. **Document changes**: Update service-specific README when adding new functionality
3. **Test before commit**: Infrastructure changes should not force rebuilds
4. **Use hash comparison scripts**: Run deployment scripts that compare hashes before applying
