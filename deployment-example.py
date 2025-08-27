"""
Example showing how to use the dockerized Langfuse trace registration service.
This client sends input + output + traces to the service without any Langfuse configuration.
"""

import json
import boto3
import requests
import time
from datetime import datetime
from typing import List, Dict, Any

def register_traces_simple(
    # Input/Output data 
    input_text: str,
    output_text: str,
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    
    # Trace data
    traces: List[Dict[str, Any]],
    
    # Optional metadata
    user_id: str = "anonymous",
    model_id: str = None,
    tags: List[str] = None,
    duration_ms: float = None,
    
    # Service endpoint (deployed Docker container)
    service_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Register traces with the dockerized service.
    No Langfuse configuration needed - it's configured at deployment time.
    """
    
    payload = {
        # Input/Output data
        "input_text": input_text,
        "output_text": output_text,
        "agent_id": agent_id,
        "agent_alias_id": agent_alias_id,
        "session_id": session_id,
        "user_id": user_id,
        "model_id": model_id,
        "tags": tags or [],
        
        # Trace data
        "traces": traces,
        
        # Optional metadata
        "trace_id": f"bedrock-{session_id}-{int(time.time())}",
        "streaming": False,
        "duration_ms": duration_ms
    }
    
    try:
        print(f"📤 Sending traces to service at {service_url}")
        print(f"   Input: {input_text[:50]}...")
        print(f"   Output: {output_text[:50]}...")
        print(f"   Traces: {len(traces)} events")
        
        response = requests.post(
            f"{service_url.rstrip('/')}/register-traces",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Traces registered successfully!")
        print(f"   Status: {result.get('status')}")
        print(f"   Trace ID: {result.get('trace_id')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to register traces: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return {
            "error": str(e),
            "status": "failed"
        }

def example_bedrock_integration(
    service_url: str = "http://localhost:8000"
):
    """
    Complete example showing how to integrate with existing Bedrock Agent code.
    """
    
    # Your existing Bedrock Agent configuration
    agent_id = "YOUR_AGENT_ID" 
    agent_alias_id = "YOUR_AGENT_ALIAS_ID"
    session_id = f"session-{int(time.time())}"
    input_text = "What's the current weather in Seattle?"
    
    print("🔬 Example: Bedrock Agent + Trace Registration Service")
    print("=" * 60)
    
    try:
        start_time = time.time()
        
        # 1. Invoke Bedrock Agent (your existing code)
        print("🚀 Step 1: Invoking Bedrock Agent...")
        bedrock_client = boto3.client('bedrock-agent-runtime')
        
        response = bedrock_client.invoke_agent(
            inputText=input_text,
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            enableTrace=True  # Required for traces
        )
        
        # 2. Extract output and traces (your existing code)
        print("📊 Step 2: Extracting output and traces...")
        output_text = ""
        traces = []
        
        for event in response['completion']:
            if 'chunk' in event:
                chunk_data = event['chunk']
                if 'bytes' in chunk_data:
                    text = chunk_data['bytes'].decode('utf-8') if isinstance(chunk_data['bytes'], bytes) else str(chunk_data['bytes'])
                    output_text += text
            elif 'trace' in event:
                traces.append(event['trace'])
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        print(f"   Output: {len(output_text)} characters")
        print(f"   Traces: {len(traces)} events")
        print(f"   Duration: {duration_ms:.2f}ms")
        
        # 3. Send to trace registration service (NEW - just add this)
        print("📤 Step 3: Registering traces in Langfuse...")
        result = register_traces_simple(
            input_text=input_text,
            output_text=output_text,
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            traces=traces,
            user_id="demo-user",
            model_id="claude-3-5-sonnet-20241022-v2:0",
            tags=["demo", "weather", "bedrock-agent"],
            duration_ms=duration_ms,
            service_url=service_url
        )
        
        print("\n🎉 Complete flow successful!")
        print(f"Agent Response: {output_text[:200]}...")
        print(f"Traces Registered: {result.get('status') == 'success'}")
        
        return {
            "agent_response": output_text,
            "traces_registered": result.get('status') == 'success',
            "trace_id": result.get('trace_id'),
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Error in example flow: {str(e)}")
        return {
            "error": str(e),
            "status": "failed"
        }

def main():
    """Main example function."""
    
    # Service endpoint (adjust based on your deployment)
    service_url = "http://localhost:8000"  # Local Docker
    # service_url = "http://your-k8s-service:8000"  # Kubernetes
    # service_url = "https://your-ecs-service.amazonaws.com"  # AWS ECS
    
    # Check if service is healthy
    try:
        health_response = requests.get(f"{service_url}/health", timeout=10)
        if health_response.status_code == 200:
            print(f"✅ Service is healthy at {service_url}")
        else:
            print(f"⚠️  Service health check failed: {health_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot reach service at {service_url}: {str(e)}")
        print("Make sure the Docker container is running:")
        print("  docker-compose up -d")
        return
    
    # Run the example
    example_bedrock_integration(service_url)

if __name__ == "__main__":
    main()