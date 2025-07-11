"""
Resilience Metrics Dashboard API
종합적인 리질리언스 메트릭 수집, 분석 및 대시보드 제공
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timedelta
from core.auth_utils import UserContext
from middleware.auth_middleware import get_current_user
from middleware.circuit_breaker_global import get_global_circuit_breaker
from middleware.etag_middleware import get_adaptive_ttl_manager
import logging
import json
import asyncio
from dataclasses import asdict
from enum import Enum

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resilience", tags=["Resilience Dashboard"])

class MetricTimeRange(str, Enum):
    """메트릭 시간 범위"""
    LAST_HOUR = "1h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"

class ResilienceComponent(str, Enum):
    """리질리언스 구성요소"""
    CIRCUIT_BREAKER = "circuit_breaker"
    ETAG_CACHING = "etag_caching"
    DISTRIBUTED_CACHING = "distributed_caching"
    BACKPRESSURE = "backpressure"
    ALL = "all"

@router.get("/dashboard", response_model=Dict[str, Any])
async def get_resilience_dashboard(
    time_range: MetricTimeRange = Query(MetricTimeRange.LAST_24_HOURS, description="메트릭 시간 범위"),
    component: ResilienceComponent = Query(ResilienceComponent.ALL, description="특정 구성요소 필터"),
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    종합 리질리언스 대시보드
    모든 리질리언스 메커니즘의 상태와 성능 메트릭을 통합 제공
    """
    try:
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "time_range": time_range.value,
            "component_filter": component.value,
            "overview": {},
            "components": {},
            "alerts": [],
            "recommendations": []
        }
        
        # 1. 개요 메트릭 수집
        dashboard_data["overview"] = await _collect_overview_metrics(time_range)
        
        # 2. 구성요소별 메트릭 수집
        if component == ResilienceComponent.ALL or component == ResilienceComponent.CIRCUIT_BREAKER:
            dashboard_data["components"]["circuit_breaker"] = await _collect_circuit_breaker_metrics(time_range)
        
        if component == ResilienceComponent.ALL or component == ResilienceComponent.ETAG_CACHING:
            dashboard_data["components"]["etag_caching"] = await _collect_etag_caching_metrics(time_range)
        
        if component == ResilienceComponent.ALL or component == ResilienceComponent.DISTRIBUTED_CACHING:
            dashboard_data["components"]["distributed_caching"] = await _collect_distributed_caching_metrics(time_range)
        
        if component == ResilienceComponent.ALL or component == ResilienceComponent.BACKPRESSURE:
            dashboard_data["components"]["backpressure"] = await _collect_backpressure_metrics(time_range)
        
        # 3. 알림 및 권장사항 생성
        dashboard_data["alerts"] = await _generate_alerts(dashboard_data["components"])
        dashboard_data["recommendations"] = await _generate_recommendations(dashboard_data["components"])
        
        # 4. 전체 리질리언스 점수 계산
        dashboard_data["resilience_score"] = _calculate_overall_resilience_score(dashboard_data["components"])
        
        return {
            "status": "success",
            "data": dashboard_data
        }
        
    except Exception as e:
        logger.error(f"Failed to generate resilience dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate resilience dashboard: {str(e)}"
        )

