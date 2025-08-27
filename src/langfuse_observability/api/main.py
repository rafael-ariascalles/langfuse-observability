"""
FastAPI service for queuing Bedrock Agent traces for Langfuse registration.
This service now queues trace processing jobs instead of processing them synchronously.
"""

import redis
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to Python path for Docker
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from fastapi import FastAPI, HTTPException
from loguru import logger

from langfuse_observability.shared.models import TraceRegistrationRequest, JobResponse, JobStatus
from langfuse_observability.shared.settings import settings
from langfuse_observability.worker.celery_app import celery_app

# Configure loguru logging
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

app = FastAPI(
    title="Langfuse Trace Registration Service", 
    version="2.0.0",
    description="Queues Bedrock Agent trace processing jobs for async processing"
)

# Redis client for job status tracking
redis_client = redis.from_url(settings.redis_url)


@app.post("/register-traces", response_model=JobResponse)
async def register_traces(request: TraceRegistrationRequest):
    """
    Queue trace registration job for async processing.
    
    This endpoint receives trace data and queues it for processing by Celery workers.
    Returns immediately with a job ID for status checking.
    """
    logger.info(f"📥 Queuing trace job for agent {request.agent_id}, session {request.session_id}")
    
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Queue the processing task
        task = celery_app.send_task('process_traces', args=[request.model_dump()], queue='traces')
        
        # Store job metadata in Redis
        job_metadata = {
            "job_id": task.id,
            "original_job_id": job_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "traces_count": len(request.traces)
        }
        
        # Store with expiration (24 hours)
        import json
        redis_client.setex(
            f"job:{task.id}", 
            86400,  # 24 hours
            json.dumps(job_metadata)
        )
        
        logger.info(f"✅ Queued trace processing job {task.id}")
        
        return JobResponse(
            job_id=task.id,
            status="pending",
            message=f"Trace processing job queued successfully. {len(request.traces)} traces to process."
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to queue trace processing job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


@app.get("/job-status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a trace processing job."""
    try:
        # Get job metadata from Redis
        job_data = redis_client.get(f"job:{job_id}")
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get task result from Celery
        from langfuse_observability.worker.celery_app import celery_app
        task_result = celery_app.AsyncResult(job_id)
        
        # Parse stored metadata
        import json
        metadata = json.loads(job_data) if isinstance(job_data, (str, bytes)) else job_data
        
        # Build status response
        status_response = JobStatus(
            job_id=job_id,
            status=task_result.state.lower(),
            created_at=datetime.fromisoformat(metadata["created_at"])
        )
        
        # Add task-specific information based on state
        if task_result.state == "PENDING":
            status_response.status = "pending"
        elif task_result.state == "PROCESSING":
            status_response.status = "processing"
            status_response.started_at = datetime.now(timezone.utc)
            if hasattr(task_result.info, 'get'):
                status_response.progress = task_result.info.get('progress')
        elif task_result.state == "SUCCESS":
            status_response.status = "completed"
            status_response.completed_at = datetime.now(timezone.utc)
            status_response.result = task_result.result
        elif task_result.state == "FAILURE":
            status_response.status = "failed"
            status_response.error = str(task_result.info)
        
        return status_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")


@app.get("/job-result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """Get the result of a completed trace processing job."""
    try:
        # Get task result from Celery
        from langfuse_observability.worker.celery_app import celery_app
        task_result = celery_app.AsyncResult(job_id)
        
        if task_result.state == "PENDING":
            raise HTTPException(status_code=202, detail="Job is still pending")
        elif task_result.state == "PROCESSING":
            raise HTTPException(status_code=202, detail="Job is still processing")
        elif task_result.state == "SUCCESS":
            return {
                "job_id": job_id,
                "status": "completed",
                "result": task_result.result
            }
        elif task_result.state == "FAILURE":
            raise HTTPException(
                status_code=500, 
                detail=f"Job failed: {str(task_result.info)}"
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Unknown job state: {task_result.state}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting job result: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job result: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"
    
    # Check Celery worker health
    try:
        worker_check = celery_app.send_task('health_check', queue='traces')
        worker_result = worker_check.get(timeout=5)
        worker_status = "healthy" if worker_result.get("status") == "healthy" else "unhealthy"
    except Exception:
        worker_status = "unhealthy"
    
    overall_status = "healthy" if redis_status == "healthy" and worker_status == "healthy" else "degraded"
    
    return {
        "status": overall_status,
        "service": "langfuse-observability-api",
        "components": {
            "redis": redis_status,
            "worker": worker_status
        }
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Langfuse Trace Registration Service (Async)",
        "version": "2.0.0",
        "description": "Queues Bedrock Agent trace processing for async worker processing",
        "endpoints": {
            "register_traces": "/register-traces",
            "job_status": "/job-status/{job_id}",
            "job_result": "/job-result/{job_id}",
            "health": "/health",
            "docs": "/docs"
        },
        "workflow": {
            "1": "POST /register-traces -> get job_id",
            "2": "GET /job-status/{job_id} -> check progress",
            "3": "GET /job-result/{job_id} -> get final result"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)