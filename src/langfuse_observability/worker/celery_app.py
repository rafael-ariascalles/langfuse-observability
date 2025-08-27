"""Celery application configuration."""

import sys
from pathlib import Path

# Add src to Python path for Docker
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from celery import Celery
from langfuse_observability.shared.settings import settings

# Create Celery app
celery_app = Celery(
    "langfuse_observability_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["langfuse_observability.worker.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_track_started=settings.celery_task_track_started,
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    
    # Task routing and execution
    task_routes={
        "langfuse_observability.worker.tasks.*": {"queue": "traces"}
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # Only take one task at a time
    task_acks_late=True,  # Acknowledge task only after completion
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    
    # Retry configuration
    task_default_retry_delay=60,  # 60 seconds
    task_max_retries=3,
    
    # Result expiration
    result_expires=3600,  # 1 hour
)