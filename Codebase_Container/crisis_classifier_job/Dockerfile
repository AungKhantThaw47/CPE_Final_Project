FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH="/workspace:${PYTHONPATH}"

# Install torch CPU first (separate step to use smaller CPU-only version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install other requirements
COPY Codebase_Container/crisis_classifier_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the pre-trained Gemma model (1.2GB - copied last to avoid cache invalidation)
COPY Codebase_Container/crisis_classifier_job/crisis_model.pkl .

# Copy shared utils from root (build context is project root)
COPY utils /workspace/utils

# Copy application code
COPY Codebase_Container/crisis_classifier_job/classify_articles.py .

# Run as a batch job
CMD ["python", "classify_articles.py"]