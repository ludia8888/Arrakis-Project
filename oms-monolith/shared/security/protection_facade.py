"""
Protection Facade - Circuit Breaker & Rate Limiter 통합
우회 불가능한 단일 보호 계층 제공
"""

import asyncio
import time
import hashlib
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from shared.utils.logger import get_logger
from shared.exceptions import OntologyException

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """회로 차단기 상태"""
    CLOSED = "closed"        # 정상 작동
    OPEN = "open"           # 차단 상태
    HALF_OPEN = "half_open" # 복구 테스트 중


class RateLimitStrategy(str, Enum):
    """Rate Limiting 전략"""
    FIXED_WINDOW = "fixed_window"        # 고정 윈도우
    SLIDING_WINDOW = "sliding_window"    # 슬라이딩 윈도우
    TOKEN_BUCKET = "token_bucket"        # 토큰 버킷
    LEAKY_BUCKET = "leaky_bucket"       # 누수 버킷
    ADAPTIVE = "adaptive"                # 적응형


@dataclass
class CircuitBreakerConfig:
    """회로 차단기 설정"""
    failure_threshold: int = 5           # 실패 임계값
    success_threshold: int = 3           # 복구 성공 임계값
    timeout: float = 60.0               # 타임아웃 (초)
    half_open_timeout: float = 30.0     # Half-open 타임아웃
    
    # 진단 설정
    enable_health_check: bool = True
    health_check_interval: float = 10.0
    failure_rate_threshold: float = 0.5  # 50% 실패율
    
    # Redis 분산 설정
    use_distributed_state: bool = True
    redis_key_prefix: str = "circuit_breaker"


@dataclass 
class RateLimiterConfig:
    """Rate Limiter 설정"""
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    requests_per_window: int = 100       # 윈도우당 요청 수
    window_size: int = 60               # 윈도우 크기 (초)
    
    # Token/Leaky Bucket 설정
    bucket_capacity: int = 100
    refill_rate: float = 1.0            # 초당 토큰 보충률
    
    # Adaptive 설정
    enable_adaptive: bool = False
    adaptive_factor: float = 1.5
    load_threshold: float = 0.8
    
    # 분산 설정
    use_distributed_state: bool = True
    redis_key_prefix: str = "rate_limiter"


class ProtectionViolation(OntologyException):
    """보호 계층 위반 예외"""
    
    def __init__(
        self,
        message: str,
        violation_type: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.violation_type = violation_type
        self.context = context or {}
        self.timestamp = time.time()


class CircuitBreaker:
    """Enterprise-grade Circuit Breaker"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        
        # 상태 카운터
        self.failure_count = 0
        self.success_count = 0
        self.request_count = 0
        
        # 타이밍
        self.last_failure_time = 0.0
        self.state_change_time = time.time()
        
        # 통계
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        
        # 분산 상태 (Redis)
        self._redis_client = None
        if config.use_distributed_state:
            self._setup_distributed_state()
    
    def _setup_distributed_state(self):
        """Redis 분산 상태 설정"""
        try:
            from shared.clients.redis_ha_client import RedisHAClient
            self._redis_client = RedisHAClient()
        except Exception as e:
            logger.warning(f"Failed to setup distributed circuit breaker state: {e}")
            self.config.use_distributed_state = False
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """보호된 함수 실행"""
        await self._check_state()
        
        if self.state == CircuitState.OPEN:
            raise ProtectionViolation(
                f"Circuit breaker '{self.name}' is OPEN",
                violation_type="CIRCUIT_OPEN",
                context={
                    "circuit_name": self.name,
                    "failure_count": self.failure_count,
                    "last_failure": self.last_failure_time
                }
            )
        
        start_time = time.time()
        self.request_count += 1
        self.total_requests += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._record_success()
            return result
            
        except Exception as e:
            await self._record_failure()
            raise
        
        finally:
            execution_time = time.time() - start_time
            logger.debug(f"Circuit breaker '{self.name}' execution: {execution_time:.3f}s")
    
    async def _check_state(self):
        """상태 확인 및 전환"""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time >= self.config.timeout:
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.failure_count = 0
                await self._update_distributed_state()
        
        elif self.state == CircuitState.HALF_OPEN:
            if current_time - self.state_change_time >= self.config.half_open_timeout:
                logger.warning(f"Circuit breaker '{self.name}' half-open timeout, returning to OPEN")
                self.state = CircuitState.OPEN
                self.last_failure_time = current_time
                await self._update_distributed_state()
    
    async def _record_success(self):
        """성공 기록"""
        self.success_count += 1
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.state_change_time = time.time()
                await self._update_distributed_state()
    
    async def _record_failure(self):
        """실패 기록"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN")
                self.state = CircuitState.OPEN
                self.state_change_time = time.time()
                await self._update_distributed_state()
        
        elif self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' failed in half-open, returning to OPEN")
            self.state = CircuitState.OPEN
            self.state_change_time = time.time()
            await self._update_distributed_state()
    
    async def _update_distributed_state(self):
        """분산 상태 업데이트"""
        if not self._redis_client:
            return
        
        try:
            state_key = f"{self.config.redis_key_prefix}:{self.name}:state"
            state_data = {
                "state": self.state,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "state_change_time": self.state_change_time
            }
            await self._redis_client.setex(state_key, 300, state_data)
        except Exception as e:
            logger.error(f"Failed to update distributed circuit breaker state: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": self.total_failures / max(self.total_requests, 1),
            "last_failure_time": self.last_failure_time,
            "state_change_time": self.state_change_time
        }


