"""Shared data models for the Langfuse Observability Service."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class TraceRegistrationRequest(BaseModel):
    """Request model for trace registration."""
    # Input data (what was sent to the agent)
    input_text: str
    agent_id: str
    agent_alias_id: str
    session_id: str
    user_id: str = "anonymous"
    model_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Output data (what came back from the agent)
    output_text: str = ""
    
    # Trace data from Bedrock Agent
    traces: List[Dict[str, Any]]
    
    # Optional metadata
    trace_id: Optional[str] = None
    streaming: bool = False
    duration_ms: Optional[float] = None


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str
    status: str = "pending"
    message: str = "Job queued for processing"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobStatus(BaseModel):
    """Job status model."""
    job_id: str
    status: str  # pending, processing, completed, failed
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None