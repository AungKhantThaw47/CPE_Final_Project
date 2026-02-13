# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04 AS builder

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install Python 3.11 and build dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for python and pip
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Upgrade pip and install wheel
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements file FIRST (before code changes)
# This allows Docker to cache pip install if requirements haven't changed
# Build context is project root, so specify full path
COPY Codebase_Container/gpu_batch_job/requirements.txt .

# Install Python dependencies to /install directory
# Uses --extra-index-url to support both PyPI and PyTorch repos
# This layer will only rebuild if requirements.txt changes
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================
# Stage 2: Intermediate - Additional processing
# ============================================
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04 AS intermediate

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Copy installed packages from builder
COPY --from=builder /install /install

# Add your intermediate processing here
RUN echo "Intermediate stage processing..." && \
    ls -la /install

# ============================================
# Stage 3: Runtime - Minimal final image
# ============================================
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install only Python runtime (no dev packages or build tools)
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Additional setup stage (add your commands here)
RUN echo "Python setup preparation..." && \
    python3.11 --version

# Create symbolic links for python and pip
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Copy installed packages from intermediate stage
COPY --from=intermediate /install /usr/local

# Copy shared utils from root (build context is project root)
COPY utils /workspace/utils

# Copy job script LAST
# This ensures code changes don't trigger package reinstall
COPY Codebase_Container/gpu_batch_job/main.py .

# Set environment variables for CUDA
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Add Python site-packages to path
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:$PYTHONPATH

# Run the job script (must exit after completion)
ENTRYPOINT ["python", "main.py"]
