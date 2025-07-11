"""
Enterprise-Grade Distributed Tracing Integration
Jaeger 기반 리질리언스 메커니즘 통합 트레이싱
"""
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes

logger = logging.getLogger(__name__)

# =============================================================================
# Enterprise Tracing Configuration
# =============================================================================

@dataclass
class TracingConfig:
    """트레이싱 설정"""
    service_name: str = "oms-enterprise"
    service_version: str = "2.0.0"
    jaeger_endpoint: str = "http://localhost:14268/api/traces"
    sampling_rate: float = 1.0  # 100% sampling for enterprise monitoring
    max_tag_value_length: int = 1000
    max_export_batch_size: int = 512
    export_timeout_millis: int = 30000
    schedule_delay_millis: int = 5000

class EnterpriseTracer:
    """엔터프라이즈급 분산 트레이싱"""
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self._tracer = None
        self._setup_tracing()
    
    def _setup_tracing(self):
        """트레이싱 초기화"""
        try:
            # Resource 정의
            resource = Resource.create({
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
                "deployment.environment": "production",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.language": "python"
            })
            
            # TracerProvider 설정
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
            
            # Jaeger Exporter 설정
            import os
            jaeger_host = os.getenv("JAEGER_AGENT_HOST", "localhost")
            jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))
            collector_endpoint = os.getenv("JAEGER_COLLECTOR_ENDPOINT", self.config.jaeger_endpoint)
            
            logger.info(f"Configuring Jaeger: host={jaeger_host}, port={jaeger_port}, collector={collector_endpoint}")
            
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
                collector_endpoint=collector_endpoint if collector_endpoint else None,
            )
            
            # Batch Span Processor 설정
            span_processor = BatchSpanProcessor(
                jaeger_exporter,
                max_export_batch_size=self.config.max_export_batch_size,
                export_timeout_millis=self.config.export_timeout_millis,
                schedule_delay_millis=self.config.schedule_delay_millis
            )
            
            provider.add_span_processor(span_processor)
            
            # Tracer 생성
            self._tracer = trace.get_tracer(
                __name__,
                version=self.config.service_version
            )
            
            logger.info(f"Enterprise tracing initialized for {self.config.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            # Fallback to NoOp tracer
            self._tracer = trace.NoOpTracer()
    
    def get_tracer(self):
        """트레이서 반환"""
        return self._tracer

# =============================================================================
# Resilience Mechanism Tracing Decorators
# =============================================================================

class ResilienceTracing:
    """리질리언스 메커니즘 트레이싱 유틸리티"""
    
    def __init__(self, tracer):
        self.tracer = tracer
    
    def trace_circuit_breaker(self, circuit_name: str, operation: str):
        """서킷 브레이커 트레이싱 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"circuit_breaker.{operation}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    # 기본 속성 설정
                    span.set_attributes({
                        "resilience.type": "circuit_breaker",
                        "circuit_breaker.name": circuit_name,
                        "circuit_breaker.operation": operation,
                        "component": "resilience"
                    })
                    
                    start_time = time.time()
                    
                    try:
                        # 서킷 브레이커 상태 추가
                        if hasattr(args[0], 'state'):
                            span.set_attribute("circuit_breaker.state", str(args[0].state))
                        if hasattr(args[0], 'failure_count'):
                            span.set_attribute("circuit_breaker.failure_count", args[0].failure_count)
                        
                        result = await func(*args, **kwargs)
                        
                        # 성공 정보 기록
                        span.set_status(Status(StatusCode.OK))
                        span.set_attribute("circuit_breaker.result", "success")
                        
                        return result
                        
                    except Exception as e:
                        # 실패 정보 기록
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("circuit_breaker.result", "failure")
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        
                        raise
                    
                    finally:
                        # 실행 시간 기록
                        duration = time.time() - start_time
                        span.set_attribute("circuit_breaker.duration_ms", duration * 1000)
            
            return wrapper
        return decorator
    
    def trace_cache_operation(self, cache_type: str, operation: str):
        """캐시 작업 트레이싱 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"cache.{cache_type}.{operation}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    # 기본 속성 설정
                    span.set_attributes({
                        "resilience.type": "cache",
                        "cache.type": cache_type,
                        "cache.operation": operation,
                        "component": "resilience"
                    })
                    
                    # 캐시 키 정보 (가능한 경우)
                    if len(args) > 1:
                        cache_key = args[1] if isinstance(args[1], str) else str(args[1])
                        span.set_attribute("cache.key", cache_key[:100])  # 처음 100자만
                    
                    start_time = time.time()
                    
                    try:
                        result = await func(*args, **kwargs)
                        
                        # 결과에 따른 정보 설정
                        if operation == "get":
                            hit = result is not None
                            span.set_attribute("cache.hit", hit)
                            span.set_attribute("cache.result", "hit" if hit else "miss")
                        elif operation in ["set", "delete"]:
                            span.set_attribute("cache.result", "success")
                        
                        # E-Tag 관련 정보 (E-Tag 캐시인 경우)
                        if cache_type == "etag" and hasattr(result, 'ttl'):
                            span.set_attribute("cache.ttl_seconds", getattr(result, 'ttl', 0))
                        
                        span.set_status(Status(StatusCode.OK))
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("cache.result", "error")
                        span.set_attribute("error.type", type(e).__name__)
                        
                        raise
                    
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("cache.duration_ms", duration * 1000)
            
            return wrapper
        return decorator
    
    def trace_backpressure(self, queue_type: str, operation: str):
        """백프레셔 트레이싱 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"backpressure.{operation}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    span.set_attributes({
                        "resilience.type": "backpressure",
                        "backpressure.queue_type": queue_type,
                        "backpressure.operation": operation,
                        "component": "resilience"
                    })
                    
                    # 큐 상태 정보 (가능한 경우)
                    if hasattr(args[0], 'queue_size'):
                        span.set_attribute("backpressure.queue_size", args[0].queue_size)
                    if hasattr(args[0], 'max_size'):
                        span.set_attribute("backpressure.max_size", args[0].max_size)
                    
                    start_time = time.time()
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        span.set_attribute("backpressure.result", "accepted")
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        
                        # 백프레셔로 인한 거부인지 확인
                        if "queue full" in str(e).lower() or "rejected" in str(e).lower():
                            span.set_attribute("backpressure.result", "rejected")
                            span.set_attribute("backpressure.rejection_reason", "queue_full")
                        else:
                            span.set_attribute("backpressure.result", "error")
                        
                        raise
                    
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("backpressure.duration_ms", duration * 1000)
            
            return wrapper
        return decorator
    
    def trace_http_request(self, endpoint: str, method: str = "GET"):
        """HTTP 요청 트레이싱 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"http.{method.lower()}.{endpoint}",
                    kind=trace.SpanKind.SERVER
                ) as span:
                    # HTTP 관련 표준 속성
                    span.set_attributes({
                        SpanAttributes.HTTP_METHOD: method,
                        SpanAttributes.HTTP_URL: endpoint,
                        "component": "http",
                        "http.type": "server"
                    })
                    
                    # 요청 시작 시간
                    span.set_attribute("http.request.start_time", datetime.utcnow().isoformat())
                    
                    try:
                        result = await func(*args, **kwargs)
                        
                        # 응답 상태 코드
                        status_code = getattr(result, 'status_code', 200)
                        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
                        
                        # 응답 크기 (가능한 경우)
                        if hasattr(result, 'content'):
                            content_length = len(getattr(result, 'content', b''))
                            span.set_attribute("http.response.size", content_length)
                        
                        # 상태에 따른 span 상태 설정
                        if 200 <= status_code < 400:
                            span.set_status(Status(StatusCode.OK))
                        else:
                            span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))
                        
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
                        raise
            
            return wrapper
        return decorator
    
    def trace_database_operation(self, db_type: str, operation: str, table: str = None):
        """데이터베이스 작업 트레이싱 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"db.{db_type}.{operation}",
                    kind=trace.SpanKind.CLIENT
                ) as span:
                    span.set_attributes({
                        SpanAttributes.DB_SYSTEM: db_type,
                        SpanAttributes.DB_OPERATION: operation,
                        "component": "database"
                    })
                    
                    if table:
                        span.set_attribute(SpanAttributes.DB_SQL_TABLE, table)
                    
                    start_time = time.time()
                    
                    try:
                        result = await func(*args, **kwargs)
                        
                        # 결과 행 수 (가능한 경우)
                        if hasattr(result, '__len__'):
                            span.set_attribute("db.rows_affected", len(result))
                        
                        span.set_status(Status(StatusCode.OK))
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("db.error.type", type(e).__name__)
                        raise
                    
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("db.duration_ms", duration * 1000)
            
            return wrapper
        return decorator

# =============================================================================
# Business Operation Tracing
# =============================================================================

class BusinessTracing:
    """비즈니스 로직 트레이싱"""
    
    def __init__(self, tracer):
        self.tracer = tracer
    
    def trace_schema_operation(self, operation: str, branch: str = None):
        """스키마 작업 트레이싱"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"schema.{operation}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    span.set_attributes({
                        "business.domain": "ontology",
                        "business.operation": operation,
                        "schema.operation": operation,
                        "component": "business"
                    })
                    
                    if branch:
                        span.set_attribute("schema.branch", branch)
                    
                    # 스키마 정보 (가능한 경우)
                    if len(args) > 1 and hasattr(args[1], 'name'):
                        span.set_attribute("schema.name", args[1].name)
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        span.set_attribute("schema.result", "success")
                        
                        # 검증 결과 (검증 작업인 경우)
                        if operation == "validate" and hasattr(result, 'is_valid'):
                            span.set_attribute("schema.validation.valid", result.is_valid)
                            if hasattr(result, 'errors'):
                                span.set_attribute("schema.validation.error_count", len(result.errors))
                        
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("schema.result", "failure")
                        raise
            
            return wrapper
        return decorator
    
    def trace_document_operation(self, operation: str, doc_type: str = None):
        """문서 작업 트레이싱"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"document.{operation}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    span.set_attributes({
                        "business.domain": "document",
                        "business.operation": operation,
                        "document.operation": operation,
                        "component": "business"
                    })
                    
                    if doc_type:
                        span.set_attribute("document.type", doc_type)
                    
                    # 문서 정보 (가능한 경우)
                    if len(args) > 1:
                        doc = args[1]
                        if hasattr(doc, 'id'):
                            span.set_attribute("document.id", str(doc.id))
                        if hasattr(doc, 'size'):
                            span.set_attribute("document.size_bytes", doc.size)
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        span.set_attribute("document.result", "success")
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("document.result", "failure")
                        raise
            
            return wrapper
        return decorator
    
    def trace_audit_event(self, event_type: str):
        """감사 이벤트 트레이싱"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    f"audit.{event_type}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    span.set_attributes({
                        "business.domain": "audit",
                        "audit.event_type": event_type,
                        "component": "audit"
                    })
                    
                    # 감사 이벤트 정보
                    if len(args) > 1:
                        event = args[1]
                        if hasattr(event, 'user_id'):
                            span.set_attribute("audit.user_id", str(event.user_id))
                        if hasattr(event, 'resource'):
                            span.set_attribute("audit.resource", str(event.resource))
                        if hasattr(event, 'action'):
                            span.set_attribute("audit.action", str(event.action))
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        span.set_attribute("audit.result", "recorded")
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("audit.result", "failed")
                        raise
            
            return wrapper
        return decorator

