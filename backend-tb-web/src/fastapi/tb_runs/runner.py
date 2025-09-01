import docker
import os
from dotenv import load_dotenv
load_dotenv()
import asyncio
from pathlib import Path
from typing import Dict
import json
import uuid
import shutil
import zipfile
import io
import tarfile
import posixpath
from pathlib import PurePosixPath
import time
from tb_tasks.firebase.firebase_client import get_storage_client
from pydantic import BaseModel
from typing import Dict

class APIKey(BaseModel):
    ANTHROPIC_API_KEY: str
    GEMINI_API_KEY: str
    OPENAI_API_KEY: str


def tar_stream_from_zip(zip_bytes: bytes, root: str = "") -> bytes:
    """Convert ZIP bytes into a tar stream, filtering macOS metadata."""
    def skip(name: str) -> bool:
        p = PurePosixPath(name.replace("\\", "/"))
        parts = p.parts
        # ignore empty names, macOS metadata folders/files
        if not parts:
            return True
        if "__MACOSX" in parts:
            return True
        base = parts[-1]
        if base == ".DS_Store" or base.startswith("._"):
            return True
        return False

    buf = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buf, mode="w") as tar, zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for zi in zf.infolist():
            name = zi.filename
            if skip(name):
                continue
            # normalize to posix and prefix under "root/"
            norm = posixpath.join(root, name.replace("\\", "/"))
            if norm.endswith("/"):
                ti = tarfile.TarInfo(norm.rstrip("/"))
                ti.type = tarfile.DIRTYPE
                ti.mtime = now
                tar.addfile(ti)
            else:
                data = zf.read(zi)
                ti = tarfile.TarInfo(norm)
                ti.size = len(data)
                ti.mtime = now
                tar.addfile(ti, io.BytesIO(data))
    buf.seek(0)
    return buf.read()



