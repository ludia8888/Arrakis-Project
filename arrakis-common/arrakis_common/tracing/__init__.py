"""
Production-ready distributed tracing configuration for Arrakis microservices.
Provides consistent tracing setup across all services with Jaeger backend.
"""

import logging
import os
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes

# Configure logging
logger = logging.getLogger(__name__)


class TracingConfig:
 """Configuration for distributed tracing."""

 def __init__(self, service_name: str, environment: str = None):
 self.service_name = service_name
 self.environment = environment or os.getenv("APP_ENV", "development")

 # Jaeger configuration
 self.jaeger_endpoint = os.getenv(
 "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
 )
 self.jaeger_agent_host = os.getenv("JAEGER_AGENT_HOST", "localhost")
 self.jaeger_agent_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

 # Sampling configuration
 self.sampling_rate = float(os.getenv("TRACING_SAMPLING_RATE", "1.0"))
 self.max_tag_value_length = int(
 os.getenv("JAEGER_MAX_TAG_VALUE_LENGTH", "1024")
 )

 # Service metadata
 self.service_version = os.getenv("SERVICE_VERSION", "1.0.0")
 self.service_instance_id = os.getenv("HOSTNAME", "unknown")

 # Custom tags
 self.custom_tags = self._load_custom_tags()

 def _load_custom_tags(self) -> Dict[str, str]:
 """Load custom tags from environment variables."""
 custom_tags = {}

 # Add standard tags
 custom_tags.update(
 {
 "service.namespace": "arrakis",
 "service.environment": self.environment,
 "service.version": self.service_version,
 "service.instance.id": self.service_instance_id,
 "deployment.environment": self.environment,
 }
 )

 # Add any custom tags from environment
 for key, value in os.environ.items():
 if key.startswith("TRACING_TAG_"):
 tag_name = key[12:].lower() # Remove TRACING_TAG_ prefix
 custom_tags[tag_name] = value

 return custom_tags


def setup_tracing(
 service_name: str,
 environment: str = None,
 enable_console_export: bool = False,
 custom_resource_attributes: Dict[str, Any] = None,
) -> TracerProvider:
 """
 Set up distributed tracing for a microservice.

 Args:
 service_name: Name of the service
 environment: Environment (development, staging, production)
 enable_console_export: Whether to also export to console
 custom_resource_attributes: Additional resource attributes

 Returns:
 TracerProvider instance
 """
 config = TracingConfig(service_name, environment)

 logger.info(f"Setting up tracing for {service_name} in {config.environment}")

 # Create resource with service information
 resource_attributes = {
 ResourceAttributes.SERVICE_NAME: service_name,
 ResourceAttributes.SERVICE_VERSION: config.service_version,
 ResourceAttributes.SERVICE_INSTANCE_ID: config.service_instance_id,
 ResourceAttributes.DEPLOYMENT_ENVIRONMENT: config.environment,
 ResourceAttributes.SERVICE_NAMESPACE: "arrakis",
 }

 # Add custom resource attributes
 if custom_resource_attributes:
 resource_attributes.update(custom_resource_attributes)

 # Add custom tags
 resource_attributes.update(config.custom_tags)

 resource = Resource.create(resource_attributes)

 # Create tracer provider
 tracer_provider = TracerProvider(resource = resource)

 # Set up Jaeger exporter
 jaeger_exporter = JaegerExporter(
 agent_host_name = config.jaeger_agent_host,
 agent_port = config.jaeger_agent_port,
 collector_endpoint = config.jaeger_endpoint,
 max_tag_value_length = config.max_tag_value_length,
 )

 # Create span processor for Jaeger
 jaeger_processor = BatchSpanProcessor(
 jaeger_exporter,
 max_queue_size = 2048,
 schedule_delay_millis = 5000,
 export_timeout_millis = 30000,
 max_export_batch_size = 512,
 )

 tracer_provider.add_span_processor(jaeger_processor)

 # Optionally add console exporter for debugging
 if enable_console_export or config.environment == "development":
 console_exporter = ConsoleSpanExporter()
 console_processor = BatchSpanProcessor(console_exporter)
 tracer_provider.add_span_processor(console_processor)

 # Set global tracer provider
 trace.set_tracer_provider(tracer_provider)

 # Set up propagation
 set_global_textmap(JaegerPropagator())

 logger.info(f"Tracing configured successfully for {service_name}")

 return tracer_provider


