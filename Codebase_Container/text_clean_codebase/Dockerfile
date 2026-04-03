FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH="/workspace:${PYTHONPATH}"

# Copy requirements FIRST (least frequently changed)
# This layer is cached unless requirements.txt changes
# Build context is project root, so specify full path
COPY Codebase_Container/text_clean_codebase/requirements.txt .

# Install dependencies
# Cached layer - only rebuilds if requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utils from root (build context is project root)
COPY utils /workspace/utils

# Copy application code LAST (most frequently changed)
# This ensures code changes don't invalidate dependency cache
COPY Codebase_Container/text_clean_codebase/clean_crawl_articles.py .

# Run the cleaning script
CMD ["python", "clean_crawl_articles.py"]
