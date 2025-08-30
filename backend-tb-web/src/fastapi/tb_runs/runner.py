# task_manager.py
# import asyncio, uuid, time
# import docker
# from collections import defaultdict

# client = docker.from_env()
# user_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)  # used by your SSE endpoint

# def start_task(image: str, cmd: list[str], user_id: str, task_id: str):
#     run_id = uuid.uuid4().hex[:8]
#     name = f"{user_id}_{task_id}_{run_id}"  # nice for 'docker ps', but don't rely on it
#     cont = client.containers.run(
#         image,
#         cmd,
#         name=name,
#         detach=True,
#         stdout=True,
#         stderr=True,
#         tty=False,
#         stdin_open=False,
#         labels={"app":"tb","user":user_id,"task":task_id,"run":run_id},
#         environment={"PYTHONUNBUFFERED":"1"},
#         # resources, volumes, network, etc. here as needed
#     )
#     return cont, run_id



# async def stream_container(cont, user_id: str, task_id: str, run_id: str):
#     """
#     Push stdout/stderr lines from this task's container into the user's SSE queue.
#     """
#     # Use low-level API for better control if you prefer:
#     # api = docker.APIClient(); logs = api.attach(cont.id, stream=True, logs=True, demux=True)
#     loop = asyncio.get_running_loop()
#     def _iter():
#         # tail=0 avoids replay; follow=True keeps streaming
#         return cont.logs(stream=True, follow=True, tail=0, stdout=True, stderr=True)
#     it = await loop.run_in_executor(None, _iter)

#     seq = 0
#     buffer = b""
#     try:
#         for chunk in it:  # this iterator blocks; that's okay in the executor thread
#             # chunk is bytes; may contain partial lines
#             buffer += chunk
#             while True:
#                 nl = buffer.find(b"\n")
#                 if nl == -1: break
#                 line, buffer = buffer[:nl+1], buffer[nl+1:]
#                 seq += 1
#                 await user_queues[user_id].put({
#                     "taskId": task_id,      # e.g., "task7"
#                     "runId": run_id,        # for multi-run panes
#                     "seq": seq,
#                     "stream": "stdout",     # if you want separate streams, use demux=True and detect stderr
#                     "data": line.decode("utf-8", "ignore"),
#                 })
#     finally:
#         # flush any remainder
#         if buffer:
#             seq += 1
#             await user_queues[user_id].put({
#                 "taskId": task_id, "runId": run_id, "seq": seq, "stream": "stdout",
#                 "data": buffer.decode("utf-8", "ignore")
#             })
#         # send a done marker
#         await user_queues[user_id].put({
#             "taskId": task_id, "runId": run_id, "seq": seq+1, "stream": "status", "data": "[done]\n"
#         })

# async def launch_10(image: str, base_cmd: list[str], user_id: str):
#     tasks = []
#     for i in range(10):
#         task_id = f"task{i+1}"
#         cmd = base_cmd[:]  # customize per task if needed
#         cont, run_id = start_task(image, cmd, user_id, task_id)
#         tasks.append(asyncio.create_task(stream_container(cont, user_id, task_id, run_id)))
#     # don't await gather here if you want this to be fire-and-forget; otherwise:
#     await asyncio.gather(*tasks)
import docker
import tempfile
import os
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Callable, AsyncGenerator
import json

class TerminalBenchRunner:
    def __init__(self):
        self.client = docker.from_env()
        self.image_name = "terminal-bench-runner"

    def build_image(self):
        """Build the Docker image"""
        dockerfile_path = Path(__file__).parent / "Dockerfile"
        self.client.images.build(
            path=str(dockerfile_path.parent),
            dockerfile=str(dockerfile_path),
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

        Args:
            zip_file_path: Path to the task zip file
            task_name: Name of the task to run
            user_id: User ID for the stream
            task_id: Unique task ID
            output_queue: Queue to send streaming output to

        Returns:
            dict: Final execution result
        """
        run_id = str(uuid.uuid4())
        seq = 0

        def send_message(msg_type: str, content: str, is_error: bool = False):
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
            try:
                output_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass  # Drop messages if queue is full

        # Create a temporary directory for mounting
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Send initial status
                send_message("status", f"Starting task: {task_name}")

                # Copy zip file to temp directory
                temp_zip_path = os.path.join(temp_dir, "task.zip")
                with open(zip_file_path, 'rb') as src, open(temp_zip_path, 'wb') as dst:
                    dst.write(src.read())

                send_message("status", "Task file prepared, starting container...")

                # Run container with streaming
                container = self.client.containers.run(
                    image=self.image_name,
                    environment={
                        "TASK_ZIP_PATH": "/app/task.zip",
                        "TASK_NAME": task_name
                    },
                    volumes={
                        temp_zip_path: {
                            'bind': '/app/task.zip',
                            'mode': 'ro'
                        }
                    },
                    remove=False,  # Don't auto-remove so we can get logs
                    detach=True,   # Run in background so we can stream
                    stdout=True,
                    stderr=True
                )

                send_message("status", f"Container started: {container.id[:12]}")

                # Stream logs in real-time
                log_stream = container.logs(stream=True, follow=True, stdout=True, stderr=True)

                for log_line in log_stream:
                    line = log_line.decode('utf-8').rstrip()
                    if line:
                        send_message("output", line)

                # Wait for container to finish
                result = container.wait()
                exit_code = result['StatusCode']

                # Get final logs if any
                final_logs = container.logs(stdout=True, stderr=True).decode('utf-8')

                # Clean up container
                container.remove()

                if exit_code == 0:
                    send_message("status", "Task completed successfully")
                    return {
                        "status": "success",
                        "exit_code": exit_code,
                        "task_name": task_name,
                        "run_id": run_id
                    }
                else:
                    send_message("status", f"Task failed with exit code {exit_code}", is_error=True)
                    return {
                        "status": "failed",
                        "exit_code": exit_code,
                        "task_name": task_name,
                        "run_id": run_id,
                        "error": f"Container exited with code {exit_code}"
                    }

            except Exception as e:
                send_message("status", f"Error: {str(e)}", is_error=True)
                return {
                    "status": "error",
                    "task_name": task_name,
                    "run_id": run_id,
                    "error": str(e)
                }
