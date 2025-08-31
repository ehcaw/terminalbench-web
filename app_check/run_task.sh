#!/bin/bash
set -e

echo "=== CONTAINER STARTED ==="
echo "Current time: $(date)"
echo "Current user: $(whoami)"
echo "Current directory: $(pwd)"
echo "Environment variables:"
echo "  TASK_ZIP_PATH: ${TASK_ZIP_PATH}"
echo "  TASK_NAME: ${TASK_NAME}"
echo "  PATH: ${PATH}"

echo "=== CHECKING TERMINAL-BENCH ==="
if command -v tb &> /dev/null; then
    echo "✓ terminal-bench found at: $(which tb)"
    echo "terminal-bench version: $(tb --version 2>&1 || echo 'version check failed')"
else
    echo "✗ terminal-bench not found in PATH"
fi

echo "=== PROCESSING TASK FILE ==="
mkdir -p /app/tasks

if [ -f "${TASK_ZIP_PATH}" ]; then
    echo "✓ ZIP file found at ${TASK_ZIP_PATH}"
    echo "ZIP file size: $(ls -lh ${TASK_ZIP_PATH} | awk '{print $5}')"

    cd /app/tasks
    echo "Extracting to $(pwd)..."
    unzip -o "${TASK_ZIP_PATH}"

    echo "=== EXTRACTED CONTENTS ==="
    ls -la /app/tasks/

    if [ ! -z "${TASK_NAME}" ]; then
        if [ -d "${TASK_NAME}" ]; then
            echo "✓ Task directory '${TASK_NAME}' found"
            echo "Task directory contents:"
            ls -la "${TASK_NAME}/"
        else
            echo "✗ Task directory '${TASK_NAME}' not found"
        fi
    fi
else
    echo "✗ ZIP file not found at ${TASK_ZIP_PATH}"
    exit 1
fi

if [ ! -z "${TASK_NAME}" ]; then
    if [ -d "${TASK_NAME}" ]; then
        echo "✓ Task directory '${TASK_NAME}' found"
        echo "Task directory contents:"
        ls -la "${TASK_NAME}/"
    else
        echo "✗ Task directory '${TASK_NAME}' not found"
        echo "Looking for the actual task directory..."
        # Find the first directory that's not __MACOSX
        ACTUAL_TASK_DIR=$(find . -maxdepth 1 -type d ! -name "." ! -name "__MACOSX*" | head -1 | sed 's|./||')

        if [ ! -z "${ACTUAL_TASK_DIR}" ]; then
            echo "✓ Found actual task directory: '${ACTUAL_TASK_DIR}'"
            TASK_NAME="${ACTUAL_TASK_DIR}"
            echo "Task directory contents:"
            ls -la "${TASK_NAME}/"
        else
            echo "✗ No valid task directory found"
            exit 1
        fi
    fi
fi

echo "=== READY TO RUN TASK ==="
exec uv run tb run --agent terminus --model-name anthropic/claude-4-sonnet-latest --livestream

# Sleep a bit so you can see it in docker ps
sleep 5
