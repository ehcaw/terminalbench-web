import os
import io
import json
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, storage
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger(__name__)


class FirebaseStorageClient:
    """
    Firebase Storage client for handling file uploads, downloads, and management.
    Designed to work with zip files containing task directories.
    """

    def __init__(self, bucket_name: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Initialize Firebase Storage client.

        Args:
            bucket_name: Firebase Storage bucket name. If None, uses default bucket.
            credentials_path: Path to Firebase service account JSON file.
                            If None, uses environment variables or GOOGLE_APPLICATION_CREDENTIALS.
        """
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self._bucket = None
        self._initialized = False

    def _ensure_initialized(self):
        """Ensure Firebase is initialized and bucket is available."""
        if self._initialized:
            return

        self._initialize_firebase(self.credentials_path)
        self._bucket = storage.bucket(self.bucket_name)
        self._initialized = True


    def _initialize_firebase(self, credentials_path: Optional[str] = None):
        """Initialize Firebase Admin SDK if not already initialized."""
        try:
            # Check if Firebase is already initialized
            app = firebase_admin.get_app()
            logger.info("Firebase Admin SDK already initialized, using existing app")
            return  # Use existing app
        except ValueError:
            # Firebase not initialized, initialize it
            logger.info("Initializing Firebase Admin SDK...")

            if credentials_path:
                logger.info(f"Using credentials file: {credentials_path}")
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
            else:
                # Try to use environment variables first
                cred = self._get_credentials_from_env()
                if cred:
                    logger.info("Using credentials from environment variables")
                    firebase_admin.initialize_app(cred)
                else:
                    # If no credentials found, raise an error - don't try default credentials
                    error_msg = (
                        "No Firebase credentials found. Please set one of:\n"
                        "1. Environment variables: FIREBASE_ADMIN_PROJECT_ID, FIREBASE_ADMIN_PRIVATE_KEY, FIREBASE_ADMIN_CLIENT_EMAIL\n"
                        "2. Pass credentials_path parameter\n"
                        "Note: Firebase may already be initialized by the auth module."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
    def _get_credentials_from_env(self) -> Optional[credentials.Certificate]:
        """
        Create Firebase credentials from environment variables.

        Required environment variables:
        - FIREBASE_PROJECT_ID
        - FIREBASE_PRIVATE_KEY
        - FIREBASE_CLIENT_EMAIL

        Returns:
            Firebase Certificate credentials or None if env vars not found
        """
        project_id = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
        private_key = os.getenv("FIREBASE_ADMIN_PRIVATE_KEY")
        client_email = os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL")

        if not all([project_id, private_key, client_email]):
            missing = []
            if not project_id:
                missing.append("FIREBASE_ADMIN_PROJECT_ID")
            if not private_key:
                missing.append("FIREBASE_ADMIN_PRIVATE_KEY")
            if not client_email:
                missing.append("FIREBASE_ADMIN_CLIENT_EMAIL")

            logger.info(f"Missing Firebase environment variables: {', '.join(missing)}")
            return None

        # Replace escaped newlines in private key
        private_key = private_key.replace("\\n", "\n")

        # Create credentials dict
        creds_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": os.getenv("FIREBASE_ADMIN_PRIVATE_KEY_ID", ""),
            "private_key": private_key,
            "client_email": client_email,
            "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }

        try:
            logger.info("Successfully created Firebase credentials from environment variables")
            return credentials.Certificate(creds_dict)
        except Exception as e:
            logger.error(f"Failed to create credentials from environment variables: {e}")
            return None

    async def upload_zip_file(
        self,
        file: UploadFile,
        user_id: str,
        task_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a zip file to Firebase Storage.

        Args:
            file: FastAPI UploadFile object (zip file)
            user_id: User ID for organizing files
            task_name: Optional task name for the file
            metadata: Optional metadata to attach to the file

        Returns:
            Dict containing upload info (file_path, download_url, etc.)
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            # Generate file path in storage
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = file.filename or f"task_{timestamp}"

            # Sanitize filename
            safe_filename = self._sanitize_filename(filename)

            # Create storage path: tasks/{user_id}/{safe_filename}.zip
            storage_path = f"tasks/{user_id}/{safe_filename}"

            # Read file content
            await file.seek(0)  # Ensure we're at the beginning
            file_content = await file.read()

            # Create blob and upload
            blob = self._bucket.blob(storage_path)

            # Set metadata
            blob_metadata = {
                "user_id": user_id,
                "uploaded_at": datetime.utcnow().isoformat(),
                "original_filename": file.filename or "unknown",
                "content_type": file.content_type or "application/zip",
                "file_size": str(len(file_content))
            }

            if task_name:
                blob_metadata["task_name"] = task_name

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Upload the file
            blob.upload_from_string(
                file_content,
                content_type=file.content_type or "application/zip"
            )

            logger.info(f"Successfully uploaded {storage_path} ({len(file_content)} bytes)")

            # Generate signed URL for download (valid for 1 hour)
            download_url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(hours=1),
                method="GET"
            )

            return {
                "success": True,
                "storage_path": storage_path,
                "download_url": download_url,
                "file_size": len(file_content),
                "uploaded_at": blob_metadata["uploaded_at"],
                "metadata": blob_metadata
            }

        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to Firebase Storage: {str(e)}"
            )

    def upload_file_from_path(
        self,
        local_file_path: str,
        storage_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file from local filesystem to Firebase Storage.

        Args:
            local_file_path: Path to local file
            storage_path: Destination path in Firebase Storage
            metadata: Optional metadata to attach

        Returns:
            Dict containing upload info
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            if not os.path.exists(local_file_path):
                raise FileNotFoundError(f"Local file not found: {local_file_path}")

            blob = self._bucket.blob(storage_path)

            # Set metadata
            blob_metadata = {
                "uploaded_at": datetime.utcnow().isoformat(),
                "original_path": local_file_path,
                "file_size": str(os.path.getsize(local_file_path))
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Upload file
            blob.upload_from_filename(local_file_path)

            logger.info(f"Successfully uploaded {local_file_path} to {storage_path}")

            return {
                "success": True,
                "storage_path": storage_path,
                "local_path": local_file_path,
                "file_size": os.path.getsize(local_file_path),
                "uploaded_at": blob_metadata["uploaded_at"]
            }

        except Exception as e:
            logger.error(f"Failed to upload file from path: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {str(e)}"
            )

    def download_file(self, storage_path: str, local_path: Optional[str] = None) -> bytes:
        """
        Download a file from Firebase Storage.

        Args:
            storage_path: Path in Firebase Storage
            local_path: Optional local path to save file

        Returns:
            File content as bytes
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            blob = self._bucket.blob(storage_path)

            if not blob.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found in storage: {storage_path}"
                )

            # Download content
            content = blob.download_as_bytes()

            # Save to local file if path provided
            if local_path:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(content)
                logger.info(f"Downloaded {storage_path} to {local_path}")

            return content

        except Exception as e:
            logger.error(f"Failed to download file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file: {str(e)}"
            )

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from Firebase Storage.

        Args:
            storage_path: Path in Firebase Storage

        Returns:
            True if deleted successfully
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            blob = self._bucket.blob(storage_path)

            if not blob.exists():
                logger.warning(f"File not found for deletion: {storage_path}")
                return False

            blob.delete()
            logger.info(f"Successfully deleted {storage_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete file: {str(e)}"
            )

    def list_user_files(self, user_id: str, prefix: str = "tasks/") -> list:
        """
        List files for a specific user.

        Args:
            user_id: User ID
            prefix: Storage path prefix

        Returns:
            List of file info dicts
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            user_prefix = f"{prefix}{user_id}/"
            blobs = self._bucket.list_blobs(prefix=user_prefix)

            files = []
            for blob in blobs:
                files.append({
                    "name": blob.name,
                    "size": blob.size,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "metadata": blob.metadata or {},
                    "content_type": blob.content_type
                })

            return files

        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list files: {str(e)}"
            )

    def get_file_info(self, storage_path: str) -> Dict[str, Any]:
        """
        Get information about a file in storage.

        Args:
            storage_path: Path in Firebase Storage

        Returns:
            Dict with file information
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            blob = self._bucket.blob(storage_path)
            blob.reload()  # Load metadata

            if not blob.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {storage_path}"
                )

            return {
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "metadata": blob.metadata or {},
                "content_type": blob.content_type,
                "etag": blob.etag,
                "generation": blob.generation
            }

        except Exception as e:
            logger.error(f"Failed to get file info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get file info: {str(e)}"
            )

    def generate_signed_url(
        self,
        storage_path: str,
        expiration_hours: int = 1,
        method: str = "GET"
    ) -> str:
        """
        Generate a signed URL for file access.

        Args:
            storage_path: Path in Firebase Storage
            expiration_hours: Hours until URL expires
            method: HTTP method (GET, PUT, etc.)

        Returns:
            Signed URL string
        """
        try:
            # Ensure Firebase is initialized
            self._ensure_initialized()

            blob = self._bucket.blob(storage_path)

            if method == "GET" and not blob.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {storage_path}"
                )

            url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(hours=expiration_hours),
                method=method
            )

            return url

        except Exception as e:
            logger.error(f"Failed to generate signed URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate signed URL: {str(e)}"
            )

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for storage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove unsafe characters
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext

        return filename


# Global client instance (optional)
_storage_client: Optional[FirebaseStorageClient] = None


def get_storage_client(
    bucket_name: Optional[str] = None,
    credentials_path: Optional[str] = None
) -> FirebaseStorageClient:
    """
    Get or create a global Firebase Storage client instance.

    Args:
        bucket_name: Firebase Storage bucket name (can also use FIREBASE_STORAGE_BUCKET env var)
        credentials_path: Path to credentials file

    Returns:
        FirebaseStorageClient instance
    """
    global _storage_client

    if _storage_client is None:
        # Use environment variable for bucket if not provided
        if not bucket_name:
            bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")

        _storage_client = FirebaseStorageClient(
            bucket_name=bucket_name,
            credentials_path=credentials_path
        )

    return _storage_client
