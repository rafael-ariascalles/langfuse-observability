"""
Shared Pydantic models for the Langfuse observability service.
"""

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
