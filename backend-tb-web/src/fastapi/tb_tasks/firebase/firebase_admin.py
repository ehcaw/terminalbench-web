import os
from typing import Optional, Dict, Any
import logging
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# Try to import Firebase Admin SDK
FIREBASE_AVAILABLE = False
firebase_app = None

try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth
    FIREBASE_AVAILABLE = True

    def initialize_firebase_admin():
        """Initialize Firebase Admin SDK with service account credentials."""
        if firebase_admin._apps:
            logger.info("Firebase app already exists, returning existing app")
            return firebase_admin.get_app()

        logger.info("Attempting to initialize Firebase Admin SDK...")

        try:
            # Try to use service account key file first
            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
            logger.info(f"Checking service account path: {service_account_path}")
            if service_account_path and os.path.exists(service_account_path):
                logger.info("Using service account key file")
                cred = credentials.Certificate(service_account_path)
                return firebase_admin.initialize_app(cred)

            # Try to use environment variables for service account
            project_id = os.getenv('FIREBASE_ADMIN_PROJECT_ID')
            client_email = os.getenv('FIREBASE_ADMIN_CLIENT_EMAIL')
            private_key = os.getenv('FIREBASE_ADMIN_PRIVATE_KEY')

            logger.info(f"Environment variables - Project ID: {project_id}")
            logger.info(f"Client Email: {client_email}")
            logger.info(f"Private Key length: {len(private_key) if private_key else 0}")
            logger.info(f"Private Key starts with: {private_key[:50] if private_key else 'None'}...")

            if project_id and client_email and private_key:
                logger.info("Using environment variables for service account")
                try:
                    private_key = private_key.replace('\\n', '\n')
                    service_account_info = {
                        "type": "service_account",
                        "project_id": project_id,
                        "private_key_id": os.getenv("FIREBASE_ADMIN_PRIVATE_KEY_ID", ""),
                        "private_key": private_key,
                        "client_email": client_email,
                        "client_id": os.getenv("FIREBASE_ADMIN_CLIENT_ID", ""),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
                    }
                    logger.info(f"Service account info created for project: {project_id}")
                    cred = credentials.Certificate(service_account_info)
                    logger.info("Certificate created successfully")
                    app = firebase_admin.initialize_app(cred)
                    logger.info(f"Firebase app initialized successfully: {app.name}")
                    return app
                except Exception as service_account_error:
                    logger.error(f"Failed to initialize with service account: {service_account_error}")
                    logger.error(f"Service account error type: {type(service_account_error).__name__}")

            # Try to use default credentials with explicit project ID
            project_id = os.getenv('FIREBASE_ADMIN_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
            logger.info(f"Trying default credentials with project ID: {project_id}")
            if project_id:
                logger.info("Using default credentials with explicit project ID")
                try:
                    cred = credentials.ApplicationDefault()
                    options = {'projectId': project_id}
                    app = firebase_admin.initialize_app(cred, options)
                    logger.info(f"Firebase app initialized with default credentials: {app.name}")
                    return app
                except Exception as default_cred_error:
                    logger.error(f"Failed to initialize with default credentials: {default_cred_error}")
                    logger.error(f"Default credentials error type: {type(default_cred_error).__name__}")
            else:
                logger.error("No project ID found. Set FIREBASE_ADMIN_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable.")
                return None

        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    firebase_app = initialize_firebase_admin()

except ImportError:
    logger.warning("Firebase Admin SDK not installed. Authentication will be disabled.")

# Security scheme for JWT token
security = HTTPBearer()

class FirebaseUser:
    """Represents an authenticated Firebase user."""

    def __init__(self, uid: str, email: Optional[str] = None,
                 email_verified: bool = False, claims: Optional[Dict[str, Any]] = None):
        self.uid = uid
        self.email = email
        self.email_verified = email_verified
        self.claims = claims or {}

    def __str__(self):
        return f"FirebaseUser(uid={self.uid}, email={self.email})"

async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> FirebaseUser:
    """
    Verify Firebase ID token and return user information.
    """
    logger.info(f"Firebase available: {FIREBASE_AVAILABLE}, Firebase app: {firebase_app is not None}")

    if not FIREBASE_AVAILABLE or not firebase_app:
        logger.error("Firebase authentication not available")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase authentication not available"
        )

    token = credentials.credentials
    logger.info(f"Received token (first 20 chars): {token[:20]}...")

    try:
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        email_verified = decoded_token.get('email_verified', False)

        logger.info(f"Token decoded successfully. UID: {uid}, Email: {email}")

        if not uid:
            logger.error("Token missing user ID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        return FirebaseUser(
            uid=uid,
            email=email,
            email_verified=email_verified,
            claims=decoded_token
        )

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = None) -> Optional[FirebaseUser]:
    """
    Optionally verify Firebase ID token. Returns None if no token is provided.
    """
    if not credentials or not FIREBASE_AVAILABLE or not firebase_app:
        return None

    try:
        return await verify_firebase_token(credentials)
    except HTTPException:
        return None

def require_admin_access(user: FirebaseUser = Depends(verify_firebase_token)) -> FirebaseUser:
    """
    Require admin access for the authenticated user.
    """
    if not user.claims.get('admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

def require_email_verified(user: FirebaseUser = Depends(verify_firebase_token)) -> FirebaseUser:
    """
    Require email verification for the authenticated user.
    """
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    return user