def instrument_service(app = None, db_engine = None, redis_client = None) -> None:
 """
 Instrument a service with automatic tracing for common libraries.

 Args:
 app: FastAPI application instance
 db_engine: SQLAlchemy engine
 redis_client: Redis client
 """
 logger.info("Instrumenting service with automatic tracing...")

 # Instrument HTTP requests
 RequestsInstrumentor().instrument()
 AioHttpClientInstrumentor().instrument()

 # Instrument FastAPI if provided
 if app:
 FastAPIInstrumentor.instrument_app(app)
 logger.info("FastAPI instrumentation enabled")

 # Instrument database if provided
 if db_engine:
 SQLAlchemyInstrumentor().instrument(engine = db_engine)
 logger.info("SQLAlchemy instrumentation enabled")

 # Instrument Redis if provided
 if redis_client:
 RedisInstrumentor().instrument(redis_client = redis_client)
 logger.info("Redis instrumentation enabled")

 # Instrument logging
 LoggingInstrumentor().instrument()

 logger.info("Service instrumentation complete")


def create_custom_span(
 tracer_name: str,
 span_name: str,
 attributes: Dict[str, Any] = None,
 kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
 """
 Create a custom span for manual instrumentation.

 Args:
 tracer_name: Name of the tracer
 span_name: Name of the span
 attributes: Custom attributes to add to the span
 kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)

 Returns:
 Span context manager
 """
 tracer = trace.get_tracer(tracer_name)

 span = tracer.start_span(span_name, kind = kind)

 if attributes:
 for key, value in attributes.items():
 span.set_attribute(key, str(value))

 return span


def add_span_attributes(span: trace.Span, attributes: Dict[str, Any]) -> None:
 """
 Add attributes to an existing span.

 Args:
 span: The span to add attributes to
 attributes: Dictionary of attributes to add
 """
 for key, value in attributes.items():
 span.set_attribute(key, str(value))


def set_span_error(span: trace.Span, error: Exception) -> None:
 """
 Mark a span as having an error and add error details.

 Args:
 span: The span to mark as error
 error: The exception that occurred
 """
 span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
 span.set_attribute("error", True)
 span.set_attribute("error.type", type(error).__name__)
 span.set_attribute("error.message", str(error))


class TracingMiddleware:
 """Custom tracing middleware for additional context."""

 def __init__(self, service_name: str):
 self.service_name = service_name
 self.tracer = trace.get_tracer(service_name)

 async def __call__(self, request, call_next):
 """Process request with tracing context."""
 # Extract route information
 route = getattr(request, "route", None)
 if route:
 operation_name = f"{request.method} {route.path}"
 else:
 operation_name = f"{request.method} {request.url.path}"

 # Create span for the request
 with self.tracer.start_as_current_span(
 operation_name, kind = trace.SpanKind.SERVER
 ) as span:
 # Add request attributes
 span.set_attribute("http.method", request.method)
 span.set_attribute("http.url", str(request.url))
 span.set_attribute("http.scheme", request.url.scheme)
 span.set_attribute("http.host", request.url.hostname or "unknown")
 span.set_attribute("http.target", request.url.path)

 # Add user agent if available
 user_agent = request.headers.get("user-agent")
 if user_agent:
 span.set_attribute("http.user_agent", user_agent)

 # Add custom headers as attributes
 for header_name in ["x-request-id", "x-trace-id", "x-user-id"]:
 header_value = request.headers.get(header_name)
 if header_value:
 span.set_attribute(
 f"http.request.header.{header_name}", header_value
 )

 try:
 # Process request
 response = await call_next(request)

 # Add response attributes
 span.set_attribute("http.status_code", response.status_code)
 span.set_attribute(
 "http.response.size",
 response.headers.get("content-length", "unknown"),
 )

 # Mark as error if status code indicates error
 if response.status_code >= 400:
 span.set_status(
 trace.Status(
 trace.StatusCode.ERROR, f"HTTP {response.status_code}"
 )
 )
 span.set_attribute("error", True)

 return response

 except Exception as e:
 # Handle exceptions
 set_span_error(span, e)
 raise


def get_current_trace_id() -> Optional[str]:
 """Get the current trace ID if available."""
 span = trace.get_current_span()
 if span.is_recording():
 trace_id = span.get_span_context().trace_id
 return format(trace_id, "032x")
 return None


def get_current_span_id() -> Optional[str]:
 """Get the current span ID if available."""
 span = trace.get_current_span()
 if span.is_recording():
 span_id = span.get_span_context().span_id
 return format(span_id, "016x")
 return None


def create_child_span(name: str, parent_span: trace.Span = None) -> trace.Span:
 """
 Create a child span with proper parent relationship.

 Args:
 name: Name of the child span
 parent_span: Parent span (uses current span if None)

 Returns:
 Child span
 """
 tracer = trace.get_tracer(__name__)

 if parent_span:
 with trace.use_span(parent_span):
 return tracer.start_span(name)
 else:
 return tracer.start_span(name)


# Service-specific tracing configurations
SERVICE_CONFIGS = {
 "ontology-management-service": {
 "sampling_rate": 1.0, # Sample all requests for core service
 "custom_attributes": {"service.type": "core", "service.criticality": "high"},
 },
 "user-service": {
 "sampling_rate": 1.0,
 "custom_attributes": {"service.type": "auth", "service.criticality": "high"},
 },
 "audit-service": {
 "sampling_rate": 0.5, # Sample 50% for audit service
 "custom_attributes": {"service.type": "audit", "service.criticality": "medium"},
 },
 "data-kernel-service": {
 "sampling_rate": 1.0,
 "custom_attributes": {"service.type": "data", "service.criticality": "high"},
 },
 "embedding-service": {
 "sampling_rate": 0.3, # Sample 30% for high-volume service
 "custom_attributes": {"service.type": "ml", "service.criticality": "medium"},
 },
 "scheduler-service": {
 "sampling_rate": 1.0,
 "custom_attributes": {
 "service.type": "orchestration",
 "service.criticality": "high",
 },
 },
 "event-gateway": {
 "sampling_rate": 0.1, # Sample 10% for very high-volume service
 "custom_attributes": {"service.type": "gateway", "service.criticality": "high"},
 },
}


def setup_service_tracing(service_name: str, app = None, **kwargs) -> TracerProvider:
 """
 Set up tracing with service-specific configuration.

 Args:
 service_name: Name of the service
 app: FastAPI application instance
 **kwargs: Additional configuration options

 Returns:
 TracerProvider instance
 """
 # Get service-specific config
 service_config = SERVICE_CONFIGS.get(service_name, {})

 # Set sampling rate
 if "sampling_rate" in service_config:
 os.environ["TRACING_SAMPLING_RATE"] = str(service_config["sampling_rate"])

 # Add custom attributes
 custom_attributes = service_config.get("custom_attributes", {})
 custom_attributes.update(kwargs.get("custom_resource_attributes", {}))

 # Set up tracing
 tracer_provider = setup_tracing(
 service_name = service_name,
 custom_resource_attributes = custom_attributes,
 **kwargs,
 )

 # Instrument the service
 instrument_service(app = app, **kwargs)

 return tracer_provider


__all__ = [
 "TracingConfig",
 "setup_tracing",
 "setup_service_tracing",
 "instrument_service",
 "create_custom_span",
 "add_span_attributes",
 "set_span_error",
 "TracingMiddleware",
 "get_current_trace_id",
 "get_current_span_id",
 "create_child_span",
]
