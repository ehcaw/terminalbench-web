# Firebase Setup Guide

This guide will help you set up Firebase Authentication for the Task Benchmark application.

## Prerequisites

- A Google account
- Node.js and Bun installed
- Python 3.8+ for the backend

## Step 1: Create a Firebase Project

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Click "Create a project" or "Add project"
3. Enter a project name (e.g., "task-benchmark")
4. Enable Google Analytics if desired
5. Create the project

## Step 2: Enable Authentication

1. In the Firebase Console, go to "Authentication" in the left sidebar
2. Click "Get started"
3. Go to the "Sign-in method" tab
4. Enable "Google" as a sign-in provider:
   - Click on "Google"
   - Toggle "Enable"
   - Select a support email
   - Save

## Step 3: Configure Web App

1. In the Firebase Console, go to "Project settings" (gear icon)
2. Scroll down to "Your apps" section
3. Click the web icon (`</>`) to add a web app
4. Enter an app nickname (e.g., "task-benchmark-web")
5. Check "Also set up Firebase Hosting" if you plan to deploy
6. Click "Register app"
7. Copy the Firebase configuration object

## Step 4: Set Up Frontend Environment

1. In the `tb-web-frontend` directory, create a `.env.local` file:

```bash
cp .env.local.example .env.local
```

2. Fill in your Firebase configuration in `.env.local`:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key_here
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project_id.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id_here
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project_id.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id_here
NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id_here
```

## Step 5: Set Up Backend Service Account

1. In the Firebase Console, go to "Project settings" → "Service accounts"
2. Click "Generate new private key"
3. Download the JSON file
4. Choose one of these options:

### Option A: Environment Variables (Recommended)

Extract the following values from the JSON file and add them to your backend environment:

```env
FIREBASE_ADMIN_PROJECT_ID=your_project_id
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your_project_id.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
```

### Option B: Service Account File

1. Save the JSON file securely (e.g., `/path/to/service-account.json`)
2. Set the environment variable:

```env
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json
```

## Step 6: Install Dependencies

### Frontend

```bash
cd tb-web-frontend
bun install
```

### Backend

```bash
cd tb-web-backend
pip install -r requirements.txt
```

## Step 7: Configure CORS (Optional)

If your frontend and backend are on different domains, update the CORS settings in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],  # Add your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Step 8: Start the Applications

### Start Backend

```bash
cd tb-web-backend/fastapi
uvicorn main:app --reload --port 8000
```

### Start Frontend

```bash
cd tb-web-frontend
bun dev
```

## Step 9: Test Authentication

1. Open http://localhost:3000 in your browser
2. You should be redirected to the sign-in page
3. Click "Sign in with Google"
4. Complete the Google OAuth flow
5. You should be redirected back to the dashboard

## Step 10: Test File Upload

1. Navigate to http://localhost:3000/upload
2. Upload a ZIP file containing a task directory
3. Verify that the file is validated and uploaded successfully

## Security Considerations

1. **Never commit** `.env.local` or service account JSON files to version control
2. Use environment variables in production
3. Restrict Firebase project access to authorized users only
4. Enable Firebase App Check for additional security in production
5. Set up proper Firebase Security Rules if using Firestore

## Troubleshooting

### "Firebase Admin SDK not initialized"

- Check that your service account credentials are correctly set
- Verify the environment variables are loaded
- Ensure the private key has proper line breaks (`\n`)

### CORS Errors

- Update the `allow_origins` list in the FastAPI CORS middleware
- Ensure your frontend URL is included

### Authentication Redirect Issues

- Verify the `authDomain` in your Firebase config
- Check that the OAuth redirect URLs are configured in Firebase Console

### Upload Fails with 401

- Ensure the user is authenticated
- Check that the Firebase ID token is being sent in the Authorization header
- Verify the token hasn't expired (tokens expire after 1 hour)

## Additional Features

### Custom Claims

To add admin roles or other custom claims:

```python
from firebase_admin import auth

# Set admin claim
auth.set_custom_user_claims(user_uid, {'admin': True})
```

### Email Verification

To require email verification:

```python
from firebase_admin import verify_firebase_token, require_email_verified

@app.post("/admin-endpoint")
async def admin_endpoint(
    current_user: FirebaseUser = Depends(require_email_verified)
):
    # This endpoint requires verified email
    pass
```

## Production Deployment

1. Set up environment variables in your production environment
2. Use a secure secret management service for Firebase credentials
3. Enable Firebase App Check
4. Set up proper monitoring and logging
5. Configure Firebase Security Rules
6. Use HTTPS for all endpoints

For more information, see the [Firebase Documentation](https://firebase.google.com/docs).