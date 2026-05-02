FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH="/workspace:${PYTHONPATH}"

COPY Codebase_Container/events_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY utils /workspace/utils

COPY Codebase_Container/events_api/main.py .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120", "main:app"]