class RateLimiter:
    """Enterprise-grade Rate Limiter with multiple strategies"""
    
    def __init__(self, name: str, config: RateLimiterConfig):
        self.name = name
        self.config = config
        
        # 전략별 저장소
        self._windows: Dict[str, List[float]] = {}
        self._buckets: Dict[str, Dict[str, float]] = {}
        
        # 분산 상태
        self._redis_client = None
        if config.use_distributed_state:
            self._setup_distributed_state()
        
        # 적응형 설정
        self._adaptive_limits: Dict[str, int] = {}
        self._load_history: List[float] = []
    
    def _setup_distributed_state(self):
        """Redis 분산 상태 설정"""
        try:
            from shared.clients.redis_ha_client import RedisHAClient
            self._redis_client = RedisHAClient()
        except Exception as e:
            logger.warning(f"Failed to setup distributed rate limiter state: {e}")
            self.config.use_distributed_state = False
    
    async def check_limit(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Rate limit 확인"""
        if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._check_sliding_window(identifier)
        elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._check_token_bucket(identifier)
        elif self.config.strategy == RateLimitStrategy.ADAPTIVE:
            return await self._check_adaptive(identifier)
        else:
            return await self._check_fixed_window(identifier)
    
    async def _check_sliding_window(self, identifier: str) -> Optional[Dict[str, Any]]:
        """슬라이딩 윈도우 검사"""
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        # 분산 상태 확인
        if self._redis_client:
            return await self._check_distributed_sliding_window(identifier, current_time, window_start)
        
        # 로컬 상태 확인
        if identifier not in self._windows:
            self._windows[identifier] = []
        
        # 만료된 요청 제거
        self._windows[identifier] = [
            req_time for req_time in self._windows[identifier]
            if req_time > window_start
        ]
        
        # 현재 요청 수 확인
        current_requests = len(self._windows[identifier])
        
        if current_requests >= self.config.requests_per_window:
            return {
                "violation_type": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {current_requests}/{self.config.requests_per_window} requests in {self.config.window_size}s",
                "limit": self.config.requests_per_window,
                "window": self.config.window_size,
                "current_requests": current_requests,
                "retry_after": int(self._windows[identifier][0] + self.config.window_size - current_time) if self._windows[identifier] else 0
            }
        
        # 요청 기록
        self._windows[identifier].append(current_time)
        return None
    
    async def _check_distributed_sliding_window(
        self, 
        identifier: str, 
        current_time: float, 
        window_start: float
    ) -> Optional[Dict[str, Any]]:
        """분산 슬라이딩 윈도우 검사"""
        try:
            key = f"{self.config.redis_key_prefix}:{self.name}:{identifier}"
            
            # Redis에서 윈도우 데이터 조회
            requests = await self._redis_client.zrangebyscore(
                key, window_start, current_time
            )
            
            if len(requests) >= self.config.requests_per_window:
                oldest_request = float(requests[0]) if requests else current_time
                retry_after = int(oldest_request + self.config.window_size - current_time)
                
                return {
                    "violation_type": "RATE_LIMIT_EXCEEDED",
                    "message": f"Distributed rate limit exceeded: {len(requests)}/{self.config.requests_per_window} requests",
                    "limit": self.config.requests_per_window,
                    "current_requests": len(requests),
                    "retry_after": max(retry_after, 0)
                }
            
            # 현재 요청 기록
            await self._redis_client.zadd(key, {str(current_time): current_time})
            await self._redis_client.expire(key, self.config.window_size + 10)
            
            # 만료된 요청 정리
            await self._redis_client.zremrangebyscore(key, 0, window_start)
            
            return None
            
        except Exception as e:
            logger.error(f"Distributed rate limiting failed: {e}")
            # 분산 실패 시 로컬로 폴백
            return await self._check_sliding_window(identifier)
    
    async def _check_token_bucket(self, identifier: str) -> Optional[Dict[str, Any]]:
        """토큰 버킷 검사"""
        current_time = time.time()
        
        if identifier not in self._buckets:
            self._buckets[identifier] = {
                "tokens": float(self.config.bucket_capacity),
                "last_refill": current_time
            }
        
        bucket = self._buckets[identifier]
        
        # 토큰 보충
        time_passed = current_time - bucket["last_refill"]
        tokens_to_add = time_passed * self.config.refill_rate
        bucket["tokens"] = min(
            self.config.bucket_capacity,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_refill"] = current_time
        
        # 토큰 소비
        if bucket["tokens"] < 1:
            return {
                "violation_type": "RATE_LIMIT_EXCEEDED",
                "message": "Token bucket exhausted",
                "bucket_capacity": self.config.bucket_capacity,
                "refill_rate": self.config.refill_rate,
                "current_tokens": bucket["tokens"],
                "retry_after": int(1 / self.config.refill_rate)
            }
        
        bucket["tokens"] -= 1
        return None
    
    async def _check_adaptive(self, identifier: str) -> Optional[Dict[str, Any]]:
        """적응형 Rate Limiting"""
        # 현재 시스템 부하 계산
        current_load = await self._calculate_system_load()
        
        # 동적 제한값 계산
        if current_load > self.config.load_threshold:
            adaptive_limit = int(self.config.requests_per_window / self.config.adaptive_factor)
        else:
            adaptive_limit = self.config.requests_per_window
        
        self._adaptive_limits[identifier] = adaptive_limit
        
        # 기존 슬라이딩 윈도우 로직 사용하되 동적 제한값 적용
        original_limit = self.config.requests_per_window
        self.config.requests_per_window = adaptive_limit
        
        result = await self._check_sliding_window(identifier)
        
        # 원래 제한값 복원
        self.config.requests_per_window = original_limit
        
        if result:
            result["adaptive_limit"] = adaptive_limit
            result["system_load"] = current_load
        
        return result
    
    async def _calculate_system_load(self) -> float:
        """시스템 부하 계산 (간단한 구현)"""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return max(cpu_percent, memory_percent) / 100.0
        except:
            return 0.5  # 기본값


class ProtectionFacade:
    """
    보호 Facade - Circuit Breaker와 Rate Limiter의 통합 관리
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._default_circuit_config = CircuitBreakerConfig()
        self._default_rate_config = RateLimiterConfig()
    
    def get_circuit_breaker(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Circuit Breaker 인스턴스 반환"""
        if name not in self._circuit_breakers:
            config = config or self._default_circuit_config
            self._circuit_breakers[name] = CircuitBreaker(name, config)
        return self._circuit_breakers[name]
    
    def get_rate_limiter(
        self,
        name: str,
        config: Optional[RateLimiterConfig] = None
    ) -> RateLimiter:
        """Rate Limiter 인스턴스 반환"""
        if name not in self._rate_limiters:
            config = config or self._default_rate_config
            self._rate_limiters[name] = RateLimiter(name, config)
        return self._rate_limiters[name]
    
    async def protect_execution(
        self,
        func: Callable,
        circuit_breaker_name: str,
        rate_limiter_name: str,
        rate_limit_identifier: str,
        *args,
        **kwargs
    ) -> Any:
        """완전 보호된 함수 실행 (Circuit Breaker + Rate Limiter)"""
        
        # 1. Rate Limit 확인
        rate_limiter = self.get_rate_limiter(rate_limiter_name)
        rate_violation = await rate_limiter.check_limit(rate_limit_identifier)
        
        if rate_violation:
            raise ProtectionViolation(
                rate_violation["message"],
                rate_violation["violation_type"],
                rate_violation
            )
        
        # 2. Circuit Breaker로 실행
        circuit_breaker = self.get_circuit_breaker(circuit_breaker_name)
        return await circuit_breaker.execute(func, *args, **kwargs)
    
    def get_protection_stats(self) -> Dict[str, Any]:
        """모든 보호 장치 통계 반환"""
        return {
            "circuit_breakers": {
                name: breaker.get_stats()
                for name, breaker in self._circuit_breakers.items()
            },
            "rate_limiters": {
                name: {
                    "name": limiter.name,
                    "config": {
                        "strategy": limiter.config.strategy,
                        "requests_per_window": limiter.config.requests_per_window,
                        "window_size": limiter.config.window_size
                    },
                    "adaptive_limits": getattr(limiter, "_adaptive_limits", {})
                }
                for name, limiter in self._rate_limiters.items()
            }
        }


# 글로벌 인스턴스
_protection_facade_instance: Optional[ProtectionFacade] = None


def get_protection_facade() -> ProtectionFacade:
    """글로벌 ProtectionFacade 인스턴스 반환"""
    global _protection_facade_instance
    if _protection_facade_instance is None:
        _protection_facade_instance = ProtectionFacade()
    return _protection_facade_instance