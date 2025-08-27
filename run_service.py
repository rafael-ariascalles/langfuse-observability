#!/usr/bin/env python3
"""
Script to run the Langfuse Observability Service with proper configuration.
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

def main():
    """Run the Langfuse Observability Service."""
    
    # Configuration from environment variables or defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"🚀 Starting Langfuse Observability Service...")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Log Level: {log_level}")
    print(f"   Reload: {reload}")
    print(f"   Access URL: http://{host}:{port}")
    print(f"   Health Check: http://{host}:{port}/health")
    print(f"   API Docs: http://{host}:{port}/docs")
    
    # Run the FastAPI application
    uvicorn.run(
        "langfuse_observability.main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=reload,
        access_log=True
    )

if __name__ == "__main__":
    main()