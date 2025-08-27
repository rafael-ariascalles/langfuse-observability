"""
Async client example for the new Celery-based Langfuse Observability Service.
This shows how to work with the job-based async API.
"""

import json
import boto3
import requests
import time
from datetime import datetime
from typing import List, Dict, Any, Optional


class AsyncLangfuseObservabilityClient:
    """Async client for the Langfuse Observability Service."""
    
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
        streaming: bool = False,
        wait_for_completion: bool = True,
        poll_interval: int = 2,
        max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """
        Invoke Bedrock Agent and register traces asynchronously.
        
        Args:
            input_text: The prompt/question for the agent
            agent_id: Bedrock Agent ID
            agent_alias_id: Bedrock Agent Alias ID
            session_id: Conversation session ID
            user_id: User identifier
            model_id: Model ID used by the agent
            tags: Tags for filtering in Langfuse
            streaming: Whether to use streaming mode
            wait_for_completion: Whether to wait for job completion
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait for completion
        
        Returns:
            Dictionary with agent response and job information
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
            start_time = time.time()
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
            
            agent_duration = time.time() - start_time
            print(f"📊 Agent completed in {agent_duration:.2f}s. Extracted {len(traces)} traces")
            
            # Submit traces to observability service
            job_response = self.submit_traces_async(
                input_text=input_text,
                output_text=completion_text,
                agent_id=agent_id,
                agent_alias_id=agent_alias_id,
                session_id=session_id,
                user_id=user_id,
                model_id=model_id,
                tags=tags,
                traces=traces,
                duration_ms=agent_duration * 1000,
                streaming=streaming
            )
            
            result = {
                "completion": completion_text,
                "traces_count": len(traces),
                "agent_duration": agent_duration,
                "job_id": job_response.get("job_id"),
                "job_status": job_response.get("status"),
                "status": "success"
            }
            
            # Wait for job completion if requested
            if wait_for_completion and job_response.get("job_id"):
                print(f"⏳ Waiting for trace processing job {job_response['job_id']}...")
                job_result = self.wait_for_job_completion(
                    job_response["job_id"],
                    poll_interval=poll_interval,
                    max_wait_time=max_wait_time
                )
                result["observability"] = job_result
            
            return result
            
        except Exception as e:
            print(f"❌ Error during agent invocation: {str(e)}")
            return {
                "error": str(e),
                "status": "error"
            }
    
    def submit_traces_async(
        self,
        input_text: str,
        output_text: str,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        traces: List[Dict[str, Any]],
        user_id: str = "anonymous",
        model_id: str = None,
        tags: List[str] = None,
        duration_ms: float = None,
        streaming: bool = False,
        trace_id: str = None
    ) -> Dict[str, Any]:
        """
        Submit traces to the service for async processing.
        
        Returns:
            Response with job_id for tracking
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
            "streaming": streaming,
            "duration_ms": duration_ms
        }
        
        if trace_id:
            payload["trace_id"] = trace_id
        
        try:
            print(f"📤 Submitting {len(traces)} traces for async processing...")
            
            response = self.session.post(
                f"{self.service_url}/register-traces",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Job queued successfully: {result['job_id']}")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to submit traces: {str(e)}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the current status of a processing job."""
        try:
            response = self.session.get(
                f"{self.service_url}/job-status/{job_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get job status: {str(e)}")
            return {
                "error": str(e),
                "status": "unknown"
            }
    
    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed job."""
        try:
            response = self.session.get(
                f"{self.service_url}/job-result/{job_id}",
                timeout=10
            )
            
            if response.status_code == 202:
                # Job still processing
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get job result: {str(e)}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def wait_for_job_completion(
        self, 
        job_id: str, 
        poll_interval: int = 2, 
        max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """
        Wait for job completion by polling status.
        
        Args:
            job_id: The job ID to monitor
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            
        Returns:
            Final job result or timeout error
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status = self.get_job_status(job_id)
            
            if status.get("status") == "completed":
                result = self.get_job_result(job_id)
                if result:
                    print(f"✅ Job {job_id} completed successfully!")
                    return result
            
            elif status.get("status") == "failed":
                print(f"❌ Job {job_id} failed: {status.get('error')}")
                return status
            
            elif status.get("status") in ["pending", "processing"]:
                print(f"⏳ Job {job_id} status: {status.get('status')}")
                time.sleep(poll_interval)
            
            else:
                print(f"❓ Unknown job status: {status}")
                time.sleep(poll_interval)
        
        # Timeout
        print(f"⏰ Job {job_id} timed out after {max_wait_time} seconds")
        return {
            "status": "timeout",
            "error": f"Job did not complete within {max_wait_time} seconds"
        }


def main():
    """Example usage of the Async Langfuse Observability Client."""
    
    # Agent configuration
    agent_config = {
        "agent_id": "YOUR_AGENT_ID",
        "agent_alias_id": "YOUR_AGENT_ALIAS_ID", 
        "session_id": f"session-{int(datetime.now().timestamp())}",
        "user_id": "demo-user",
        "model_id": "claude-3-5-sonnet-20241022-v2:0",
        "tags": ["demo", "bedrock-agent", "async"]
    }
    
    # Create async client
    client = AsyncLangfuseObservabilityClient("http://localhost:8000")
    
    print("🤖 Async Langfuse Observability Demo")
    print("=" * 50)
    
    # Test the service
    result = client.invoke_agent_with_observability(
        input_text="What's the weather like today?",
        **agent_config,
        wait_for_completion=True,  # Wait for trace processing
        poll_interval=2,  # Check status every 2 seconds
        max_wait_time=120  # Wait up to 2 minutes
    )
    
    if result["status"] == "success":
        print(f"\n🤖 Agent Response: {result['completion']}")
        print(f"📊 Processed {result['traces_count']} traces")
        print(f"⏱️  Agent took: {result['agent_duration']:.2f}s")
        
        if "observability" in result:
            obs = result["observability"]
            if obs.get("status") == "completed":
                print(f"✅ Traces registered in Langfuse: {obs['result'].get('message')}")
            else:
                print(f"⚠️  Trace processing status: {obs.get('status')}")
    else:
        print(f"\n❌ Error: {result['error']}")

    # Example: Submit without waiting
    print("\n" + "=" * 50)
    print("🚀 Example: Fire and forget mode")
    
    result2 = client.invoke_agent_with_observability(
        input_text="Tell me a joke",
        **agent_config,
        wait_for_completion=False  # Don't wait, just return job ID
    )
    
    if result2["status"] == "success":
        print(f"📋 Job ID: {result2['job_id']}")
        print(f"🤖 Agent Response: {result2['completion']}")
        print("💡 Check job status later with client.get_job_status(job_id)")


if __name__ == "__main__":
    main()