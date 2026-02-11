FROM python:3.11-slim

WORKDIR /app

# Copy requirements FIRST (least frequently changed)
# This layer is cached unless requirements.txt changes
COPY requirements.txt .

# Install dependencies
# Cached layer - only rebuilds if requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utils (changes less frequently than app code)
# Expected to be in build context via terraform copy
COPY utils /workspace/utils

# Copy application code LAST (most frequently changed)
# This ensures code changes don't invalidate dependency cache
COPY main.py .

# Run the application
CMD ["python", "main.py"]
