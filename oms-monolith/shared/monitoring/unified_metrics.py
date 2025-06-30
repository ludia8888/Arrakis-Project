"""
Unified Metrics System - Single Source of Truth for All Metrics
모든 메트릭의 단일 관리 지점으로 Grafana 대시보드 일관성 보장
"""

import time
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """메트릭 타입"""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"
    INFO = "info"


@dataclass
class MetricDefinition:
    """표준화된 메트릭 정의"""
    name: str
    description: str
    metric_type: MetricType
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # Histogram용
    namespace: str = "oms"
    subsystem: str = ""
    
    def get_full_name(self) -> str:
        """전체 메트릭 이름 생성"""
        parts = [self.namespace]
        if self.subsystem:
            parts.append(self.subsystem)
        parts.append(self.name)
        return "_".join(parts)


class UnifiedMetricsRegistry:
    """
    통합 메트릭 레지스트리
    
    모든 메트릭을 중앙에서 관리하여 이름 충돌과 중복을 방지
    """
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._metrics: Dict[str, Any] = {}
        self._definitions: Dict[str, MetricDefinition] = {}
        
        # 표준 메트릭 정의 등록
        self._register_standard_metrics()
    
    def _register_standard_metrics(self):
        """표준 메트릭 정의 등록"""
        
        # 보안 관련 메트릭
        self.register_metric(MetricDefinition(
            name="security_violations_total",
            description="Total number of security violations",
            metric_type=MetricType.COUNTER,
            labels=["violation_type", "source", "severity"]
        ))
        
        self.register_metric(MetricDefinition(
            name="authentication_attempts_total",
            description="Total authentication attempts",
            metric_type=MetricType.COUNTER,
            labels=["result", "source", "user_type"]
        ))
        
        self.register_metric(MetricDefinition(
            name="rate_limit_violations_total",
            description="Total rate limit violations",
            metric_type=MetricType.COUNTER,
            labels=["limiter_name", "identifier_type", "action"]
        ))
        
        # Circuit Breaker 메트릭
        self.register_metric(MetricDefinition(
            name="circuit_breaker_state",
            description="Current circuit breaker state (0=closed, 1=open, 2=half_open)",
            metric_type=MetricType.GAUGE,
            labels=["circuit_name", "service"]
        ))
        
        self.register_metric(MetricDefinition(
            name="circuit_breaker_requests_total",
            description="Total circuit breaker requests",
            metric_type=MetricType.COUNTER,
            labels=["circuit_name", "result"]
        ))
        
        # HTTP 요청 메트릭
        self.register_metric(MetricDefinition(
            name="http_requests_total",
            description="Total HTTP requests",
            metric_type=MetricType.COUNTER,
            labels=["method", "endpoint", "status_code"]
        ))
        
        self.register_metric(MetricDefinition(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            metric_type=MetricType.HISTOGRAM,
            labels=["method", "endpoint", "status_code"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        ))
        
        # GraphQL 메트릭
        self.register_metric(MetricDefinition(
            name="graphql_requests_total",
            description="Total GraphQL requests",
            metric_type=MetricType.COUNTER,
            labels=["operation_type", "operation_name", "result"]
        ))
        
        self.register_metric(MetricDefinition(
            name="graphql_query_complexity",
            description="GraphQL query complexity score",
            metric_type=MetricType.HISTOGRAM,
            labels=["operation_name"],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500]
        ))
        
        self.register_metric(MetricDefinition(
            name="graphql_query_depth",
            description="GraphQL query depth",
            metric_type=MetricType.HISTOGRAM,
            labels=["operation_name"],
            buckets=[1, 2, 3, 5, 7, 10, 15, 20]
        ))
        
        # 데이터베이스 메트릭
        self.register_metric(MetricDefinition(
            name="database_connections_active",
            description="Active database connections",
            metric_type=MetricType.GAUGE,
            labels=["database", "connection_pool"]
        ))
        
        self.register_metric(MetricDefinition(
            name="database_query_duration_seconds",
            description="Database query duration in seconds",
            metric_type=MetricType.HISTOGRAM,
            labels=["database", "operation", "table"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        ))
        
        # 이벤트 시스템 메트릭
        self.register_metric(MetricDefinition(
            name="events_published_total",
            description="Total events published",
            metric_type=MetricType.COUNTER,
            labels=["event_type", "publisher", "result"]
        ))
        
        self.register_metric(MetricDefinition(
            name="events_consumed_total",
            description="Total events consumed",
            metric_type=MetricType.COUNTER,
            labels=["event_type", "consumer", "result"]
        ))
        
        # 시스템 메트릭
        self.register_metric(MetricDefinition(
            name="system_health",
            description="System health status (1=healthy, 0=unhealthy)",
            metric_type=MetricType.GAUGE,
            labels=["component", "check_type"]
        ))
        
        self.register_metric(MetricDefinition(
            name="cache_operations_total",
            description="Total cache operations",
            metric_type=MetricType.COUNTER,
            labels=["cache_name", "operation", "result"]
        ))
    
    def register_metric(self, definition: MetricDefinition) -> str:
        """메트릭 정의 등록"""
        
        full_name = definition.get_full_name()
        
        if full_name in self._definitions:
            logger.warning(f"Metric {full_name} already registered, skipping")
            return full_name
        
        # Prometheus 메트릭 생성
        if definition.metric_type == MetricType.COUNTER:
            metric = Counter(
                full_name,
                definition.description,
                definition.labels,
                registry=self.registry
            )
        elif definition.metric_type == MetricType.HISTOGRAM:
            metric = Histogram(
                full_name,
                definition.description,
                definition.labels,
                buckets=definition.buckets,
                registry=self.registry
            )
        elif definition.metric_type == MetricType.GAUGE:
            metric = Gauge(
                full_name,
                definition.description,
                definition.labels,
                registry=self.registry
            )
        elif definition.metric_type == MetricType.SUMMARY:
            metric = Summary(
                full_name,
                definition.description,
                definition.labels,
                registry=self.registry
            )
        elif definition.metric_type == MetricType.INFO:
            metric = Info(
                full_name,
                definition.description,
                registry=self.registry
            )
        else:
            raise ValueError(f"Unsupported metric type: {definition.metric_type}")
        
        self._metrics[full_name] = metric
        self._definitions[full_name] = definition
        
        logger.info(f"Registered metric: {full_name}")
        return full_name
    
    def get_metric(self, name: str) -> Any:
        """메트릭 인스턴스 반환"""
        
        # 전체 이름으로 조회
        if name in self._metrics:
            return self._metrics[name]
        
        # 짧은 이름으로 조회 시도
        for full_name, metric in self._metrics.items():
            if full_name.endswith(f"_{name}") or full_name.endswith(name):
                return metric
        
        raise KeyError(f"Metric not found: {name}")
    
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 1.0):
        """카운터 증가"""
        metric = self.get_metric(name)
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """히스토그램 관측값 기록"""
        metric = self.get_metric(name)
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """게이지 값 설정"""
        metric = self.get_metric(name)
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    
    def get_registry(self) -> CollectorRegistry:
        """Prometheus 레지스트리 반환"""
        return self.registry
    
    def generate_metrics(self) -> str:
        """메트릭 데이터 생성 (Prometheus 형식)"""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_metric_definitions(self) -> Dict[str, MetricDefinition]:
        """등록된 메트릭 정의 반환"""
        return self._definitions.copy()


