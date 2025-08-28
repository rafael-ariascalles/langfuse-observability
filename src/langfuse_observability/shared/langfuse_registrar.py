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
            
            # Create root agent trace
            root_trace = self._create_root_agent_trace(request, trace_id)
            
            # Process each Bedrock trace and create Langfuse objects
            processed_objects = []
            total_generations = 0
            total_tools = 0
            total_retrievers = 0
            total_spans = 0
            total_guardrails = 0
            total_events = 0
            
            for i, bedrock_trace in enumerate(request.traces):
                try:
                    # Map Bedrock trace to Langfuse objects
                    langfuse_objects = self.mapper.map_bedrock_trace(bedrock_trace)
                    
                    for obj in langfuse_objects:
                        # Create the appropriate Langfuse object
                        created_obj = self._create_langfuse_object(root_trace, obj, i)
                        if created_obj:
                            processed_objects.append(created_obj)
                            
                            # Count object types
                            obj_type = obj.get("type", "unknown")
                            if obj_type == "generation":
                                total_generations += 1
                            elif obj_type == "tool":
                                total_tools += 1
                            elif obj_type == "retriever":
                                total_retrievers += 1
                            elif obj_type == "span":
                                total_spans += 1
                            elif obj_type == "guardrail":
                                total_guardrails += 1
                            elif obj_type == "event":
                                total_events += 1
                
                except Exception as e:
                    logger.error(f"Error processing trace {i}: {str(e)}")
                    # Create fallback event for failed trace
                    self._create_fallback_event(root_trace, bedrock_trace, str(e), i)
            
            # Update root trace with processing summary
            end_time = time.time()
            processing_duration = (end_time - start_time) * 1000
            
            # Create a summary span to capture the processing results
            root_trace.start_span(
                name="trace_processing_summary",
                input=f"Processed {len(request.traces)} Bedrock Agent traces",
                output=f"Created {len(processed_objects)} structured Langfuse objects",
                metadata={
                    "type": "event",
                    "level": "INFO",
                    "processing_duration_ms": processing_duration,
                    "processed_objects": {
                        "generations": total_generations,
                        "tools": total_tools,
                        "retrievers": total_retrievers,
                        "spans": total_spans,
                        "guardrails": total_guardrails,
                        "events": total_events,
                        "total": len(processed_objects)
                    },
                    "langfuse_object_type": "event"
                }
            ).end()
            
            # End the root trace and flush to ensure data is sent to Langfuse
            root_trace.end()
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
        
        # Create root trace using correct Langfuse SDK syntax
        root_trace = self.langfuse.start_span(
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
        
        # Create generation using correct Langfuse SDK syntax
        generation = self.langfuse.start_generation(
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
        
        # Tools are spans with tool-specific metadata
        tool = parent_trace.start_span(
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
        
        # Retrievers are spans with retriever-specific metadata
        retriever = parent_trace.start_span(
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
        
        span = parent_trace.start_span(
            name=name,
            input=obj_data.get("input"),
            output=obj_data.get("output"),
            metadata=obj_data.get("metadata", {})
        )
        
        logger.debug(f"Created span: {name}")
        return span
    
    def _create_guardrail(self, parent_trace, obj_data: Dict[str, Any], name: str):
        """Create Langfuse guardrail object for content protection."""
        
        # Guardrails are spans with guardrail-specific metadata
        guardrail = parent_trace.start_span(
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
        
        # Events are created as child spans with event-specific metadata
        event = parent_trace.start_span(
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
        
        fallback_event = parent_trace.start_span(
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