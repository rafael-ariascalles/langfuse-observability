"""
Configuration example for the Langfuse Observability Service.
Copy this file to config.py and update with your actual values.
"""

# Langfuse Configuration
LANGFUSE_CONFIG = {
    "public_key": "pk-lf-your-public-key-here",
    "secret_key": "sk-lf-your-secret-key-here", 
    "api_url": "https://us.cloud.langfuse.com",  # or your self-hosted URL
    "project_name": "Amazon Bedrock Agents",
    "environment": "development"  # or "production", "staging", etc.
}

# Bedrock Agent Configuration
AGENT_CONFIG = {
    "agent_id": "YOUR_AGENT_ID_HERE",
    "agent_alias_id": "YOUR_AGENT_ALIAS_ID_HERE",
    "model_id": "claude-3-5-sonnet-20241022-v2:0"  # Model used by your agent
}

# Service Configuration  
SERVICE_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "log_level": "INFO"  # DEBUG, INFO, WARNING, ERROR
}

# Default tags for all traces
DEFAULT_TAGS = [
    "bedrock-agent",
    "langfuse-observability", 
    "aws"
]