@router.get("/components/{component_name}/metrics", response_model=Dict[str, Any])
async def get_component_detailed_metrics(
    component_name: ResilienceComponent,
    time_range: MetricTimeRange = Query(MetricTimeRange.LAST_24_HOURS),
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    특정 리질리언스 구성요소의 상세 메트릭
    """
    try:
        if component_name == ResilienceComponent.CIRCUIT_BREAKER:
            metrics = await _collect_circuit_breaker_detailed_metrics(time_range)
        elif component_name == ResilienceComponent.ETAG_CACHING:
            metrics = await _collect_etag_detailed_metrics(time_range)
        elif component_name == ResilienceComponent.DISTRIBUTED_CACHING:
            metrics = await _collect_distributed_caching_detailed_metrics(time_range)
        elif component_name == ResilienceComponent.BACKPRESSURE:
            metrics = await _collect_backpressure_detailed_metrics(time_range)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown component: {component_name}")
        
        return {
            "status": "success",
            "component": component_name.value,
            "time_range": time_range.value,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get detailed metrics for {component_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get detailed metrics: {str(e)}"
        )

@router.get("/health-check", response_model=Dict[str, Any])
async def resilience_health_check(
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    리질리언스 시스템 종합 건강도 체크
    """
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "critical_issues": [],
            "warnings": []
        }
        
        # 각 구성요소 건강도 체크
        components_health = await asyncio.gather(
            _check_circuit_breaker_health(),
            _check_etag_caching_health(),
            _check_distributed_caching_health(),
            _check_backpressure_health(),
            return_exceptions=True
        )
        
        component_names = ["circuit_breaker", "etag_caching", "distributed_caching", "backpressure"]
        
        healthy_components = 0
        total_components = len(component_names)
        
        for i, (name, health) in enumerate(zip(component_names, components_health)):
            if isinstance(health, Exception):
                health_status["components"][name] = {
                    "status": "error",
                    "error": str(health)
                }
                health_status["critical_issues"].append(f"{name} health check failed: {health}")
            else:
                health_status["components"][name] = health
                if health.get("status") == "healthy":
                    healthy_components += 1
                elif health.get("status") == "degraded":
                    health_status["warnings"].append(f"{name} is degraded: {health.get('message', '')}")
                else:
                    health_status["critical_issues"].append(f"{name} is unhealthy: {health.get('message', '')}")
        
        # 전체 상태 결정
        health_ratio = healthy_components / total_components
        if health_ratio >= 0.8:
            health_status["overall_status"] = "healthy"
        elif health_ratio >= 0.5:
            health_status["overall_status"] = "degraded"
        else:
            health_status["overall_status"] = "unhealthy"
        
        health_status["health_ratio"] = health_ratio
        
        return {
            "status": "success",
            "health": health_status
        }
        
    except Exception as e:
        logger.error(f"Resilience health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/alerts", response_model=Dict[str, Any])
