# GCS Folder Rename Job

This Cloud Run Job moves objects from one GCS folder prefix to another while preserving the relative path under the folder.

## Execution Model

The job is designed for parallel execution using Cloud Run Job tasks:
- Each task reads the same source prefix.
- Each object is assigned to a task by hashing its object name.
- The job copies and deletes only the objects assigned to that task.

This keeps the operation outside the main data pipeline while allowing large folder moves to run in parallel.

## Configuration

Required environment variables:
- `SOURCE_PREFIX` or `--source`
- `DESTINATION_PREFIX` or `--destination`

Optional environment variables:
- `GCS_BUCKET` or `--bucket`
- `APPLY=true` to perform the move
- `OVERWRITE=true` to replace existing destination objects
- `TASK_COUNT` and `PARALLELISM` are controlled by Terraform/Cloud Run Job configuration

## Usage

Dry run:
```bash
python main.py --bucket my-bucket --source pending_review/old-hash/ --destination pending_review/new-hash/
```

Apply:
```bash
python main.py --bucket my-bucket --source pending_review/old-hash/ --destination pending_review/new-hash/ --apply
```
