FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY clean_crawl_articles.py .

# Run the cleaning script
CMD ["python", "clean_crawl_articles.py"]
