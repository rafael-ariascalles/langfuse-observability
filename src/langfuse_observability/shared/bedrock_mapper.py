"""
Bedrock Agent trace to Langfuse trace mapper.
Maps Bedrock Agent traces to structured Langfuse trace types (generation, tool, retriever, etc.)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from loguru import logger

class BedrockToLangfuseMapper:
    """Maps Bedrock Agent traces to structured Langfuse trace objects."""
    
    def __init__(self):
        self.trace_mappings = {
            "orchestrationTrace": self._map_orchestration_trace,
            "preProcessingTrace": self._map_preprocessing_trace,
            "postProcessingTrace": self._map_postprocessing_trace,
            "guardrailTrace": self._map_guardrail_trace,
            "failureTrace": self._map_failure_trace,
        }
    
    def map_bedrock_trace(self, bedrock_trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Map a single Bedrock trace to one or more Langfuse objects.
        
        Args:
            bedrock_trace: Raw Bedrock Agent trace event
            
        Returns:
            List of Langfuse trace objects (generation, tool, span, etc.)
        """
        trace_content = bedrock_trace.get("trace", {})
        event_time = bedrock_trace.get("eventTime")
        
        langfuse_objects = []
        
        # Process each trace type
        for trace_type, mapper_func in self.trace_mappings.items():
            if trace_type in trace_content:
                try:
                    mapped_objects = mapper_func(trace_content[trace_type], event_time)
                    if isinstance(mapped_objects, list):
                        langfuse_objects.extend(mapped_objects)
                    elif mapped_objects:
                        langfuse_objects.append(mapped_objects)
                except Exception as e:
                    logger.error(f"Error mapping {trace_type}: {str(e)}")
                    # Create fallback event
                    langfuse_objects.append(self._create_fallback_event(trace_type, trace_content[trace_type], str(e)))
        
        return langfuse_objects
    
    def _map_orchestration_trace(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Map orchestration trace to generation + tool/retriever objects.
        
        orchestrationTrace contains:
        - modelInvocationInput/Output: Main LLM call → generation
        - rationale: Reasoning step → span
        - actionGroup: Function/API call → tool
        - knowledgeBaseLookup: Vector search → retriever
        - codeInterpreter: Code execution → tool
        """
        objects = []
        
        # Main LLM generation
        if "modelInvocationInput" in trace_data or "modelInvocationOutput" in trace_data:
            generation = self._create_generation_from_model_invocation(trace_data, event_time)
            if generation:
                objects.append(generation)
        
        # Rationale/reasoning span
        if "rationale" in trace_data:
            rationale_span = self._create_rationale_span(trace_data["rationale"], event_time)
            if rationale_span:
                objects.append(rationale_span)
        
        # Action group calls → tools
        if "actionGroupInvocations" in trace_data:
            for action in trace_data["actionGroupInvocations"]:
                tool_call = self._create_tool_from_action_group(action, event_time)
                if tool_call:
                    objects.append(tool_call)
        
        # Knowledge base lookups → retrievers
        if "knowledgeBaseLookupInput" in trace_data or "knowledgeBaseLookupOutput" in trace_data:
            retriever = self._create_retriever_from_knowledge_base(trace_data, event_time)
            if retriever:
                objects.append(retriever)
        
        # Code interpreter → tool
        if "codeInterpreterInvocations" in trace_data:
            for code_call in trace_data["codeInterpreterInvocations"]:
                code_tool = self._create_tool_from_code_interpreter(code_call, event_time)
                if code_tool:
                    objects.append(code_tool)
        
        return objects
    
    def _create_generation_from_model_invocation(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create Langfuse generation object from model invocation data."""
        model_input = trace_data.get("modelInvocationInput", {})
        model_output = trace_data.get("modelInvocationOutput", {})
        
        if not model_input and not model_output:
            return None
        
        # Extract input text
        input_text = ""
        if "text" in model_input:
            input_text = model_input["text"]
        elif "inferenceConfiguration" in model_input:
            # Sometimes the prompt is in inference config
            input_text = str(model_input.get("inferenceConfiguration", {}))
        
        # Extract output and usage
        output_text = ""
        usage_data = {}
        model_name = "bedrock-agent-model"
        
        if model_output:
            raw_response = model_output.get("rawResponse", {})
            if isinstance(raw_response, dict):
                # Extract text content
                if "content" in raw_response:
                    content = raw_response["content"]
                    if isinstance(content, list) and len(content) > 0:
                        output_text = str(content[0].get("text", ""))
                    elif isinstance(content, str):
                        output_text = content
                    else:
                        output_text = str(content)
                
                # Extract token usage
                if "usage" in raw_response:
                    usage = raw_response["usage"]
                    usage_data = {
                        "input": usage.get("inputTokens", 0),
                        "output": usage.get("outputTokens", 0),
                        "total": usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
                    }
                
                # Extract model info
                if "modelId" in raw_response:
                    model_name = raw_response["modelId"]
        
        generation = {
            "type": "generation",
            "name": "bedrock_agent_orchestration",
            "input": input_text or "No input captured",
            "output": output_text or "No output captured",
            "model": model_name,
            "metadata": {
                "component": "orchestration",
                "trace_id": model_input.get("traceId") or model_output.get("traceId"),
                "event_time": event_time,
                "raw_model_input": model_input,
                "raw_model_output": model_output
            }
        }
        
        if usage_data:
            generation["usage"] = usage_data
        
        return generation
    
    def _create_rationale_span(self, rationale_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create span for agent reasoning/rationale."""
        if not rationale_data:
            return None
        
        return {
            "type": "span",
            "name": "agent_reasoning",
            "input": rationale_data.get("text", ""),
            "metadata": {
                "component": "reasoning",
                "trace_id": rationale_data.get("traceId"),
                "event_time": event_time,
                "raw_rationale": rationale_data
            }
        }
    
    def _create_tool_from_action_group(self, action_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create tool object from action group invocation."""
        if not action_data:
            return None
        
        invocation_input = action_data.get("invocationInput", {})
        observation = action_data.get("observation", {})
        
        # Extract tool name and input
        tool_name = invocation_input.get("actionGroupName", "unknown_action")
        function_name = invocation_input.get("function", "unknown_function")
        parameters = invocation_input.get("parameters", {})
        
        # Extract output
        output_data = {}
        if observation:
            if "actionGroupInvocationOutput" in observation:
                output_data = observation["actionGroupInvocationOutput"]
            elif "finalResponse" in observation:
                output_data = observation["finalResponse"]
            else:
                output_data = observation
        
        return {
            "type": "tool",
            "name": f"{tool_name}.{function_name}",
            "input": {
                "function": function_name,
                "parameters": parameters
            },
            "output": output_data,
            "metadata": {
                "component": "action_group",
                "action_group_name": tool_name,
                "function_name": function_name,
                "trace_id": invocation_input.get("traceId") or observation.get("traceId"),
                "event_time": event_time,
                "raw_action": action_data
            }
        }
    
    def _create_retriever_from_knowledge_base(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create retriever object from knowledge base lookup."""
        kb_input = trace_data.get("knowledgeBaseLookupInput", {})
        kb_output = trace_data.get("knowledgeBaseLookupOutput", {})
        
        if not kb_input and not kb_output:
            return None
        
        # Extract query and results
        query = ""
        if kb_input:
            query = kb_input.get("text", "") or str(kb_input.get("retrievalFilter", {}))
        
        results = []
        if kb_output and "retrievedReferences" in kb_output:
            for ref in kb_output["retrievedReferences"]:
                result = {
                    "content": ref.get("content", {}).get("text", ""),
                    "metadata": ref.get("metadata", {}),
                    "location": ref.get("location", {}),
                    "score": ref.get("score")
                }
                results.append(result)
        
        return {
            "type": "retriever",
            "name": "bedrock_knowledge_base",
            "input": query,
            "output": results,
            "metadata": {
                "component": "knowledge_base",
                "knowledge_base_id": kb_input.get("knowledgeBaseId") or kb_output.get("knowledgeBaseId"),
                "retrieval_results_count": len(results),
                "trace_id": kb_input.get("traceId") or kb_output.get("traceId"),
                "event_time": event_time,
                "raw_kb_data": trace_data
            }
        }
    
    def _create_tool_from_code_interpreter(self, code_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create tool object from code interpreter invocation."""
        if not code_data:
            return None
        
        invocation_input = code_data.get("invocationInput", {})
        observation = code_data.get("observation", {})
        
        # Extract code and results
        code_input = invocation_input.get("code", "")
        code_output = ""
        files_created = []
        
        if observation:
            if "codeInterpreterInvocationOutput" in observation:
                output_data = observation["codeInterpreterInvocationOutput"]
                if "executionOutput" in output_data:
                    code_output = output_data["executionOutput"]
                if "files" in output_data:
                    files_created = output_data["files"]
        
        return {
            "type": "tool",
            "name": "code_interpreter",
            "input": {
                "code": code_input
            },
            "output": {
                "execution_output": code_output,
                "files_created": files_created
            },
            "metadata": {
                "component": "code_interpreter",
                "trace_id": invocation_input.get("traceId") or observation.get("traceId"),
                "event_time": event_time,
                "raw_code_data": code_data
            }
        }
    
    def _map_preprocessing_trace(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Map preprocessing trace to span."""
        if not trace_data:
            return None
        
        # Get model invocation data if available
        model_output = trace_data.get("modelInvocationOutput", {})
        parsed_response = model_output.get("parsedResponse", {}) if model_output else {}
        
        return {
            "type": "span",
            "name": "input_preprocessing",
            "input": trace_data.get("modelInvocationInput", {}).get("text", ""),
            "output": parsed_response.get("rationale", "") if parsed_response else "",
            "metadata": {
                "component": "preprocessing",
                "is_valid": parsed_response.get("isValid", True) if parsed_response else True,
                "trace_id": trace_data.get("modelInvocationInput", {}).get("traceId") or 
                           trace_data.get("modelInvocationOutput", {}).get("traceId"),
                "event_time": event_time,
                "raw_preprocessing": trace_data
            }
        }
    
    def _map_postprocessing_trace(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Map postprocessing trace to span."""
        if not trace_data:
            return None
        
        # Get model invocation data if available
        model_output = trace_data.get("modelInvocationOutput", {})
        parsed_response = model_output.get("parsedResponse", {}) if model_output else {}
        
        return {
            "type": "span",
            "name": "output_postprocessing",
            "input": trace_data.get("modelInvocationInput", {}).get("text", ""),
            "output": parsed_response.get("text", "") if parsed_response else "",
            "metadata": {
                "component": "postprocessing",
                "trace_id": trace_data.get("modelInvocationInput", {}).get("traceId") or 
                           trace_data.get("modelInvocationOutput", {}).get("traceId"),
                "event_time": event_time,
                "raw_postprocessing": trace_data
            }
        }
    
    def _map_guardrail_trace(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Map guardrail trace to guardrail object."""
        if not trace_data:
            return None
        
        action = trace_data.get("action", "NONE")
        trace_id = trace_data.get("traceId", "")
        outputs = trace_data.get("outputs", [])
        
        # Determine input/output based on trace_id (pre vs post)
        if "pre" in trace_id.lower():
            guardrail_type = "input_guardrail"
        else:
            guardrail_type = "output_guardrail"
        
        # Extract guardrail content
        guardrail_input = ""
        guardrail_output = ""
        
        if outputs and len(outputs) > 0:
            first_output = outputs[0]
            if isinstance(first_output, dict):
                guardrail_output = first_output.get("text", str(first_output))
            else:
                guardrail_output = str(first_output)
        
        return {
            "type": "guardrail",
            "name": guardrail_type,
            "input": guardrail_input,
            "output": {
                "action": action,
                "outputs": outputs,
                "blocked": action in ["BLOCKED", "INTERVENED"]
            },
            "metadata": {
                "component": "guardrail",
                "guardrail_action": action,
                "trace_id": trace_id,
                "event_time": event_time,
                "raw_guardrail": trace_data
            }
        }
    
    def _map_failure_trace(self, trace_data: Dict[str, Any], event_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Map failure trace to event."""
        if not trace_data:
            return None
        
        failure_reason = trace_data.get("failureReason", "Unknown failure")
        
        return {
            "type": "event",
            "name": "agent_failure",
            "input": "",
            "output": failure_reason,
            "level": "ERROR",
            "metadata": {
                "component": "failure",
                "failure_reason": failure_reason,
                "trace_id": trace_data.get("traceId"),
                "event_time": event_time,
                "raw_failure": trace_data
            }
        }
    
    def _create_fallback_event(self, trace_type: str, trace_data: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Create fallback event when mapping fails."""
        return {
            "type": "event",
            "name": f"unmapped_{trace_type}",
            "input": f"Failed to map {trace_type}: {error_message}",
            "output": json.dumps(trace_data, default=str),
            "level": "WARNING",
            "metadata": {
                "component": "mapper_fallback",
                "original_trace_type": trace_type,
                "mapping_error": error_message,
                "event_time": datetime.now(timezone.utc).isoformat()
            }
        }
    
    def create_agent_metadata(self, request) -> Dict[str, Any]:
        """Create metadata for the root agent trace."""
        return {
            "agent_id": request.agent_id,
            "agent_alias_id": request.agent_alias_id,
            "model_id": request.model_id,
            "session_id": request.session_id,
            "user_id": request.user_id,
            "tags": request.tags,
            "streaming": request.streaming,
            "duration_ms": request.duration_ms,
            "traces_count": len(request.traces)
        }