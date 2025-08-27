# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an async Langfuse Observability Service that queues Bedrock Agent traces for background processing and registration in Langfuse. The service uses Celery workers for scalable, non-blocking trace processing.

## Architecture

- **FastAPI API**: `src/langfuse_observability/api/main.py` - Lightweight API that queues jobs and provides status endpoints
- **Celery Workers**: `src/langfuse_observability/worker/` - Background workers that process traces using OpenTelemetry
- **Redis**: Message broker for Celery and job status storage
- **Shared Components**: `src/langfuse_observability/shared/` - Common models, settings, and trace processing logic
- **TraceRegistrar**: `shared/trace_registrar.py` - Handles OpenTelemetry setup and converts Bedrock traces to Langfuse spans

## Key Components

### Service Configuration (Environment Variables)
```
# Langfuse Configuration (required)
LANGFUSE_PUBLIC_KEY=<required>
LANGFUSE_SECRET_KEY=<required>
LANGFUSE_API_URL=<optional, defaults to https://us.cloud.langfuse.com>
LANGFUSE_PROJECT_NAME=<optional>
LANGFUSE_ENVIRONMENT=<optional>

# Service Configuration (optional)
LANGFUSE_HOST=<optional>
LANGFUSE_PORT=<optional>
LANGFUSE_LOG_LEVEL=<optional>

# Redis/Celery Configuration (optional)
LANGFUSE_REDIS_URL=<defaults to redis://localhost:6379/0>
LANGFUSE_CELERY_BROKER_URL=<defaults to redis://localhost:6379/0>
LANGFUSE_CELERY_RESULT_BACKEND=<defaults to redis://localhost:6379/0>
```

### Trace Processing
The service processes different types of Bedrock Agent traces:
- `orchestrationTrace`: Main LLM invocations with input/output and token usage
- `preProcessingTrace`: Pre-processing steps
- `postProcessingTrace`: Post-processing steps  
- `guardrailTrace`: Guardrail evaluations
- `failureTrace`: Error conditions

## Development Commands

### Dependencies
```bash
# Install dependencies
uv sync

# Add new dependencies
uv add <package-name>
```

### Running Services Locally
```bash
# Run API server
python src/langfuse_observability/api/main.py

# Run Celery worker
python src/langfuse_observability/worker/main.py

# Or use the legacy single-service mode
python src/langfuse_observability/main.py
```

### Docker Development
```bash
# Quick start with Makefile (uses .env file)
make run        # Start API + Worker + Redis

# With monitoring (includes Flower UI)
make monitoring # Also starts Flower at localhost:5555

# Other Makefile commands
make stop         # Stop all services
make logs         # View all logs
make logs-api     # View API logs only
make logs-worker  # View worker logs only  
make health       # Check service health
make clean        # Full cleanup
make help         # Show all commands
```

### Testing the Service
- Health check: `GET /health` (checks API, Redis, and workers)
- Service info: `GET /`
- Submit traces: `POST /register-traces` (returns job_id)
- Job status: `GET /job-status/{job_id}`
- Job result: `GET /job-result/{job_id}`
- API docs: `/docs` (Swagger UI)
- Worker monitoring: `http://localhost:5555` (Flower UI, when using `make monitoring`)

### Client Examples
- `client_example_async.py`: New async client with job polling
- `client_example.py`: Legacy synchronous client (still works with old API)
- `deployment-example.py`: For testing deployed services

## Async Client Integration

### New Workflow (Recommended)
1. **Submit job**: `POST /register-traces` → get `job_id`
2. **Poll status**: `GET /job-status/{job_id}` → check progress 
3. **Get result**: `GET /job-result/{job_id}` → final trace data

### Client Options
- **Fire-and-forget**: Submit job, don't wait for result
- **Polling**: Submit job, poll until completion
- **Blocking**: Use `client_example_async.py` with `wait_for_completion=True`

### Payload Structure (unchanged)
- `input_text`, `output_text`: The agent conversation
- `agent_id`, `agent_alias_id`, `session_id`: Agent metadata
- `traces`: Array of Bedrock Agent trace events
- Optional: `user_id`, `model_id`, `tags`, `duration_ms`

The service handles all Langfuse authentication and OpenTelemetry configuration internally via workers.