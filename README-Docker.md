# Langfuse Trace Registration Service - Docker Deployment

A containerized FastAPI service that registers Bedrock Agent traces in Langfuse. Langfuse configuration is provided via environment variables at deployment time.

## Features

- **Environment-based Configuration**: Langfuse credentials configured at deployment
- **Simple API**: Send only input + output + traces (no config in requests)
- **Docker Ready**: Pre-built container with health checks
- **Production Ready**: Uses loguru logging and pydantic-settings

## Quick Start with Docker

### 1. Set Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your Langfuse credentials
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_API_URL=https://us.cloud.langfuse.com
LANGFUSE_PROJECT_NAME=My Bedrock Project
LANGFUSE_ENVIRONMENT=production
```

### 2. Run with Docker Compose

```bash
# Build and start the service
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Test the Service

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## API Usage

### Simple Request Format

```bash
curl -X POST "http://localhost:8000/register-traces" \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "What is the weather in Seattle?",
    "output_text": "The weather in Seattle is currently cloudy with a temperature of 15°C.",
    "agent_id": "ABCD1234",
    "agent_alias_id": "ALIAS123",
    "session_id": "session-456",
    "user_id": "user789",
    "model_id": "claude-3-5-sonnet-20241022-v2:0",
    "tags": ["weather", "demo"],
    "traces": [
      {
        "trace": {
          "orchestrationTrace": {
            "modelInvocationInput": {
              "text": "What is the weather in Seattle?",
              "type": "PRE_PROCESSING",
              "traceId": "trace-123"
            }
          }
        },
        "eventTime": "2024-01-01T12:00:00Z"
      }
    ],
    "duration_ms": 1250.5
  }'
```

### Python Client

```python
import requests

# Simple registration
def register_traces(input_text, output_text, agent_id, agent_alias_id, session_id, traces):
    response = requests.post('http://localhost:8000/register-traces', json={
        "input_text": input_text,
        "output_text": output_text,
        "agent_id": agent_id,
        "agent_alias_id": agent_alias_id,
        "session_id": session_id,
        "traces": traces,
        "user_id": "current-user",
        "tags": ["bedrock-agent"]
    })
    return response.json()
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | ✅ | - | Langfuse public API key |
| `LANGFUSE_SECRET_KEY` | ✅ | - | Langfuse secret API key |
| `LANGFUSE_API_URL` | ❌ | `https://us.cloud.langfuse.com` | Langfuse API endpoint |
| `LANGFUSE_PROJECT_NAME` | ❌ | `Amazon Bedrock Agents` | Project name in Langfuse |
| `LANGFUSE_ENVIRONMENT` | ❌ | `development` | Environment tag |
| `LANGFUSE_HOST` | ❌ | `0.0.0.0` | Service bind host |
| `LANGFUSE_PORT` | ❌ | `8000` | Service port |
| `LANGFUSE_LOG_LEVEL` | ❌ | `INFO` | Log level |

## Deployment Options

### 1. Docker Compose (Recommended for Development)

