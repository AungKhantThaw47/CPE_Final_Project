# Use NVIDIA CUDA base image with Python support
# This provides CUDA toolkit and cuDNN for GPU acceleration
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install Python 3.11 and required system packages
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for python and pip
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# Copy requirements file FIRST (before code changes)
# This allows Docker to cache pip install if requirements haven't changed
COPY requirements.txt .

# Install Python dependencies
# Uses --extra-index-url to support both PyPI and PyTorch repos
# This layer will only rebuild if requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utils (expected to be in build context)
# Placed AFTER pip install so code changes don't invalidate cache
COPY utils /workspace/utils

# Copy job script LAST
# This ensures code changes don't trigger pip reinstall
COPY main.py .

# Set environment variables for CUDA
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Run the job script (must exit after completion)
ENTRYPOINT ["python", "main.py"]