# =============================================================================
# Global Tracing Setup
# =============================================================================

# Global tracer instances
_enterprise_tracer: Optional[EnterpriseTracer] = None
_resilience_tracing: Optional[ResilienceTracing] = None
_business_tracing: Optional[BusinessTracing] = None

def initialize_enterprise_tracing(config: TracingConfig = None) -> EnterpriseTracer:
    """엔터프라이즈 트레이싱 초기화"""
    global _enterprise_tracer, _resilience_tracing, _business_tracing
    
    if not config:
        config = TracingConfig()
    
    _enterprise_tracer = EnterpriseTracer(config)
    tracer = _enterprise_tracer.get_tracer()
    
    _resilience_tracing = ResilienceTracing(tracer)
    _business_tracing = BusinessTracing(tracer)
    
    logger.info("Enterprise tracing initialized successfully")
    return _enterprise_tracer

def get_enterprise_tracer() -> Optional[EnterpriseTracer]:
    """엔터프라이즈 트레이서 반환"""
    return _enterprise_tracer

def get_resilience_tracing() -> Optional[ResilienceTracing]:
    """리질리언스 트레이싱 반환"""
    return _resilience_tracing

def get_business_tracing() -> Optional[BusinessTracing]:
    """비즈니스 트레이싱 반환"""
    return _business_tracing

