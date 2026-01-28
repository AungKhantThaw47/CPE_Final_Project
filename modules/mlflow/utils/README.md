# Shared Utilities

This folder contains reusable utility modules shared across all codebase containers.

## Structure

```
utils/
├── __init__.py       # Package initialization
├── gcs_utils.py      # Google Cloud Storage utilities
└── README.md         # This file
```

## Usage in Codebase Containers

### 1. Update Dockerfile

Add this line to copy the utils folder into your container:

```dockerfile
# Copy shared utils from project root
COPY ../../utils /workspace/utils
```

### 2. Import in Python code

```python
import sys
sys.path.insert(0, '/workspace')  # Add workspace to Python path

from utils.gcs_utils import save_results_to_gcs
```

## Available Utilities

### `gcs_utils.py`

**`save_results_to_gcs(results_data, confirm_save=True)`**

Save computation results to Google Cloud Storage.

**Parameters:**
- `results_data` (dict): Results data to save
- `confirm_save` (bool): If True, actually save to GCS. If False, dry-run mode.

**Returns:**
- dict: Upload status information

**Environment Variables:**
- `GCS_BUCKET`: Target GCS bucket name
- `JOB_NAME`: Job identifier for organizing files

**Example:**

```python
results = {
    "computation": "matrix_multiplication",
    "duration": 2.5,
    "result_mean": 0.123
}

# Actual save
status = save_results_to_gcs(results, confirm_save=True)

# Dry run
status = save_results_to_gcs(results, confirm_save=False)
```

## Adding New Utilities

1. Create a new `.py` file in this folder
2. Document the module with docstrings
3. Update this README
4. Import in `__init__.py` if needed for easier access
5. Update Dockerfiles that need to use the new utility
