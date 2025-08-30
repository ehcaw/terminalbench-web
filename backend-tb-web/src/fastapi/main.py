from typing import Union

import os
import zipfile
import tempfile
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
    storage_path: str,
    task_name: str,
    current_user: FirebaseUser = Depends(verify_firebase_token)
):
    """Run a task from a file already in Firebase Storage"""

    import uuid
    task_id = str(uuid.uuid4())
    user_id = current_user.uid

    # Get or create user queue
    output_queue = user_queues[user_id]

    # Download file from Firebase Storage
    try:
        storage_client = get_storage_client()
        def download_file():
            blob = storage_client.bucket.blob(storage_path)
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {storage_path}")

            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            blob.download_to_filename(temp_file.name)
            return temp_file.name

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        temp_file_path = await loop.run_in_executor(None, download_file)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download file from storage: {str(e)}"
        )

    # Start the task in the background (same logic as above)
    async def run_task_background():
        try:
            result = await tb_runner.run_task_streaming(
                temp_file_path,
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
                os.unlink(temp_file_path)
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
