FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI and curl for healthchecks
RUN apt-get update && apt-get install -y curl docker.io && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip
RUN pip install uv

# Install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir --upgrade -r requirements.txt

# Setup a nonroot user for security and Docker access
RUN adduser --disabled-password --gecos '' nonroot
RUN usermod -aG docker nonroot
# USER nonroot

# Copy the app
COPY main.py /app/main.py
COPY tb_benches /app/tb_benches
COPY tb_runs /app/tb_runs
COPY tb_tasks /app/tb_tasks

# Expose the app's port
EXPOSE 8000

# Run the FastAPI server
ENTRYPOINT ["python", "-m"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
