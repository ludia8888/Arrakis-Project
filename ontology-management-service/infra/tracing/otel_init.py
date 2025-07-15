"""
OpenTelemetry Initialization Module
Ensures proper initialization order for all OTel components
"""
import os
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor

# Production OpenTelemetry instrumentation imports - all required for production
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

HAS_FASTAPI_INSTRUMENTATION = True
HAS_REDIS_INSTRUMENTATION = True
HAS_ASYNCIO_INSTRUMENTATION = True
HAS_REQUESTS_INSTRUMENTATION = True

from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

HAS_HTTPX_INSTRUMENTATION = True

# Production instrumentations - all required
from opentelemetry.instrumentation.aiohttp import AioHTTPClientInstrumentor

HAS_AIOHTTP_INSTRUMENTATION = True

from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

HAS_ASYNCPG_INSTRUMENTATION = True

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

HAS_SQLALCHEMY_INSTRUMENTATION = True

from opentelemetry.instrumentation.celery import CeleryInstrumentor

HAS_CELERY_INSTRUMENTATION = True
import logging

from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)


class OpenTelemetryManager:
 """Centralized OpenTelemetry management"""

 def __init__(self):
 self.tracer_provider: Optional[TracerProvider] = None
 self.meter_provider: Optional[MeterProvider] = None
 self.initialized = False

 def initialize(self, service_name: str = "oms-monolith"):
 """Initialize OpenTelemetry with proper order"""
 if self.initialized:
 logger.warning("OpenTelemetry already initialized")
 return

 logger.info("Initializing OpenTelemetry...")

 # Create resource
 resource = Resource.create(
 {
 "service.name": service_name,
 "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
 "deployment.environment": os.getenv("ENVIRONMENT", "development"),
 }
 )

 # Initialize Trace Provider
 self.tracer_provider = TracerProvider(resource = resource)

 # Add exporters based on configuration
 if os.getenv("JAEGER_ENABLED", "true").lower() == "true":
 jaeger_exporter = JaegerExporter(
 agent_host_name = os.getenv("JAEGER_AGENT_HOST", "localhost"),
 agent_port = int(os.getenv("JAEGER_AGENT_PORT", "6831")),
 collector_endpoint = os.getenv("JAEGER_COLLECTOR_ENDPOINT"),
 )
 self.tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

 if os.getenv("OTLP_ENABLED", "false").lower() == "true":
 otlp_exporter = OTLPSpanExporter(
 endpoint = os.getenv("OTLP_ENDPOINT", "localhost:4317"),
 insecure = os.getenv("OTLP_INSECURE", "true").lower() == "true",
 )
 self.tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

 # Set global tracer provider
 trace.set_tracer_provider(self.tracer_provider)

 # Initialize Metrics Provider
 # Note: In 1.21.0, metrics API is still evolving
 console_metric_exporter = ConsoleMetricExporter()
 metric_reader = PeriodicExportingMetricReader(
 exporter = console_metric_exporter,
 export_interval_millis = int(os.getenv("METRICS_EXPORT_INTERVAL", "60000")),
 )
 self.meter_provider = MeterProvider(
 resource = resource, metric_readers = [metric_reader]
 )
 metrics.set_meter_provider(self.meter_provider)

 # Set up propagators (W3C + B3 for compatibility)
 propagator = CompositePropagator(
 [TraceContextTextMapPropagator(), B3MultiFormat()]
 )
 set_global_textmap(propagator)

 # Initialize instrumentations
 self._initialize_instrumentations()

 self.initialized = True
 logger.info("OpenTelemetry initialization complete")

 def _initialize_instrumentations(self):
 """Initialize all auto-instrumentations"""
 try:
 # -------------------- Core instrumentations --------------------
 if HAS_ASYNCIO_INSTRUMENTATION:
 AsyncioInstrumentor().instrument()
 else:
 logger.warning("asyncio instrumentation not available")

 if HAS_REQUESTS_INSTRUMENTATION:
 RequestsInstrumentor().instrument()
 else:
 logger.warning("requests instrumentation not available")

 # ------------------ HTTP client instrumentations ------------------
 if HAS_HTTPX_INSTRUMENTATION:
 HTTPXClientInstrumentor().instrument()
 else:
 logger.warning("httpx instrumentation not available")

 if HAS_AIOHTTP_INSTRUMENTATION:
 AioHTTPClientInstrumentor().instrument()
 else:
 logger.warning("aiohttp instrumentation not available")

 # Database instrumentations
 if HAS_ASYNCPG_INSTRUMENTATION:
 AsyncPGInstrumentor().instrument()
 else:
 logger.warning("asyncpg instrumentation not available")

 if HAS_SQLALCHEMY_INSTRUMENTATION:
 SQLAlchemyInstrumentor().instrument()
 else:
 logger.warning("sqlalchemy instrumentation not available")

 # Cache instrumentation
 if HAS_REDIS_INSTRUMENTATION:
 RedisInstrumentor().instrument()
 else:
 logger.warning("redis instrumentation not available")

 # Task queue instrumentation
 if (
 os.getenv("CELERY_ENABLED", "false").lower() == "true"
 and HAS_CELERY_INSTRUMENTATION
 ):
 CeleryInstrumentor().instrument()
 elif os.getenv("CELERY_ENABLED", "false").lower() == "true":
 logger.warning("Celery enabled but instrumentation not available")

 logger.info("All instrumentations initialized")
 except Exception as e:
 logger.error(f"Error initializing instrumentations: {e}")

 def instrument_fastapi(self, app):
 """Instrument FastAPI application"""
 if not self.initialized:
 logger.error("OpenTelemetry not initialized before FastAPI instrumentation")
 return

 if HAS_FASTAPI_INSTRUMENTATION:
 FastAPIInstrumentor.instrument_app(
 app,
 tracer_provider = self.tracer_provider,
 excluded_urls = os.getenv(
 "OTEL_PYTHON_EXCLUDED_URLS", "/health,/metrics"
 ),
 )
 logger.info("FastAPI instrumentation complete")
 else:
 logger.warning(
 "FastAPI instrumentation module not available – skipping FastAPI instrumentation"
 )

 def shutdown(self):
 """Shutdown OpenTelemetry providers"""
 if self.tracer_provider:
 self.tracer_provider.shutdown()
 logger.info("OpenTelemetry shutdown complete")


# Global instance
_otel_manager = OpenTelemetryManager()


def get_otel_manager() -> OpenTelemetryManager:
 """Get global OpenTelemetry manager"""
 return _otel_manager


def init_opentelemetry(service_name: str = "oms-monolith"):
 """Initialize OpenTelemetry (convenience function)"""
 _otel_manager.initialize(service_name)
