FROM python:3.11-slim

WORKDIR /app

COPY Codebase_Container/annotator_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Codebase_Container/annotator_job/annotate.py .

CMD ["python", "annotate.py"]
