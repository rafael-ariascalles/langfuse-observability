"""Trace registrar for handling Langfuse trace registration."""

import json
import time
import base64
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to Python path for Docker
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from fastapi import HTTPException
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode, SpanKind
from loguru import logger

from langfuse_observability.shared.models import TraceRegistrationRequest
from langfuse_observability.shared.settings import settings


class TraceRegistrar:
    """Handles registering input/output with traces to Langfuse."""
    
    def __init__(self):
        self.tracer_provider = None
        self._setup_tracer_provider()
    
    def _setup_tracer_provider(self) -> None:
        """Set up OpenTelemetry tracer provider for Langfuse using global settings."""
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": "langfuse-trace-registration-service",
                "deployment.environment": settings.environment,
                "service.version": "1.0.0",
                "service.namespace": "bedrock-agents"
            })
            
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Create auth header for Langfuse
            auth_token = base64.b64encode(
                f"{settings.public_key}:{settings.secret_key}".encode()
            ).decode()
            
            # Setup OTLP exporter for Langfuse
            otlp_exporter = OTLPSpanExporter(
                endpoint=f"{settings.api_url}/api/public/otel/v1/traces",
                headers={"Authorization": f"Basic {auth_token}"},
                timeout=30
            )
            
            # Add batch span processor
            self.tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            
            logger.info(f"✅ Tracer provider configured for Langfuse at {settings.api_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup tracer provider: {str(e)}")
            raise
    
    def register_traces(self, request: TraceRegistrationRequest) -> Dict[str, Any]:
        """Register input/output with traces in Langfuse."""
        try:
            # Use the pre-configured tracer provider
            tracer = self.tracer_provider.get_tracer("bedrock-agent-trace-registrar")
            
            # Generate trace ID if not provided
            trace_id = request.trace_id or f"trace-{int(time.time())}"
            
            # Start root span for the complete agent interaction
            start_time = datetime.now(timezone.utc)
            
            with tracer.start_as_current_span(
                name=f"Bedrock Agent: {request.agent_id}",
                kind=SpanKind.CLIENT,
                attributes={
                    "gen_ai.operation.name": "agent",
                    "agent.id": request.agent_id,
                    "agent.alias_id": request.agent_alias_id,
                    "session.id": request.session_id,
                    "user.id": request.user_id,
                    "custom.trace_id": trace_id,
                    "tags": json.dumps(request.tags),
                    "stream_mode": request.streaming,
                    "llm.system": "aws.bedrock",
                    "llm.request.model": request.model_id or "bedrock-agent-default",
                    "gen_ai.prompt": request.input_text,
                    "gen_ai.completion": request.output_text,
                    "service.name": "langfuse-trace-registration-service",
                    "trace.start_time": start_time.isoformat(),
                }
            ) as root_span:
                
                # Add duration if provided
                if request.duration_ms:
                    root_span.set_attribute("trace.duration_ms", request.duration_ms)
                
                # Process each trace event
                processed_traces = []
                for i, trace_data in enumerate(request.traces):
                    try:
                        processed_trace = self._process_single_trace(
                            trace_data, root_span, tracer, i
                        )
                        processed_traces.append(processed_trace)
                    except Exception as e:
                        logger.error(f"Error processing trace {i}: {str(e)}")
                        root_span.record_exception(e)
                
                # Set completion attributes on root span
                end_time = datetime.now(timezone.utc)
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                root_span.set_attribute("trace.end_time", end_time.isoformat())
                root_span.set_attribute("trace.duration_ms", duration_ms)
                root_span.set_attribute("traces.count", len(processed_traces))
                root_span.set_status(Status(StatusCode.OK))
            
            # Force flush to ensure data is sent to Langfuse
            success = self.tracer_provider.force_flush(timeout_millis=10000)
            
            return {
                "status": "success",
                "trace_id": trace_id,
                "processed_traces": len(processed_traces),
                "flushed": success,
                "message": "Traces successfully sent to Langfuse"
            }
            
        except Exception as e:
            logger.error(f"❌ Error registering traces: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to register traces: {str(e)}")
    
    def _process_single_trace(
        self, 
        trace_data: Dict[str, Any], 
        parent_span, 
        tracer, 
        trace_index: int
    ) -> Dict[str, Any]:
        """Process a single trace event and create appropriate spans."""
        
        trace_content = trace_data.get("trace", {})
        event_time = trace_data.get("eventTime")
        
        # Determine trace type and create appropriate span
        span_name = "unknown_trace"
        span_attributes = {
            "trace.index": trace_index,
            "trace.type": "unknown"
        }
        
        if event_time:
            if isinstance(event_time, str):
                span_attributes["trace.event_time"] = event_time
            elif isinstance(event_time, datetime):
                span_attributes["trace.event_time"] = event_time.isoformat()
        
        # Handle different trace types
        if "orchestrationTrace" in trace_content:
            span_name = "orchestrationTrace"
            span_attributes["trace.type"] = "orchestration"
            self._add_orchestration_attributes(trace_content["orchestrationTrace"], span_attributes)
            
        elif "preProcessingTrace" in trace_content:
            span_name = "pre_processing"
            span_attributes["trace.type"] = "preprocessing"
            self._add_preprocessing_attributes(trace_content["preProcessingTrace"], span_attributes)
            
        elif "postProcessingTrace" in trace_content:
            span_name = "postProcessingTrace"
            span_attributes["trace.type"] = "postprocessing"
            self._add_postprocessing_attributes(trace_content["postProcessingTrace"], span_attributes)
            
        elif "guardrailTrace" in trace_content:
            span_name = "guardrail_trace"
            span_attributes["trace.type"] = "guardrail"
            self._add_guardrail_attributes(trace_content["guardrailTrace"], span_attributes)
            
        elif "failureTrace" in trace_content:
            span_name = "failure_trace"
            span_attributes["trace.type"] = "failure"
            self._add_failure_attributes(trace_content["failureTrace"], span_attributes)
        
        # Create span for this trace
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            context=trace.set_span_in_context(parent_span)
        ) as trace_span:
            
            # Add the full trace data as an event
            trace_span.add_event(
                name="bedrock_trace_data",
                attributes={
                    "trace.raw_data": json.dumps(trace_data),
                    "trace.processed_at": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return {
            "type": span_attributes["trace.type"],
            "span_name": span_name,
            "processed": True
        }
    
    def _add_orchestration_attributes(self, orchestration_trace: Dict, attributes: Dict):
        """Add orchestration-specific attributes."""
        if "modelInvocationInput" in orchestration_trace:
            model_input = orchestration_trace["modelInvocationInput"]
            attributes["llm.request.type"] = model_input.get("type", "unknown")
            if "text" in model_input:
                attributes["gen_ai.prompt"] = model_input["text"]
        
        if "modelInvocationOutput" in orchestration_trace:
            model_output = orchestration_trace["modelInvocationOutput"]
            if "rawResponse" in model_output:
                raw_response = model_output["rawResponse"]
                if "content" in raw_response:
                    attributes["gen_ai.completion"] = str(raw_response["content"])
                if "usage" in raw_response:
                    usage = raw_response["usage"]
                    attributes["gen_ai.usage.prompt_tokens"] = usage.get("inputTokens", 0)
                    attributes["gen_ai.usage.completion_tokens"] = usage.get("outputTokens", 0)
                    attributes["gen_ai.usage.total_tokens"] = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
    
    def _add_preprocessing_attributes(self, preprocessing_trace: Dict, attributes: Dict):
        """Add preprocessing-specific attributes."""
        if "modelInvocationOutput" in preprocessing_trace:
            model_output = preprocessing_trace["modelInvocationOutput"]
            if "parsedResponse" in model_output:
                parsed = model_output["parsedResponse"]
                attributes["preprocessing.is_valid"] = parsed.get("isValid", False)
                attributes["preprocessing.rationale"] = parsed.get("rationale", "")
    
    def _add_postprocessing_attributes(self, postprocessing_trace: Dict, attributes: Dict):
        """Add postprocessing-specific attributes."""
        if "modelInvocationOutput" in postprocessing_trace:
            model_output = postprocessing_trace["modelInvocationOutput"]
            if "parsedResponse" in model_output:
                parsed = model_output["parsedResponse"]
                attributes["postprocessing.text"] = parsed.get("text", "")
    
    def _add_guardrail_attributes(self, guardrail_trace: Dict, attributes: Dict):
        """Add guardrail-specific attributes."""
        attributes["guardrail.action"] = guardrail_trace.get("action", "NONE")
        attributes["guardrail.trace_id"] = guardrail_trace.get("traceId", "unknown")
        if "outputs" in guardrail_trace:
            outputs = guardrail_trace["outputs"]
            if isinstance(outputs, list) and len(outputs) > 0:
                attributes["guardrail.output"] = json.dumps(outputs[0])
    
    def _add_failure_attributes(self, failure_trace: Dict, attributes: Dict):
        """Add failure-specific attributes."""
        attributes["failure.trace_id"] = failure_trace.get("traceId", "unknown")
        attributes["failure.failure_reason"] = failure_trace.get("failureReason", "unknown")