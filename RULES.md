# Project Architecture Rules

## Directory Structure

### 1. Single Utils Folder at Root

**Rule**: Maintain only ONE `utils/` folder at the project root level.

**Location**: `D:\workspace\CPE_Final_Project\utils/`

**Rationale**:
- Prevents code duplication across multiple codebase directories
- Ensures consistent utility functions across all services and jobs
- Simplifies maintenance and updates to shared utilities
- Terraform build process copies root `utils/` to each container build context automatically

**What NOT to do**:
- ❌ Do not create `utils/` folders inside individual codebase directories:
  - ❌ `Codebase_Container/cloud_scheduler_function/utils/`
  - ❌ `Codebase_Container/crawler_job/utils/`
  - ❌ `Codebase_Container/gpu_batch_job/utils/`
  - ❌ `Codebase_Container/text_clean_codebase/utils/`
  - ❌ `modules/mlflow/utils/`

**What to do**:
- ✅ Add all shared utilities to `utils/` at project root
- ✅ Reference utilities in your code assuming they're in the build context
- ✅ Terraform handles copying `utils/` during Docker image builds

**Current Root Utils Structure**:
```
utils/
├── __init__.py
├── gcs_utils.js
├── gcs_utils.py
└── README.md
```

---

## Build and Deployment

### 2. Infrastructure Files Don't Trigger Rebuilds

**Excluded from rebuild triggers**:
- `.build-hash*` files
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
COPY requirements.txt .

# 4. Install dependencies (cached layer)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy shared utils (terraform provides during build)
COPY utils /workspace/utils

# 6. Copy application code (most frequently changed)
COPY main.py .

# 7. Runtime configuration
CMD ["python", "main.py"]
```

**Rationale**: Maximizes GCP Cloud Build cache effectiveness, reducing build times by ~70% for code-only changes.

---

## Git Workflow

### 4. Build Hash Tracking

**Dual File System**:
- `.build-hash.github` - Tracked in git, references last code commit
- `.build-hash.local` - Ignored by git, tracks local development changes

**Purpose**: 
- Prevents unnecessary rebuilds in CI when no code changes exist
- Allows local development without polluting commit history
- Terraform automatically manages these files

---

## Best Practices

1. **Keep utilities DRY**: If a function is used by multiple services, it belongs in `utils/`
2. **Document utilities**: Update `utils/README.md` when adding new functions
3. **Test before commit**: Infrastructure changes should not force rebuilds
4. **Review build hashes**: Ensure `.build-hash.github` references appropriate commits
