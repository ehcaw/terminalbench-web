import os
import zipfile
import tempfile
import asyncio
from datetime import datetime
from collections import defaultdict
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.requests import Request

from tb_tasks.firebase.validate_tasks import validate_directory, list_relative_files, safe_extract
from tb_tasks.firebase.firebase_admin import FirebaseUser, verify_firebase_token
from tb_tasks.firebase.firebase_client import get_storage_client
from tb_runs.runner import TerminalBenchRunner
from tb_runs.redis import check_redis_running_tasks, set_redis_running_task, redis
from pydantic import BaseModel

class RunTaskRequest(BaseModel):
    storage_path: str
    task_name: str

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
    tb_runner.build_image()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


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
    """
    import io
    import tempfile
    import uuid
    import json

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

        # NOW that we have upload_result, generate task ID and store metadata
        task_id = str(uuid.uuid4())

        # Store task metadata in Redis for lookup
        task_metadata = {
            "task_id": task_id,
            "storage_path": upload_result["storage_path"],
            "original_filename": file.filename,
            "user_id": current_user.uid,
            "uploaded_at": upload_result["uploaded_at"],
            "file_size": upload_result["file_size"],
            "validation_result": validation_result
        }

        try:
            # Store in Redis with expiration (30 days)
            task_key = f"task_metadata:{task_id}"
            redis.set(task_key, json.dumps(task_metadata))
            redis.expire(task_key, 2592000)  # 30 days

            # Also store a reverse lookup: storage_path -> task_id
            storage_key = f"storage_lookup:{current_user.uid}:{upload_result['storage_path']}"
            redis.set(storage_key, task_id)
            redis.expire(storage_key, 2592000)

            print(f"DEBUG: Stored task metadata for {task_id}")
        except Exception as redis_error:
            print(f"WARNING: Failed to store task metadata in Redis: {redis_error}")
            # Don't fail the upload if Redis fails

        # Combine validation and upload results
        result = {
            "success": True,
            "message": "Task uploaded and validated successfully",
            "task_id": task_id,  # Return the task ID
            **validation_result,
            "upload_info": {
                "storage_path": upload_result["storage_path"],
                "file_size": upload_result["file_size"],
                "uploaded_at": upload_result["uploaded_at"],
                "task_id": task_id
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
async def stream(request: Request, user_id: str, task_id: str = None, run_id: str = None, since_seq: int = 0):
    """
    Stream task output with buffering support

    Parameters:
    - user_id: User ID for the stream
    - task_id: Specific task ID (optional, for single task streaming)
    - run_id: Specific run ID (optional, for single run streaming)
    - since_seq: Get messages since this sequence number (for resuming)
    """
    from tb_runs.redis import task_buffer

    q = user_queues[user_id]

    async def gen():
        # If specific task/run requested, send buffered output first
        if task_id and run_id:
            try:
                if since_seq > 0:
                    # Get only new messages since last seen
                    buffered_messages = await task_buffer.get_output_since(task_id, run_id, since_seq)
                else:
                    # Get all buffered messages
                    buffered_messages = await task_buffer.get_full_output(task_id, run_id)

                # Send buffered messages first
                for msg in buffered_messages:
                    if await request.is_disconnected():
                        return
                    event = "task-output"
                    eid = f"{msg['taskId']}:{msg['runId']}:{msg['seq']}"
                    yield sse_format(event, msg, eid)

                # Check if task is complete
                metadata = await task_buffer.get_task_metadata(task_id, run_id)
                if metadata and metadata.get('is_complete'):
                    # Task is complete, just send buffered data and close
                    return

            except Exception as e:
                print(f"Error getting buffered output: {e}")

        # Continue with live streaming
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(q.get(), timeout=15)

                # Filter messages if specific task/run requested
                if task_id and msg.get('taskId') != task_id:
                    continue
                if run_id and msg.get('runId') != run_id:
                    continue

                event = "task-output"
                eid = f"{msg['taskId']}:{msg['runId']}:{msg['seq']}"
                yield sse_format(event, msg, eid)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


@app.get("/task-output/{task_id}/{run_id}")
async def get_task_output(task_id: str, run_id: str, since_seq: int = 0):
    """
    Get buffered task output (useful for polling or initial load)
    """
    from tb_runs.redis import task_buffer

    try:
        if since_seq > 0:
            messages = await task_buffer.get_output_since(task_id, run_id, since_seq)
        else:
            messages = await task_buffer.get_full_output(task_id, run_id)

        metadata = await task_buffer.get_task_metadata(task_id, run_id)

        return {
            "messages": messages,
            "metadata": metadata,
            "total_messages": len(messages)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task output: {str(e)}")


@app.get("/task-status/{task_id}/{run_id}")
async def get_task_status(task_id: str, run_id: str):
    """
    Get current task status and metadata
    """
    from tb_runs.redis import task_buffer

    try:
        metadata = await task_buffer.get_task_metadata(task_id, run_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Task not found")

        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task status: {str(e)}")

@app.post("/run-task-from-storage")
async def run_task_from_firebase_storage(
    request: RunTaskRequest,
    current_user: FirebaseUser = Depends(verify_firebase_token)
):
    """Run a task from a file already in Firebase Storage"""
    import uuid
    import json

    run_id = str(uuid.uuid4())  # This is the run ID
    user_id = current_user.uid

    # Try to resolve the task info
    task_id = request.task_name  # This might be a task ID or filename
    storage_path = request.storage_path
    task_name = request.task_name

    print(f"DEBUG: Initial task_id: {task_id}")
    print(f"DEBUG: Initial storage_path: {storage_path}")
    print(f"DEBUG: Initial task_name: {task_name}")

    # Clean up storage path first - remove any double .zip extensions
    if storage_path and storage_path.endswith('.zip.zip'):
        storage_path = storage_path[:-4]  # Remove the extra .zip
        print(f"DEBUG: Cleaned double .zip from storage_path: {storage_path}")

    # If task_name looks like a UUID, try to resolve it from metadata
    if len(task_id) == 36 and task_id.count('-') == 4:
        try:
            task_key = f"task_metadata:{task_id}"
            task_data = redis.get(task_key)
            if task_data:
                task_metadata = json.loads(task_data)
                if task_metadata["user_id"] == current_user.uid:
                    storage_path = task_metadata["storage_path"]
                    # Extract actual task name from the original filename (remove .zip)
                    original_filename = task_metadata["original_filename"]
                    task_name = original_filename.replace('.zip', '') if original_filename.endswith('.zip') else original_filename
                    print(f"DEBUG: Resolved from metadata - storage_path: {storage_path}, task_name: {task_name}")
                else:
                    raise HTTPException(status_code=403, detail="Access denied to this task")
            else:
                # If not found in metadata, treat as filename
                print(f"DEBUG: Task ID {task_id} not found in metadata, treating as filename")
                # Clean up task_name (remove .zip if present)
                clean_task_name = task_id.replace('.zip', '') if task_id.endswith('.zip') else task_id
                storage_path = f"tasks/{user_id}/{clean_task_name}.zip"
                task_name = clean_task_name
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid task metadata")
    else:
        # If it's not a UUID, it's probably a filename
        # Clean up task_name (remove .zip if present)
        clean_task_name = task_name.replace('.zip', '') if task_name.endswith('.zip') else task_name

        # If storage_path is provided, use it as-is (already cleaned above)
        # If not provided or empty, construct it
        if not storage_path or storage_path == "":
            storage_path = f"tasks/{user_id}/{clean_task_name}.zip"
        # Ensure storage_path ends with .zip if it doesn't already
        elif not storage_path.endswith('.zip'):
            storage_path = f"{storage_path}.zip"

        # Update task_name to not have .zip
        task_name = clean_task_name

    # Clean up storage path (remove leading slash)
    if storage_path.startswith("/"):
        storage_path = storage_path[1:]

    # Final validation - ensure storage_path ends with exactly one .zip
    if not storage_path.endswith('.zip'):
        storage_path = f"{storage_path}.zip"
    elif storage_path.endswith('.zip.zip'):
        # This should have been caught earlier, but double-check
        storage_path = storage_path[:-4]
        print(f"DEBUG: Emergency fix - removed double .zip: {storage_path}")

    print(f"DEBUG: Final storage_path: {storage_path}")
    print(f"DEBUG: Final task_name: {task_name}")

    # Validate that we don't have any obvious path issues
    if '.zip.zip' in storage_path:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid storage path detected: {storage_path}. Please contact support."
        )

    # Get or create user queue
    output_queue = user_queues[user_id]

    # Download file from Firebase Storage
    try:
        storage_client = get_storage_client()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

        def download_file():
            try:
                print(f"DEBUG: Calling storage_client.download_file with path: {storage_path}")
                content = storage_client.download_file(storage_path, temp_file.name)
                print(f"DEBUG: Successfully downloaded {len(content)} bytes")
                return temp_file.name
            except Exception as download_error:
                print(f"DEBUG: Download failed with error: {str(download_error)}")
                print(f"DEBUG: Error type: {type(download_error)}")
                # If download fails and we suspect a path issue, log more details
                if '.zip' in str(download_error).lower() or 'not found' in str(download_error).lower():
                    print(f"DEBUG: Suspected path issue. Original request data:")
                    print(f"DEBUG:   - request.storage_path: {request.storage_path}")
                    print(f"DEBUG:   - request.task_name: {request.task_name}")
                    print(f"DEBUG:   - final storage_path: {storage_path}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download file from storage path '{storage_path}': {str(download_error)}"
                )

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        temp_file_path = await loop.run_in_executor(None, download_file)
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # For unexpected errors, provide more context
        print(f"DEBUG: Unexpected error in file download setup: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while preparing file download: {str(e)}"
        )

    # Start the task in the background
    async def run_task_background():
        try:
            print(f"=== ATTEMPT {datetime.now()} ===")
            print(f"RESOLVED storage_path: '{storage_path}'")
            print(f"RESOLVED task_name: '{task_name}'")

            result = await tb_runner.run_task_streaming(
                temp_file_path,
                task_name,
                user_id,
                run_id,  # Use run_id for the execution
                output_queue
            )

            print(f"DEBUG: Task execution completed successfully: {result}")

            completion_message = {
                "type": "complete",
                "content": "Task execution finished",
                "taskId": task_id,  # Original task ID
                "runId": run_id,    # Execution run ID
                "seq": 999999,
                "timestamp": asyncio.get_event_loop().time(),
                "result": result
            }
            output_queue.put_nowait(completion_message)

        except Exception as e:
            print(f"DEBUG: Task execution failed with error: {str(e)}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")

            error_message = {
                "type": "error",
                "content": f"Task execution failed: {str(e)}",
                "taskId": task_id,
                "runId": run_id,
                "seq": 999999,
                "timestamp": asyncio.get_event_loop().time(),
                "isError": True,
                "error": str(e)
            }
            output_queue.put_nowait(error_message)

    asyncio.create_task(run_task_background())
    await set_redis_running_task(user_id, task_name, run_id)

    return {
        "status": "started",
        "task_id": task_id,
        "run_id": run_id,
        "user_id": user_id,
        "storage_path": storage_path,
        "stream_url": f"/stream?user_id={user_id}&task_id={task_id}&run_id={run_id}",
        "message": "Task started. Connect to stream endpoint to receive output."
    }



@app.get("/check-running-tasks")
async def check_running_tasks(user_id: str, task_id: str):
    response = await check_redis_running_tasks(user_id, task_id)
    return response

@app.get("/check-active-docker-runs")
def check_active_docker_runs(user_id: str):
    import docker
    client = docker.from_env()
    containers = client.containers.list(filters={"label": f"user_id={user_id}"})
    return {
        "active_runs": len(containers),
        "containers": [c.name for c in containers]
    }

@app.get("/task-info/{task_id}")
async def get_task_info(task_id: str, current_user: FirebaseUser = Depends(verify_firebase_token)):
    """Get task information by task ID"""
    import json

    try:
        task_key = f"task_metadata:{task_id}"
        task_data = redis.get(task_key)

        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")

        task_metadata = json.loads(task_data)

        # Verify user owns this task
        if task_metadata["user_id"] != current_user.uid:
            raise HTTPException(status_code=403, detail="Access denied")

        return task_metadata
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid task metadata")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task info: {str(e)}")

@app.get("/user-tasks")
async def get_user_tasks(current_user: FirebaseUser = Depends(verify_firebase_token)):
    """Get all tasks for the current user"""
    import json

    try:
        # Scan for all task metadata keys for this user
        user_tasks = []
        for key in redis.scan_iter("task_metadata:*"):
            task_data = redis.get(key)
            if task_data:
                try:
                    metadata = json.loads(task_data)
                    if metadata.get("user_id") == current_user.uid:
                        user_tasks.append(metadata)
                except json.JSONDecodeError:
                    continue

        # Sort by upload date
        user_tasks.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)

        return {
            "tasks": user_tasks,
            "count": len(user_tasks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user tasks: {str(e)}")
