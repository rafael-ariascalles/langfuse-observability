"""
Example client that sends traces to the Langfuse Observability Service.
This shows how to extract traces from Bedrock Agent responses and send them to the service.
"""

import json
import boto3
import requests
from datetime import datetime
from typing import List, Dict, Any

class LangfuseObservabilityClient:
    """Client for sending traces to the Langfuse Observability Service."""
    
    def __init__(self, service_url: str = "http://localhost:8000"):
        self.service_url = service_url.rstrip("/")
        self.session = requests.Session()
    
    def invoke_agent_with_observability(
        self,
        input_text: str,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        user_id: str = "anonymous",
        model_id: str = None,
        tags: List[str] = None,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Invoke Bedrock Agent and send traces to Langfuse Observability Service.
        
        Note: Langfuse configuration is handled by the service via environment variables.
        
        Args:
            input_text: The prompt/question for the agent
            agent_id: Bedrock Agent ID
            agent_alias_id: Bedrock Agent Alias ID
            session_id: Conversation session ID
            user_id: User identifier
            model_id: Model ID used by the agent
            tags: Tags for filtering in Langfuse
            streaming: Whether to use streaming mode
        
        Returns:
            Dictionary with agent response and observability status
        """
        tags = tags or []
        
        # Create Bedrock client
        bedrock_client = boto3.client('bedrock-agent-runtime')
        
        # Prepare invocation parameters
        invoke_params = {
            "inputText": input_text,
            "agentId": agent_id,
            "agentAliasId": agent_alias_id,
            "sessionId": session_id,
            "enableTrace": True  # Required to get trace data
        }
        
        if streaming:
            invoke_params["streamingConfigurations"] = {
                "applyGuardrailInterval": 10,
                "streamFinalResponse": True
            }
        
        try:
            # Invoke the Bedrock Agent
            print(f"🚀 Invoking agent {agent_id} with input: {input_text}")
            response = bedrock_client.invoke_agent(**invoke_params)
            
            # Extract traces and completion from response
            traces = []
            completion_text = ""
            
            for event in response['completion']:
                # Collect text chunks
                if 'chunk' in event:
                    chunk_data = event['chunk']
                    if 'bytes' in chunk_data:
                        text = chunk_data['bytes'].decode('utf-8') if isinstance(chunk_data['bytes'], bytes) else str(chunk_data['bytes'])
                        completion_text += text
                
                # Collect trace events
                elif 'trace' in event:
                    traces.append(event['trace'])
            
            print(f"📊 Extracted {len(traces)} traces from agent response")
            
            # Send traces to observability service
            observability_result = self.send_traces_to_service(
                agent_data={
                    "input_text": input_text,
                    "output_text": completion_text,
                    "agent_id": agent_id,
                    "agent_alias_id": agent_alias_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "model_id": model_id,
                    "tags": tags
                },
                traces=traces,
                streaming=streaming
            )
            
            return {
                "completion": completion_text,
                "traces_count": len(traces),
                "observability": observability_result,
                "status": "success"
            }
            
        except Exception as e:
            print(f"❌ Error during agent invocation: {str(e)}")
            return {
                "error": str(e),
                "status": "error"
            }
    
    def send_traces_to_service(
        self,
        agent_data: Dict[str, Any],
        traces: List[Dict[str, Any]],
        streaming: bool = False,
        trace_id: str = None
    ) -> Dict[str, Any]:
        """
        Send traces to the Langfuse Observability Service.
        
        Args:
            agent_data: Original agent invocation data
            traces: List of trace events from Bedrock Agent
            streaming: Whether streaming mode was used
            trace_id: Optional custom trace ID
        
        Returns:
            Response from the observability service
        """
        payload = {
            # Input/Output data
            "input_text": agent_data["input_text"],
            "output_text": agent_data.get("output_text", ""),
            "agent_id": agent_data["agent_id"],
            "agent_alias_id": agent_data["agent_alias_id"],
            "session_id": agent_data["session_id"],
            "user_id": agent_data.get("user_id", "anonymous"),
            "model_id": agent_data.get("model_id"),
            "tags": agent_data.get("tags", []),
            
            # Trace data
            "traces": traces,
            
            # Optional metadata
            "streaming": streaming
        }
        
        if trace_id:
            payload["trace_id"] = trace_id
        
        try:
            print(f"📤 Sending {len(traces)} traces to observability service...")
            
            response = self.session.post(
                f"{self.service_url}/register-traces",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Traces sent successfully: {result['message']}")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send traces to service: {str(e)}")
            return {
                "error": str(e),
                "status": "failed"
            }

def main():
    """Example usage of the Langfuse Observability Client."""
    
    # Agent configuration
    agent_config = {
        "agent_id": "YOUR_AGENT_ID",
        "agent_alias_id": "YOUR_AGENT_ALIAS_ID",
        "session_id": f"session-{int(datetime.now().timestamp())}",
        "user_id": "demo-user",
        "model_id": "claude-3-5-sonnet-20241022-v2:0",
        "tags": ["demo", "bedrock-agent", "langfuse"]
    }
    
    # Create client (Langfuse config is handled by the service environment variables)
    client = LangfuseObservabilityClient("http://localhost:8000")
    
    # Test the service
    result = client.invoke_agent_with_observability(
        input_text="What's the weather like today?",
        **agent_config,
        streaming=False
    )
    
    if result["status"] == "success":
        print(f"\n🤖 Agent Response: {result['completion']}")
        print(f"📊 Processed {result['traces_count']} traces")
        print(f"🔗 Observability Status: {result['observability']['status']}")
    else:
        print(f"\n❌ Error: {result['error']}")

if __name__ == "__main__":
    main()