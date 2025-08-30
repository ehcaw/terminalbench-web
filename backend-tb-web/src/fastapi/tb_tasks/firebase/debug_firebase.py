#!/usr/bin/env python3
"""
Debug script to check Firebase environment variables and credentials setup.
Run this to diagnose Firebase authentication issues.
"""

import os
import sys
import json
from typing import Dict, Any

def check_env_vars() -> Dict[str, Any]:
    """Check Firebase environment variables."""
    required_vars = [
        "FIREBASE_ADMIN_PROJECT_ID",
        "FIREBASE_ADMIN_PRIVATE_KEY",
        "FIREBASE_ADMIN_CLIENT_EMAIL"
    ]

    optional_vars = [
        "FIREBASE_STORAGE_BUCKET",
        "FIREBASE_ADMIN_PRIVATE_KEY_ID",
        "FIREBASE_ADMIN_CLIENT_ID",
        "GOOGLE_APPLICATION_CREDENTIALS"
    ]

    results = {
        "required": {},
        "optional": {},
        "missing_required": [],
        "all_present": True
    }

    print("🔍 Checking Firebase Environment Variables...")
    print("=" * 50)

    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Only show first/last few chars for security
            if var == "FIREBASE_ADMIN_PRIVATE_KEY":
                display_value = f"{value[:30]}...{value[-30:]}" if len(value) > 60 else "***HIDDEN***"
            else:
                display_value = value

            results["required"][var] = True
            print(f"✅ {var}: {display_value}")
        else:
            results["required"][var] = False
            results["missing_required"].append(var)
            results["all_present"] = False
            print(f"❌ {var}: NOT SET")

    print("\nOptional variables:")
    print("-" * 20)

    # Check optional variables
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            results["optional"][var] = True
            print(f"✅ {var}: {value}")
        else:
            results["optional"][var] = False
            print(f"⚠️  {var}: NOT SET")

    return results

def validate_private_key(private_key: str) -> bool:
    """Validate private key format."""
    if not private_key:
        return False

    # Check if it starts and ends with proper markers
    starts_correct = private_key.strip().startswith("-----BEGIN PRIVATE KEY-----")
    ends_correct = private_key.strip().endswith("-----END PRIVATE KEY-----")

    return starts_correct and ends_correct

def test_firebase_initialization():
    """Test Firebase initialization with current environment."""
    print("\n🚀 Testing Firebase Initialization...")
    print("=" * 50)

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized
        try:
            app = firebase_admin.get_app()
            print("✅ Firebase Admin SDK already initialized")
            return True
        except ValueError:
            pass

        # Try to initialize with env vars
        project_id = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
        private_key = os.getenv("FIREBASE_ADMIN_PRIVATE_KEY")
        client_email = os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL")

        if all([project_id, private_key, client_email]):
            print("🔧 Attempting to initialize with environment variables...")

            # Validate private key format
            if not validate_private_key(private_key):
                print("❌ Private key format appears invalid")
                print("   Should start with '-----BEGIN PRIVATE KEY-----'")
                print("   and end with '-----END PRIVATE KEY-----'")
                return False

            # Replace escaped newlines
            private_key = private_key.replace("\\n", "\n")

            creds_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key,
                "client_email": client_email,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
            }

            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Successfully initialized Firebase with environment variables!")
            return True

        else:
            print("❌ Missing required environment variables for Firebase initialization")
            return False

    except ImportError:
        print("❌ firebase-admin package not installed")
        print("   Run: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {str(e)}")
        return False

def provide_setup_instructions(results: Dict[str, Any]):
    """Provide setup instructions based on missing variables."""
    if results["all_present"]:
        print("\n🎉 All required environment variables are set!")
        return

    print("\n📋 Setup Instructions:")
    print("=" * 50)

    print("You need to set the following environment variables:")
    print()

    for var in results["missing_required"]:
        if var == "FIREBASE_ADMIN_PROJECT_ID":
            print(f"export {var}='your-firebase-project-id'")
        elif var == "FIREBASE_ADMIN_CLIENT_EMAIL":
            print(f"export {var}='firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com'")
        elif var == "FIREBASE_ADMIN_PRIVATE_KEY":
            print(f'export {var}=\'-----BEGIN PRIVATE KEY-----\\nYOUR_PRIVATE_KEY_HERE\\n-----END PRIVATE KEY-----\'')

    print()
    print("💡 Tips:")
    print("- For Docker, add these to your docker-compose.yml environment section")
    print("- For local development, add them to your .env file")
    print("- Make sure the private key includes \\n characters for line breaks")
    print("- The private key should be enclosed in single quotes to preserve formatting")

def main():
    """Main debug function."""
    print("🔥 Firebase Debug Tool")
    print("=" * 50)

    # Check environment variables
    results = check_env_vars()

    # Test Firebase initialization
    success = test_firebase_initialization()

    # Provide instructions if needed
    if not success:
        provide_setup_instructions(results)

    print("\n" + "=" * 50)
    if success:
        print("🎉 Firebase setup looks good!")
    else:
        print("❌ Firebase setup needs attention. Follow the instructions above.")

if __name__ == "__main__":
    main()
