"""
Shared Pydantic models for the Langfuse observability service.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class TraceRegistrationRequest(BaseModel):
    """Request model for trace registration."""
    
    # Input data (what was sent to the agent)
    input_text: str = Field(..., description="The original prompt/question sent to the agent")
    agent_id: str = Field(..., description="Bedrock Agent ID")
    agent_alias_id: str = Field(..., description="Bedrock Agent Alias ID")
    session_id: str = Field(..., description="Conversation session ID")
    user_id: str = Field(default="anonymous", description="User identifier")
    model_id: Optional[str] = Field(default=None, description="Model ID used by the agent")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering in Langfuse")
    
    # Output data (what came back from the agent)
    output_text: str = Field(default="", description="The response received from the agent")
    
    # Trace data from Bedrock Agent
    traces: List[Dict[str, Any]] = Field(..., description="List of trace events from Bedrock Agent")
    
    # Optional metadata
    trace_id: Optional[str] = Field(default=None, description="Optional custom trace ID")
    streaming: bool = Field(default=False, description="Whether streaming mode was used")
    duration_ms: Optional[float] = Field(default=None, description="Total duration of the interaction")


class JobResponse(BaseModel):
    """Response model for async job submission."""
    
    job_id: str = Field(..., description="Unique job identifier for tracking")
    status: str = Field(..., description="Initial job status (typically 'pending')")
    message: str = Field(..., description="Human-readable status message")


class JobStatus(BaseModel):
    """Response model for job status queries."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status (pending, processing, success, failure)")
    created_at: datetime = Field(..., description="When the job was created")
    started_at: Optional[datetime] = Field(default=None, description="When the job started processing")
    completed_at: Optional[datetime] = Field(default=None, description="When the job completed")
    progress: Optional[Dict[str, Any]] = Field(default=None, description="Progress information if available")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Job result if completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