class TerminalBenchRunner:
    def __init__(self):
        self._client = None
        self.image_name = "terminal-bench-runner"

    @property
    def client(self):
        """Lazy initialization of Docker client"""
        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Docker daemon: {e}")
        return self._client

    def build_image(self):
        """Build the Docker image"""
        try:
            dockerfile_path = Path(__file__).parent / "Dockerfile"
            self.client.images.build(
                path=str(dockerfile_path.parent),
                dockerfile=str(dockerfile_path),
                tag=self.image_name,
                rm=True
            )
        except Exception as e:
            print(f"Warning: Failed to build Docker image: {e}")
            print("Docker may not be available or accessible")

    async def run_task_streaming(
        self,
        zip_file_content: bytes,
        task_name: str,
        user_id: str,
        task_id: str,
        output_queue: asyncio.Queue
    ) -> Dict:
        run_id = str(uuid.uuid4())
        seq = 0
        container = None
        exit_code = -1

        try:
            self.client.ping()
        except Exception as e:
            raise RuntimeError(f"Docker is not available or not responding: {e}")

        def send_message(msg_type: str, content: str, is_error: bool = False):
            # ... (this function remains the same) ...
            nonlocal seq
            seq += 1
            message = {
                "type": msg_type, "content": content, "taskId": task_id,
                "runId": run_id, "seq": seq, "timestamp": __import__('time').time(),
                "isError": is_error
            }
            try:
                output_queue.put_nowait(message)
            except asyncio.QueueFull:
                print(f"DEBUG: Queue full, dropped message: {msg_type}")

        shared_volume_base = os.path.abspath(os.path.expanduser("~/task_files"))
        host_input_dir = os.path.join(shared_volume_base, f"{run_id}_input")
        host_output_dir = os.path.join(shared_volume_base, f"{run_id}_output")

        os.makedirs(host_input_dir, exist_ok=True)
        os.makedirs(host_output_dir, exist_ok=True)

        import io
        with zipfile.ZipFile(io.BytesIO(zip_file_content), 'r') as zip_ref:
            zip_ref.extractall(host_input_dir)
        print(f"DEBUG: [{run_id}] Extracted task files to '{host_input_dir}'")


        container = None
        try:
            send_message("status", f"Starting task: {task_name}")

            container = self.client.containers.create(
                image=self.image_name,
                working_dir="/app", # Start in the staging directory
                environment={
                    "TASK_NAME": task_name,
                    "RUN_ID": run_id,
                    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
                },
                volumes={
                    # host_input_dir: {'bind': container_tasks_path, 'mode': 'ro'},
                    # # Mount the empty output dir to /app/runs
                    # host_output_dir: {'bind': container_runs_path, 'mode': 'rw'}
                    'task_files': {'bind': '/shared', 'mode': 'rw'},
                    '/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'rw'}
                },
                detach=True,
            )

            tar_bytes = tar_stream_from_zip(zip_file_content, root="tasks")
            container.put_archive("/app", tar_bytes)
            container.start()


            async def pump_logs():
                def _read():
                    for chunk in container.logs(stream=True, follow=True):
                        try:
                            line = chunk.decode("utf-8", "replace")
                        except Exception:
                            line = str(chunk)
                        send_message("log", line.rstrip("\n"))
                return await asyncio.to_thread(_read)

            log_task = asyncio.create_task(pump_logs())

            # 4) Wait for completion
            result = await asyncio.to_thread(container.wait)  # non-blocking to the event loop
            exit_code = result.get("StatusCode", -1)
            send_message("status", f"Container finished with exit code {exit_code}.")

            # Ensure logs drain
            try:
                await asyncio.wait_for(log_task, timeout=5)
            except asyncio.TimeoutError:
                log_task.cancel()

            # 5) Read result pointer/manifest from the host (written by your run_task script)
            latest_ptr = os.path.join(host_output_dir, "LATEST_RUN.txt")
            manifest_path = os.path.join(host_output_dir, "manifest.json")

            latest_dir_name = ""
            if os.path.exists(latest_ptr):
                latest_dir_name = open(latest_ptr).read().strip()

            final_dir = os.path.join(host_output_dir, latest_dir_name) if latest_dir_name else None

            # Example: return paths so your API layer can post-process
            return {
                "status": "success" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "run_id": run_id,
                "output_base": host_output_dir,
                "latest_dir": final_dir,
                "manifest_path": manifest_path if os.path.exists(manifest_path) else None,
            }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            # This is the most important log for debugging silent failures
            print(f"\n\n--- UNHANDLED EXCEPTION IN TASK RUNNER [{run_id}] ---\n{error_trace}\n-------------------------------------------------\n")
            send_message("status", f"A critical error occurred: {e}", is_error=True)
            return {"status": "error", "run_id": run_id, "error": str(e)}
        finally:
            # --- 5. CLEANUP ---
            print(f"INFO: [{run_id}] Starting cleanup...")
            if container:
                # Only remove the container if it succeeded, to allow for debugging failed runs
                if exit_code == 0:
                    print(f"INFO: [{run_id}] Removing successful container...")
                    #container.remove()
                else:
                    print(f"WARNING: [{run_id}] Leaving failed container '{container.id[:12]}' for inspection.")

            # Always clean up the host directories
            if os.path.exists(host_input_dir):
                shutil.rmtree(host_input_dir)
            if os.path.exists(host_output_dir):
                shutil.rmtree(host_output_dir)
            print(f"INFO: [{run_id}] Cleanup complete.")

# Helper function to compile results
def compile_results_from_directory(directory: str) -> Dict:
    """Finds and compiles terminal-bench results from a directory into a single JSON object."""
    results = {"files": {}}
    if not os.path.isdir(directory):
        return {"error": "Results directory not found."}

    for root, _, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Store file content under its relative path
                    relative_path = os.path.relpath(file_path, directory)
                    results["files"][relative_path] = f.read()
            except Exception as e:
                results["files"][filename] = f"Error reading file: {e}"

    # Try to parse the main report.json if it exists
    report_path = os.path.join(directory, "report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r') as f:
                results["report"] = json.load(f)
        except json.JSONDecodeError:
            results["report"] = {"error": "Failed to parse report.json"}

    return results
