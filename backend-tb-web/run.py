#!/usr/bin/env python3
"""
Backend startup script for Task Benchmark API.
This script handles environment loading and starts the FastAPI server.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def load_env():
    """Load environment variables from .env file if it exists."""
    env_file = current_dir / ".env"
    if env_file.exists():
        print(f"Loading environment from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value
    else:
        print("No .env file found, using system environment variables")

def main():
    """Main entry point."""
    load_env()

    # Configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    print(f"Starting Task Benchmark API server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log Level: {log_level}")

    # Start the server
    uvicorn.run(
        "fastapi.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        reload_dirs=[str(current_dir / "fastapi")] if reload else None,
    )

if __name__ == "__main__":
    main()
