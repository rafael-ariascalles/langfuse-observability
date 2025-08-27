"""
Simple client example for the Langfuse Trace Registration Service.
This shows how to send input + output + traces to register in Langfuse.
"""

import json
import boto3
import requests
import time
from datetime import datetime
from typing import List, Dict, Any

def register_agent_traces_in_langfuse(
    # Input data
    input_text: str,
    output_text: str,
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    
    # Trace data (extracted from Bedrock Agent response)
    traces: List[Dict[str, Any]],
    
    # Langfuse configuration
    langfuse_public_key: str,
    langfuse_secret_key: str,
    langfuse_api_url: str = "https://us.cloud.langfuse.com",
    
    # Optional metadata
    user_id: str = "anonymous",
    model_id: str = None,
    tags: List[str] = None,
    duration_ms: float = None,
    
    # Service configuration
    service_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Register agent interaction traces in Langfuse via the registration service.
    
    Args:
        input_text: The original prompt/question sent to the agent
        output_text: The response received from the agent
        agent_id: Bedrock Agent ID
        agent_alias_id: Bedrock Agent Alias ID
        session_id: Conversation session ID
        traces: List of trace events from Bedrock Agent response
        langfuse_public_key: Langfuse public key
        langfuse_secret_key: Langfuse secret key
        langfuse_api_url: Langfuse API URL
        user_id: User identifier
        model_id: Model ID used by the agent
        tags: Tags for filtering in Langfuse
        duration_ms: Total duration of the interaction
        service_url: URL of the registration service
    
    Returns:
        Response from the registration service
    """
    
    # Prepare the request payload
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
        
        # Langfuse configuration
        "langfuse_config": {
            "public_key": langfuse_public_key,
            "secret_key": langfuse_secret_key,
            "api_url": langfuse_api_url,
            "project_name": "Bedrock Agent Traces",
            "environment": "development"
        },
        
        # Optional metadata
        "trace_id": f"bedrock-{session_id}-{int(time.time())}",
        "streaming": False,
        "duration_ms": duration_ms
    }
    
    try:
        print(f"📤 Registering traces for agent {agent_id}, session {session_id}")
        print(f"   Input: {input_text[:100]}...")
        print(f"   Output: {output_text[:100]}...")
        print(f"   Traces: {len(traces)} trace events")
        
        response = requests.post(
            f"{service_url.rstrip('/')}/register-traces",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Traces registered successfully in Langfuse!")
        print(f"   Status: {result.get('status')}")
        print(f"   Trace ID: {result.get('trace_id')}")
        print(f"   Processed: {result.get('processed_traces')} traces")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to register traces: {str(e)}")
        return {
            "error": str(e),
            "status": "failed"
        }

def invoke_bedrock_agent_and_register_traces(
    input_text: str,
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    langfuse_public_key: str,
    langfuse_secret_key: str,
    user_id: str = "demo-user",
    service_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Complete example: Invoke Bedrock Agent and register traces in Langfuse.
    
    This function:
    1. Invokes the Bedrock Agent
    2. Extracts the output text and traces
    3. Sends them to the registration service
    4. Returns the agent response and registration status
    """
    
    start_time = time.time()
    
    try:
        # Create Bedrock client
        bedrock_client = boto3.client('bedrock-agent-runtime')
        
        # Invoke the agent
        print(f"🚀 Invoking Bedrock Agent {agent_id}...")
        response = bedrock_client.invoke_agent(
            inputText=input_text,
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            enableTrace=True  # Required to get trace data
        )
        
        # Extract output and traces from response
        output_text = ""
        traces = []
        
        for event in response['completion']:
            # Collect text chunks
            if 'chunk' in event:
                chunk_data = event['chunk']
                if 'bytes' in chunk_data:
                    text = chunk_data['bytes'].decode('utf-8') if isinstance(chunk_data['bytes'], bytes) else str(chunk_data['bytes'])
                    output_text += text
            
            # Collect trace events
            elif 'trace' in event:
                traces.append(event['trace'])
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        print(f"✅ Agent invocation completed in {duration_ms:.2f}ms")
        print(f"   Output: {len(output_text)} characters")
        print(f"   Traces: {len(traces)} events")
        
        # Register traces in Langfuse
        registration_result = register_agent_traces_in_langfuse(
            input_text=input_text,
            output_text=output_text,
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            traces=traces,
            langfuse_public_key=langfuse_public_key,
            langfuse_secret_key=langfuse_secret_key,
            user_id=user_id,
            duration_ms=duration_ms,
            service_url=service_url
        )
        
        return {
            "input": input_text,
            "output": output_text,
            "traces_count": len(traces),
            "duration_ms": duration_ms,
            "registration": registration_result,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Error during agent invocation: {str(e)}")
        return {
            "error": str(e),
            "status": "error"
        }

def main():
    """Example usage of the trace registration."""
    
    # Configuration - Replace with your actual values
    config = {
        "agent_id": "YOUR_AGENT_ID",
        "agent_alias_id": "YOUR_AGENT_ALIAS_ID", 
        "session_id": f"session-{int(time.time())}",
        "langfuse_public_key": "pk-lf-your-public-key",
        "langfuse_secret_key": "sk-lf-your-secret-key",
        "user_id": "demo-user",
        "service_url": "http://localhost:8000"
    }
    
    # Test input
    input_text = "What's the weather like in Seattle today?"
    
    print("🔬 Testing Bedrock Agent + Langfuse Registration")
    print("=" * 60)
    
    # Run the complete flow
    result = invoke_bedrock_agent_and_register_traces(
        input_text=input_text,
        **config
    )
    
    if result["status"] == "success":
        print("\n🎉 Complete flow successful!")
        print(f"Input: {result['input']}")
        print(f"Output: {result['output'][:200]}...")
        print(f"Traces: {result['traces_count']}")
        print(f"Duration: {result['duration_ms']:.2f}ms")
        print(f"Registration: {result['registration']['status']}")
    else:
        print(f"\n❌ Flow failed: {result['error']}")

if __name__ == "__main__":
    main()