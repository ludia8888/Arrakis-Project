"""
Circuit Breaker 모니터링 API
글로벌 서킷 브레이커 상태 조회 및 제어 엔드포인트
"""
import logging
from datetime import datetime
from typing import Any, Dict, List

from core.auth_utils import UserContext
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from fastapi import APIRouter, Depends, HTTPException
from middleware.auth_middleware import get_current_user
from middleware.circuit_breaker_global import (
 GlobalCircuitState,
 get_global_circuit_breaker,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix = "/circuit-breaker", tags = ["Circuit Breaker"])


@router.get("/status", response_model = Dict[str, Any])
async def get_circuit_breaker_status(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 글로벌 서킷 브레이커 상태 조회
 모니터링 및 운영팀이 서비스 상태를 확인할 수 있습니다.
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 status = await circuit_breaker.get_status()
 return {
 "status": "success",
 "data": status,
 "timestamp": status.get("last_state_change"),
 "health": {
 "is_healthy": status["state"] != GlobalCircuitState.OPEN.value,
 "state_description": _get_state_description(status["state"]),
 "recommendations": _get_recommendations(status),
 },
 }
 except Exception as e:
 logger.error(f"Failed to get circuit breaker status: {e}")
 raise HTTPException(
 status_code = 500,
 detail = f"Failed to retrieve circuit breaker status: {str(e)}",
 )


@router.post(
 "/reset", dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
async def reset_circuit_breaker(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 글로벌 서킷 브레이커 리셋 (관리자 전용)
 운영팀이 수동으로 서킷을 닫을 수 있습니다.
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 # 강제로 CLOSED 상태로 전환
 await circuit_breaker._transition_to_closed()

 logger.warning(
 f"Global circuit breaker manually reset by user {current_user.user_id}",
 extra={
 "user_id": current_user.user_id,
 "username": current_user.username,
 "action": "circuit_breaker_reset",
 },
 )

 return {
 "status": "success",
 "message": "Circuit breaker reset to CLOSED state",
 "reset_by": current_user.username,
 "new_state": "closed",
 }
 except Exception as e:
 logger.error(f"Failed to reset circuit breaker: {e}")
 raise HTTPException(
 status_code = 500, detail = f"Failed to reset circuit breaker: {str(e)}"
 )


@router.get("/metrics", response_model = Dict[str, Any])
async def get_circuit_breaker_metrics(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 서킷 브레이커 메트릭 조회
 성능 분석 및 임계값 튜닝에 사용됩니다.
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 status = await circuit_breaker.get_status()
 metrics = status.get("metrics", {})

 # 추가 계산된 메트릭
 uptime_percentage = _calculate_uptime_percentage(status)
 mttr = _calculate_mttr(metrics) # Mean Time To Recovery

 return {
 "status": "success",
 "metrics": {
 **metrics,
 "calculated_metrics": {
 "uptime_percentage": uptime_percentage,
 "mean_time_to_recovery_seconds": mttr,
 "availability_score": _calculate_availability_score(status),
 "resilience_health": _assess_resilience_health(status),
 },
 },
 "thresholds": {
 "failure_threshold": status["config"]["failure_threshold"],
 "error_rate_threshold": status["config"]["error_rate_threshold"],
 "timeout_seconds": status["config"]["timeout_seconds"],
 },
 }
 except Exception as e:
 logger.error(f"Failed to get circuit breaker metrics: {e}")
 raise HTTPException(
 status_code = 500,
 detail = f"Failed to retrieve circuit breaker metrics: {str(e)}",
 )


def _get_state_description(state: str) -> str:
 """서킷 브레이커 상태 설명"""
 descriptions = {
 "closed": "정상 동작 중 - 모든 요청이 처리됩니다",
 "open": "차단 상태 - 임계값 초과로 인해 요청이 차단됩니다",
 "half_open": "복구 시도 중 - 제한된 수의 요청만 허용됩니다",
 }
 return descriptions.get(state, f"알 수 없는 상태: {state}")


def _get_recommendations(status: Dict[str, Any]) -> list:
 """상태에 따른 권장사항"""
 state = status["state"]
 metrics = status.get("metrics", {})

 recommendations = []

 if state == "open":
 recommendations.extend(
 [
 "서비스가 일시적으로 중단되었습니다. 근본 원인을 조사하세요.",
 "로그를 확인하여 오류 패턴을 분석하세요.",
 "의존성 서비스(Database, TerminusDB, Redis) 상태를 확인하세요.",
 ]
 )
 elif state == "half_open":
 recommendations.append("서비스가 복구를 시도 중입니다. 모니터링을 계속하세요.")
 elif metrics.get("recent_error_rate", 0) > 0.3:
 recommendations.append("에러율이 높습니다. 서비스 성능을 모니터링하세요.")

 if metrics.get("consecutive_failures", 0) > 0:
 recommendations.append(
 f"연속 실패: {metrics['consecutive_failures']}회 - 시스템 안정성을 검토하세요."
 )

 return recommendations


def _calculate_uptime_percentage(status: Dict[str, Any]) -> float:
 """가동시간 백분율 계산"""
 metrics = status.get("metrics", {})
 total_requests = metrics.get("total_requests", 0)
 failed_requests = metrics.get("failed_requests", 0)

 if total_requests == 0:
 return 100.0

 success_requests = total_requests - failed_requests
 return round((success_requests / total_requests) * 100, 2)


def _calculate_mttr(metrics: Dict[str, Any]) -> float:
 """평균 복구 시간 계산 (초)"""
 # 단순화된 계산 - 실제로는 더 복잡한 로직 필요
 consecutive_failures = metrics.get("consecutive_failures", 0)
 if consecutive_failures == 0:
 return 0.0

 # 실패당 평균 복구 시간 추정 (예: 30초)
 return consecutive_failures * 30.0


def _calculate_availability_score(status: Dict[str, Any]) -> int:
 """가용성 점수 계산 (0-100)"""
 state = status["state"]
 metrics = status.get("metrics", {})

 if state == "open":
 return 0 # 완전 차단 상태
 elif state == "half_open":
 return 50 # 부분 가용
 else:
 # CLOSED 상태에서는 에러율에 따라 점수 계산
 error_rate = metrics.get("recent_error_rate", 0)
 return max(0, min(100, int((1 - error_rate) * 100)))


def _assess_resilience_health(status: Dict[str, Any]) -> str:
 """리질리언스 건강도 평가"""
 availability_score = _calculate_availability_score(status)

 if availability_score >= 95:
 return "excellent"
 elif availability_score >= 80:
 return "good"
 elif availability_score >= 60:
 return "fair"
 else:
 return "poor"


@router.get("/distributed/status", response_model = Dict[str, Any])
async def get_distributed_status(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 분산 서킷 브레이커 상태 조회
 여러 OMS 인스턴스의 서킷 브레이커 상태를 종합적으로 확인
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 distributed_health = await circuit_breaker.get_distributed_health()
 distributed_info = await circuit_breaker._get_distributed_info()

 return {
 "status": "success",
 "distributed_health": distributed_health,
 "distributed_info": distributed_info,
 "recommendations": _get_distributed_recommendations(distributed_health),
 }
 except Exception as e:
 logger.error(f"Failed to get distributed status: {e}")
 raise HTTPException(
 status_code = 500, detail = f"Failed to retrieve distributed status: {str(e)}"
 )


@router.post(
 "/distributed/sync",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))],
)
async def force_distributed_sync(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 분산 환경 강제 동기화
 Redis를 통해 모든 OMS 인스턴스의 서킷 브레이커 상태를 동기화
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 await circuit_breaker.force_distributed_sync()

 # 동기화 후 상태 확인
 distributed_health = await circuit_breaker.get_distributed_health()

 logger.info(
 f"Distributed synchronization forced by user {current_user.user_id}",
 extra={
 "user_id": current_user.user_id,
 "username": current_user.username,
 "action": "distributed_sync",
 },
 )

 return {
 "status": "success",
 "message": "Distributed synchronization completed",
 "synchronized_by": current_user.username,
 "post_sync_health": distributed_health,
 }
 except Exception as e:
 logger.error(f"Failed to force distributed sync: {e}")
 raise HTTPException(
 status_code = 500,
 detail = f"Failed to force distributed synchronization: {str(e)}",
 )


@router.get("/distributed/health", response_model = Dict[str, Any])
async def get_distributed_health(
 current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """
 분산 환경 건강도 조회
 OMS 클러스터 전체의 서킷 브레이커 건강도 분석
 """
 circuit_breaker = get_global_circuit_breaker()

 if not circuit_breaker:
 raise HTTPException(
 status_code = 503, detail = "Global circuit breaker not initialized"
 )

 try:
 distributed_health = await circuit_breaker.get_distributed_health()

 # 클러스터 레벨 분석
 cluster_analysis = _analyze_cluster_health(distributed_health)

 return {
 "status": "success",
 "distributed_health": distributed_health,
 "cluster_analysis": cluster_analysis,
 "timestamp": datetime.now().isoformat(),
 }
 except Exception as e:
 logger.error(f"Failed to get distributed health: {e}")
 raise HTTPException(
 status_code = 500, detail = f"Failed to retrieve distributed health: {str(e)}"
 )


def _get_distributed_recommendations(distributed_health: Dict[str, Any]) -> List[str]:
 """분산 환경 권장사항 생성"""
 recommendations = []

 status = distributed_health.get("status", "unknown")
 total_instances = distributed_health.get("total_instances", 0)
 failed_instances = distributed_health.get("failed_instances", 0)
 health_ratio = distributed_health.get("health_ratio", 0)

 if status == "disabled":
 recommendations.append("Redis 기반 분산 상태 관리가 비활성화되어 있습니다. 프로덕션 환경에서는 활성화를 권장합니다.")
 elif status == "isolated":
 recommendations.append(
 "다른 OMS 인스턴스가 감지되지 않습니다. 단일 인스턴스 환경이거나 네트워크 분할이 발생했을 수 있습니다."
 )
 elif status == "unhealthy":
 recommendations.extend(
 [
 f"클러스터 건강도가 좋지 않습니다 (건강도: {health_ratio:.1%})",
 f"{failed_instances}개 인스턴스가 실패 상태입니다. 즉시 조사가 필요합니다.",
 "로드 밸런서 설정을 확인하고 실패한 인스턴스를 재시작하는 것을 고려하세요.",
 ]
 )
 elif status == "degraded":
 recommendations.extend(
 [
 f"클러스터가 부분적으로 저하된 상태입니다 (건강도: {health_ratio:.1%})",
 "일부 인스턴스의 성능을 모니터링하고 필요시 조치하세요.",
 ]
 )

 if total_instances == 1:
 recommendations.append("단일 인스턴스 환경입니다. 고가용성을 위해 추가 인스턴스 배포를 고려하세요.")
 elif total_instances > 10:
 recommendations.append("대규모 클러스터입니다. 서킷 브레이커 임계값 조정을 고려하세요.")

 return recommendations


def _analyze_cluster_health(distributed_health: Dict[str, Any]) -> Dict[str, Any]:
 """클러스터 건강도 분석"""
 status = distributed_health.get("status", "unknown")
 total_instances = distributed_health.get("total_instances", 0)
 healthy_instances = distributed_health.get("healthy_instances", 0)
 degraded_instances = distributed_health.get("degraded_instances", 0)
 failed_instances = distributed_health.get("failed_instances", 0)
 health_ratio = distributed_health.get("health_ratio", 0)

 # 클러스터 리질리언스 점수 계산 (0-100)
 resilience_score = 0

 if status == "healthy":
 resilience_score = 90 + (health_ratio * 10) # 90-100점
 elif status == "degraded":
 resilience_score = 60 + (health_ratio * 30) # 60-90점
 elif status == "unhealthy":
 resilience_score = health_ratio * 60 # 0-60점

 # 가용성 등급
 if resilience_score >= 95:
 availability_grade = "A+"
 elif resilience_score >= 90:
 availability_grade = "A"
 elif resilience_score >= 80:
 availability_grade = "B"
 elif resilience_score >= 70:
 availability_grade = "C"
 else:
 availability_grade = "D"

 return {
 "resilience_score": min(100, max(0, resilience_score)),
 "availability_grade": availability_grade,
 "cluster_size": total_instances,
 "distribution": {
 "healthy": healthy_instances,
 "degraded": degraded_instances,
 "failed": failed_instances,
 },
 "risk_assessment": _assess_cluster_risk(
 health_ratio, total_instances, failed_instances
 ),
 }


def _assess_cluster_risk(
 health_ratio: float, total_instances: int, failed_instances: int
) -> str:
 """클러스터 위험도 평가"""
 if total_instances <= 1:
 return "high" if failed_instances > 0 else "medium"

 if health_ratio >= 0.8:
 return "low"
 elif health_ratio >= 0.5:
 return "medium"
 else:
 return "high"
