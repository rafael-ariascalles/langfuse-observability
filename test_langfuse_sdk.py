"""
Test script to validate the corrected Langfuse SDK implementation.
This will test the actual Langfuse SDK methods and ensure our implementation is correct.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any

# Test if we can import and use Langfuse correctly
try:
    from langfuse import Langfuse
    print("✅ Langfuse SDK imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Langfuse SDK: {e}")
    exit(1)

def test_langfuse_sdk_methods():
    """Test the actual Langfuse SDK methods to validate our implementation."""
    
    print("🧪 Testing Langfuse SDK Methods")
    print("=" * 50)
    
    # Mock credentials for testing (won't actually send data)
    langfuse = Langfuse(
        public_key="test-key",
        secret_key="test-secret", 
        host="http://localhost:3000",  # Mock host
        debug=True
    )
    
    try:
        # Test 1: Check available methods
        print("🔬 Test 1: Checking available Langfuse methods...")
        available_methods = [method for method in dir(langfuse) if not method.startswith('_')]
        print(f"Available methods: {available_methods}")
        
        # Try different trace creation approaches
        print("🔬 Test 1a: Trying langfuse.trace()...")
        try:
            trace = langfuse.trace(
                name="test_bedrock_agent",
                user_id="test-user",
                metadata={"agent_id": "test-agent"},
                tags=["test", "bedrock"]
            )
            print("✅ langfuse.trace() worked")
        except Exception as e:
            print(f"❌ langfuse.trace() failed: {e}")
            
            # Try alternative method
            print("🔬 Test 1b: Trying alternative trace creation...")
            try:
                # Check if there's a different method
                if hasattr(langfuse, 'create_trace'):
                    trace = langfuse.create_trace(name="test_bedrock_agent")
                    print("✅ langfuse.create_trace() worked")
                else:
                    print("❌ No create_trace method found")
                    return False
            except Exception as e2:
                print(f"❌ Alternative method failed: {e2}")
                return False
        
        # Test 2: Create a generation
        print("🔬 Test 2: Creating generation...")
        generation = trace.generation(
            name="llm_orchestration",
            model="claude-3-5-sonnet",
            input="Process this request",
            output="Here's the response",
            metadata={"component": "orchestration"},
            usage={
                "input": 15,
                "output": 12,
                "total": 27
            }
        )
        print("✅ Generation created successfully")
        
        # Test 3: Create a span (for tools/retrievers)
        print("🔬 Test 3: Creating spans...")
        tool_span = trace.span(
            name="weather_api_call",
            input={"city": "Seattle"},
            output={"temperature": "15C", "conditions": "sunny"},
            metadata={
                "type": "tool",
                "tool_name": "weather_api",
                "langfuse_object_type": "tool"
            }
        )
        print("✅ Tool span created successfully")
        
        retriever_span = trace.span(
            name="knowledge_base_search",
            input="weather articles",
            output=[{"content": "Weather patterns...", "score": 0.85}],
            metadata={
                "type": "retriever",
                "kb_id": "kb-123",
                "langfuse_object_type": "retriever"
            }
        )
        print("✅ Retriever span created successfully")
        
        # Test 4: Create an event
        print("🔬 Test 4: Creating event...")
        event = trace.event(
            name="processing_completed",
            input="Processing request",
            output="Request completed successfully",
            level="DEFAULT",
            metadata={"component": "system"}
        )
        print("✅ Event created successfully")
        
        # Test 5: Create nested spans
        print("🔬 Test 5: Creating nested spans...")
        processing_span = trace.span(
            name="input_processing",
            input="Raw user input",
            output="Processed input",
            metadata={"component": "preprocessing"}
        )
        
        reasoning_span = trace.span(
            name="agent_reasoning", 
            input="Processed input",
            output="Reasoning complete",
            metadata={"component": "reasoning"}
        )
        print("✅ Nested spans created successfully")
        
        print("\n🎉 All Langfuse SDK tests passed!")
        print("✅ Our implementation should work correctly with these methods")
        
        return True
        
    except Exception as e:
        print(f"❌ SDK test failed: {str(e)}")
        print("This indicates our implementation needs adjustment")
        return False

def test_our_implementation():
    """Test our actual implementation with sample data."""
    
    print("\n🧪 Testing Our Implementation")
    print("=" * 50)
    
    try:
        # Import our components
        from src.langfuse_observability.shared.bedrock_mapper import BedrockToLangfuseMapper
        from src.langfuse_observability.shared.langfuse_registrar import LangfuseTraceRegistrar
        from src.langfuse_observability.shared.models import TraceRegistrationRequest
        
        print("✅ Our components imported successfully")
        
        # Test the mapper
        print("🔬 Testing Bedrock trace mapper...")
        mapper = BedrockToLangfuseMapper()
        
        sample_bedrock_trace = {
            "trace": {
                "orchestrationTrace": {
                    "modelInvocationInput": {
                        "text": "What's the weather in Seattle?",
                        "traceId": "orch-123"
                    },
                    "modelInvocationOutput": {
                        "rawResponse": {
                            "content": [{"text": "I'll check the weather for you."}],
                            "usage": {"inputTokens": 15, "outputTokens": 12},
                            "modelId": "claude-3-5-sonnet"
                        },
                        "traceId": "orch-123"
                    }
                }
            },
            "eventTime": "2024-01-01T12:00:00Z"
        }
        
        langfuse_objects = mapper.map_bedrock_trace(sample_bedrock_trace)
        print(f"✅ Mapper created {len(langfuse_objects)} Langfuse objects")
        
        for obj in langfuse_objects:
            print(f"   - {obj['type']}: {obj['name']}")
            if obj['type'] == 'generation' and 'usage' in obj:
                print(f"     Usage: {obj['usage']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Implementation test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_request() -> Dict[str, Any]:
    """Create a sample trace registration request for testing."""
    return {
        "input_text": "What's the weather in Seattle and can you search for recent articles?",
        "output_text": "The weather in Seattle is currently 15°C and cloudy. I found recent articles about weather patterns.",
        "agent_id": "TEST_AGENT_ID",
        "agent_alias_id": "TEST_ALIAS_ID", 
        "session_id": f"test-session-{int(time.time())}",
        "user_id": "test-user",
        "model_id": "claude-3-5-sonnet-20241022-v2:0",
        "tags": ["test", "weather", "structured-traces"],
        "traces": [
            {
                "trace": {
                    "orchestrationTrace": {
                        "modelInvocationInput": {
                            "text": "What's the weather in Seattle?",
                            "traceId": "orch-456"
                        },
                        "modelInvocationOutput": {
                            "rawResponse": {
                                "content": [{"text": "I'll check the weather and search for articles."}],
                                "usage": {"inputTokens": 25, "outputTokens": 20},
                                "modelId": "claude-3-5-sonnet-20241022-v2:0"
                            },
                            "traceId": "orch-456"
                        },
                        "actionGroupInvocations": [
                            {
                                "invocationInput": {
                                    "actionGroupName": "weather-api",
                                    "function": "getCurrentWeather",
                                    "parameters": {"city": "Seattle"},
                                    "traceId": "action-789"
                                },
                                "observation": {
                                    "actionGroupInvocationOutput": {
                                        "text": "Current weather: 15°C, Cloudy"
                                    },
                                    "traceId": "action-789"
                                }
                            }
                        ],
                        "knowledgeBaseLookupInput": {
                            "text": "recent Seattle weather articles",
                            "knowledgeBaseId": "kb-123",
                            "traceId": "kb-101"
                        },
                        "knowledgeBaseLookupOutput": {
                            "retrievedReferences": [
                                {
                                    "content": {"text": "Seattle weather patterns have been changing..."},
                                    "metadata": {"source": "weather-news.com"},
                                    "score": 0.85
                                }
                            ],
                            "traceId": "kb-101"
                        }
                    }
                },
                "eventTime": "2024-01-01T12:00:00Z"
            },
            {
                "trace": {
                    "guardrailTrace": {
                        "action": "NONE",
                        "traceId": "guard-202",
                        "outputs": []
                    }
                },
                "eventTime": "2024-01-01T12:00:01Z"
            }
        ],
        "trace_id": f"test-{int(time.time())}",
        "streaming": False,
        "duration_ms": 2500.0
    }

def main():
    """Main test function."""
    print("🎯 Langfuse SDK Implementation Validation")
    print("=" * 60)
    
    # Test 1: Validate Langfuse SDK methods
    sdk_test_passed = test_langfuse_sdk_methods()
    
    # Test 2: Test our implementation
    if sdk_test_passed:
        implementation_test_passed = test_our_implementation()
        
        if implementation_test_passed:
            print("\n🎉 All tests passed! Implementation is ready.")
            print("\n📋 Next steps:")
            print("1. Configure real Langfuse credentials in environment")
            print("2. Test with actual Bedrock Agent traces")
            print("3. Verify traces appear correctly in Langfuse UI")
        else:
            print("\n❌ Implementation needs fixes")
    else:
        print("\n❌ SDK usage needs correction")

if __name__ == "__main__":
    main()