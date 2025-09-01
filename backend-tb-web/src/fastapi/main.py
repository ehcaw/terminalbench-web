import os
import zipfile
from collections import defaultdict
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from tb_tasks.firebase.validate_tasks import validate_directory, list_relative_files, safe_extract
from tb_tasks.firebase.firebase_admin import FirebaseUser, verify_firebase_token
from tb_tasks.firebase.firebase_client import get_storage_client
from tb_runs.runner import TerminalBenchRunner
from fastapi.responses import StreamingResponse
from fastapi.requests import Request
import asyncio
from pydantic import BaseModel


class TaskRequest(BaseModel):
    task_name: str
    storage_path: str

app = FastAPI(title="Task Benchmark API", version="1.0.0")
tb_runner = TerminalBenchRunner()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://tb-afterquery.wache.dev"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    try:
        tb_runner.build_image()
        print("Docker image built successfully")
    except Exception as e:
        print(f"Warning: Could not build Docker image during startup: {e}")
        print("Docker functionality may be limited until Docker is available")

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/test-task")
async def test_task_execution():
    """Test endpoint to trigger task execution without auth"""
    import uuid
    import tempfile
    import os

    # Create a simple test zip file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
        import zipfile
        with zipfile.ZipFile(temp_zip.name, 'w') as zf:
            zf.writestr('test-task/task.yaml', 'name: test-task\nversion: 1.0')
            zf.writestr('test-task/run.sh', '#!/bin/bash\necho "Test task running"')

        temp_file_path = temp_zip.name

    task_id = str(uuid.uuid4())
    user_id = "test-user"
    task_name = "test-task"

    # Get or create user queue
    if user_id not in user_queues:
        user_queues[user_id] = asyncio.Queue(maxsize=1000)

    output_queue = user_queues[user_id]

    # Start the task
    async def run_test_task():
        try:
            result = await tb_runner.run_task_streaming(
                temp_file_path,
                task_name,
                user_id,
                task_id,
                output_queue
            )
            print(f"Test task result: {result}")
        except Exception as e:
            print(f"Test task error: {e}")
        finally:
            try:
                os.unlink(temp_file_path)
            except:
                pass

    asyncio.create_task(run_test_task())

    return {
        "status": "test task started",
        "task_id": task_id,
        "message": "Check logs for debug output"
    }


@app.get("/health/docker")
def docker_health_check():
    """
    Check if Docker is available and accessible.
    """
    try:
        # Try to get Docker client info
        client = tb_runner.client
        info = client.info()
        return {
            "status": "healthy",
            "docker_available": True,
            "docker_version": info.get("ServerVersion", "unknown"),
            "containers_running": info.get("ContainersRunning", 0)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "docker_available": False,
            "error": str(e),
            "message": "Docker daemon is not accessible"
        }



@app.get("/debug/firebase")
async def debug_firebase():
    """
    Debug endpoint to check Firebase configuration and status.
    """
    from tb_tasks.firebase.firebase_admin import FIREBASE_AVAILABLE, firebase_app
    import os

    env_vars = {
        "FIREBASE_ADMIN_PROJECT_ID": os.getenv("FIREBASE_ADMIN_PROJECT_ID"),
        "FIREBASE_ADMIN_CLIENT_EMAIL": bool(os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL")),
        "FIREBASE_ADMIN_PRIVATE_KEY": bool(os.getenv("FIREBASE_ADMIN_PRIVATE_KEY")),
        "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT"),
        "FIREBASE_STORAGE_BUCKET": os.getenv("FIREBASE_STORAGE_BUCKET"),
    }

    firebase_info = {}
    if firebase_app:
        firebase_info = {
            "name": firebase_app.name,
            "project_id": getattr(firebase_app, 'project_id', 'unknown')
        }

    return {
        "firebase_available": FIREBASE_AVAILABLE,
        "firebase_app_initialized": firebase_app is not None,
        "firebase_app_info": firebase_info,
        "environment_variables": env_vars,
        "message": "Check logs for detailed Firebase initialization info"
    }