```yaml
version: '3.8'
services:
  langfuse-trace-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LANGFUSE_PUBLIC_KEY=pk-lf-your-key
      - LANGFUSE_SECRET_KEY=sk-lf-your-key
      - LANGFUSE_API_URL=https://us.cloud.langfuse.com
      - LANGFUSE_ENVIRONMENT=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### 2. Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langfuse-trace-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: langfuse-trace-service
  template:
    metadata:
      labels:
        app: langfuse-trace-service
    spec:
      containers:
      - name: langfuse-trace-service
        image: langfuse-trace-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: LANGFUSE_PUBLIC_KEY
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: public-key
        - name: LANGFUSE_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: secret-key
        - name: LANGFUSE_API_URL
          value: "https://us.cloud.langfuse.com"
        - name: LANGFUSE_ENVIRONMENT
          value: "production"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: langfuse-trace-service
spec:
  selector:
    app: langfuse-trace-service
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

### 3. AWS ECS

```json
{
  "family": "langfuse-trace-service",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskRole",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "langfuse-trace-service",
      "image": "YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/langfuse-trace-service:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LANGFUSE_API_URL",
          "value": "https://us.cloud.langfuse.com"
        },
        {
          "name": "LANGFUSE_ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "LANGFUSE_PUBLIC_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT:secret:langfuse/public-key"
        },
        {
          "name": "LANGFUSE_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT:secret:langfuse/secret-key"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/langfuse-trace-service",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

## Integration Examples

### With Existing Bedrock Agent Code

```python
# Your existing function
def invoke_bedrock_agent(input_text, agent_id, agent_alias_id, session_id):
    # Your existing Bedrock invocation
    bedrock_client = boto3.client('bedrock-agent-runtime')
    response = bedrock_client.invoke_agent(
        inputText=input_text,
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        enableTrace=True
    )
    
    # Extract output and traces
    output_text = ""
    traces = []
    for event in response['completion']:
        if 'chunk' in event:
            output_text += event['chunk']['bytes'].decode('utf-8')
        elif 'trace' in event:
            traces.append(event['trace'])
    
    # ADD THIS: Register traces in Langfuse
    try:
        requests.post('http://langfuse-service:8000/register-traces', json={
            "input_text": input_text,
            "output_text": output_text,
            "agent_id": agent_id,
            "agent_alias_id": agent_alias_id,
            "session_id": session_id,
            "traces": traces,
            "user_id": "current-user"
        }, timeout=30)
    except Exception as e:
        print(f"Warning: Failed to register traces: {e}")
    
    return output_text
```

### Lambda Function Integration

```python
import json
import boto3
import requests
import os

def lambda_handler(event, context):
    # Extract parameters
    input_text = event['input_text']
    agent_id = event['agent_id']
    agent_alias_id = event['agent_alias_id']
    session_id = event.get('session_id', context.aws_request_id)
    
    # Invoke Bedrock Agent
    bedrock_client = boto3.client('bedrock-agent-runtime')
    response = bedrock_client.invoke_agent(
        inputText=input_text,
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        enableTrace=True
    )
    
    # Extract data
    output_text = ""
    traces = []
    for event in response['completion']:
        if 'chunk' in event:
            output_text += event['chunk']['bytes'].decode('utf-8')
        elif 'trace' in event:
            traces.append(event['trace'])
    
    # Register traces (async/background)
    trace_service_url = os.environ['TRACE_SERVICE_URL']
    try:
        requests.post(f'{trace_service_url}/register-traces', 
                     json={
                         "input_text": input_text,
                         "output_text": output_text,
                         "agent_id": agent_id,
                         "agent_alias_id": agent_alias_id,
                         "session_id": session_id,
                         "traces": traces,
                         "user_id": event.get('user_id', 'lambda-user')
                     }, timeout=10)
    except:
        pass  # Don't fail Lambda if trace registration fails
    
    return {
        'statusCode': 200,
        'body': json.dumps({'response': output_text})
    }
```

## Monitoring and Troubleshooting

### Health Check

```bash
curl http://localhost:8000/health
# Response: {"status": "healthy", "service": "langfuse-observability"}
```

### Logs

```bash
# View service logs
docker-compose logs -f langfuse-trace-service

# Example log output:
2024-01-01 12:00:00 | INFO | ✅ Tracer provider configured for Langfuse at https://us.cloud.langfuse.com
2024-01-01 12:01:30 | INFO | 📥 Registering traces for agent ABCD1234, session session-123
2024-01-01 12:01:31 | INFO | ✅ Successfully registered 3 traces
```

### Common Issues

1. **Service won't start**: Check environment variables
2. **Traces not appearing**: Verify Langfuse credentials and API URL
3. **High latency**: Consider adjusting batch processor settings
4. **Connection errors**: Check network connectivity to Langfuse

### Build and Push to Registry

```bash
# Build image
docker build -t langfuse-trace-service:latest .

# Tag for registry
docker tag langfuse-trace-service:latest YOUR_REGISTRY/langfuse-trace-service:latest

# Push
docker push YOUR_REGISTRY/langfuse-trace-service:latest
```

## Production Considerations

1. **Resource Limits**: Set appropriate CPU/memory limits
2. **Health Checks**: Use the `/health` endpoint for orchestrator health checks
3. **Secrets Management**: Use proper secret management (AWS Secrets Manager, K8s Secrets, etc.)
4. **Monitoring**: Monitor service metrics and Langfuse ingestion
5. **Scaling**: Service is stateless and can be horizontally scaled
6. **Security**: Run as non-root user (already configured in Dockerfile)

This service provides a clean separation between your application logic and observability concerns, making it easy to add trace registration to existing Bedrock Agent applications.