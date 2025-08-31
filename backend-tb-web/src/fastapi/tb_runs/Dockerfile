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

# Add uv tools to PATH
ENV PATH="/root/.local/bin:${PATH}"

# Create necessary directories
RUN mkdir -p /app/tasks
WORKDIR /app

# Copy the script
COPY run_task.sh /app/run_task.sh
RUN chmod +x /app/run_task.sh

ENTRYPOINT ["/app/run_task.sh"]
