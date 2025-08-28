"""
FastAPI service for registering Bedrock Agent traces in Langfuse.
Receives input data + traces and registers them using direct Langfuse SDK.
Uses structured Langfuse trace types: generation, tool, retriever, span, guardrail, event.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
import sys

# Import shared components
from .shared.models import TraceRegistrationRequest
from .shared.langfuse_registrar import create_langfuse_registrar

# Configure loguru logging
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_")
    
    # Langfuse configuration (loaded from LANGFUSE_* environment variables)
    public_key: str
    secret_key: str
    api_url: str = "https://us.cloud.langfuse.com"
    project_name: str = "Amazon Bedrock Agents"
    environment: str = "development"
    
    # Service configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

# Global settings instance
settings = Settings()

app = FastAPI(
    title="Langfuse Trace Registration Service", 
    version="2.0.0",
    description="Registers Bedrock Agent traces as structured Langfuse objects (generation, tool, retriever, etc.)"
)

# Initialize global Langfuse registrar
langfuse_registrar = None

def get_langfuse_registrar():
    """Get or create the global Langfuse registrar."""
    global langfuse_registrar
    if langfuse_registrar is None:
        langfuse_registrar = create_langfuse_registrar(settings)
    return langfuse_registrar
@app.post("/register-traces")
async def register_traces(request: TraceRegistrationRequest):
    """
    Register Bedrock Agent traces in Langfuse using structured trace types.
    
    This endpoint receives:
    - Input text (what was sent to the agent)
    - Output text (what the agent returned)
    - Agent metadata (agent ID, session, user info)
    - Trace events from Bedrock Agent
    
    And creates structured Langfuse objects:
    - generation: LLM calls with prompts, completions, and token usage
    - tool: Action groups and code interpreter calls
    - retriever: Knowledge base lookups
    - span: Pre/post processing and reasoning steps
    - guardrail: Content protection evaluations
    - event: Discrete events and failures
    """
    logger.info(f"📥 Registering structured traces for agent {request.agent_id}, session {request.session_id}")
    
    try:
        # Get Langfuse registrar
        registrar = get_langfuse_registrar()
        
        # Register traces using direct Langfuse SDK
        result = registrar.register_traces(request)
        
        logger.info(f"✅ Successfully registered {result['created_objects']} Langfuse objects "
                   f"from {result['processed_traces']} traces")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to register traces: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "langfuse-observability"}

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Langfuse Trace Registration Service",
        "version": "2.0.0",
        "description": "Registers Bedrock Agent traces as structured Langfuse objects (generation, tool, retriever, etc.)",
        "trace_types": [
            "generation - LLM calls with prompts, completions, token usage",
            "tool - Action groups and code interpreter calls", 
            "retriever - Knowledge base lookups and searches",
            "span - Pre/post processing and reasoning steps",
            "guardrail - Content protection evaluations",
            "event - Discrete events and failures"
        ],
        "endpoints": {
            "register_traces": "/register-traces",
            "health": "/health",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)