FROM python:3.11-slim

WORKDIR /app

COPY Codebase_Container/extractor_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Codebase_Container/extractor_job/extract.py .

CMD ["python", "extract.py"]
