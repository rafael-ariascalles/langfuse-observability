"""Celery tasks for trace processing."""

import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to Python path for Docker
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from celery import current_task
from loguru import logger

from langfuse_observability.worker.celery_app import celery_app
from langfuse_observability.shared.models import TraceRegistrationRequest
from langfuse_observability.shared.trace_registrar import TraceRegistrar


@celery_app.task(bind=True, name="process_traces")
def process_traces(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process traces asynchronously.
    
    Args:
        request_data: Dictionary containing trace registration request data
        
    Returns:
        Dictionary with processing results
    """
    job_id = self.request.id
    logger.info(f"📥 Starting trace processing for job {job_id}")
    
    try:
        # Update task state to processing
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "status": "processing",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "progress": {"current": 0, "total": len(request_data.get("traces", []))}
            }
        )
        
        # Parse request data into Pydantic model
        request = TraceRegistrationRequest(**request_data)
        
        # Create trace registrar instance
        trace_registrar = TraceRegistrar()
        
        # Process traces
        start_time = time.time()
        result = trace_registrar.register_traces(request)
        processing_time = time.time() - start_time
        
        # Add processing metadata
        result.update({
            "job_id": job_id,
            "processing_time_seconds": processing_time,
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"✅ Completed trace processing for job {job_id} in {processing_time:.2f}s")
        return result
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"❌ Error processing traces for job {job_id}: {error_msg}")
        
        # Update task state to failed
        current_task.update_state(
            state="FAILURE",
            meta={
                "job_id": job_id,
                "status": "failed",
                "error": error_msg,
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Re-raise the exception for Celery to handle retries
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(name="health_check")
def health_check() -> Dict[str, Any]:
    """Health check task for worker monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "worker": "langfuse-observability-worker"
    }