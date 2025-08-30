FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv and terminal-bench
RUN pip install uv
RUN uv tool install terminal-bench

# Create necessary directories
RUN mkdir -p /app/tasks
WORKDIR /app

# Create the main execution script
COPY <<EOF /app/run_task.sh
#!/bin/bash
set -e

# Environment variables expected:
# - TASK_ZIP_PATH: Path to the zip file
# - TASK_NAME: Name of the task to run

echo "Starting terminal-bench runner..."
echo "Task ZIP: \${TASK_ZIP_PATH}"
echo "Task Name: \${TASK_NAME}"

# Create tasks directory in home
mkdir -p ~/tasks

# Extract zip file to ~/tasks
if [ -f "\${TASK_ZIP_PATH}" ]; then
    echo "Extracting \${TASK_ZIP_PATH} to ~/tasks/"
    cd ~/tasks
    unzip -o "\${TASK_ZIP_PATH}"
    echo "Extraction complete. Contents:"
    ls -la ~/tasks/
else
    echo "Error: ZIP file not found at \${TASK_ZIP_PATH}"
    exit 1
fi

# Run terminal-bench
if [ ! -z "\${TASK_NAME}" ]; then
    echo "Running terminal-bench with task: \${TASK_NAME}"
    cd ~/tasks
    exec terminal-bench run "\${TASK_NAME}"
else
    echo "No task name provided"
    exit 1
fi
EOF

RUN chmod +x /app/run_task.sh

ENTRYPOINT ["/app/run_task.sh"]
