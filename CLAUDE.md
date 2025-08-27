# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Langfuse Observability Service that receives Bedrock Agent traces and registers them in Langfuse for observability and analytics. The service acts as a bridge between AWS Bedrock Agents and Langfuse, using OpenTelemetry to structure and send trace data.

## Architecture

- **FastAPI Service**: `src/langfuse_observability/main.py` - Core service that receives trace registration requests
- **TraceRegistrar**: Handles OpenTelemetry setup and trace processing, converts Bedrock Agent traces into structured Langfuse spans
- **OpenTelemetry Integration**: Uses OTLP exporter to send traces to Langfuse's OpenTelemetry endpoint
- **Environment-based Configuration**: All Langfuse credentials configured via `LANGFUSE_*` environment variables

## Key Components

### Service Configuration (Environment Variables)
```
LANGFUSE_PUBLIC_KEY=<required>
LANGFUSE_SECRET_KEY=<required>
LANGFUSE_API_URL=<optional, defaults to https://us.cloud.langfuse.com>
LANGFUSE_PROJECT_NAME=<optional>
LANGFUSE_ENVIRONMENT=<optional>
LANGFUSE_HOST=<optional>
LANGFUSE_PORT=<optional>
LANGFUSE_LOG_LEVEL=<optional>
```

### Trace Processing
The service processes different types of Bedrock Agent traces:
- `orchestrationTrace`: Main LLM invocations with input/output and token usage
- `preProcessingTrace`: Pre-processing steps
- `postProcessingTrace`: Post-processing steps  
- `guardrailTrace`: Guardrail evaluations
- `failureTrace`: Error conditions

## Development Commands

### Running the Service
```bash
# Install dependencies
uv sync

# Run service directly
python src/langfuse_observability/main.py

# Run via script
python run_service.py

# With custom configuration
HOST=0.0.0.0 PORT=8080 LOG_LEVEL=debug python run_service.py
```

### Docker Development
```bash
# Quick start with Makefile (uses .env file)
make run

# Other Makefile commands
make stop    # Stop the service
make logs    # View logs
make health  # Check service health
make clean   # Full cleanup
make help    # Show all commands

# Manual Docker Compose (if needed)
docker-compose up -d
docker-compose logs -f langfuse-trace-service
docker-compose down
```

### Testing the Service
- Health check: `GET /health`
- Service info: `GET /`
- Register traces: `POST /register-traces`
- API docs: `/docs` (Swagger UI)

Use `client_example.py` for end-to-end testing with real Bedrock Agents, or `deployment-example.py` for testing with a deployed service.

## Client Integration

Clients send traces via `POST /register-traces` with this payload structure:
- `input_text`, `output_text`: The agent conversation
- `agent_id`, `agent_alias_id`, `session_id`: Agent metadata
- `traces`: Array of Bedrock Agent trace events
- Optional: `user_id`, `model_id`, `tags`, `duration_ms`

The service handles all Langfuse authentication and OpenTelemetry configuration internally.