#!/usr/bin/env bash

set -u

TF_BIN="${TF:-terraform}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/terraform_post_action.py"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

if ! command -v "$TF_BIN" >/dev/null 2>&1; then
  echo "terraform post-action: missing Terraform binary '$TF_BIN'" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "terraform post-action: missing required tool 'python3'" >&2
  exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
  echo "terraform post-action: missing helper script '$PYTHON_SCRIPT'" >&2
  exit 1
fi

export TF="$TF_BIN"
if [ -x "$VENV_PYTHON" ]; then
  "$VENV_PYTHON" "$PYTHON_SCRIPT"
else
  python3 "$PYTHON_SCRIPT"
fi
