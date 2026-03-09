FROM python:3.11-slim

WORKDIR /app

COPY Codebase_Container/extractor_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Codebase_Container/extractor_job/extract.py .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "300", "extract:app"]
