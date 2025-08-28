"""
Direct Langfuse trace registrar using native Langfuse SDK.
Replaces OpenTelemetry with structured Langfuse trace types.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from langfuse import Langfuse
from loguru import logger

from .bedrock_mapper import BedrockToLangfuseMapper
from .models import TraceRegistrationRequest

class LangfuseTraceRegistrar:
    """Handles registering Bedrock Agent traces directly with Langfuse SDK."""
    
    def __init__(self, public_key: str, secret_key: str, api_url: str, 
                 project_name: str = "Amazon Bedrock Agents", 
                 environment: str = "development"):
        """Initialize Langfuse client and trace mapper."""
        try:
            # Initialize Langfuse client
            self.langfuse = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=api_url,
                debug=False  # Set to True for debugging
            )
            
            # Initialize trace mapper
            self.mapper = BedrockToLangfuseMapper()
            
            # Store configuration
            self.project_name = project_name
            self.environment = environment
            
            logger.info(f"✅ Langfuse client initialized for project '{project_name}' at {api_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Langfuse client: {str(e)}")
            raise
    
    def register_traces(self, request: TraceRegistrationRequest) -> Dict[str, Any]:
        """
        Register Bedrock Agent traces as structured Langfuse objects.
        
        Creates a hierarchical trace structure:
        - Root agent trace (contains the full conversation)
        - Child objects: generations, tools, retrievers, spans, etc.
        
        Args:
            request: Trace registration request with input/output and traces
            
        Returns:
            Result dictionary with trace ID and processing info
        """
        start_time = time.time()
        trace_id = request.trace_id or f"bedrock-{request.session_id}-{int(start_time)}"
        
        try:
            logger.info(f"🔄 Processing traces for agent {request.agent_id}, session {request.session_id}")
            
            # Process traces with hierarchical structure like OpenTelemetry implementation
            processed_objects = []
            total_generations = 0
            total_tools = 0
            total_retrievers = 0
            total_spans = 0
            total_guardrails = 0
            total_events = 0
            
            # Create L1 root span for the entire agent session
            with self.langfuse.start_as_current_span(
                name=f"Bedrock Agent: {request.agent_id}",
                input=request.input_text,
                output=request.output_text,
                metadata={
                    "agent_id": request.agent_id,
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "tags": json.dumps(request.tags or []),
                    "trace_type": "root_agent_trace",
                    "project_name": self.project_name,
                    "environment": self.environment
                }
            ) as root_span:
                
                for i, bedrock_trace in enumerate(request.traces):
                    try:
                        # Process each trace with hierarchical structure based on trace type
                        result = self._process_trace_hierarchically(bedrock_trace, root_span, i)
                        if result:
                            processed_objects.extend(result["objects"])
                            total_generations += result.get("generations", 0)
                            total_tools += result.get("tools", 0)
                            total_retrievers += result.get("retrievers", 0)
                            total_spans += result.get("spans", 0)
                            total_guardrails += result.get("guardrails", 0)
                            total_events += result.get("events", 0)
                    
                    except Exception as e:
                        logger.error(f"Error processing trace {i}: {str(e)}")
                        # Create fallback event for failed trace
                        with self.langfuse.start_as_current_span(
                            name=f"processing_error_{i}",
                            input=f"Failed to process Bedrock trace: {str(e)}",
                            output=str(bedrock_trace),
                            metadata={
                                "type": "event",
                                "level": "ERROR",
                                "component": "trace_processor",
                                "error_message": str(e),
                                "trace_index": i
                            }
                        ):
                            pass
                
                # Update root span with processing summary
                end_time = time.time()
                processing_duration = (end_time - start_time) * 1000
                
                root_span.update(
                    output=f"Successfully processed {len(processed_objects)} structured Langfuse objects from {len(request.traces)} Bedrock traces",
                    metadata={
                        "processing_duration_ms": processing_duration,
                        "processed_objects": {
                            "generations": total_generations,
                            "tools": total_tools,
                            "retrievers": total_retrievers,
                            "spans": total_spans,
                            "guardrails": total_guardrails,
                            "events": total_events,
                            "total": len(processed_objects)
                        }
                    }
                )
            
            # Flush to ensure data is sent to Langfuse
            self.langfuse.flush()
            
            logger.info(f"✅ Successfully registered {len(processed_objects)} Langfuse objects "
                       f"(gen:{total_generations}, tool:{total_tools}, ret:{total_retrievers}, "
                       f"span:{total_spans}, guard:{total_guardrails}, event:{total_events})")
            
            return {
                "status": "success",
                "trace_id": trace_id,
                "processed_traces": len(request.traces),
                "created_objects": len(processed_objects),
                "object_counts": {
                    "generations": total_generations,
                    "tools": total_tools,
                    "retrievers": total_retrievers,
                    "spans": total_spans,
                    "guardrails": total_guardrails,
                    "events": total_events
                },
                "processing_duration_ms": processing_duration,
                "message": f"Successfully created {len(processed_objects)} structured Langfuse objects"
            }
            
        except Exception as e:
            logger.error(f"❌ Error registering traces: {str(e)}")
            raise Exception(f"Failed to register traces in Langfuse: {str(e)}")
    
    def _create_root_agent_trace(self, request: TraceRegistrationRequest, trace_id: str):
        """Create the root agent trace that contains all child objects."""
        
        # Get agent metadata
        metadata = self.mapper.create_agent_metadata(request)
        metadata.update({
            "project_name": self.project_name,
            "environment": self.environment,
            "langfuse_version": "direct_sdk",
            "trace_created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create root trace using correct 2025 Langfuse SDK - use start_as_current_span for proper context
        root_trace = self.langfuse.start_as_current_span(
            name=f"bedrock_agent_{request.agent_id}",
            input=request.input_text,
            output=request.output_text,
            metadata={
                **metadata,
                "session_id": request.session_id,
                "user_id": request.user_id,
                "tags": json.dumps(request.tags or []),
                "trace_type": "root_agent_trace"
            }
        )
        
        logger.debug(f"Created root trace: {trace_id}")
        return root_trace
    
    def _process_trace_hierarchically(self, bedrock_trace: Dict[str, Any], root_span, trace_index: int) -> Dict[str, Any]:
        """
        Process Bedrock trace with hierarchical structure like OpenTelemetry implementation.
        
        Hierarchy:
        L1: Root span "Bedrock Agent: [agent_id]"
          L2: Major components (orchestrationTrace, preProcessingTrace, postProcessingTrace, guardrailTrace)  
            L3: Sub-operations (generation/llm, rationale, action_group, knowledgeBaseLookup)
              L4: Specific results (model output, action result, retrieval results)
        """
        trace_content = bedrock_trace.get("trace", {})
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        # Handle different trace types with proper hierarchy
        if "orchestrationTrace" in trace_content:
            result = self._process_orchestration_trace_hierarchically(trace_content["orchestrationTrace"], root_span)
            processed_objects.extend(result["objects"])
            self._update_counts(counts, result["counts"])
            
        elif "preProcessingTrace" in trace_content:
            result = self._process_preprocessing_trace_hierarchically(trace_content["preProcessingTrace"], root_span)
            processed_objects.extend(result["objects"])
            self._update_counts(counts, result["counts"])
            
        elif "postProcessingTrace" in trace_content:
            result = self._process_postprocessing_trace_hierarchically(trace_content["postProcessingTrace"], root_span)
            processed_objects.extend(result["objects"])
            self._update_counts(counts, result["counts"])
            
        elif "guardrailTrace" in trace_content:
            result = self._process_guardrail_trace_hierarchically(trace_content["guardrailTrace"], root_span)
            processed_objects.extend(result["objects"])
            self._update_counts(counts, result["counts"])
            
        elif "failureTrace" in trace_content:
            result = self._process_failure_trace_hierarchically(trace_content["failureTrace"], root_span)
            processed_objects.extend(result["objects"])
            self._update_counts(counts, result["counts"])
        
        return {"objects": processed_objects, **counts}
    
    def _process_orchestration_trace_hierarchically(self, orch_trace: Dict[str, Any], root_span) -> Dict[str, Any]:
        """Process orchestration trace with L2->L3->L4 hierarchy"""
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        # L2: Create orchestrationTrace span
        with self.langfuse.start_as_current_observation(
            name="orchestrationTrace",
            as_type="span",
            input=orch_trace.get("modelInvocationInput", {}).get("text", ""),
            output="",  # Will be updated when we get the output
            metadata={
                "component": "orchestration",
                "trace_type": "ORCHESTRATION",
                "level": "L2"
            }
        ) as l2_span:
            
            # L3: Handle LLM invocation (generation) - Use new 2025 SDK pattern
            if "modelInvocationInput" in orch_trace or "modelInvocationOutput" in orch_trace:
                with self.langfuse.start_as_current_observation(
                    name="llm",
                    as_type="generation",
                    model=self._extract_model_id(orch_trace),
                    input=orch_trace.get("modelInvocationInput", {}).get("text", ""),
                    output="",  # Will be updated
                    metadata={
                        "component": "llm",
                        "level": "L3",
                        "parent_component": "orchestration"
                    }
                ) as l3_generation:
                    
                    # L4: Model invocation output - Create separate child object for OpenTelemetry parity
                    if "modelInvocationOutput" in orch_trace:
                        model_output = orch_trace["modelInvocationOutput"]
                        output_text = self._extract_output_text(model_output)
                        usage_data = self._extract_usage_data(model_output)
                        
                        # Update L3 generation with basic output
                        l3_generation.update(
                            output=output_text,
                            usage_details=usage_data
                        )
                        
                        # L4: Create child span for model output details (OpenTelemetry parity)
                        with l3_generation.start_as_current_observation(
                            name="OrchestrationModelInvocationOutput",
                            as_type="span",
                            input="Model inference completed",
                            output=output_text,
                            metadata={
                                "component": "model_output",
                                "level": "L4", 
                                "parent_component": "llm",
                                "raw_response": model_output.get("parsedResponse", {}),
                                "filtered": model_output.get("parsedResponse", {}).get("isGuardrailFiltered", False),
                                "usage_details": usage_data
                            }
                        ):
                            processed_objects.append("span")  # L4 span
                            counts["spans"] += 1
                        
                        l2_span.update(output=output_text)  # Update L2 span output too
                        
                    processed_objects.append("generation")  # L3 generation
                    counts["generations"] += 1
            
            # L3: Handle rationale
            if "rationale" in orch_trace:
                with self.langfuse.start_as_current_observation(
                    name="rationale",
                    as_type="span",
                    input=orch_trace["rationale"].get("text", ""),
                    output="Agent reasoning completed",
                    metadata={
                        "component": "rationale",
                        "level": "L3",
                        "parent_component": "orchestration"
                    }
                ):
                    processed_objects.append("span")
                    counts["spans"] += 1
            
            # L3: Handle action groups (tools) - Check both invocationInput and observation
            action_group_input = orch_trace.get("invocationInput", {}).get("actionGroupInvocationInput")
            action_group_output = orch_trace.get("observation", {}).get("actionGroupInvocationOutput")
            
            if action_group_input or action_group_output:
                action_name = f"{action_group_input.get('actionGroupName', 'unknown')}" if action_group_input else "action_group"
                
                with self.langfuse.start_as_current_observation(
                    name=action_name,
                    as_type="tool",
                    input=action_group_input or {},
                    output="",
                    metadata={
                        "component": "action_group", 
                        "level": "L3",
                        "parent_component": "orchestration",
                        "tool_type": "action_group",
                        "api_path": action_group_input.get("apiPath") if action_group_input else None,
                        "execution_type": action_group_input.get("executionType") if action_group_input else None
                    }
                ) as l3_tool:
                    
                    # Update L3 tool with basic output
                    if action_group_output:
                        l3_tool.update(output=action_group_output)
                        
                        # L4: Create child span for action result details (OpenTelemetry parity)
                        with l3_tool.start_as_current_observation(
                            name="action_result",
                            as_type="span",
                            input="Action group execution completed",
                            output=action_group_output,
                            metadata={
                                "component": "action_result",
                                "level": "L4",
                                "parent_component": "action_group",
                                "action_group_name": action_group_input.get("actionGroupName") if action_group_input else None,
                                "api_path": action_group_input.get("apiPath") if action_group_input else None,
                                "execution_result": action_group_output
                            }
                        ):
                            processed_objects.append("span")  # L4 span
                            counts["spans"] += 1
                        
                    processed_objects.append("tool")  # L3 tool
                    counts["tools"] += 1
            
            # L3: Handle knowledge base lookups (retrievers) - Check both invocationInput and observation
            kb_input = orch_trace.get("invocationInput", {}).get("knowledgeBaseLookupInput")
            kb_output = orch_trace.get("observation", {}).get("knowledgeBaseLookupOutput")
            
            if kb_input or kb_output:
                with self.langfuse.start_as_current_observation(
                    name="knowledgeBaseLookup",
                    as_type="retriever",
                    input=kb_input.get("text", "") if kb_input else "",
                    output="",
                    metadata={
                        "component": "knowledge_base",
                        "level": "L3", 
                        "parent_component": "orchestration",
                        "knowledge_base_id": kb_input.get("knowledgeBaseId") if kb_input else None,
                        "retrieval_type": "semantic_search"
                    }
                ) as l3_retriever:
                    
                    # Update L3 retriever with basic output
                    if kb_output:
                        results = kb_output.get("retrievedReferences", [])
                        l3_retriever.update(output={"retrieved_documents": len(results), "results": results})
                        
                        # L4: Create child span for retrieval results details (OpenTelemetry parity)
                        with l3_retriever.start_as_current_observation(
                            name="knowledgeBaseLookupOutput",
                            as_type="span",
                            input="Knowledge base search completed",
                            output={"retrieved_documents": len(results), "results": results},
                            metadata={
                                "component": "retrieval_results",
                                "level": "L4",
                                "parent_component": "knowledge_base",
                                "knowledge_base_id": kb_input.get("knowledgeBaseId") if kb_input else None,
                                "query": kb_input.get("text") if kb_input else None,
                                "results_count": len(results),
                                "retrieved_references": results
                            }
                        ):
                            processed_objects.append("span")  # L4 span
                            counts["spans"] += 1
                        
                    processed_objects.append("retriever")  # L3 retriever
                    counts["retrievers"] += 1
            
            # L3: Handle code interpreter
            if "codeInterpreterInvocations" in orch_trace:
                for code_call in orch_trace["codeInterpreterInvocations"]:
                    with self.langfuse.start_as_current_span(
                        name="CodeInterpreter",
                        input=code_call.get("invocationInput", {}).get("code", ""),
                        output="",
                        metadata={
                            "component": "code_interpreter",
                            "level": "L3",
                            "parent_component": "orchestration", 
                            "type": "tool",
                            "langfuse_object_type": "tool"
                        }
                    ) as l3_code:
                        
                        # Update L3 code interpreter with basic output
                        if "observation" in code_call:
                            output_data = code_call["observation"].get("codeInterpreterInvocationOutput", {})
                            l3_code.update(output=output_data)
                            
                            # L4: Create child span for code interpreter result details (OpenTelemetry parity)
                            with l3_code.start_as_current_observation(
                                name="code_interpreter_result",
                                as_type="span",
                                input="Code execution completed",
                                output=output_data,
                                metadata={
                                    "component": "code_result",
                                    "level": "L4",
                                    "parent_component": "code_interpreter",
                                    "execution_result": output_data,
                                    "code_input": code_call.get("invocationInput", {}).get("code", "")
                                }
                            ):
                                processed_objects.append("span")  # L4 span
                                counts["spans"] += 1
                            
                        processed_objects.append("tool")  # L3 tool
                        counts["tools"] += 1
            
            # L3: Handle final response
            final_response = orch_trace.get("observation", {}).get("finalResponse")
            if final_response:
                with self.langfuse.start_as_current_observation(
                    name="finalResponse",
                    as_type="span",
                    input="Processing final response for user",
                    output=final_response.get("text", ""),
                    metadata={
                        "component": "final_response",
                        "level": "L3",
                        "parent_component": "orchestration",
                        "response_type": orch_trace.get("observation", {}).get("type", "FINISH")
                    }
                ):
                    processed_objects.append("span")
                    counts["spans"] += 1
        
        return {"objects": processed_objects, "counts": counts}
    
    def _process_preprocessing_trace_hierarchically(self, prep_trace: Dict[str, Any], root_span) -> Dict[str, Any]:
        """Process preprocessing trace with L2->L3->L4 hierarchy"""
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        # L2: Create preprocessing span
        with self.langfuse.start_as_current_observation(
            name="pre_processing",
            as_type="span",
            input=prep_trace.get("modelInvocationInput", {}).get("text", ""),
            output="",
            metadata={
                "component": "preprocessing",
                "trace_type": "PRE_PROCESSING", 
                "level": "L2"
            }
        ) as l2_span:
            
            # L3: Handle LLM invocation if present
            if "modelInvocationInput" in prep_trace or "modelInvocationOutput" in prep_trace:
                with self.langfuse.start_as_current_observation(
                    name="llm",
                    as_type="generation",
                    model=self._extract_model_id(prep_trace),
                    input=prep_trace.get("modelInvocationInput", {}).get("text", ""),
                    output="",
                    metadata={
                        "component": "llm",
                        "level": "L3",
                        "parent_component": "preprocessing"
                    }
                ) as l3_generation:
                    
                    # L4: Preprocessing model output (OpenTelemetry parity)
                    if "modelInvocationOutput" in prep_trace:
                        model_output = prep_trace["modelInvocationOutput"]
                        output_text = self._extract_output_text(model_output)
                        usage_data = self._extract_usage_data(model_output)
                        
                        # Update L3 generation
                        l3_generation.update(
                            output=output_text,
                            usage_details=usage_data
                        )
                        
                        # L4: Create child span for preprocessing model output details
                        with l3_generation.start_as_current_observation(
                            name="PreProcessingModelInvocationOutput",
                            as_type="span",
                            input="Preprocessing model inference completed",
                            output=output_text,
                            metadata={
                                "component": "model_output",
                                "level": "L4",
                                "parent_component": "llm",
                                "trace_type": "PRE_PROCESSING",
                                "raw_response": model_output.get("parsedResponse", {}),
                                "usage_details": usage_data
                            }
                        ):
                            processed_objects.append("span")  # L4 span
                            counts["spans"] += 1
                        
                        l2_span.update(output=output_text)
                        
                    processed_objects.append("generation")  # L3 generation
                    counts["generations"] += 1
        
        return {"objects": processed_objects, "counts": counts}
    
    def _process_postprocessing_trace_hierarchically(self, post_trace: Dict[str, Any], root_span) -> Dict[str, Any]:
        """Process postprocessing trace with L2->L3->L4 hierarchy"""
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        # L2: Create postprocessing span
        with self.langfuse.start_as_current_observation(
            name="postProcessingTrace", 
            as_type="span",
            input=post_trace.get("modelInvocationInput", {}).get("text", ""),
            output="",
            metadata={
                "component": "postprocessing",
                "trace_type": "POST_PROCESSING",
                "level": "L2"
            }
        ) as l2_span:
            
            # L3: Handle LLM invocation
            if "modelInvocationInput" in post_trace or "modelInvocationOutput" in post_trace:
                with self.langfuse.start_as_current_observation(
                    name="llm",
                    as_type="generation",
                    model=self._extract_model_id(post_trace),
                    input=post_trace.get("modelInvocationInput", {}).get("text", ""),
                    output="",
                    metadata={
                        "component": "llm",
                        "level": "L3", 
                        "parent_component": "postprocessing"
                    }
                ) as l3_generation:
                    
                    # L4: Postprocessing model output (OpenTelemetry parity)
                    if "modelInvocationOutput" in post_trace:
                        model_output = post_trace["modelInvocationOutput"]
                        output_text = self._extract_output_text(model_output)
                        usage_data = self._extract_usage_data(model_output)
                        
                        # Update L3 generation
                        l3_generation.update(
                            output=output_text,
                            usage_details=usage_data
                        )
                        
                        # L4: Create child span for postprocessing model output details
                        with l3_generation.start_as_current_observation(
                            name="PostProcessingModelInvocationOutput",
                            as_type="span",
                            input="Postprocessing model inference completed",
                            output=output_text,
                            metadata={
                                "component": "model_output",
                                "level": "L4",
                                "parent_component": "llm",
                                "trace_type": "POST_PROCESSING",
                                "raw_response": model_output.get("parsedResponse", {}),
                                "usage_details": usage_data
                            }
                        ):
                            processed_objects.append("span")  # L4 span
                            counts["spans"] += 1
                        
                        l2_span.update(output=output_text)
                        
                    processed_objects.append("generation")  # L3 generation
                    counts["generations"] += 1
        
        return {"objects": processed_objects, "counts": counts}
    
    def _process_guardrail_trace_hierarchically(self, guard_trace: Dict[str, Any], root_span) -> Dict[str, Any]:
        """Process guardrail trace with L2 hierarchy"""
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        action = guard_trace.get("action", "NONE")
        trace_id = guard_trace.get("traceId", "")
        
        # Determine guardrail type
        guardrail_name = "guardrail_pre" if "pre" in trace_id else "guardrail_post"
        
        # L2: Create guardrail span using native 2025 SDK guardrail type
        with self.langfuse.start_as_current_observation(
            name=guardrail_name,
            as_type="guardrail",
            input="",
            output=f"Action: {action}",
            metadata={
                "component": "guardrail",
                "level": "L2",
                "guardrail_action": action,
                "blocked": action in ["BLOCKED", "INTERVENED"],
                "guardrail_type": "bedrock_agent",
                "input_assessments": guard_trace.get("inputAssessments", []),
                "output_assessments": guard_trace.get("outputAssessments", [])
            }
        ):
            processed_objects.append("guardrail")
            counts["guardrails"] += 1
        
        return {"objects": processed_objects, "counts": counts}
    
    def _process_failure_trace_hierarchically(self, failure_trace: Dict[str, Any], root_span) -> Dict[str, Any]:
        """Process failure trace with L2 hierarchy"""
        processed_objects = []
        counts = {"generations": 0, "tools": 0, "retrievers": 0, "spans": 0, "guardrails": 0, "events": 0}
        
        failure_reason = failure_trace.get("failureReason", "Unknown failure")
        
        # L2: Create failure event span
        with self.langfuse.start_as_current_span(
            name="agent_failure",
            input="",
            output=failure_reason,
            metadata={
                "component": "failure",
                "level": "L2",
                "failure_reason": failure_reason,
                "type": "event",
                "level": "ERROR",
                "langfuse_object_type": "event"
            }
        ):
            processed_objects.append("event")
            counts["events"] += 1
        
        return {"objects": processed_objects, "counts": counts}
    
    def _extract_model_id(self, trace_data: Dict[str, Any]) -> str:
        """Extract model ID from trace data"""
        if "modelInvocationOutput" in trace_data:
            raw_response = trace_data["modelInvocationOutput"].get("rawResponse", {})
            if isinstance(raw_response, dict):
                return raw_response.get("modelId", "bedrock-agent-model")
        return "bedrock-agent-model"
    
    def _extract_output_text(self, model_output: Dict[str, Any]) -> str:
        """Extract output text from model invocation output"""
        raw_response = model_output.get("rawResponse", {})
        if isinstance(raw_response, dict) and "content" in raw_response:
            content = raw_response["content"]
            if isinstance(content, list) and len(content) > 0:
                return str(content[0].get("text", ""))
            elif isinstance(content, str):
                return content
        return ""
    
    def _extract_usage_data(self, model_output: Dict[str, Any]) -> Dict[str, int]:
        """Extract usage data from model invocation output"""
        raw_response = model_output.get("rawResponse", {})
        if isinstance(raw_response, dict) and "usage" in raw_response:
            usage = raw_response["usage"]
            return {
                "input": usage.get("inputTokens", 0),
                "output": usage.get("outputTokens", 0),
                "total": usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
            }
        return {}
    
    def _update_counts(self, target_counts: Dict[str, int], source_counts: Dict[str, int]):
        """Update target counts with source counts"""
        for key, value in source_counts.items():
            target_counts[key] = target_counts.get(key, 0) + value
    
    def _create_langfuse_object_context(self, obj_data: Dict[str, Any], trace_index: int):
        """Create the appropriate Langfuse object context manager based on type."""
        
        obj_type = obj_data.get("type")
        obj_name = obj_data.get("name", f"bedrock_{obj_type}_{trace_index}")
        
        if obj_type == "generation":
            return self._create_generation_context(obj_data, obj_name)
        elif obj_type in ["tool", "retriever", "span", "guardrail", "event"]:
            return self._create_span_context(obj_data, obj_name, obj_type)
        else:
            logger.warning(f"Unknown object type: {obj_type}")
            return self._create_span_context(obj_data, f"unknown_{obj_name}", "event")
    
    def _create_generation_context(self, obj_data: Dict[str, Any], name: str):
        """Create generation context manager."""
        
        # Build generation parameters
        generation_params = {
            "name": name,
            "input": obj_data.get("input"),
            "output": obj_data.get("output"),
            "model": obj_data.get("model", "bedrock-agent-model"),
            "metadata": obj_data.get("metadata", {})
        }
        
        # Create generation context
        generation_context = self.langfuse.start_as_current_generation(**generation_params)
        
        # Add usage if available (needs to be done after creation)
        usage_data = obj_data.get("usage")
        if usage_data:
            # Usage will be updated within the context
            pass
            
        logger.debug(f"Created generation context: {name}")
        return generation_context
    
    def _create_span_context(self, obj_data: Dict[str, Any], name: str, span_type: str):
        """Create span context manager."""
        
        metadata = {
            **obj_data.get("metadata", {}),
            "type": span_type,
            "langfuse_object_type": span_type
        }
        
        if span_type == "event":
            metadata["level"] = obj_data.get("level", "DEFAULT")
            
        span_context = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata=metadata
        )
        
        logger.debug(f"Created {span_type} span context: {name}")
        return span_context
    
    def _create_langfuse_object(self, parent_trace, obj_data: Dict[str, Any], trace_index: int):
        """Create the appropriate Langfuse object based on type."""
        
        obj_type = obj_data.get("type")
        obj_name = obj_data.get("name", f"bedrock_{obj_type}_{trace_index}")
        
        try:
            if obj_type == "generation":
                return self._create_generation(parent_trace, obj_data, obj_name)
            elif obj_type == "tool":
                return self._create_tool(parent_trace, obj_data, obj_name)
            elif obj_type == "retriever":
                return self._create_retriever(parent_trace, obj_data, obj_name)
            elif obj_type == "span":
                return self._create_span(parent_trace, obj_data, obj_name)
            elif obj_type == "guardrail":
                return self._create_guardrail(parent_trace, obj_data, obj_name)
            elif obj_type == "event":
                return self._create_event(parent_trace, obj_data, obj_name)
            else:
                logger.warning(f"Unknown object type: {obj_type}")
                return self._create_event(parent_trace, obj_data, f"unknown_{obj_name}")
        
        except Exception as e:
            logger.error(f"Error creating {obj_type} object: {str(e)}")
            return None
    
    def _create_generation(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse generation object for LLM calls."""
        
        # Build generation parameters
        generation_params = {
            "name": name,
            "input": obj_data.get("input"),
            "output": obj_data.get("output"),
            "model": obj_data.get("model", "bedrock-agent-model"),
            "metadata": obj_data.get("metadata", {})
        }
        
        # Add token usage if available
        usage_data = obj_data.get("usage")
        if usage_data:
            generation_params["usage"] = {
                "input": usage_data.get("input", 0),
                "output": usage_data.get("output", 0),
                "total": usage_data.get("total", 0)
            }
        
        # Create generation using correct 2025 Langfuse SDK syntax
        generation = self.langfuse.start_as_current_generation(
            name=generation_params["name"],
            input=generation_params["input"],
            output=generation_params["output"],
            model=generation_params["model"],
            metadata=generation_params["metadata"]
        )
        
        # Add usage if available
        if "usage" in generation_params:
            generation.update(
                usage_details=generation_params["usage"]
            )
        
        logger.debug(f"Created generation: {name}")
        return generation
    
    def _create_tool(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse tool object for external calls."""
        
        # Tools are spans with tool-specific metadata - use current context
        tool = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata={
                **obj_data.get("metadata", {}),
                "type": "tool",  # Langfuse categorization
                "langfuse_object_type": "tool"
            }
        )
        
        logger.debug(f"Created tool span: {name}")
        return tool
    
    def _create_retriever(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse retriever object for data retrieval."""
        
        # Retrievers are spans with retriever-specific metadata - use current context
        retriever = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata={
                **obj_data.get("metadata", {}),
                "type": "retriever",  # Langfuse categorization
                "langfuse_object_type": "retriever"
            }
        )
        
        logger.debug(f"Created retriever span: {name}")
        return retriever
    
    def _create_span(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse span object for durations."""
        
        span = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata=obj_data.get("metadata", {})
        )
        
        logger.debug(f"Created span: {name}")
        return span
    
    def _create_guardrail(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse guardrail object for content protection."""
        
        # Guardrails are spans with guardrail-specific metadata - use current context
        guardrail = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata={
                **obj_data.get("metadata", {}),
                "type": "guardrail",  # Langfuse categorization
                "langfuse_object_type": "guardrail"
            }
        )
        
        logger.debug(f"Created guardrail span: {name}")
        return guardrail
    
    def _create_event(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse event object for discrete events."""
        
        # Events are created as child spans with event-specific metadata - use current context
        event = self.langfuse.start_as_current_span(
            name=name,
            input=obj_data.get("input", ""),
            output=obj_data.get("output", ""),
            metadata={
                **obj_data.get("metadata", {}),
                "type": "event",
                "level": obj_data.get("level", "DEFAULT"),
                "langfuse_object_type": "event"
            }
        )
        
        logger.debug(f"Created event: {name}")
        return event
    
    def _create_fallback_event(self, parent_trace, bedrock_trace: Dict[str, Any], error_msg: str, trace_index: int):
        """Create fallback event when trace processing fails."""
        
        fallback_event = self.langfuse.start_as_current_span(
            name=f"processing_error_{trace_index}",
            input=f"Failed to process Bedrock trace: {error_msg}",
            output=str(bedrock_trace),
            metadata={
                "type": "event",
                "level": "ERROR",
                "component": "trace_processor",
                "error_message": error_msg,
                "trace_index": trace_index,
                "original_trace": bedrock_trace,
                "langfuse_object_type": "event"
            }
        )
        
        logger.debug(f"Created fallback event for trace {trace_index}")
        return fallback_event
    
def create_langfuse_registrar(settings) -> LangfuseTraceRegistrar:
    """Factory function to create LangfuseTraceRegistrar from settings."""
    return LangfuseTraceRegistrar(
        public_key=settings.public_key,
        secret_key=settings.secret_key,
        api_url=settings.api_url,
        project_name=settings.project_name,
        environment=settings.environment
    )