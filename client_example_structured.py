"""
Example client for testing the new structured Langfuse trace types.
This demonstrates how the service now creates proper Langfuse objects instead of generic spans.
"""

import json
import boto3
import requests
import time
from datetime import datetime
from typing import List, Dict, Any

def test_structured_traces(
    input_text: str = "What's the weather in Seattle and can you search for recent articles about it?",
    agent_id: str = "YOUR_AGENT_ID",
    agent_alias_id: str = "YOUR_AGENT_ALIAS_ID",
    session_id: str = None,
    service_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Test the new structured Langfuse trace registration.
    
    This will create:
    - generation objects for LLM calls
    - tool objects for action groups/code interpreter
    - retriever objects for knowledge base lookups
    - span objects for pre/post processing
    - guardrail objects for content protection
    - event objects for failures
    """
    
    if not session_id:
        session_id = f"test-session-{int(time.time())}"
    
    start_time = time.time()
    
    try:
        # Step 1: Invoke Bedrock Agent
        print("🚀 Step 1: Invoking Bedrock Agent...")
        bedrock_client = boto3.client('bedrock-agent-runtime')
        
        response = bedrock_client.invoke_agent(
            inputText=input_text,
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            enableTrace=True  # Required for structured traces
        )
        
        # Step 2: Extract output and traces
        print("📊 Step 2: Extracting traces for structured processing...")
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
        
        print(f"✅ Agent invocation completed:")
        print(f"   📝 Input: {input_text[:80]}...")
        print(f"   🤖 Output: {output_text[:80]}...")
        print(f"   📊 Traces: {len(traces)} events")
        print(f"   ⏱️ Duration: {duration_ms:.2f}ms")
        
        # Step 3: Analyze trace types (for educational purposes)
        trace_types = {}
        for trace in traces:
            trace_content = trace.get("trace", {})
            for trace_type in trace_content.keys():
                trace_types[trace_type] = trace_types.get(trace_type, 0) + 1
        
        print(f"\n📋 Trace types found: {dict(trace_types)}")
        
        # Step 4: Send to structured Langfuse service
        print("\n🔄 Step 3: Registering structured traces in Langfuse...")
        
        payload = {
            "input_text": input_text,
            "output_text": output_text,
            "agent_id": agent_id,
            "agent_alias_id": agent_alias_id,
            "session_id": session_id,
            "user_id": "structured-test-user",
            "model_id": "claude-3-5-sonnet-20241022-v2:0",
            "tags": ["structured-traces", "test", "demo"],
            "traces": traces,
            "trace_id": f"structured-test-{session_id}",
            "streaming": False,
            "duration_ms": duration_ms
        }
        
        response = requests.post(
            f"{service_url.rstrip('/')}/register-traces",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Structured traces registered successfully!")
        print(f"   🆔 Trace ID: {result.get('trace_id')}")
        print(f"   📊 Raw traces processed: {result.get('processed_traces')}")
        print(f"   🏗️ Langfuse objects created: {result.get('created_objects')}")
        print(f"   ⏱️ Processing time: {result.get('processing_duration_ms', 0):.2f}ms")
        
        # Show structured object counts
        if 'object_counts' in result:
            counts = result['object_counts']
            print(f"\n🎯 Structured Langfuse objects created:")
            print(f"   🧠 Generations (LLM calls): {counts.get('generations', 0)}")
            print(f"   🔧 Tools (action groups/code): {counts.get('tools', 0)}")
            print(f"   🔍 Retrievers (knowledge base): {counts.get('retrievers', 0)}")
            print(f"   📏 Spans (processing steps): {counts.get('spans', 0)}")
            print(f"   🛡️ Guardrails (content protection): {counts.get('guardrails', 0)}")
            print(f"   📅 Events (discrete events): {counts.get('events', 0)}")
        
        return {
            "status": "success",
            "agent_response": output_text,
            "traces_processed": len(traces),
            "langfuse_objects": result.get('created_objects', 0),
            "object_breakdown": result.get('object_counts', {}),
            "trace_id": result.get('trace_id'),
            "duration_ms": duration_ms,
            "processing_duration_ms": result.get('processing_duration_ms', 0)
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP Error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return {"status": "http_error", "error": str(e)}
        
    except Exception as e:
        print(f"❌ General Error: {str(e)}")
        return {"status": "error", "error": str(e)}

def create_sample_trace_data():
    """Create sample trace data for testing without actual Bedrock Agent."""
    return [
        {
            "trace": {
                "orchestrationTrace": {
                    "modelInvocationInput": {
                        "text": "What's the weather in Seattle?",
                        "type": "PRE_PROCESSING",
                        "traceId": "trace-orch-123"
                    },
                    "modelInvocationOutput": {
                        "rawResponse": {
                            "content": [{"text": "I'll check the weather in Seattle for you."}],
                            "usage": {"inputTokens": 15, "outputTokens": 12},
                            "modelId": "claude-3-5-sonnet-20241022-v2:0"
                        },
                        "traceId": "trace-orch-123"
                    },
                    "actionGroupInvocations": [
                        {
                            "invocationInput": {
                                "actionGroupName": "weather-api",
                                "function": "getCurrentWeather",
                                "parameters": {"city": "Seattle", "state": "WA"},
                                "traceId": "trace-action-456"
                            },
                            "observation": {
                                "actionGroupInvocationOutput": {
                                    "text": "Current weather in Seattle: 15°C, Cloudy"
                                },
                                "traceId": "trace-action-456"
                            }
                        }
                    ],
                    "knowledgeBaseLookupInput": {
                        "text": "recent articles about Seattle weather",
                        "knowledgeBaseId": "kb-789",
                        "traceId": "trace-kb-789"
                    },
                    "knowledgeBaseLookupOutput": {
                        "retrievedReferences": [
                            {
                                "content": {"text": "Seattle weather patterns have changed recently..."},
                                "metadata": {"source": "weather-news.com"},
                                "location": {"s3Location": {"uri": "s3://kb/doc1.pdf"}},
                                "score": 0.85
                            }
                        ],
                        "traceId": "trace-kb-789"
                    }
                }
            },
            "eventTime": "2024-01-01T12:00:00Z"
        },
        {
            "trace": {
                "preProcessingTrace": {
                    "modelInvocationOutput": {
                        "parsedResponse": {
                            "isValid": True,
                            "rationale": "Valid weather request"
                        },
                        "traceId": "trace-pre-101"
                    }
                }
            },
            "eventTime": "2024-01-01T12:00:01Z"
        },
        {
            "trace": {
                "guardrailTrace": {
                    "action": "NONE",
                    "traceId": "trace-guard-pre-202",
                    "outputs": []
                }
            },
            "eventTime": "2024-01-01T12:00:02Z"
        },
        {
            "trace": {
                "postProcessingTrace": {
                    "modelInvocationOutput": {
                        "parsedResponse": {
                            "text": "The weather in Seattle is currently 15°C and cloudy based on recent data."
                        },
                        "traceId": "trace-post-303"
                    }
                }
            },
            "eventTime": "2024-01-01T12:00:03Z"
        }
    ]

def test_with_sample_data(service_url: str = "http://localhost:8000"):
    """Test the structured trace service with sample data."""
    print("🧪 Testing with sample trace data...")
    
    payload = {
        "input_text": "What's the weather in Seattle and can you search for recent articles?",
        "output_text": "The weather in Seattle is currently 15°C and cloudy based on recent data and articles.",
        "agent_id": "SAMPLE_AGENT_ID",
        "agent_alias_id": "SAMPLE_ALIAS_ID",
        "session_id": f"sample-session-{int(time.time())}",
        "user_id": "sample-test-user",
        "model_id": "claude-3-5-sonnet-20241022-v2:0",
        "tags": ["sample-test", "structured-traces"],
        "traces": create_sample_trace_data(),
        "trace_id": f"sample-test-{int(time.time())}",
        "streaming": False,
        "duration_ms": 2500.0
    }
    
    try:
        response = requests.post(
            f"{service_url.rstrip('/')}/register-traces",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Sample test successful!")
        print(f"   🆔 Trace ID: {result.get('trace_id')}")
        print(f"   🏗️ Objects created: {result.get('created_objects')}")
        
        if 'object_counts' in result:
            counts = result['object_counts']
            print(f"   📊 Object breakdown:")
            for obj_type, count in counts.items():
                if count > 0:
                    print(f"      {obj_type}: {count}")
        
        return result
        
    except Exception as e:
        print(f"❌ Sample test failed: {str(e)}")
        return {"status": "error", "error": str(e)}

def main():
    """Main function to run structured trace tests."""
    print("🎯 Langfuse Structured Trace Registration Test")
    print("=" * 60)
    
    # Check service health
    service_url = "http://localhost:8000"
    
    try:
        health_response = requests.get(f"{service_url}/health", timeout=5)
        if health_response.status_code == 200:
            print(f"✅ Service is healthy at {service_url}")
        else:
            print(f"⚠️  Service health check failed")
            return
    except Exception as e:
        print(f"❌ Cannot reach service: {str(e)}")
        print("Make sure the service is running:")
        print("  docker-compose up -d")
        return
    
    # Test 1: Sample data test (always works)
    print(f"\n{'='*60}")
    print("TEST 1: Sample Data Test")
    print("="*60)
    test_with_sample_data(service_url)
    
    # Test 2: Real Bedrock Agent (requires configuration)
    print(f"\n{'='*60}")
    print("TEST 2: Real Bedrock Agent Test")
    print("="*60)
    print("Note: This requires valid agent configuration")
    
    # Uncomment and configure these lines to test with real agent
    # result = test_structured_traces(
    #     input_text="Tell me about the weather and search for recent news",
    #     agent_id="YOUR_REAL_AGENT_ID",
    #     agent_alias_id="YOUR_REAL_AGENT_ALIAS_ID",
    #     service_url=service_url
    # )
    
    print("\n🎉 Structured trace testing complete!")
    print("\n📋 What to check in Langfuse:")
    print("   1. Root trace should show the full agent conversation")
    print("   2. Generation objects should show LLM calls with token usage")
    print("   3. Tool objects should show action group/code interpreter calls")
    print("   4. Retriever objects should show knowledge base searches")
    print("   5. Span objects should show processing steps")
    print("   6. Proper parent-child relationships in the trace hierarchy")

if __name__ == "__main__":
    main()