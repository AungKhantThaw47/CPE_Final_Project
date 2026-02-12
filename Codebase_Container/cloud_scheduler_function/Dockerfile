FROM python:3.11-slim

WORKDIR /app

# Copy requirements FIRST (least frequently changed)
# This layer is cached unless requirements.txt changes
# Build context is project root, so specify full path
COPY Codebase_Container/cloud_scheduler_function/requirements.txt .

# Install dependencies
# Cached layer - only rebuilds if requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utils from root (build context is project root)
COPY utils /workspace/utils

# Copy application code LAST (most frequently changed)
# This ensures code changes don't invalidate dependency cache
COPY Codebase_Container/cloud_scheduler_function/main.py .

# Run the application
CMD ["python", "main.py"]