@app.post("/upload-task")
async def upload_task(
    file: UploadFile = File(..., description="Zip archive of the task directory"),
    current_user: FirebaseUser = Depends(verify_firebase_token)
):
    """
    Accepts a single zip file (multipart/form-data) that contains the task directory.
    The zip file is validated in-memory and uploaded to Firebase Storage.

    Requires Firebase authentication.

    Example with curl:
      curl -X POST http://localhost:8000/upload-task \
        -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN" \
        -F "file=@/path/to/task.zip"
    """
    import io
    import tempfile

    # Log the authenticated user
    print(f"User {current_user.email} (ID: {current_user.uid}) is uploading a task")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file_type",
                "message": "File must be a zip archive",
                "user_message": "Please upload a .zip file containing your task directory."
            }
        )

    try:
        # Read the entire file content into memory
        await file.seek(0)  # Ensure we're at the beginning
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_file",
                    "message": "Uploaded file is empty",
                    "user_message": "The uploaded file appears to be empty. Please select a valid zip file."
                }
            )

        # Create a BytesIO object to work with the zip content in memory
        zip_buffer = io.BytesIO(file_content)

        # Validate it's a proper zip file and extract file list
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                # Get the list of files in the zip
                zip_file_list = zip_ref.namelist()

                # Create a temporary directory for validation
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extract to temporary directory for validation
                    safe_extract(zip_ref, temp_dir)

                    # Get relative file paths and validate
                    rel_files = list_relative_files(temp_dir)
                    validation_result = validate_directory(rel_files)

                    if not validation_result["valid"]:
                        # Format validation errors for better user experience
                        error_message = "Task validation failed"
                        user_message = "Your task directory structure is incorrect."

                        if "missing_files" in validation_result:
                            missing = validation_result["missing_files"]
                            if missing:
                                user_message += f" Missing required files: {', '.join(missing)}"

                        if "errors" in validation_result and validation_result["errors"]:
                            user_message += f" Issues found: {'; '.join(validation_result['errors'])}"

                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "validation_failed",
                                "message": error_message,
                                "user_message": user_message,
                                "validation_details": validation_result
                            }
                        )

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_zip",
                    "message": "Uploaded file is not a valid zip archive",
                    "user_message": "The uploaded file is corrupted or not a valid zip archive. Please try uploading again."
                }
            )

        # Reset file pointer for Firebase upload
        await file.seek(0)

        # Upload to Firebase Storage
        try:
            storage_client = get_storage_client()
            user_email = current_user.email if current_user.email else "unknown"
            safe_filename = os.path.basename(file.filename)

            upload_result = await storage_client.upload_zip_file(
                file,
                current_user.uid,
                safe_filename,
                {
                    "uploaded_by": user_email,
                    "validation_result": validation_result,
                    "file_count": len(rel_files)
                }
            )
        except Exception as upload_error:
            print(f"Firebase upload error: {str(upload_error)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "upload_failed",
                    "message": f"Failed to upload to storage: {str(upload_error)}",
                    "user_message": "Upload to cloud storage failed. Please try again."
                }
            )

        # Combine validation and upload results
        result = {
            "success": True,
            "message": "Task uploaded and validated successfully",
            **validation_result,
            "upload_info": {
                "storage_path": upload_result["storage_path"],
                "file_size": upload_result["file_size"],
                "uploaded_at": upload_result["uploaded_at"]
            },
            "uploaded_by": {
                "uid": current_user.uid,
                "email": current_user.email
            }
        }

        return result

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors and return 500
        print(f"Unexpected error during upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Internal server error during file processing: {str(e)}",
                "user_message": "An unexpected error occurred. Please try again or contact support."
            }
        )

user_queues: dict[str, asyncio.Queue[dict]] = defaultdict(asyncio.Queue)

def sse_format(event: str, data: dict, id_: str) -> str:
    import json
    payload = json.dumps(data)
    return f"event: {event}\nid: {id_}\ndata: {payload}\n\n"

@app.get("/stream")
async def stream(request: Request, user_id: str):
    q = user_queues[user_id]

    async def gen():
        # heartbeat to keep proxies happy
        while True:
            if await request.is_disconnected(): break
            try:
                msg = await asyncio.wait_for(q.get(), timeout=15)
                # event name can be generic or per-task:
                event = "task-output"  # or f"task-output:{msg['taskId']}"
                eid = f"{msg['taskId']}:{msg['runId']}:{msg['seq']}"
                yield sse_format(event, msg, eid)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

