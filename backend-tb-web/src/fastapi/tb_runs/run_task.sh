#!/usr/bin/env bash
set -euo pipefail

: "${DEBUG:=0}"
if [[ "$DEBUG" == "1" ]]; then set -x; fi
umask 0022

on_err() {
  echo "!!! ERROR on line $1"
  echo "Working dir: $(pwd)"
  echo "--- /app:"
  ls -la /app || true
  echo "--- /app/tasks:"
  ls -la /app/tasks || true
  echo "--- /shared:"
  ls -la /shared || true
}
trap 'on_err $LINENO' ERR

echo "=== CONTAINER STARTED ==="
echo "Current directory: $(pwd)" # /app

echo "=== INSTALLING TOOLS ==="
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv pip install terminal-bench --system
echo "uv version: $(uv --version)"

echo "=== ENVIRONMENT VARIABLES ==="
echo "  TASK_NAME: ${TASK_NAME:-}"
echo "  RUN_ID: ${RUN_ID:-}"
echo "  ANTHROPIC_API_KEY set: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo yes || echo no)"

echo "=== SETTING UP TASK FILES ==="
INPUT_DIR="/shared/${RUN_ID:-}_input"
OUTPUT_DIR="/shared/${RUN_ID:-}_output"

echo "Listing /shared:"
ls -la /shared || true

mkdir -p /app/tasks
if [[ -n "$(find /app/tasks -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Detected preloaded /app/tasks; skipping copy from /shared."
else
  echo "No preloaded /app/tasks found. Checking ${INPUT_DIR}..."
  if [[ -d "${INPUT_DIR}" ]]; then
    echo "Copying from ${INPUT_DIR} -> /app/tasks"
    shopt -s nullglob dotglob
    cp -a "${INPUT_DIR}"/. /app/tasks/
  else
    if [[ -f "/app/task.zip" ]]; then
      echo "Found /app/task.zip; extracting to /app/tasks using Python"
      python - <<'PY'
import zipfile
with zipfile.ZipFile('/app/task.zip') as z: z.extractall('/app/tasks')
PY
    else
      echo "Warning: No input found in /app/tasks or ${INPUT_DIR}. Continuing anyway."
    fi
  fi
fi

echo "Files in /app/tasks:"
ls -la /app/tasks || true

rm -rf /app/runs
mkdir -p /app/runs

# Fail fast if Docker isn't available and terminal-bench requires it
if [[ -z "${DOCKER_HOST:-}" && ! -S /var/run/docker.sock ]]; then
  echo "ERROR: Docker socket not found. Mount /var/run/docker.sock into this container, or set DOCKER_HOST."
  exit 1
fi

echo "--- Starting terminal-bench ---"
uv run terminal-bench run \
  --agent terminus \
  --task-id "${TASK_NAME}" \
  --model-name anthropic/claude-4-sonnet \
  --livestream \
  --log-level debug

echo "--- terminal-bench finished ---"
echo "=== COPYING RESULTS TO SHARED OUTPUT ==="
mkdir -p "${OUTPUT_DIR}"
cp -a /app/runs/. "${OUTPUT_DIR}/" || true

LATEST_DIR="$(ls -1dt /app/runs/*/ 2>/dev/null | head -n 1 || true)"
LATEST_NAME=""
if [ -n "$LATEST_DIR" ] && [ -d "$LATEST_DIR" ]; then
  LATEST_NAME="$(basename "$LATEST_DIR")"
fi

echo -n "${LATEST_NAME}" > "${OUTPUT_DIR}/LATEST_RUN.txt"
ln -sfn "${LATEST_NAME}" "${OUTPUT_DIR}/LATEST_RUN"

export OUTPUT_DIR TASK_NAME RUN_ID
python - <<'PY'
import json, os, time
out = os.environ["OUTPUT_DIR"]
latest = ""
ptr = os.path.join(out, "LATEST_RUN.txt")
if os.path.exists(ptr):
    latest = open(ptr, "r").read().strip()
manifest = {
  "task_name": os.environ.get("TASK_NAME", ""),
  "run_id": os.environ.get("RUN_ID", ""),
  "latest_dir": latest,
  "latest_path": os.path.join(out, latest) if latest else "",
  "generated_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
}
with open(os.path.join(out, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
PY

echo "Output directory on shared: ${OUTPUT_DIR}"
ls -la "${OUTPUT_DIR}" || true
echo "=== TASK COMPLETED ==="
