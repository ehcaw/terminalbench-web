FROM python:alpine3.19

WORKDIR /app

# Install curl for healthchecks
RUN apk add curl

# Upgrade pip
RUN pip install --upgrade pip
RUN pip install uv

# Install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir --upgrade -r requirements.txt

# Setup a nonroot user for security
RUN adduser -D nonroot
USER nonroot

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
