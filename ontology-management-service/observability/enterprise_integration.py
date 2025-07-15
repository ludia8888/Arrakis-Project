"""
Enterprise Observability Integration
Fully integrate existing resilience dashboard with Prometheus/Grafana/Jaeger stack
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI

from .enterprise_metrics import (
    EnterpriseMetricsCollector,
    EnterpriseMetricsRegistry,
    get_metrics_collector,
    get_metrics_registry,
    metrics_endpoint,
    start_metrics_collection,
)
from .enterprise_tracing import (
    TracingConfig,
    get_business_tracing,
    get_resilience_tracing,
    initialize_enterprise_tracing,
    setup_auto_instrumentation,
)

logger = logging.getLogger(__name__)

class EnterpriseObservabilityManager:
 """엔터프라이즈 관찰성 통합 매니저"""

 def __init__(self):
 self.metrics_registry: Optional[EnterpriseMetricsRegistry] = None
 self.metrics_collector: Optional[EnterpriseMetricsCollector] = None
 self.enterprise_tracer = None
 self.resilience_tracing = None
 self.business_tracing = None
 self._initialized = False

 async def initialize(self, app: FastAPI = None):
 """관찰성 시스템 seconds기화"""
 if self._initialized:
 return

 try:
 logger.info("Initializing Enterprise Observability Stack...")

 # 1. Metrics seconds기화
 self.metrics_registry = get_metrics_registry()
 self.metrics_collector = get_metrics_collector()
 logger.info("✅ Enterprise metrics initialized")

 # 2. Tracing seconds기화
 tracing_config = TracingConfig(
 service_name = "oms-enterprise",
 service_version = "2.0.0",
 sampling_rate = 1.0 # 100% sampling for enterprise
 )
 logger.info(f"Initializing tracing with config: {tracing_config}")
 self.enterprise_tracer = initialize_enterprise_tracing(tracing_config)
 self.resilience_tracing = get_resilience_tracing()
 self.business_tracing = get_business_tracing()
 logger.info("✅ Enterprise tracing initialized")
 logger.info(f"Tracer type: {type(self.enterprise_tracer)}")
 logger.info(f"Tracer instance: {self.enterprise_tracer}")

 # 3. Auto-instrumentation 설정
 setup_auto_instrumentation()
 logger.info("✅ Auto-instrumentation setup completed")

 # 4. Metrics 수집 시작
 await start_metrics_collection()
 logger.info("✅ Metrics collection started")

 # 5. FastAPI 통합 (제공된 경우)
 if app:
 await self._integrate_with_fastapi(app)
 logger.info("✅ FastAPI integration completed")

 self._initialized = True
 logger.info("🎯 Enterprise Observability Stack fully initialized!")

 except Exception as e:
 logger.error(f"Failed to initialize observability stack: {e}")
 raise

 async def _integrate_with_fastapi(self, app: FastAPI):
 """FastAPI와 통합"""
 # Metrics endpoint 추가
 app.add_api_route("/metrics", metrics_endpoint, methods = ["GET"])

 # FastAPI OpenTelemetry instrumentation
 try:
 from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
 FastAPIInstrumentor.instrument_app(
 app,
 tracer_provider = self.enterprise_tracer.get_tracer().trace.get_tracer_provider() if self.enterprise_tracer else None,


 excluded_urls = "/health,/metrics,/api/v1/health"
 )
 logger.info("✅ FastAPI instrumented for OpenTelemetry tracing")
 except Exception as e:
 logger.warning(f"Failed to instrument FastAPI for tracing: {e}")

 # Health check endpoint에 관찰성 정보 추가
 @app.get("/observability/health")
 async def observability_health():
 """관찰성 시스템 건강도 체크"""
 return {
 "status": "healthy",
 "components": {
 "metrics": "active" if self.metrics_registry else "inactive",
 "tracing": "active" if self.enterprise_tracer else "inactive",
 "auto_instrumentation": "active"
 },
 "endpoints": {
 "metrics": "/metrics",
 "traces": "jaeger:16686",
 "dashboards": "grafana:3000"
 }
 }

 # 관찰성 설정 정보 endpoint
 @app.get("/observability/config")
 async def observability_config():
 """관찰성 설정 정보"""
 return {
 "metrics": {
 "registry": "EnterpriseMetricsRegistry",
 "collection_interval": "15s",
 "gc_monitoring": "enabled",
 "system_monitoring": "enabled"
 },
 "tracing": {
 "service_name": "oms-enterprise",
 "sampling_rate": 1.0,
 "jaeger_endpoint": "localhost:14268",
 "auto_instrumentation": "enabled"
 },
 "alerting": {
 "prometheus_rules": "enterprise_resilience_alerts.yml",
 "alertmanager": "enterprise configuration",
 "channels": ["email", "slack", "pagerduty"]
 }
 }

 def get_resilience_decorators(self):
 """리질리언스 메커니즘용 트레이싱 데코레이터 반환"""
 if not self.resilience_tracing:
 logger.warning("Resilience tracing not initialized")
 return None

 return {
 "circuit_breaker": self.resilience_tracing.trace_circuit_breaker,
 "cache": self.resilience_tracing.trace_cache_operation,
 "backpressure": self.resilience_tracing.trace_backpressure,
 "http": self.resilience_tracing.trace_http_request,
 "database": self.resilience_tracing.trace_database_operation
 }

 def get_business_decorators(self):
 """비즈니스 로직용 트레이싱 데코레이터 반환"""
 if not self.business_tracing:
 logger.warning("Business tracing not initialized")
 return None

 return {
 "schema": self.business_tracing.trace_schema_operation,
 "document": self.business_tracing.trace_document_operation,
 "audit": self.business_tracing.trace_audit_event
 }

 def get_metrics_interface(self):
 """메트릭 인터페이스 반환"""
 if not self.metrics_registry:
 logger.warning("Metrics registry not initialized")
 return None

 return {
 # Circuit Breaker Metrics
 "circuit_breaker_state": self.metrics_registry.circuit_breaker_state,
 "circuit_breaker_calls": self.metrics_registry.circuit_breaker_calls_total,
 "circuit_breaker_transitions": self.metrics_registry.circuit_breaker_state_transitions_total,


 "circuit_breaker_failure_rate": self.metrics_registry.circuit_breaker_failure_rate,

 # Cache Metrics
 "etag_cache_requests": self.metrics_registry.etag_cache_requests_total,
 "etag_cache_ttl": self.metrics_registry.etag_cache_ttl_seconds,
 "etag_cache_hit_rate": self.metrics_registry.etag_cache_hit_rate,
 "redis_operations": self.metrics_registry.redis_operations_total,
 "redis_duration": self.metrics_registry.redis_operation_duration_seconds,

 # Backpressure Metrics
 "backpressure_queue_size": self.metrics_registry.backpressure_queue_size,
 "backpressure_rejections": self.metrics_registry.backpressure_requests_rejected_total,
 "backpressure_wait_time": self.metrics_registry.backpressure_queue_wait_seconds,

 # HTTP Metrics
 "http_requests": self.metrics_registry.http_requests_total,
 "http_duration": self.metrics_registry.http_request_duration_seconds,
 "http_in_progress": self.metrics_registry.http_requests_in_progress,

 # Business Metrics
 "schema_operations": self.metrics_registry.schema_operations_total,
 "document_operations": self.metrics_registry.document_operations_total,
 "audit_events": self.metrics_registry.audit_events_total,

 # GC Metrics
 "gc_collections": self.metrics_registry.gc_collections_total,
 "gc_duration": self.metrics_registry.gc_collection_duration_seconds,
 "gc_objects_collected": self.metrics_registry.gc_objects_collected_total,
 "memory_objects_count": self.metrics_registry.memory_objects_count,

 # System Metrics
 "cpu_usage": self.metrics_registry.cpu_usage_percent,
 "memory_usage": self.metrics_registry.memory_usage_percent,
 "process_memory_rss": self.metrics_registry.memory_rss_bytes
 }

# Global observability manager instance
_observability_manager: Optional[EnterpriseObservabilityManager] = None

async def initialize_enterprise_observability(app: FastAPI = None) -> EnterpriseObservabilityManager:
 """엔터프라이즈 관찰성 seconds기화"""
 global _observability_manager

 if _observability_manager is None:
 _observability_manager = EnterpriseObservabilityManager()

 await _observability_manager.initialize(app)
 return _observability_manager

def get_observability_manager() -> Optional[EnterpriseObservabilityManager]:
 """관찰성 매니저 반환"""
 return _observability_manager

# =============================================================================
# Resilience Mechanism Integration Utilities
# =============================================================================

def integrate_circuit_breaker_metrics(circuit_breaker_instance):
 """서킷 브레이커 인스턴스와 메트릭 통합"""
 manager = get_observability_manager()
 if not manager or not manager.metrics_registry:
 return

 metrics = manager.get_metrics_interface()
 if not metrics:
 return

 # 서킷 브레이커 상태 업데이트 함수
 def update_circuit_breaker_metrics(service_name: str, circuit_name: str):
 state_mapping = {"closed": 0, "open": 1, "half_open": 2}
 state_value = state_mapping.get(circuit_breaker_instance.state, 0)

 metrics["circuit_breaker_state"].labels(
 service = service_name,
 circuit_name = circuit_name
 ).set(state_value)

 metrics["circuit_breaker_failure_rate"].labels(
 service = service_name,
 circuit_name = circuit_name
 ).set(getattr(circuit_breaker_instance, 'failure_rate', 0))

 return update_circuit_breaker_metrics

def integrate_cache_metrics(cache_instance, cache_type: str):
 """캐시 인스턴스와 메트릭 통합"""
 manager = get_observability_manager()
 if not manager or not manager.metrics_registry:
 return

 metrics = manager.get_metrics_interface()
 if not metrics:
 return

 # 캐시 메트릭 업데이트 함수
 def update_cache_metrics(operation: str, result: str, resource_type: str = None):
 if cache_type == "etag":
 metrics["etag_cache_requests"].labels(
 resource_type = resource_type or "unknown",
 result = result
 ).inc()
 elif cache_type == "redis":
 metrics["redis_operations"].labels(
 operation = operation,
 result = result
 ).inc()

 return update_cache_metrics

def integrate_backpressure_metrics(backpressure_instance):
 """백프레셔 인스턴스와 메트릭 통합"""
 manager = get_observability_manager()
 if not manager or not manager.metrics_registry:
 return

 metrics = manager.get_metrics_interface()
 if not metrics:
 return

 # 백프레셔 메트릭 업데이트 함수
 def update_backpressure_metrics(service_name: str, queue_type: str):
 queue_size = getattr(backpressure_instance, 'queue_size', 0)
 metrics["backpressure_queue_size"].labels(
 service = service_name,
 queue_type = queue_type
 ).set(queue_size)

 return update_backpressure_metrics

# =============================================================================
# Migration Utilities (기존 코드에서 새 시스템으로)
# =============================================================================

class ObservabilityMigration:
 """기존 리질리언스 대시보드에서 통합 관찰성으로 마이그레이션"""

 @staticmethod
 def migrate_custom_dashboard_to_grafana():
 """커스텀 대시보드 API를 Grafana로 마이그레이션"""
 logger.info("🔄 Migrating custom resilience dashboard to Grafana...")

 migration_guide = {
 "action": "remove_custom_api",
 "replacement": "grafana_dashboard",
 "steps": [
 "1. Remove /api/v1/resilience/dashboard routes",
 "2. Remove custom metrics collection in resilience_dashboard_routes.py",
 "3. Use Grafana Enterprise Resilience Dashboard",
 "4. Configure Prometheus scraping for enterprise metrics",
 "5. Update alerting rules in prometheus/rules/"
 ],
 "benefits": [
 "Unified monitoring stack",
 "Industry-standard tools",
 "Better performance and scalability",
 "Reduced maintenance overhead",
 "Enhanced visualization capabilities"
 ]
 }

 logger.info(f"Migration guide: {migration_guide}")
 return migration_guide

 @staticmethod
 def migrate_custom_metrics_to_prometheus():
 """커스텀 메트릭을 Prometheus 표준으로 마이그레이션"""
 logger.info("📊 Migrating custom metrics to Prometheus standard...")

 return {
 "removed_endpoints": [
 "/api/v1/resilience/dashboard",
 "/api/v1/resilience/components/{component}/metrics",
 "/api/v1/resilience/health-check",
 "/api/v1/resilience/alerts"
 ],
 "replaced_with": {
 "metrics": "/metrics (Prometheus format)",
 "dashboard": "Grafana Enterprise Resilience Dashboard",
 "health": "/observability/health",
 "alerting": "AlertManager with enterprise rules"
 },
 "new_capabilities": [
 "Garbage collection monitoring",
 "System resource tracking",
 "Security metrics",
 "Business logic metrics",
 "Database performance metrics",
 "Distributed tracing integration"
 ]
 }

# =============================================================================
# Integration Middleware
# =============================================================================

@asynccontextmanager
async def enterprise_observability_lifespan(app: FastAPI):
 """FastAPI 애플리케이션 라이프사이클에 관찰성 통합"""
 logger.info("🚀 Starting Enterprise Observability...")

 # seconds기화
 manager = await initialize_enterprise_observability(app)

 # 마이그레이션 정보 로깅
 migration = ObservabilityMigration()
 migration.migrate_custom_dashboard_to_grafana()
 migration.migrate_custom_metrics_to_prometheus()

 logger.info("✅ Enterprise Observability started successfully")

 yield

 logger.info("🛑 Shutting down Enterprise Observability...")
 # 정리 작업이 필요한 경우 여기에 추가
 logger.info("✅ Enterprise Observability shutdown complete")

# =============================================================================
# Convenience Functions
# =============================================================================

def get_circuit_breaker_tracer():
 """서킷 브레이커 트레이싱 데코레이터 반환"""
 manager = get_observability_manager()
 if manager and manager.resilience_tracing:
 return manager.resilience_tracing.trace_circuit_breaker
 return lambda circuit_name, operation: lambda func: func

def get_cache_tracer():
 """캐시 트레이싱 데코레이터 반환"""
 manager = get_observability_manager()
 if manager and manager.resilience_tracing:
 return manager.resilience_tracing.trace_cache_operation
 return lambda cache_type, operation: lambda func: func

def get_http_tracer():
 """HTTP 트레이싱 데코레이터 반환"""
 manager = get_observability_manager()
 if manager and manager.resilience_tracing:
 return manager.resilience_tracing.trace_http_request
 return lambda endpoint, method = "GET": lambda func: func

def get_business_tracer():
 """비즈니스 로직 트레이싱 데코레이터 반환"""
 manager = get_observability_manager()
 if manager and manager.business_tracing:
 return {
 "schema": manager.business_tracing.trace_schema_operation,
 "document": manager.business_tracing.trace_document_operation,
 "audit": manager.business_tracing.trace_audit_event
 }
 return {
 "schema": lambda operation, branch = None: lambda func: func,
 "document": lambda operation, doc_type = None: lambda func: func,
 "audit": lambda event_type: lambda func: func
 }