# =============================================================================
# Context Manager for Span Management
# =============================================================================

@asynccontextmanager
async def trace_operation(
    operation_name: str,
    operation_type: str = "internal",
    attributes: Dict[str, Any] = None
):
    """범용 트레이싱 컨텍스트 매니저"""
    if not _enterprise_tracer:
        yield None
        return
    
    tracer = _enterprise_tracer.get_tracer()
    
    with tracer.start_as_current_span(operation_name) as span:
        # 기본 속성 설정
        span.set_attribute("operation.type", operation_type)
        span.set_attribute("operation.start_time", datetime.utcnow().isoformat())
        
        # 추가 속성 설정
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        start_time = time.time()
        
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
            
        finally:
            duration = time.time() - start_time
            span.set_attribute("operation.duration_ms", duration * 1000)

# =============================================================================
# Auto-instrumentation for FastAPI
# =============================================================================

def setup_auto_instrumentation(app=None):
    """자동 계측 설정"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
        
        # FastAPI 자동 계측 - app이 제공되면 특정 app 계측
        if app:
            FastAPIInstrumentor.instrument_app(app)
        else:
            FastAPIInstrumentor.instrument()
        
        # HTTP 클라이언트 자동 계측
        RequestsInstrumentor.instrument()
        
        # Redis 자동 계측
        RedisInstrumentor.instrument()
        
        # AsyncIO 자동 계측
        AsyncioInstrumentor.instrument()
        
        logger.info("Auto-instrumentation setup completed")
        
    except ImportError as e:
        logger.warning(f"Some instrumentation libraries not available: {e}")
    except Exception as e:
        logger.error(f"Failed to setup auto-instrumentation: {e}")