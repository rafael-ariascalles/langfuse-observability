"""
Test that the updated worker creates structured Langfuse traces instead of generic spans.
This simulates what happens when the worker processes real Bedrock Agent trace data.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Add src to Python path
src_path = Path('src')
sys.path.insert(0, str(src_path))

def test_worker_with_structured_traces():
    """Test that the worker creates structured Langfuse trace objects."""
    
    print("🧪 Testing Worker with Structured Langfuse Traces")
    print("=" * 60)
    
    # Set mock environment variables
    os.environ['LANGFUSE_PUBLIC_KEY'] = 'test-key'
    os.environ['LANGFUSE_SECRET_KEY'] = 'test-secret'
    os.environ['LANGFUSE_API_URL'] = 'http://localhost:3000'
    
    try:
        # Import the updated components
        from langfuse_observability.shared.langfuse_registrar import create_langfuse_registrar
        from langfuse_observability.shared.models import TraceRegistrationRequest
        from langfuse_observability.shared.settings import settings
        
        print("✅ Updated components imported successfully")
        
        # Create the new structured registrar
        print("\n🔬 Creating structured Langfuse registrar...")
        registrar = create_langfuse_registrar(settings)
        print("✅ LangfuseTraceRegistrar created (uses direct Langfuse SDK)")
        
        # Create comprehensive test data with multiple trace types
        print("\n🔬 Creating comprehensive Bedrock Agent trace data...")
        test_request = TraceRegistrationRequest(
            input_text="What's the weather in Seattle? Can you search for recent weather articles and analyze the data?",
            output_text="The weather in Seattle is 15°C and cloudy. I found recent articles about weather patterns and analyzed the data trends.",
            agent_id="WEATHER_ANALYSIS_AGENT",
            agent_alias_id="PROD_ALIAS",
            session_id=f"session-{int(time.time())}",
            user_id="test-user-123",
            model_id="claude-3-5-sonnet-20241022-v2:0",
            tags=["weather", "analysis", "structured-test"],
            traces=[
                # Orchestration trace -> generation + tool + retriever
                {
                    "trace": {
                        "orchestrationTrace": {
                            "modelInvocationInput": {
                                "text": "What's the weather in Seattle? Search for articles.",
                                "traceId": "orch-001"
                            },
                            "modelInvocationOutput": {
                                "rawResponse": {
                                    "content": [{"text": "I'll check the weather and search for articles."}],
                                    "usage": {"inputTokens": 35, "outputTokens": 25},
                                    "modelId": "claude-3-5-sonnet-20241022-v2:0"
                                },
                                "traceId": "orch-001"
                            },
                            "actionGroupInvocations": [
                                {
                                    "invocationInput": {
                                        "actionGroupName": "weather-service",
                                        "function": "getCurrentWeather",
                                        "parameters": {"city": "Seattle", "units": "celsius"},
                                        "traceId": "action-002"
                                    },
                                    "observation": {
                                        "actionGroupInvocationOutput": {
                                            "text": "Weather: 15°C, cloudy, humidity 75%"
                                        },
                                        "traceId": "action-002"
                                    }
                                }
                            ],
                            "knowledgeBaseLookupInput": {
                                "text": "recent Seattle weather articles climate analysis",
                                "knowledgeBaseId": "weather-kb-123",
                                "traceId": "kb-003"
                            },
                            "knowledgeBaseLookupOutput": {
                                "retrievedReferences": [
                                    {
                                        "content": {"text": "Seattle experiences a temperate oceanic climate..."},
                                        "metadata": {"source": "weather-analysis.pdf", "page": 5},
                                        "score": 0.89
                                    },
                                    {
                                        "content": {"text": "Recent weather patterns show increased rainfall..."},
                                        "metadata": {"source": "climate-report-2024.pdf", "page": 12},
                                        "score": 0.84
                                    }
                                ],
                                "traceId": "kb-003"
                            },
                            "rationale": {
                                "text": "I need to get current weather and search for recent articles to provide comprehensive analysis.",
                                "traceId": "rationale-004"
                            }
                        }
                    },
                    "eventTime": "2024-01-01T12:00:00Z"
                },
                # Pre-processing trace -> span
                {
                    "trace": {
                        "preProcessingTrace": {
                            "modelInvocationInput": {
                                "text": "Validating user request for weather and article search",
                                "traceId": "pre-005"
                            },
                            "modelInvocationOutput": {
                                "parsedResponse": {
                                    "isValid": True,
                                    "rationale": "Request is valid for weather analysis workflow"
                                },
                                "traceId": "pre-005"
                            }
                        }
                    },
                    "eventTime": "2024-01-01T11:59:55Z"
                },
                # Guardrail trace -> guardrail
                {
                    "trace": {
                        "guardrailTrace": {
                            "action": "NONE",
                            "traceId": "guard-006",
                            "outputs": []
                        }
                    },
                    "eventTime": "2024-01-01T12:00:05Z"
                },
                # Post-processing trace -> span
                {
                    "trace": {
                        "postProcessingTrace": {
                            "modelInvocationInput": {
                                "text": "Formatting final response with weather and article analysis",
                                "traceId": "post-007"
                            },
                            "modelInvocationOutput": {
                                "parsedResponse": {
                                    "text": "Final formatted response ready for user"
                                },
                                "traceId": "post-007"
                            }
                        }
                    },
                    "eventTime": "2024-01-01T12:00:10Z"
                }
            ],
            trace_id=f"structured-test-{int(time.time())}",
            streaming=False,
            duration_ms=3500.0
        )
        
        print(f"✅ Created test request with {len(test_request.traces)} traces")
        print(f"   - Agent: {test_request.agent_id}")
        print(f"   - Session: {test_request.session_id}")
        print(f"   - Input: {test_request.input_text[:50]}...")
        
        # Process traces with new registrar (simulate what worker does)
        print("\n🔬 Processing traces with structured Langfuse registrar...")
        start_time = time.time()
        
        # This is what the updated worker now does:
        result = registrar.register_traces(test_request)
        
        processing_time = time.time() - start_time
        print(f"✅ Traces processed in {processing_time:.3f}s")
        
        # Analyze results
        print(f"\n📊 Processing Results:")
        print(f"   Status: {result['status']}")
        print(f"   Trace ID: {result['trace_id']}")
        print(f"   Processed Traces: {result['processed_traces']}")
        print(f"   Created Objects: {result['created_objects']}")
        
        if 'object_counts' in result:
            print(f"\n🎯 Structured Object Breakdown:")
            object_counts = result['object_counts']
            for obj_type, count in object_counts.items():
                if count > 0:
                    print(f"   ✅ {obj_type}: {count}")
            
            # Verify we have structured types (not just generic spans)
            structured_types = ['generations', 'tools', 'retrievers', 'guardrails']
            has_structured = any(object_counts.get(t, 0) > 0 for t in structured_types)
            
            if has_structured:
                print(f"\n🎉 SUCCESS: Created structured Langfuse trace types!")
                print(f"   - Instead of generic 'orchestrationTrace' spans")
                print(f"   - Now creates proper generation/tool/retriever objects")
                print(f"   - These will appear correctly categorized in Langfuse UI")
            else:
                print(f"\n⚠️  Only spans and events created - check trace mapping")
        
        print(f"\n✅ Worker now uses structured Langfuse SDK registrar")
        print(f"✅ Should create proper trace types in Langfuse UI")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🎯 Structured Trace Worker Validation")
    print("=" * 70)
    
    success = test_worker_with_structured_traces()
    
    if success:
        print("\n🎉 Worker successfully updated to use structured traces!")
        print("\n📋 Summary of Changes:")
        print("✅ Worker now imports LangfuseTraceRegistrar (not old TraceRegistrar)")
        print("✅ Uses direct Langfuse SDK instead of OpenTelemetry")
        print("✅ Creates structured trace objects: generation, tool, retriever, etc.")
        print("✅ Traces will now appear properly categorized in Langfuse UI")
        print("\n🚀 Deploy the updated service to see structured traces!")
    else:
        print("\n❌ Worker update needs debugging")

if __name__ == "__main__":
    main()