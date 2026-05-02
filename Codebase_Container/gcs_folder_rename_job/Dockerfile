FROM python:3.11-slim

WORKDIR /app

COPY Codebase_Container/gcs_folder_rename_job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Codebase_Container/gcs_folder_rename_job/main.py .

CMD ["python", "main.py"]
