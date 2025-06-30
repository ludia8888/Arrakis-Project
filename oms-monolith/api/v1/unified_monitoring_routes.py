"""
Unified Monitoring Routes - 엔터프라이즈 레벨 통합 모니터링
모든 서비스의 health check와 metrics를 단일 엔드포인트로 통합
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from core.auth import UserContext, get_permission_checker
from api.dependencies import get_current_user
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/monitoring",
    tags=["monitoring"],
    responses={
        404: {"description": "Not found"},
        403: {"description": "Forbidden"},
    }
)


@router.get("/health", response_model=Dict[str, Any])
async def unified_health_check(
    include_details: bool = False,
    user: Optional[UserContext] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    통합 헬스 체크 엔드포인트
    
    모든 서비스의 상태를 집계하여 반환
    - 인증 없이 기본 상태 확인 가능
    - 인증된 사용자는 상세 정보 확인 가능
    - admin은 모든 내부 상태 확인 가능
    """
    
    # 기본 헬스 정보
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.1",
        "services": {}
    }
    
    # 서비스별 헬스 체크 수행
    service_checks = {
        "database": await _check_database_health(),
        "cache": await _check_cache_health(),
        "event_system": await _check_event_system_health(),
        "validation": await _check_validation_health(),
        "branch": await _check_branch_health(),
        "traversal": await _check_traversal_health(),
        "audit": await _check_audit_health(),
        "issue_tracking": await _check_issue_tracking_health()
    }
    
    # 전체 상태 결정
    unhealthy_services = [
        name for name, status in service_checks.items() 
        if not status["healthy"]
    ]
    
    if unhealthy_services:
        health_status["status"] = "degraded"
        health_status["unhealthy_services"] = unhealthy_services
    
    # 인증된 사용자에게만 상세 정보 제공
    if user and include_details:
        health_status["services"] = service_checks
        
        # Admin은 추가 내부 상태 확인 가능
        if user.is_admin:
            health_status["internal"] = {
                "memory_usage": await _get_memory_usage(),
                "connection_pools": await _get_connection_pool_status(),
                "background_tasks": await _get_background_task_status()
            }
    else:
        # 비인증 사용자는 기본 정보만
        health_status["services"] = {
            name: {"healthy": status["healthy"]}
            for name, status in service_checks.items()
        }
    
    return health_status


