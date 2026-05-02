FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH="/workspace:${PYTHONPATH}"

COPY Codebase_Container/crisis_admin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY utils /workspace/utils

COPY Codebase_Container/crisis_admin/admin.py .
COPY Codebase_Container/crisis_admin/templates ./templates
COPY Codebase_Container/crisis_admin/static ./static

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120", "admin:app"]
