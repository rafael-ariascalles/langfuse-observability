"""Shared settings configuration."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # Redis configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_task_track_started: bool = True
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: List[str] = ["json"]
    celery_timezone: str = "UTC"
    celery_enable_utc: bool = True


# Global settings instance
settings = Settings()