@app.post("/run-task-from-storage")
async def run_task_from_firebase_storage(
    request: TaskRequest,
    current_user: FirebaseUser = Depends(verify_firebase_token)
):
    """Run a task from a file already in Firebase Storage"""
    import uuid

    print(f"User {current_user.email} (ID: {current_user.uid}) is requesting to run task from storage")
    print(f"Request data: task_name={request.task_name}, storage_path={request.storage_path}")

    task_id = str(uuid.uuid4())
    user_id = current_user.uid
    storage_path = request.storage_path
    task_name = request.task_name

    # Validate inputs
    if not storage_path or not task_name:
        raise HTTPException(
            status_code=400,
            detail="Both storage_path and task_name are required"
        )

    # Get or create user queue
    output_queue = user_queues[user_id]

    # Download file from Firebase Storage
    try:
        storage_client = get_storage_client()

        # First check if file exists
        try:
            file_info = storage_client.get_file_info(storage_path)
            print(f"File found in storage: {file_info}")
        except Exception as info_error:
            print(f"File not found or error getting info: {info_error}")
            raise HTTPException(
                status_code=404,
                detail=f"File not found in storage: {storage_path}"
            )

        zip_file_content = storage_client.download_file(storage_path)
        print(f"File content downloaded to memory ({len(zip_file_content)} bytes)")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file from storage: {str(e)}"
        )

    # Start the task in the background (same logic as above)
    async def run_task_background():
        try:
            result = await tb_runner.run_task_streaming(
                zip_file_content,
                task_name,
                user_id,
                task_id,
                output_queue
            )

            completion_message = {
                "type": "complete",
                "content": f"Task execution finished",
                "taskId": task_id,
                "runId": result.get("run_id"),
                "seq": 999999,
                "timestamp": asyncio.get_event_loop().time(),
                "result": result
            }
            output_queue.put_nowait(completion_message)

        except Exception as e:
            import traceback
            print(f"\n\n--- ERROR IN BACKGROUND TASK RUNNER ---\n")
            traceback.print_exc()
            print(f"---------------------------------------\n\n")
            error_message = {
                "type": "error",
                "content": f"Task execution failed: {str(e)}",
                "taskId": task_id,
                "runId": "error",
                "seq": 999999,
                "timestamp": asyncio.get_event_loop().time(),
                "isError": True,
                "error": str(e)
            }
            output_queue.put_nowait(error_message)
        finally:
            try:
                print("Cleaning up downloaded file from memory")
            except:
                pass

    asyncio.create_task(run_task_background())

    return {
        "status": "started",
        "task_id": task_id,
        "user_id": user_id,
        "stream_url": f"/stream?user_id={user_id}",
        "message": "Task started. Connect to stream endpoint to receive output."
    }

@app.post("/tasks/start")
async def start_task_simple(
    request: dict,
    current_user: FirebaseUser = Depends(verify_firebase_token)
):
    """Simple endpoint to start a task - for testing the new logs provider"""
    import uuid

    task_id = request.get("task_id", str(uuid.uuid4()))
    run_index = request.get("run_index", 1)
    user_id = current_user.uid

    print(f"Starting task {task_id} for user {user_id}")

    # Get or create user queue
    output_queue = user_queues[user_id]

    # Create a run ID
    run_id = str(uuid.uuid4())

    # Send some test messages to the queue
    async def send_test_messages():
        import asyncio
        seq = 0

        def send_message(stream_type: str, content: str):
            nonlocal seq
            seq += 1
            message = {
                "taskId": task_id,
                "runId": run_id,
                "seq": seq,
                "stream": stream_type,
                "data": content + "\n"
            }
            try:
                output_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

        # Send initial messages
        send_message("status", "Starting task...")
        await asyncio.sleep(1)

        send_message("stdout", "Task is running...")
        await asyncio.sleep(1)

        send_message("stdout", "Processing files...")
        await asyncio.sleep(1)

        send_message("stdout", "Running tests...")
        await asyncio.sleep(2)

        send_message("stdout", "All tests passed!")
        await asyncio.sleep(1)

        send_message("status", "[done] Task completed successfully")

    # Start background task
    asyncio.create_task(send_test_messages())

    return {
        "run_id": run_id,
        "status": "started",
        "task_id": task_id,
        "user_id": user_id
    }

@app.post("/debug/start-task")
async def debug_start_task(request: dict):
    """Debug endpoint to test task streaming without authentication"""
    import uuid

    task_id = request.get("task_id", "test-task")
    user_id = request.get("user_id", "debug-user")

    print(f"DEBUG: Starting task {task_id} for user {user_id}")

    # Get or create user queue
    output_queue = user_queues[user_id]

    # Create a run ID
    run_id = str(uuid.uuid4())

    # Send some test messages to the queue
    async def send_test_messages():
        import asyncio
        seq = 0

        def send_message(stream_type: str, content: str):
            nonlocal seq
            seq += 1
            message = {
                "taskId": task_id,
                "runId": run_id,
                "seq": seq,
                "stream": stream_type,
                "data": content + "\r\n"
            }
            try:
                output_queue.put_nowait(message)
                print(f"DEBUG: Sent message {seq}: {content[:50]}...")
            except Exception as e:
                print(f"DEBUG: Failed to send message: {e}")

        # Send initial messages
        send_message("status", "Starting task...")
        await asyncio.sleep(1)

        send_message("stdout", "Task is running...")
        await asyncio.sleep(1)

        send_message("stdout", "Processing files...")
        await asyncio.sleep(1)

        send_message("stdout", "Running tests...")
        await asyncio.sleep(2)

        send_message("stdout", "All tests passed!")
        await asyncio.sleep(1)

        send_message("status", "[done] Task completed successfully")

    # Start background task
    asyncio.create_task(send_test_messages())

    return {
        "run_id": run_id,
        "status": "started",
        "task_id": task_id,
        "user_id": user_id,
        "stream_url": f"/stream?user_id={user_id}",
        "message": "Debug task started. Connect to stream endpoint to receive output."
    }
