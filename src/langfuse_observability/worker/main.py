"""Worker main entry point."""

import sys
from pathlib import Path

# Add src to Python path for Docker
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from loguru import logger
from langfuse_observability.worker.celery_app import celery_app


def main():
    """Start the Celery worker."""
    logger.info("🚀 Starting Langfuse Observability Celery Worker...")
    
    # Start the worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--queues=traces",
        "--concurrency=4",
        "--max-tasks-per-child=100",
        "--time-limit=300",  # 5 minutes max per task
        "--soft-time-limit=240"  # 4 minutes soft limit
    ])


if __name__ == "__main__":
    main()