FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH="/workspace:${PYTHONPATH}"

COPY Codebase_Container/annotator_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY utils /workspace/utils

COPY Codebase_Container/annotator_job/annotate.py .

CMD ["python", "annotate.py"]