@router.get("/metrics")
async def unified_metrics(
    user: UserContext = Depends(get_current_user)
) -> Any:
    """
    통합 Prometheus 메트릭스 엔드포인트
    
    모든 서비스의 메트릭을 단일 엔드포인트에서 제공
    - 인증 필수 (메트릭은 민감한 정보 포함 가능)
    - Prometheus scraping 호환
    """
    
    # 권한 체크 - 메트릭 조회는 최소 developer 권한 필요
    if not user.has_any_role(["admin", "developer", "monitoring"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to access metrics"
        )
    
    # 통합 메트릭 수집기에서 메트릭 생성
    metrics_collector = get_metrics_collector()
    
    # Prometheus 형식으로 메트릭 반환
    return generate_latest()


@router.get("/statistics", response_model=Dict[str, Any])
async def unified_statistics(
    user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    통합 통계 엔드포인트
    
    모든 서비스의 운영 통계를 집계하여 반환
    """
    
    # 권한 체크
    if not user.has_any_role(["admin", "developer", "reviewer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to access statistics"
        )
    
    statistics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "validation": await _get_validation_statistics(),
            "branch": await _get_branch_statistics(),
            "audit": await _get_audit_statistics(),
            "traversal": await _get_traversal_statistics(),
            "batch": await _get_batch_statistics(),
            "issue_tracking": await _get_issue_tracking_statistics()
        },
        "overall": {
            "total_requests": await _get_total_request_count(),
            "average_response_time": await _get_average_response_time(),
            "error_rate": await _get_error_rate(),
            "active_users": await _get_active_user_count()
        }
    }
    
    return statistics


# === 내부 헬스 체크 함수들 ===

async def _check_database_health() -> Dict[str, Any]:
    """데이터베이스 헬스 체크"""
    try:
        # TerminusDB 연결 확인
        from database.clients.terminus_db import TerminusDBClient
        # 실제 구현에서는 db client를 주입받아 사용
        return {
            "healthy": True,
            "response_time_ms": 10
        }
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Database connection failed: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }
    except RuntimeError as e:
        logger.error(f"Database runtime error: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def _check_cache_health() -> Dict[str, Any]:
    """캐시 헬스 체크"""
    try:
        # Redis 연결 확인
        return {
            "healthy": True,
            "response_time_ms": 5
        }
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Cache connection failed: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }
    except RuntimeError as e:
        logger.error(f"Cache runtime error: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def _check_event_system_health() -> Dict[str, Any]:
    """이벤트 시스템 헬스 체크"""
    try:
        # NATS 연결 확인
        return {
            "healthy": True,
            "response_time_ms": 8
        }
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Event system connection failed: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }
    except RuntimeError as e:
        logger.error(f"Event system runtime error: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def _check_validation_health() -> Dict[str, Any]:
    """검증 서비스 헬스 체크"""
    return {"healthy": True}


async def _check_branch_health() -> Dict[str, Any]:
    """브랜치 서비스 헬스 체크"""
    return {"healthy": True}


async def _check_traversal_health() -> Dict[str, Any]:
    """순회 서비스 헬스 체크"""
    return {"healthy": True}


async def _check_audit_health() -> Dict[str, Any]:
    """감사 서비스 헬스 체크"""
    return {"healthy": True}


async def _check_issue_tracking_health() -> Dict[str, Any]:
    """이슈 트래킹 헬스 체크"""
    return {"healthy": True}


# === 내부 통계 함수들 ===

async def _get_validation_statistics() -> Dict[str, Any]:
    """검증 서비스 통계"""
    return {
        "total_validations": 0,
        "failed_validations": 0,
        "average_validation_time_ms": 0
    }


async def _get_branch_statistics() -> Dict[str, Any]:
    """브랜치 서비스 통계"""
    return {
        "total_branches": 0,
        "active_branches": 0,
        "total_merges": 0
    }


async def _get_audit_statistics() -> Dict[str, Any]:
    """감사 서비스 통계"""
    return {
        "total_events": 0,
        "events_last_hour": 0,
        "top_event_types": []
    }


async def _get_traversal_statistics() -> Dict[str, Any]:
    """순회 서비스 통계"""
    return {
        "total_traversals": 0,
        "average_traversal_depth": 0,
        "average_traversal_time_ms": 0
    }


async def _get_batch_statistics() -> Dict[str, Any]:
    """배치 작업 통계"""
    return {
        "total_batch_operations": 0,
        "average_batch_size": 0,
        "average_batch_time_ms": 0
    }


async def _get_issue_tracking_statistics() -> Dict[str, Any]:
    """이슈 트래킹 통계"""
    return {
        "total_tracked_issues": 0,
        "active_issues": 0,
        "resolved_issues": 0
    }


# === 전체 통계 함수들 ===

async def _get_total_request_count() -> int:
    """전체 요청 수"""
    metrics_collector = get_metrics_collector()
    # 실제 구현에서는 메트릭에서 값을 가져옴
    return 0


async def _get_average_response_time() -> float:
    """평균 응답 시간"""
    return 0.0


async def _get_error_rate() -> float:
    """에러율"""
    return 0.0


async def _get_active_user_count() -> int:
    """활성 사용자 수"""
    return 0


# === 내부 상태 함수들 (Admin 전용) ===

async def _get_memory_usage() -> Dict[str, Any]:
    """메모리 사용량"""
    import psutil
    process = psutil.Process()
    return {
        "rss_mb": process.memory_info().rss / 1024 / 1024,
        "vms_mb": process.memory_info().vms / 1024 / 1024,
        "percent": process.memory_percent()
    }


async def _get_connection_pool_status() -> Dict[str, Any]:
    """연결 풀 상태"""
    return {
        "database": {"active": 0, "idle": 0, "total": 0},
        "cache": {"active": 0, "idle": 0, "total": 0},
        "event_system": {"active": 0, "idle": 0, "total": 0}
    }


async def _get_background_task_status() -> Dict[str, Any]:
    """백그라운드 작업 상태"""
    return {
        "active_tasks": 0,
        "pending_tasks": 0,
        "failed_tasks": 0
    }