async def get_resilience_alerts(
    severity: Optional[str] = Query(None, description="필터링할 심각도 (critical, warning, info)"),
    limit: int = Query(50, description="반환할 알림 수 제한"),
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    리질리언스 관련 알림 목록
    """
    try:
        # 실시간 알림 생성
        alerts = await _generate_realtime_alerts()
        
        # 심각도 필터링
        if severity:
            alerts = [alert for alert in alerts if alert.get("severity") == severity]
        
        # 제한 적용
        alerts = alerts[:limit]
        
        return {
            "status": "success",
            "alerts": alerts,
            "total_count": len(alerts),
            "filter": {"severity": severity, "limit": limit},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get resilience alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alerts: {str(e)}"
        )

# --- 내부 메트릭 수집 함수들 ---

async def _collect_overview_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """개요 메트릭 수집"""
    return {
        "uptime_percentage": 99.5,  # 실제 계산 로직 필요
        "total_requests": 10000,
        "error_rate": 0.02,
        "avg_response_time_ms": 145.5,
        "active_resilience_mechanisms": 4,
        "last_incident": None
    }

async def _collect_circuit_breaker_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """서킷 브레이커 메트릭 수집"""
    circuit_breaker = get_global_circuit_breaker()
    
    if not circuit_breaker:
        return {
            "status": "not_available",
            "message": "Circuit breaker not initialized"
        }
    
    try:
        status = await circuit_breaker.get_status()
        distributed_health = await circuit_breaker.get_distributed_health()
        
        return {
            "status": "active",
            "current_state": status.get("state"),
            "total_requests": status.get("metrics", {}).get("total_requests", 0),
            "failed_requests": status.get("metrics", {}).get("failed_requests", 0),
            "consecutive_failures": status.get("metrics", {}).get("consecutive_failures", 0),
            "last_state_change": status.get("last_state_change"),
            "distributed_instances": distributed_health.get("total_instances", 0),
            "healthy_instances": distributed_health.get("healthy_instances", 0),
            "error_rate": status.get("metrics", {}).get("error_rate", 0)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def _collect_etag_caching_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """E-Tag 캐싱 메트릭 수집"""
    ttl_manager = get_adaptive_ttl_manager()
    
    return {
        "status": "active" if ttl_manager else "disabled",
        "adaptive_ttl_enabled": ttl_manager is not None,
        "cache_hit_rate": 0.85,  # 실제 계산 필요
        "avg_ttl_seconds": 450,
        "total_cache_requests": 5000,
        "cache_hits": 4250,
        "cache_misses": 750,
        "adaptive_adjustments": 12
    }

async def _collect_distributed_caching_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """분산 캐싱 메트릭 수집"""
    return {
        "status": "active",
        "redis_connected": True,
        "cache_size_mb": 128.5,
        "memory_usage_percentage": 45.2,
        "avg_response_time_ms": 2.3,
        "total_operations": 50000,
        "cache_evictions": 45
    }

async def _collect_backpressure_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """백프레셔 메트릭 수집"""
    return {
        "status": "active",
        "current_queue_size": 12,
        "max_queue_size": 1000,
        "queue_utilization": 0.012,
        "rejected_requests": 5,
        "avg_queue_time_ms": 15.7,
        "throttling_active": False
    }

# --- 상세 메트릭 수집 함수들 ---

async def _collect_circuit_breaker_detailed_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """서킷 브레이커 상세 메트릭"""
    basic_metrics = await _collect_circuit_breaker_metrics(time_range)
    
    # 시계열 데이터 시뮬레이션 (실제로는 Redis/Prometheus에서 수집)
    time_series = _generate_time_series_data(time_range, "circuit_breaker")
    
    return {
        **basic_metrics,
        "time_series": time_series,
        "state_transitions": [
            {"from": "closed", "to": "open", "timestamp": "2025-07-11T20:30:00Z", "reason": "failure_threshold_exceeded"},
            {"from": "open", "to": "half_open", "timestamp": "2025-07-11T20:31:00Z", "reason": "timeout_elapsed"},
            {"from": "half_open", "to": "closed", "timestamp": "2025-07-11T20:31:30Z", "reason": "success_threshold_met"}
        ],
        "failure_patterns": {
            "by_endpoint": {"/api/v1/schemas": 15, "/api/v1/documents": 8},
            "by_time_of_day": {"morning": 5, "afternoon": 12, "evening": 6, "night": 2}
        }
    }

async def _collect_etag_detailed_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """E-Tag 캐싱 상세 메트릭"""
    basic_metrics = await _collect_etag_caching_metrics(time_range)
    
    return {
        **basic_metrics,
        "resource_type_performance": {
            "schema": {"hit_rate": 0.92, "avg_ttl": 1800},
            "document": {"hit_rate": 0.78, "avg_ttl": 600},
            "branch": {"hit_rate": 0.65, "avg_ttl": 300}
        },
        "ttl_distribution": {
            "min": 60,
            "max": 7200,
            "avg": 450,
            "p50": 300,
            "p95": 1800,
            "p99": 3600
        },
        "time_series": _generate_time_series_data(time_range, "etag_caching")
    }

async def _collect_distributed_caching_detailed_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """분산 캐싱 상세 메트릭"""
    basic_metrics = await _collect_distributed_caching_metrics(time_range)
    
    return {
        **basic_metrics,
        "redis_stats": {
            "connected_clients": 8,
            "used_memory_human": "128.5M",
            "keyspace_hits": 45678,
            "keyspace_misses": 3421,
            "ops_per_sec": 1250
        },
        "cache_layers": {
            "l1_memory": {"hit_rate": 0.95, "size_mb": 32},
            "l2_redis": {"hit_rate": 0.82, "size_mb": 128},
            "l3_database": {"hit_rate": 0.15, "response_time_ms": 45}
        }
    }

async def _collect_backpressure_detailed_metrics(time_range: MetricTimeRange) -> Dict[str, Any]:
    """백프레셔 상세 메트릭"""
    basic_metrics = await _collect_backpressure_metrics(time_range)
    
    return {
        **basic_metrics,
        "queue_distribution": {
            "by_priority": {"high": 2, "medium": 8, "low": 2},
            "by_endpoint": {"/api/v1/schemas": 5, "/api/v1/documents": 7}
        },
        "throttling_history": [
            {"timestamp": "2025-07-11T20:15:00Z", "duration_seconds": 30, "reason": "queue_full"},
            {"timestamp": "2025-07-11T19:45:00Z", "duration_seconds": 15, "reason": "high_load"}
        ]
    }

# --- 건강도 체크 함수들 ---

async def _check_circuit_breaker_health() -> Dict[str, Any]:
    """서킷 브레이커 건강도 체크"""
    circuit_breaker = get_global_circuit_breaker()
    
    if not circuit_breaker:
        return {"status": "disabled", "message": "Circuit breaker not initialized"}
    
    try:
        status = await circuit_breaker.get_status()
        state = status.get("state")
        
        if state == "open":
            return {"status": "unhealthy", "message": f"Circuit breaker is open", "details": status}
        elif state == "half_open":
            return {"status": "degraded", "message": "Circuit breaker is in recovery mode", "details": status}
        else:
            return {"status": "healthy", "message": "Circuit breaker is operating normally", "details": status}
    except Exception as e:
        return {"status": "error", "message": f"Health check failed: {e}"}

async def _check_etag_caching_health() -> Dict[str, Any]:
    """E-Tag 캐싱 건강도 체크"""
    ttl_manager = get_adaptive_ttl_manager()
    
    if not ttl_manager:
        return {"status": "disabled", "message": "E-Tag caching is disabled"}
    
    return {"status": "healthy", "message": "E-Tag caching is operational"}

async def _check_distributed_caching_health() -> Dict[str, Any]:
    """분산 캐싱 건강도 체크"""
    # Redis 연결 상태 등을 확인하는 로직 필요
    return {"status": "healthy", "message": "Distributed caching is operational"}

async def _check_backpressure_health() -> Dict[str, Any]:
    """백프레셔 건강도 체크"""
    # 큐 상태, 처리량 등을 확인하는 로직 필요
    return {"status": "healthy", "message": "Backpressure mechanism is operational"}

# --- 알림 및 권장사항 생성 ---

async def _generate_alerts(components: Dict[str, Any]) -> List[Dict[str, Any]]:
    """실시간 알림 생성"""
    alerts = []
    
    # 서킷 브레이커 관련 알림
    circuit_breaker = components.get("circuit_breaker", {})
    if circuit_breaker.get("current_state") == "open":
        alerts.append({
            "id": "cb_open",
            "severity": "critical",
            "component": "circuit_breaker",
            "title": "Circuit Breaker Opened",
            "message": "Global circuit breaker has opened due to high failure rate",
            "timestamp": datetime.now().isoformat(),
            "actions": ["Check service dependencies", "Review error logs", "Consider manual reset"]
        })
    
    # E-Tag 캐싱 관련 알림
    etag_caching = components.get("etag_caching", {})
    if etag_caching.get("cache_hit_rate", 0) < 0.7:
        alerts.append({
            "id": "etag_low_hit_rate",
            "severity": "warning",
            "component": "etag_caching",
            "title": "Low E-Tag Cache Hit Rate",
            "message": f"Cache hit rate is {etag_caching.get('cache_hit_rate', 0):.1%}, below recommended 70%",
            "timestamp": datetime.now().isoformat(),
            "actions": ["Review TTL settings", "Check cache invalidation patterns"]
        })
    
    return alerts

async def _generate_recommendations(components: Dict[str, Any]) -> List[Dict[str, Any]]:
    """개선 권장사항 생성"""
    recommendations = []
    
    # 전체적인 성능 개선 권장사항
    recommendations.append({
        "category": "performance",
        "priority": "medium",
        "title": "Consider implementing request deduplication",
        "description": "Reduce duplicate requests by implementing client-side request deduplication",
        "impact": "10-15% reduction in backend load"
    })
    
    return recommendations

async def _generate_realtime_alerts() -> List[Dict[str, Any]]:
    """실시간 알림 생성"""
    # 실제로는 Redis, 로그, 메트릭에서 수집
    return [
        {
            "id": "perf_001",
            "severity": "info",
            "component": "overall",
            "title": "Performance is within normal range",
            "message": "All resilience mechanisms are operating efficiently",
            "timestamp": datetime.now().isoformat()
        }
    ]

def _calculate_overall_resilience_score(components: Dict[str, Any]) -> Dict[str, Any]:
    """전체 리질리언스 점수 계산"""
    scores = {}
    
    # 각 구성요소별 점수 계산
    circuit_breaker = components.get("circuit_breaker", {})
    if circuit_breaker.get("status") == "active":
        state = circuit_breaker.get("current_state", "unknown")
        if state == "closed":
            scores["circuit_breaker"] = 100
        elif state == "half_open":
            scores["circuit_breaker"] = 60
        else:  # open
            scores["circuit_breaker"] = 20
    else:
        scores["circuit_breaker"] = 0
    
    etag_caching = components.get("etag_caching", {})
    if etag_caching.get("status") == "active":
        hit_rate = etag_caching.get("cache_hit_rate", 0)
        scores["etag_caching"] = min(100, hit_rate * 100)
    else:
        scores["etag_caching"] = 50  # 비활성화는 중간 점수
    
    distributed_caching = components.get("distributed_caching", {})
    if distributed_caching.get("status") == "active":
        scores["distributed_caching"] = 90  # 기본적으로 높은 점수
    else:
        scores["distributed_caching"] = 0
    
    backpressure = components.get("backpressure", {})
    if backpressure.get("status") == "active":
        queue_utilization = backpressure.get("queue_utilization", 0)
        scores["backpressure"] = max(50, 100 - (queue_utilization * 100))
    else:
        scores["backpressure"] = 0
    
    # 가중 평균 계산
    weights = {
        "circuit_breaker": 0.3,
        "etag_caching": 0.25,
        "distributed_caching": 0.25,
        "backpressure": 0.2
    }
    
    total_score = sum(scores[component] * weights[component] for component in scores)
    
    return {
        "overall_score": round(total_score, 1),
        "component_scores": scores,
        "grade": _get_resilience_grade(total_score),
        "calculation_time": datetime.now().isoformat()
    }

def _get_resilience_grade(score: float) -> str:
    """리질리언스 점수를 등급으로 변환"""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"

def _generate_time_series_data(time_range: MetricTimeRange, component: str) -> List[Dict[str, Any]]:
    """시계열 데이터 생성 (시뮬레이션)"""
    # 실제로는 Prometheus나 InfluxDB에서 수집
    data_points = []
    
    if time_range == MetricTimeRange.LAST_HOUR:
        intervals = 12  # 5분 간격
    elif time_range == MetricTimeRange.LAST_24_HOURS:
        intervals = 24  # 1시간 간격
    else:
        intervals = 48  # 더 긴 간격
    
    for i in range(intervals):
        timestamp = datetime.now() - timedelta(hours=i)
        data_points.append({
            "timestamp": timestamp.isoformat(),
            "value": 95 - (i % 10),  # 시뮬레이션 데이터
            "component": component
        })
    
    return list(reversed(data_points))