class MetricsCollector:
    """
    메트릭 수집기
    
    다양한 소스에서 메트릭을 수집하여 통합 레지스트리에 기록
    """
    
    def __init__(self, registry: UnifiedMetricsRegistry):
        self.registry = registry
    
    def record_security_violation(
        self,
        violation_type: str,
        source: str,
        severity: str = "medium"
    ):
        """보안 위반 기록"""
        self.registry.increment_counter(
            "security_violations_total",
            {"violation_type": violation_type, "source": source, "severity": severity}
        )
    
    def record_authentication_attempt(
        self,
        result: str,  # success, failure, expired, etc.
        source: str,
        user_type: str = "user"
    ):
        """인증 시도 기록"""
        self.registry.increment_counter(
            "authentication_attempts_total",
            {"result": result, "source": source, "user_type": user_type}
        )
    
    def record_rate_limit_violation(
        self,
        limiter_name: str,
        identifier_type: str,  # user, ip, endpoint
        action: str = "blocked"
    ):
        """Rate Limit 위반 기록"""
        self.registry.increment_counter(
            "rate_limit_violations_total",
            {"limiter_name": limiter_name, "identifier_type": identifier_type, "action": action}
        )
    
    def record_circuit_breaker_state(
        self,
        circuit_name: str,
        state: str,  # closed, open, half_open
        service: str
    ):
        """Circuit Breaker 상태 기록"""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        self.registry.set_gauge(
            "circuit_breaker_state",
            state_value,
            {"circuit_name": circuit_name, "service": service}
        )
    
    def record_circuit_breaker_request(
        self,
        circuit_name: str,
        result: str  # success, failure, rejected
    ):
        """Circuit Breaker 요청 기록"""
        self.registry.increment_counter(
            "circuit_breaker_requests_total",
            {"circuit_name": circuit_name, "result": result}
        )
    
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: str,
        duration: float
    ):
        """HTTP 요청 기록"""
        labels = {"method": method, "endpoint": endpoint, "status_code": status_code}
        
        self.registry.increment_counter("http_requests_total", labels)
        self.registry.observe_histogram("http_request_duration_seconds", duration, labels)
    
    def record_graphql_request(
        self,
        operation_type: str,
        operation_name: str,
        result: str,
        complexity: Optional[int] = None,
        depth: Optional[int] = None
    ):
        """GraphQL 요청 기록"""
        self.registry.increment_counter(
            "graphql_requests_total",
            {"operation_type": operation_type, "operation_name": operation_name, "result": result}
        )
        
        if complexity is not None:
            self.registry.observe_histogram(
                "graphql_query_complexity",
                complexity,
                {"operation_name": operation_name}
            )
        
        if depth is not None:
            self.registry.observe_histogram(
                "graphql_query_depth",
                depth,
                {"operation_name": operation_name}
            )
    
    def record_database_query(
        self,
        database: str,
        operation: str,
        table: str,
        duration: float
    ):
        """데이터베이스 쿼리 기록"""
        self.registry.observe_histogram(
            "database_query_duration_seconds",
            duration,
            {"database": database, "operation": operation, "table": table}
        )
    
    def record_event_published(
        self,
        event_type: str,
        publisher: str,
        result: str = "success"
    ):
        """이벤트 발행 기록"""
        self.registry.increment_counter(
            "events_published_total",
            {"event_type": event_type, "publisher": publisher, "result": result}
        )
    
    def record_system_health(
        self,
        component: str,
        check_type: str,
        healthy: bool
    ):
        """시스템 건강성 기록"""
        self.registry.set_gauge(
            "system_health",
            1.0 if healthy else 0.0,
            {"component": component, "check_type": check_type}
        )


# 글로벌 인스턴스
_unified_metrics_registry: Optional[UnifiedMetricsRegistry] = None
_metrics_collector: Optional[MetricsCollector] = None


def get_unified_metrics_registry() -> UnifiedMetricsRegistry:
    """통합 메트릭 레지스트리 반환"""
    global _unified_metrics_registry
    if _unified_metrics_registry is None:
        _unified_metrics_registry = UnifiedMetricsRegistry()
    return _unified_metrics_registry


def get_metrics_collector() -> MetricsCollector:
    """메트릭 수집기 반환"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(get_unified_metrics_registry())
    return _metrics_collector


# 편의 함수들
def record_security_violation(violation_type: str, source: str, severity: str = "medium"):
    """보안 위반 기록 편의 함수"""
    get_metrics_collector().record_security_violation(violation_type, source, severity)


def record_http_request(method: str, endpoint: str, status_code: str, duration: float):
    """HTTP 요청 기록 편의 함수"""
    get_metrics_collector().record_http_request(method, endpoint, status_code, duration)


def get_metrics_data() -> str:
    """메트릭 데이터 반환 편의 함수"""
    return get_unified_metrics_registry().generate_metrics()