"""
글로벌 Circuit Breaker 구현
서비스 전체의 상태를 추적하고 임계값 초과 시 모든 요청을 차단
"""
import asyncio
import json
import time
import logging
from typing import Dict, Optional, Set
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class GlobalCircuitState(Enum):
    """글로벌 서킷 브레이커 상태"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class GlobalCircuitMetrics:
    """글로벌 서킷 브레이커 메트릭"""
    total_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    error_rate_window: list = None
    
    def __post_init__(self):
        if self.error_rate_window is None:
            self.error_rate_window = []
    
    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    @property
    def recent_error_rate(self) -> float:
        if not self.error_rate_window:
            return 0.0
        return sum(self.error_rate_window) / len(self.error_rate_window)

@dataclass
class GlobalCircuitConfig:
    """글로벌 서킷 브레이커 설정"""
    service_name: str = "oms"
    failure_threshold: int = 5
    error_rate_threshold: float = 0.6
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    metrics_window_size: int = 100
    redis_key_prefix: str = "global_circuit"
    excluded_paths: Set[str] = None
    
    def __post_init__(self):
        if self.excluded_paths is None:
            self.excluded_paths = {
                "/health", "/api/v1/health", "/metrics", "/docs", "/openapi.json",
                "/api/v1/test/health"  # 테스트 헬스체크는 제외
            }

class GlobalCircuitBreaker:
    """글로벌 서킷 브레이커 구현"""
    
    def __init__(self, config: GlobalCircuitConfig, redis_client: Optional[redis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self.state = GlobalCircuitState.CLOSED
        self.metrics = GlobalCircuitMetrics()
        self.last_state_change = datetime.now()
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
        
    async def record_request(self, success: bool, response_time_ms: float = 0):
        """요청 결과 기록"""
        async with self._lock:
            self.metrics.total_requests += 1
            
            if success:
                self.metrics.consecutive_failures = 0
                self.metrics.last_success_time = datetime.now().isoformat()
                # 윈도우에 성공 기록 (0)
                if len(self.metrics.error_rate_window) >= self.config.metrics_window_size:
                    self.metrics.error_rate_window.pop(0)
                self.metrics.error_rate_window.append(0)
            else:
                self.metrics.failed_requests += 1
                self.metrics.consecutive_failures += 1
                self.metrics.last_failure_time = datetime.now().isoformat()
                # 윈도우에 실패 기록 (1)
                if len(self.metrics.error_rate_window) >= self.config.metrics_window_size:
                    self.metrics.error_rate_window.pop(0)
                self.metrics.error_rate_window.append(1)
                
            # Redis에 상태 저장
            if self.redis_client:
                await self._save_state_to_redis()
                
            # 서킷 상태 확인 및 변경
            await self._check_circuit_state()
    
    async def _check_circuit_state(self):
        """서킷 상태 확인 및 변경"""
        current_state = self.state
        
        if current_state == GlobalCircuitState.CLOSED:
            # CLOSED → OPEN 조건 확인
            should_open = (
                self.metrics.consecutive_failures >= self.config.failure_threshold or
                (len(self.metrics.error_rate_window) >= 10 and 
                 self.metrics.recent_error_rate >= self.config.error_rate_threshold)
            )
            
            if should_open:
                await self._transition_to_open()
                
        elif current_state == GlobalCircuitState.OPEN:
            # OPEN → HALF_OPEN 조건 확인 (타임아웃 후)
            time_since_open = (datetime.now() - self.last_state_change).total_seconds()
            if time_since_open >= self.config.timeout_seconds:
                await self._transition_to_half_open()
                
        elif current_state == GlobalCircuitState.HALF_OPEN:
            # HALF_OPEN → CLOSED/OPEN 조건은 요청 처리 중에 확인
            pass
    
    async def _transition_to_open(self):
        """OPEN 상태로 전환"""
        self.state = GlobalCircuitState.OPEN
        self.last_state_change = datetime.now()
        logger.warning(
            f"🔥 GLOBAL Circuit Breaker OPENED for {self.config.service_name}",
            extra={
                "service": self.config.service_name,
                "consecutive_failures": self.metrics.consecutive_failures,
                "error_rate": self.metrics.recent_error_rate,
                "total_requests": self.metrics.total_requests
            }
        )
        
        if self.redis_client:
            await self._save_state_to_redis()
    
    async def _transition_to_half_open(self):
        """HALF_OPEN 상태로 전환"""
        self.state = GlobalCircuitState.HALF_OPEN
        self.last_state_change = datetime.now()
        self.half_open_calls = 0
        logger.info(
            f"🔄 GLOBAL Circuit Breaker HALF-OPEN for {self.config.service_name}",
            extra={"service": self.config.service_name}
        )
        
        if self.redis_client:
            await self._save_state_to_redis()
    
    async def _transition_to_closed(self):
        """CLOSED 상태로 전환"""
        self.state = GlobalCircuitState.CLOSED
        self.last_state_change = datetime.now()
        self.half_open_calls = 0
        logger.info(
            f"✅ GLOBAL Circuit Breaker CLOSED for {self.config.service_name}",
            extra={"service": self.config.service_name}
        )
        
        if self.redis_client:
            await self._save_state_to_redis()
    
    async def can_proceed(self) -> bool:
        """요청 처리 가능 여부 확인"""
        # Redis에서 최신 상태 로드
        if self.redis_client:
            await self._load_state_from_redis()
        
        await self._check_circuit_state()
        
        if self.state == GlobalCircuitState.CLOSED:
            return True
        elif self.state == GlobalCircuitState.HALF_OPEN:
            async with self._lock:
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
        else:  # OPEN
            return False
    
    async def handle_half_open_result(self, success: bool):
        """HALF_OPEN 상태에서의 요청 결과 처리"""
        if self.state != GlobalCircuitState.HALF_OPEN:
            return
        
        async with self._lock:
            self.half_open_calls = max(0, self.half_open_calls - 1)
            
            if success:
                # 성공 시 CLOSED로 전환
                await self._transition_to_closed()
            else:
                # 실패 시 OPEN으로 전환
                await self._transition_to_open()
    
    async def _save_state_to_redis(self):
        """Redis에 상태 저장 (분산 환경용 원자적 업데이트)"""
        if not self.redis_client:
            return
        
        try:
            state_data = {
                "state": self.state.value,
                "metrics": asdict(self.metrics),
                "last_state_change": self.last_state_change.isoformat(),
                "half_open_calls": self.half_open_calls,
                "instance_id": f"oms-{time.time()}",  # 인스턴스 식별자
                "updated_at": datetime.now().isoformat()
            }
            
            redis_key = f"{self.config.redis_key_prefix}:{self.config.service_name}"
            
            # 원자적 업데이트를 위한 Lua 스크립트
            lua_script = """
                local key = KEYS[1]
                local new_data = ARGV[1]
                local ttl = ARGV[2]
                
                -- 기존 데이터 확인
                local existing = redis.call('GET', key)
                if existing then
                    local existing_data = cjson.decode(existing)
                    local new_data_parsed = cjson.decode(new_data)
                    
                    -- 더 최신 데이터인지 확인 (타임스탬프 기반)
                    if existing_data.updated_at and new_data_parsed.updated_at then
                        if existing_data.updated_at > new_data_parsed.updated_at then
                            return existing  -- 더 오래된 데이터면 업데이트 안함
                        end
                    end
                end
                
                -- 데이터 저장
                redis.call('SETEX', key, ttl, new_data)
                return new_data
            """
            
            # Redis Lua 스크립트 실행
            await self.redis_client.eval(
                lua_script,
                1,  # 키 개수
                redis_key,  # 키
                json.dumps(state_data, default=str),  # 새 데이터
                str(int(timedelta(hours=1).total_seconds()))  # TTL (초)
            )
            
            logger.debug(f"Circuit breaker state saved to Redis: {self.state.value}")
            
        except Exception as e:
            logger.error(f"Failed to save circuit state to Redis: {e}")
    
    async def _load_state_from_redis(self):
        """Redis에서 상태 로드 (분산 환경용 충돌 방지)"""
        if not self.redis_client:
            return
        
        try:
            redis_key = f"{self.config.redis_key_prefix}:{self.config.service_name}"
            state_data = await self.redis_client.get(redis_key)
            
            if state_data:
                data = json.loads(state_data)
                
                # 현재 로컬 상태와 Redis 상태 비교
                current_time = datetime.now()
                redis_updated_at = datetime.fromisoformat(data.get("updated_at", current_time.isoformat()))
                local_updated_at = getattr(self, '_last_local_update', datetime.min)
                
                # Redis 상태가 더 최신이면 업데이트
                if redis_updated_at > local_updated_at:
                    old_state = self.state.value
                    
                    self.state = GlobalCircuitState(data["state"])
                    self.metrics = GlobalCircuitMetrics(**data["metrics"])
                    self.last_state_change = datetime.fromisoformat(data["last_state_change"])
                    self.half_open_calls = data.get("half_open_calls", 0)
                    self._last_local_update = redis_updated_at
                    
                    # 상태 변경 로깅
                    if old_state != self.state.value:
                        logger.info(
                            f"Circuit breaker state synchronized from Redis: {old_state} → {self.state.value}",
                            extra={
                                "service": self.config.service_name,
                                "old_state": old_state,
                                "new_state": self.state.value,
                                "sync_source": "redis"
                            }
                        )
                
        except Exception as e:
            logger.error(f"Failed to load circuit state from Redis: {e}")
    
    async def get_status(self) -> Dict:
        """현재 상태 조회 (분산 상태 포함)"""
        if self.redis_client:
            await self._load_state_from_redis()
        
        # 분산 환경 정보 수집
        distributed_info = await self._get_distributed_info()
        
        return {
            "service": self.config.service_name,
            "state": self.state.value,
            "metrics": asdict(self.metrics),
            "last_state_change": self.last_state_change.isoformat(),
            "half_open_calls": self.half_open_calls,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "error_rate_threshold": self.config.error_rate_threshold,
                "timeout_seconds": self.config.timeout_seconds
            },
            "distributed": distributed_info
        }
    
    async def _get_distributed_info(self) -> Dict:
        """분산 환경 정보 수집"""
        if not self.redis_client:
            return {"enabled": False}
        
        try:
            # 다른 인스턴스들의 상태 확인
            pattern = f"{self.config.redis_key_prefix}:*"
            keys = await self.redis_client.keys(pattern)
            
            instances = []
            for key in keys:
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        instance_data = json.loads(data)
                        instances.append({
                            "service_key": key.decode() if isinstance(key, bytes) else key,
                            "state": instance_data.get("state"),
                            "instance_id": instance_data.get("instance_id"),
                            "updated_at": instance_data.get("updated_at"),
                            "metrics_summary": {
                                "total_requests": instance_data.get("metrics", {}).get("total_requests", 0),
                                "failed_requests": instance_data.get("metrics", {}).get("failed_requests", 0)
                            }
                        })
                except Exception as e:
                    logger.warning(f"Failed to parse instance data from {key}: {e}")
            
            return {
                "enabled": True,
                "total_instances": len(instances),
                "instances": instances,
                "consensus_state": self._calculate_consensus_state(instances)
            }
            
        except Exception as e:
            logger.error(f"Failed to get distributed info: {e}")
            return {"enabled": True, "error": str(e)}
    
    def _calculate_consensus_state(self, instances: List[Dict]) -> str:
        """인스턴스들의 합의 상태 계산"""
        if not instances:
            return "unknown"
        
        state_counts = {}
        for instance in instances:
            state = instance.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
        
        # 가장 많은 상태를 합의 상태로 결정
        if state_counts:
            consensus_state = max(state_counts.items(), key=lambda x: x[1])[0]
            return consensus_state
        
        return "unknown"
    
    async def force_distributed_sync(self):
        """분산 환경에서 강제 동기화"""
        if not self.redis_client:
            logger.warning("Redis client not available for distributed sync")
            return
        
        try:
            # 현재 상태를 강제로 Redis에 저장
            await self._save_state_to_redis()
            
            # 다른 인스턴스들의 최신 상태 확인
            await self._load_state_from_redis()
            
            logger.info(f"Forced distributed synchronization completed for {self.config.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to force distributed sync: {e}")
    
    async def get_distributed_health(self) -> Dict:
        """분산 환경 건강도 확인"""
        if not self.redis_client:
            return {"status": "disabled", "message": "Redis not configured"}
        
        try:
            distributed_info = await self._get_distributed_info()
            instances = distributed_info.get("instances", [])
            
            if not instances:
                return {"status": "isolated", "message": "No other instances found"}
            
            # 상태 분석
            total_instances = len(instances)
            healthy_instances = len([i for i in instances if i.get("state") == "closed"])
            degraded_instances = len([i for i in instances if i.get("state") == "half_open"])
            failed_instances = len([i for i in instances if i.get("state") == "open"])
            
            health_ratio = healthy_instances / total_instances if total_instances > 0 else 0
            
            if health_ratio >= 0.8:
                status = "healthy"
            elif health_ratio >= 0.5:
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "total_instances": total_instances,
                "healthy_instances": healthy_instances,
                "degraded_instances": degraded_instances,
                "failed_instances": failed_instances,
                "health_ratio": health_ratio,
                "consensus_state": distributed_info.get("consensus_state")
            }
            
        except Exception as e:
            logger.error(f"Failed to get distributed health: {e}")
            return {"status": "error", "error": str(e)}

class GlobalCircuitBreakerMiddleware(BaseHTTPMiddleware):
    """글로벌 서킷 브레이커 미들웨어"""
    
    def __init__(self, app: ASGIApp, config: GlobalCircuitConfig, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.config = config
        self.circuit_breaker = GlobalCircuitBreaker(config, redis_client)
        
    async def dispatch(self, request: Request, call_next) -> Response:
        """요청 처리"""
        # 제외 경로 확인
        if request.url.path in self.config.excluded_paths:
            return await call_next(request)
        
        # 서킷 상태 확인
        can_proceed = await self.circuit_breaker.can_proceed()
        
        if not can_proceed:
            logger.warning(
                f"🚫 GLOBAL Circuit Breaker blocking request to {request.url.path}",
                extra={
                    "path": request.url.path,
                    "state": self.circuit_breaker.state.value,
                    "service": self.config.service_name
                }
            )
            raise HTTPException(
                status_code=503,
                detail=f"Service {self.config.service_name} temporarily unavailable - global circuit breaker is {self.circuit_breaker.state.value}"
            )
        
        # 요청 처리
        start_time = time.time()
        success = False
        
        try:
            response = await call_next(request)
            success = response.status_code < 500  # 5xx는 실패로 간주
            return response
        except HTTPException as e:
            success = e.status_code < 500  # 4xx는 성공으로 간주 (클라이언트 오류)
            raise
        except Exception as e:
            success = False  # 기타 예외는 실패
            raise
        finally:
            response_time_ms = (time.time() - start_time) * 1000
            
            # 결과 기록
            await self.circuit_breaker.record_request(success, response_time_ms)
            
            # HALF_OPEN 상태에서의 결과 처리
            if self.circuit_breaker.state == GlobalCircuitState.HALF_OPEN:
                await self.circuit_breaker.handle_half_open_result(success)

# 글로벌 인스턴스
_global_circuit_breaker: Optional[GlobalCircuitBreaker] = None

def get_global_circuit_breaker() -> Optional[GlobalCircuitBreaker]:
    """글로벌 서킷 브레이커 인스턴스 조회"""
    return _global_circuit_breaker

def set_global_circuit_breaker(circuit_breaker: GlobalCircuitBreaker):
    """글로벌 서킷 브레이커 인스턴스 설정"""
    global _global_circuit_breaker
    _global_circuit_breaker = circuit_breaker