import docker
from dotenv import load_dotenv
import tempfile
import os
import asyncio
import uuid
from pathlib import Path
from .redis import task_buffer

load_dotenv()

class TerminalBenchRunner:
    def __init__(self):
        self.client = docker.from_env()
        self.image_name = "terminal-bench-runner"

    def build_image(self):
        """Build the Docker image"""
        dockerfile_path = Path(__file__).parent / "Dockerfile"
        self.client.images.build(
            path=str(dockerfile_path.parent),
            dockerfile="Dockerfile",
            tag=self.image_name,
            rm=True
        )

    async def run_task_streaming(
        self,
        zip_file_path: str,
        task_name: str,
        user_id: str,
        task_id: str,
        output_queue: asyncio.Queue
    ) -> dict:
        """
        Run a terminal-bench task with streaming output
        """

        print(f"DEBUG: ===== run_task_streaming CALLED =====")
        print(f"DEBUG: zip_file_path: {zip_file_path}")
        print(f"DEBUG: task_name: '{task_name}'")
        print(f"DEBUG: user_id: {user_id}")
        print(f"DEBUG: task_id: {task_id}")
        run_id = str(uuid.uuid4())
        seq = 0

        def send_message(msg_type: str, content: str, is_error: bool = False, buffer: bool = True):
            nonlocal seq
            seq += 1
            message = {
                "type": msg_type,
                "content": content,
                "taskId": task_id,
                "runId": run_id,
                "seq": seq,
                "timestamp": asyncio.get_event_loop().time(),
                "isError": is_error
            }

            # Only buffer important messages to reduce Redis writes
            if buffer and should_buffer_message(msg_type, content):
                try:
                    task_buffer.append_output(task_id, run_id, message)
                except Exception as e:
                    print(f"DEBUG: Failed to store message in buffer: {e}")

            # Always send to real-time queue for live streaming
            try:
                output_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

        def should_buffer_message(msg_type: str, content: str) -> bool:
            """Determine if a message should be buffered (reduces 90% of writes)"""
            # Always buffer these important message types
            if msg_type in ["status", "error", "complete"]:
                return True

            # For output messages, filter out build noise
            if msg_type == "output":
                # Skip common build/download noise
                skip_patterns = [
                    "Downloading", "Extracting", "Installing", "Building wheels",
                    "Collecting", "Using cached", "Running setup.py",
                    "Successfully installed", "Requirement already satisfied",
                    "Step ", " ---> ", "Removing intermediate container",
                    "Successfully built", "Archive:", "inflating:", "creating:",
                    "GET https://", "200 OK", "Sending build context"
                ]

                # Don't buffer if it's noise
                for pattern in skip_patterns:
                    if pattern in content:
                        return False

                # Buffer task execution output
                return True

            return False

        temp_dir = None
        container = None

        try:
            send_message("status", f"Starting task: {task_name}")

            # Verify source file exists
            if not os.path.exists(zip_file_path):
                raise Exception(f"Source zip file does not exist: {zip_file_path}")

            file_size = os.path.getsize(zip_file_path)
            print(f"DEBUG: Source file size: {file_size} bytes")

            if file_size == 0:
                raise Exception("Source zip file is empty")

            # Create a temporary directory for building a custom image
            temp_dir = tempfile.mkdtemp(prefix="tb_build_")

            # Copy the original Dockerfile and script
            dockerfile_source = Path(__file__).parent / "Dockerfile"
            script_source = Path(__file__).parent / "run_task.sh"

            # Copy files to temp directory
            import shutil
            shutil.copy2(dockerfile_source, os.path.join(temp_dir, "Dockerfile"))
            shutil.copy2(script_source, os.path.join(temp_dir, "run_task.sh"))
            shutil.copy2(zip_file_path, os.path.join(temp_dir, "task.zip"))

            # Create a custom Dockerfile that includes the task file
            custom_dockerfile = f"""FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    git \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker CLI (not the daemon)
RUN apt-get update && apt-get install -y docker-ce-cli && rm -rf /var/lib/apt/lists/*

# Install uv and terminal-bench
RUN pip install uv
RUN uv tool install terminal-bench

# Add uv tools to PATH
ENV PATH="/root/.local/bin:${{PATH}}"

# Create necessary directories
RUN mkdir -p /app/tasks
WORKDIR /app

# Copy the script and task file
COPY run_task.sh /app/run_task.sh
COPY task.zip /app/task.zip
RUN chmod +x /app/run_task.sh

# Set environment variables
ENV TASK_ZIP_PATH=/app/task.zip
ENV TASK_NAME={task_name}
ENV ANTHROPIC_API_KEY={os.getenv('ANTHROPIC_API_KEY', '')}

ENTRYPOINT ["/app/run_task.sh"]
"""

            # Write the custom Dockerfile
            with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
                f.write(custom_dockerfile)

            send_message("status", "Building custom Docker image with task file...")

            # Build custom image with the task file included
            custom_image_name = f"tb-task-{task_id}-{run_id[:8]}"

            print(f"DEBUG: Building image {custom_image_name} from {temp_dir}")

            # Build the image
            loop = asyncio.get_event_loop()

            def build_image():
                try:
                    image, build_logs = self.client.images.build(
                        path=temp_dir,
                        tag=custom_image_name,
                        rm=True,
                        pull=False
                    )
                    return image, list(build_logs)
                except Exception as e:
                    print(f"DEBUG: Image build failed: {str(e)}")
                    raise e

            image, build_logs = await loop.run_in_executor(None, build_image)

            send_message("status", f"Image built successfully: {custom_image_name}")

            container_name = f"tb_{user_id}_{task_id}_{run_id[:8]}"

            # Run the container with the built-in task file
            container = self.client.containers.run(
                image=custom_image_name,
                name=container_name,
                environment={
                    "PYTHONUNBUFFERED": "1"
                },
                volumes = {
                    # Mount Docker socket to allow Docker-in-Docker if needed
                    "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}
                },
                labels={
                    "app": "terminal-bench",
                    "user": user_id,
                    "user_id": user_id,
                    "task": task_id,
                    "run": run_id
                },
                remove=False,
                detach=True,
                stdout=True,
                stderr=True
            )

            send_message("status", f"Container started: {container.id[:12]}")

            # Stream logs
            loop = asyncio.get_event_loop()

            def stream_and_wait():
                try:
                    execution_started = False
                    output_buffer = []

                    for log_line in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                        line = log_line.decode('utf-8').rstrip()
                        if not line:
                            continue

                        # Detect when actual task execution starts
                        if "=== RUNNING TASK ===" in line:
                            execution_started = True
                            # Send buffered important messages from build phase
                            for buffered_msg in output_buffer:
                                async def send_buffered():
                                    send_message("output", buffered_msg, buffer=True)
                                asyncio.run_coroutine_threadsafe(send_buffered(), loop)
                            output_buffer.clear()

                        # During build phase, buffer selectively
                        if not execution_started:
                            if should_buffer_message("output", line):
                                output_buffer.append(line)
                            # Still send to live stream but don't buffer noise
                            async def send_build_message():
                                send_message("output", line, buffer=False)
                            asyncio.run_coroutine_threadsafe(send_build_message(), loop)
                        else:
                            # During execution, buffer everything important
                            async def send_exec_message():
                                send_message("output", line, buffer=True)
                            asyncio.run_coroutine_threadsafe(send_exec_message(), loop)

                    # Wait for container to finish
                    result = container.wait()
                    return result['StatusCode']
                except Exception as e:
                    print(f"DEBUG: Stream error: {str(e)}")
                    return f"error: {str(e)}"

            # Run in executor
            exit_code = await loop.run_in_executor(None, stream_and_wait)

            if isinstance(exit_code, str) and exit_code.startswith("error:"):
                raise Exception(exit_code[7:])

            if exit_code == 0:
                send_message("status", "Task completed successfully")
                task_buffer.mark_task_complete(task_id, run_id, "success")
                return {
                    "status": "success",
                    "exit_code": exit_code,
                    "task_name": task_name,
                    "run_id": run_id
                }
            else:
                send_message("status", f"Task failed with exit code {exit_code}", is_error=True)
                task_buffer.force_flush(task_id, run_id)
                return {
                    "status": "failed",
                    "exit_code": exit_code,
                    "task_name": task_name,
                    "run_id": run_id,
                    "error": f"Container exited with code {exit_code}"
                }

        except Exception as e:
            send_message("status", f"Error: {str(e)}", is_error=True)
            task_buffer.mark_task_complete(task_id, run_id, "error")
            return {
                "status": "error",
                "task_name": task_name,
                "run_id": run_id,
                "error": str(e)
            }
        finally:
            # Cleanup
            if container:
                try:
                    # Clean up the container
                    # container.remove(force=True)
                    print(f"DEBUG: Container {container.id} removed")
                except Exception as cleanup_error:
                    print(f"DEBUG: Error removing container: {cleanup_error}")

            # Clean up the custom image
            try:
                if 'custom_image_name' in locals():
                    self.client.images.remove(custom_image_name, force=True)
                    print(f"DEBUG: Image {custom_image_name} removed")
            except Exception as cleanup_error:
                print(f"DEBUG: Error removing image: {cleanup_error}")

            # Clean up temp directory
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    print(f"DEBUG: Temp directory {temp_dir} removed")
                except Exception as cleanup_error:
                    print(f"DEBUG: Error removing temp dir: {cleanup_error}")


    def check_running_tasks_for_user(self, user_id:str):
        """Check if there are running tasks for a given user"""
        containers = self.client.containers.list(filters={"label": f"user={user_id}"})
        return containers
