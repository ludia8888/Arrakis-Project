"""
ETag Middleware
Handles ETag generation and validation for efficient caching using a decorator-based approach
and resilience patterns.
"""
import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from arrakis_common import get_logger
from bootstrap.config import get_config
from core.auth import UserContext
from core.resilience.version_service_wrapper import get_resilient_version_service
from core.versioning.version_service import get_version_service
from fastapi import Request, Response, status
from middleware.etag_analytics import get_etag_analytics
from models.etag import DeltaRequest
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = get_logger(__name__)

# --- Resilience Configuration ---
ETAG_SERVICE_TIMEOUT = 0.5 # 500ms timeout for version_service calls

class CacheFrequency(Enum):
 """리소스 접근 빈도"""
 VERY_LOW = "very_low" # 하루 1회 미만
 LOW = "low" # 하루 1-10회
 MEDIUM = "medium" # 하루 10-100회
 HIGH = "high" # 하루 100-1000회
 VERY_HIGH = "very_high" # 하루 1000회 이상

class ResourceType(Enum):
 """리소스 타입별 캐싱 특성"""
 SCHEMA = "schema" # 변경 빈도 낮음, 긴 TTL
 DOCUMENT = "document" # 변경 빈도 보통, 중간 TTL
 BRANCH = "branch" # 변경 빈도 높음, 짧은 TTL
 ORGANIZATION = "organization" # 변경 빈도 매우 낮음, 매우 긴 TTL

@dataclass
class AdaptiveTTLConfig:
 """적응형 TTL 설정"""
 resource_type: str
 base_ttl_seconds: int = 300 # 기본 TTL (5분)
 min_ttl_seconds: int = 60 # 최소 TTL (1분)
 max_ttl_seconds: int = 3600 # 최대 TTL (1시간)
 hit_rate_threshold: float = 0.8 # 캐시 히트율 임계값
 access_frequency_weight: float = 0.3 # 접근 빈도 가중치
 modification_frequency_weight: float = 0.4 # 변경 빈도 가중치
 stability_weight: float = 0.3 # 안정성 가중치

@dataclass
class CacheStatistics:
 """캐시 통계"""
 total_requests: int = 0
 cache_hits: int = 0
 cache_misses: int = 0
 last_modified: Optional[datetime] = None
 first_access: Optional[datetime] = None
 last_access: Optional[datetime] = None
 modification_count: int = 0

 @property
 def hit_rate(self) -> float:
 if self.total_requests == 0:
 return 0.0
 return self.cache_hits / self.total_requests

 @property
 def access_frequency(self) -> CacheFrequency:
 if not self.first_access:
 return CacheFrequency.VERY_LOW

 time_span = (datetime.now() - self.first_access).total_seconds()
 if time_span < 86400: # 하루 미만
 daily_accesses = self.total_requests
 else:
 daily_accesses = self.total_requests / (time_span / 86400)

 if daily_accesses >= 1000:
 return CacheFrequency.VERY_HIGH
 elif daily_accesses >= 100:
 return CacheFrequency.HIGH
 elif daily_accesses >= 10:
 return CacheFrequency.MEDIUM
 elif daily_accesses >= 1:
 return CacheFrequency.LOW
 else:
 return CacheFrequency.VERY_LOW

class AdaptiveTTLManager:
 """적응형 TTL 관리자"""

 def __init__(self, redis_client = None):
 self.redis_client = redis_client
 self.stats_cache: Dict[str, CacheStatistics] = {}
 self.ttl_configs: Dict[str, AdaptiveTTLConfig] = {
 "schema": AdaptiveTTLConfig("schema", 1800, 300, 7200), # 30분 기본, 최대 2시간
 "document": AdaptiveTTLConfig("document", 600, 120, 3600), # 10분 기본, 최대 1시간
 "branch": AdaptiveTTLConfig("branch", 300, 60, 1800), # 5분 기본, 최대 30분
 "organization": AdaptiveTTLConfig("organization", 3600, 900, 14400) # 1시간 기본, 최대 4시간
 }

 async def get_adaptive_ttl(self, resource_type: str, resource_id: str) -> int:
 """리소스에 대한 적응형 TTL 계산"""
 cache_key = f"{resource_type}:{resource_id}"

 # 캐시 통계 로드
 stats = await self._load_cache_statistics(cache_key)

 # TTL 설정 가져오기
 config = self.ttl_configs.get(resource_type, AdaptiveTTLConfig(resource_type))

 # 적응형 TTL 계산
 calculated_ttl = await self._calculate_adaptive_ttl(stats, config)

 logger.debug(
 f"Adaptive TTL calculated for {cache_key}: {calculated_ttl}s",
 extra={
 "resource_type": resource_type,
 "resource_id": resource_id,
 "hit_rate": stats.hit_rate,
 "access_frequency": stats.access_frequency.value,
 "calculated_ttl": calculated_ttl
 }
 )

 return calculated_ttl

 async def _calculate_adaptive_ttl(self, stats: CacheStatistics,
     config: AdaptiveTTLConfig) -> int:
 """적응형 TTL 계산 로직"""
 base_ttl = config.base_ttl_seconds

 # 1. 캐시 히트율에 따른 조정
 hit_rate_multiplier = 1.0
 if stats.hit_rate > config.hit_rate_threshold:
 # 높은 히트율 → TTL 증가
 hit_rate_multiplier = 1.0 + (stats.hit_rate - config.hit_rate_threshold) * 2
 elif stats.hit_rate < config.hit_rate_threshold * 0.5:
 # 낮은 히트율 → TTL 감소
 hit_rate_multiplier = 0.5 + (stats.hit_rate / config.hit_rate_threshold) * 0.5

 # 2. 접근 빈도에 따른 조정
 frequency_multiplier = self._get_frequency_multiplier(stats.access_frequency)

 # 3. 변경 빈도에 따른 조정
 modification_multiplier = await self._get_modification_multiplier(stats)

 # 4. 최종 TTL 계산
 adaptive_ttl = int(
 base_ttl *
 (hit_rate_multiplier ** config.access_frequency_weight) *
 (frequency_multiplier ** config.modification_frequency_weight) *
 (modification_multiplier ** config.stability_weight)
 )

 # 최소/최대값 제한
 return max(config.min_ttl_seconds, min(config.max_ttl_seconds, adaptive_ttl))

 def _get_frequency_multiplier(self, frequency: CacheFrequency) -> float:
 """접근 빈도에 따른 배수"""
 multipliers = {
 CacheFrequency.VERY_LOW: 0.5,
 CacheFrequency.LOW: 0.7,
 CacheFrequency.MEDIUM: 1.0,
 CacheFrequency.HIGH: 1.3,
 CacheFrequency.VERY_HIGH: 1.5
 }
 return multipliers.get(frequency, 1.0)

 async def _get_modification_multiplier(self, stats: CacheStatistics) -> float:
 """변경 빈도에 따른 배수"""
 if not stats.first_access:
 return 1.0

 time_span_days = (datetime.now() - stats.first_access).total_seconds() / 86400
 if time_span_days < 1:
 return 1.0

 modifications_per_day = stats.modification_count / time_span_days

 if modifications_per_day < 0.1: # 10일에 1회 미만
 return 1.5
 elif modifications_per_day < 0.5: # 2일에 1회 미만
 return 1.2
 elif modifications_per_day < 2: # 하루에 2회 미만
 return 1.0
 elif modifications_per_day < 10: # 하루에 10회 미만
 return 0.7
 else: # 하루에 10회 이상
 return 0.5

 async def record_cache_access(self, resource_type: str, resource_id: str,
     is_hit: bool):
 """캐시 접근 기록"""
 cache_key = f"{resource_type}:{resource_id}"
 stats = await self._load_cache_statistics(cache_key)

 # 통계 업데이트
 stats.total_requests += 1
 if is_hit:
 stats.cache_hits += 1
 else:
 stats.cache_misses += 1

 if not stats.first_access:
 stats.first_access = datetime.now()
 stats.last_access = datetime.now()

 # Redis에 저장
 await self._save_cache_statistics(cache_key, stats)

 async def record_modification(self, resource_type: str, resource_id: str):
 """리소스 변경 기록"""
 cache_key = f"{resource_type}:{resource_id}"
 stats = await self._load_cache_statistics(cache_key)

 stats.modification_count += 1
 stats.last_modified = datetime.now()

 await self._save_cache_statistics(cache_key, stats)

 async def _load_cache_statistics(self, cache_key: str) -> CacheStatistics:
 """Redis에서 캐시 통계 로드"""
 if not self.redis_client:
 return self.stats_cache.get(cache_key, CacheStatistics())

 try:
 redis_key = f"etag_stats:{cache_key}"
 data = await self.redis_client.get(redis_key)

 if data:
 stats_data = json.loads(data)
 return CacheStatistics(
 total_requests = stats_data.get("total_requests", 0),
 cache_hits = stats_data.get("cache_hits", 0),
 cache_misses = stats_data.get("cache_misses", 0),
 last_modified = datetime.fromisoformat(stats_data["last_modified"]) if stats_data.get("last_modified") else None,


 first_access = datetime.fromisoformat(stats_data["first_access"]) if stats_data.get("first_access") else None,


 last_access = datetime.fromisoformat(stats_data["last_access"]) if stats_data.get("last_access") else None,


 modification_count = stats_data.get("modification_count", 0)
 )

 except Exception as e:
 logger.warning(f"Failed to load cache statistics for {cache_key}: {e}")

 return CacheStatistics()

 async def _save_cache_statistics(self, cache_key: str, stats: CacheStatistics):
 """Redis에 캐시 통계 저장"""
 if not self.redis_client:
 self.stats_cache[cache_key] = stats
 return

 try:
 redis_key = f"etag_stats:{cache_key}"
 stats_data = {
 "total_requests": stats.total_requests,
 "cache_hits": stats.cache_hits,
 "cache_misses": stats.cache_misses,
 "last_modified": stats.last_modified.isoformat() if stats.last_modified else None,
 "first_access": stats.first_access.isoformat() if stats.first_access else None,
 "last_access": stats.last_access.isoformat() if stats.last_access else None,
 "modification_count": stats.modification_count
 }

 # 1주일 TTL로 통계 저장
 await self.redis_client.setex(
 redis_key,
 604800, # 7일
 json.dumps(stats_data, default = str)
 )

 except Exception as e:
 logger.warning(f"Failed to save cache statistics for {cache_key}: {e}")
 # 메모리 캐시로 폴백
 self.stats_cache[cache_key] = stats

# 글로벌 적응형 TTL 매니저
_adaptive_ttl_manager: Optional[AdaptiveTTLManager] = None

def get_adaptive_ttl_manager() -> Optional[AdaptiveTTLManager]:
 """적응형 TTL 매니저 인스턴스 반환"""
 return _adaptive_ttl_manager

def set_adaptive_ttl_manager(manager: AdaptiveTTLManager):
 """적응형 TTL 매니저 설정"""
 global _adaptive_ttl_manager
 _adaptive_ttl_manager = manager

# --- Prometheus Metrics ---
# (Metrics definitions remain unchanged)
etag_requests_total = Counter(
 'etag_requests_total', 'Total number of ETag requests', ['method', 'resource_type',
     'result']
)
etag_cache_hits = Counter(
 'etag_cache_hits_total', 'Number of ETag cache hits (304 responses)', ['resource_type']
)
etag_cache_misses = Counter(
 'etag_cache_misses_total', 'Number of ETag cache misses (200 responses with ETag)',
     ['resource_type']
)
etag_validation_duration = Histogram(
 'etag_validation_duration_seconds', 'Time spent validating ETags', ['resource_type']
)
etag_generation_duration = Histogram(
 'etag_generation_duration_seconds', 'Time spent generating ETags', ['resource_type']
)
etag_cache_effectiveness = Gauge(
 'etag_cache_effectiveness_ratio', 'Cache hit ratio (hits / total requests)',
     ['resource_type']
)

# --- Decorator for enabling ETag on routes ---

def enable_etag(resource_type_func: Callable[[Dict], str],
    resource_id_func: Callable[[Dict], str], branch_func: Callable[[Dict], str]):
 """
 Decorator to enable ETag handling for a specific FastAPI route.
 Instead of static strings, this now accepts functions that extract
 the necessary info from path parameters, allowing for more flexible
 and complex URL structures.

 Args:
 resource_type_func: A function that takes path_params and returns the resource type.
 resource_id_func: A function that takes path_params and returns the resource ID.
 branch_func: A function that takes path_params and returns the branch name.
 """
 def decorator(func):
 @wraps(func)
 async def wrapper(*args, **kwargs):
 return await func(*args, **kwargs)

 # Attach metadata to the endpoint function for the middleware to find
 wrapper._etag_info = {
 "resource_type_func": resource_type_func,
 "resource_id_func": resource_id_func,
 "branch_func": branch_func,
 }
 return wrapper
 return decorator


class ETagMiddleware(BaseHTTPMiddleware):
 """
 Middleware for handling ETags and conditional requests.
 This version uses a decorator-based approach for safety and maintainability
 and includes resilience patterns (timeout, fallback) for service calls.
 """

 def __init__(self, app: ASGIApp):
 super().__init__(app)
 self.config = get_config()
 self.timeout = self.config.service.resilience_timeout
 self.version_service = None
 self.analytics = get_etag_analytics()
 self.adaptive_ttl_manager = None

 async def dispatch(self, request: Request, call_next: Callable) -> Response:
 """Process request with ETag handling"""
 # Check if E-Tag caching is enabled
 if not os.getenv('ENABLE_ETAG_CACHING', 'false').lower() == 'true':
 return await call_next(request)

 # Initialize version service and adaptive TTL manager if needed (lazy initialization)
 if not self.version_service:
 # Get redis client from app state
 redis_client = getattr(request.app.state, 'redis_client', None)
 if redis_client:
 self.version_service = await get_resilient_version_service(redis_client)
 # Initialize adaptive TTL manager
 if not self.adaptive_ttl_manager:
 self.adaptive_ttl_manager = AdaptiveTTLManager(redis_client)
 set_adaptive_ttl_manager(self.adaptive_ttl_manager)
 logger.info("Adaptive TTL manager initialized")
 else:
 # Skip ETag functionality if redis is not available
 logger.warning("Redis client not available, skipping ETag functionality")
 return await call_next(request)

 # Process the request normally first
 response = await call_next(request)

 # For GET requests with conditional headers, check if we can return 304
 if request.method == "GET":
 if_none_match = request.headers.get("If-None-Match")
 if if_none_match:
 # Check if the endpoint has ETag enabled (after routing)
 etag_info = self._get_etag_info_from_request(request)
 if etag_info:
 # Extract resource context using functions provided by the decorator
 resource_ctx = self._build_resource_context(request.path_params, etag_info)
 if resource_ctx:
 # --- Resilience Pattern: Timeout and Fallback ---
 try:
 start_time = time.time()
 # Validate ETag with a strict timeout
 is_valid, _ = await asyncio.wait_for(
 self.version_service.validate_etag(
 resource_type = resource_ctx["type"],
 resource_id = resource_ctx["id"],
 branch = resource_ctx["branch"],
 client_etag = if_none_match
 ),
 timeout = self.timeout
 )
 validation_time = time.time() - start_time
 etag_validation_duration.labels(resource_type = resource_ctx["type"]).observe(validation_time)

 if is_valid:
 # Cache hit - return 304 Not Modified
 etag_cache_hits.labels(resource_type = resource_ctx["type"]).inc()
 etag_requests_total.labels(method = 'GET', resource_type = resource_ctx["type"],
     result = "cache_hit").inc()
 logger.info("ETag cache hit", extra={"resource_ctx": resource_ctx,
     "etag": if_none_match})

 # Record cache hit for adaptive TTL
 if self.adaptive_ttl_manager:
 await self.adaptive_ttl_manager.record_cache_access(
 resource_ctx["type"],
 resource_ctx["id"],
 is_hit = True
 )

 self.analytics.record_request(
 resource_type = resource_ctx["type"],
 is_cache_hit = True,
 response_time_ms = validation_time * 1000,
 etag = if_none_match
 )

 # Calculate adaptive Cache-Control headers
 cache_control_headers = await self._get_adaptive_cache_headers(resource_ctx)
 response_headers = {"ETag": if_none_match}
 response_headers.update(cache_control_headers)

 return Response(
 status_code = status.HTTP_304_NOT_MODIFIED,
 headers = response_headers
 )

 except asyncio.TimeoutError:
 # Fallback: ETag 검사를 포기하고 실제 응답 반환
 logger.warning(
 "ETag version service timed out, bypassing ETag check",
 timeout = self.timeout
 )
 self.analytics.record_timeout()
 except Exception as e:
 logger.error(f"ETag validation failed with an unexpected error: {e}",
     extra={"resource_ctx": resource_ctx})

 # Now check if the endpoint has ETag enabled (after routing)
 etag_info = self._get_etag_info_from_request(request)
 if not etag_info:
 return response

 # Extract resource context using functions provided by the decorator
 resource_ctx = self._build_resource_context(request.path_params, etag_info)
 if not resource_ctx:
 logger.warning(f"ETag: Could not build resource context for {request.url.path}")
 return response

 # Add ETag to successful GET responses
 if response.status_code == 200 and request.method == "GET":
 # --- Resilience Pattern: Timeout and Fallback ---
 try:
 start_time = time.time()
 # Get resource version with a strict timeout
 version = await asyncio.wait_for(
 self.version_service.get_resource_version(
 resource_type = resource_ctx["type"],
 resource_id = resource_ctx["id"],
 branch = resource_ctx["branch"]
 ),
 timeout = self.timeout
 )
 generation_time = time.time() - start_time
 etag_generation_duration.labels(resource_type = resource_ctx["type"]).observe(generation_time)

 if version:
 response.headers["ETag"] = version.current_version.etag
 response.headers["X-Version"] = str(version.current_version.version)

 # Add adaptive Cache-Control headers
 cache_control_headers = await self._get_adaptive_cache_headers(resource_ctx)
 for header, value in cache_control_headers.items():
 response.headers[header] = value

 etag_cache_misses.labels(resource_type = resource_ctx["type"]).inc()
 etag_requests_total.labels(method = 'GET', resource_type = resource_ctx["type"],
     result = "cache_miss").inc()
 logger.info("ETag cache miss - generated new ETag", extra={
 "resource_ctx": resource_ctx,
 "etag": version.current_version.etag,
 "adaptive_ttl": cache_control_headers.get("Cache-Control")
 })

 # Record cache miss for adaptive TTL
 if self.adaptive_ttl_manager:
 await self.adaptive_ttl_manager.record_cache_access(
 resource_ctx["type"],
 resource_ctx["id"],
 is_hit = False
 )

 self.analytics.record_request(
 resource_type = resource_ctx["type"],
 is_cache_hit = False,
 response_time_ms = generation_time * 1000,
 etag = version.current_version.etag
 )
 self._update_cache_effectiveness(resource_ctx["type"])
 else:
 # No version found, create initial version based on response content
 try:
 from core.auth_utils import UserContext

 # Get response content for hashing
 response_body = b""
 if hasattr(response, 'body'):
 response_body = response.body
 elif hasattr(response, 'content'):
 response_body = response.content

 # Create a user context for version creation
 user_context = UserContext(
 user_id = "system",
 username = "system",
 email = "system@oms.local",
 roles = ["system"],
 tenant_id = "default"
 )

 # Create initial version
 import json
 content_dict = {}
 try:
 content_str = response_body.decode('utf-8') if response_body else "{}"
 content_dict = json.loads(content_str) if content_str != "{}" else {}
 except:
 content_dict = {"raw_content": response_body.decode('utf-8', errors = 'ignore')}

 initial_version = await self.version_service.track_change(
 resource_type = resource_ctx["type"],
 resource_id = resource_ctx["id"],
 branch = resource_ctx["branch"],
 content = content_dict,
 change_type = "initial_version",
 user = user_context,
 change_summary = "Initial version created by ETag middleware"
 )

 if initial_version:
 response.headers["ETag"] = initial_version.current_version.etag
 response.headers["X-Version"] = str(initial_version.current_version.version)
 logger.info("ETag - created initial version", extra={
 "resource_ctx": resource_ctx,
 "etag": initial_version.current_version.etag
 })

 except Exception as e:
 logger.error(f"Failed to create initial ETag version: {e}",
     extra={"resource_ctx": resource_ctx})

 except asyncio.TimeoutError:
 # Fallback: ETag 검사를 포기하고 실제 응답 반환
 logger.warning(
 "ETag version service timed out, bypassing ETag check",
 timeout = self.timeout
 )
 self.analytics.record_timeout()
 return await call_next(request)
 except Exception as e:
 logger.error(f"ETag generation failed with an unexpected error: {e}",
     extra={"resource_ctx": resource_ctx})

 return response

 def _get_etag_info_from_request(self, request: Request) -> Optional[Dict[str, Any]]:
 """Check if the matched route's endpoint has ETag info attached by the decorator."""
 # Use official FastAPI attributes for accessing route information
 # Note: These are accessed after routing is complete in middleware
 endpoint = None
 route = None

 # Safely access scope data with fallbacks
 try:
 # request.scope is the official way to access ASGI scope
 # but we should use it carefully and defensively
 route = request.scope.get("route") if "route" in request.scope else None
 endpoint = request.scope.get("endpoint") if "endpoint" in request.scope else None

 logger.debug(f"Route found: {route is not None},
     Endpoint found: {endpoint is not None}")

 # If endpoint is not directly available, try to extract from route
 if not endpoint and route:
 endpoint = getattr(route, "endpoint", None)
 logger.debug(f"Got endpoint from route: {endpoint}")
 except Exception as e:
 logger.debug(f"Failed to access route info from scope: {e}")
 return None

 # Check various ways the ETag info might be attached
 if endpoint:
 # Direct attachment
 if hasattr(endpoint, "_etag_info"):
 logger.debug("Found ETag info directly on endpoint")
 return endpoint._etag_info

 # Check wrapped function (common with @inject decorator)
 if hasattr(endpoint, "__wrapped__"):
 wrapped = endpoint.__wrapped__
 logger.debug(f"Checking wrapped function: {wrapped}")
 if hasattr(wrapped, "_etag_info"):
 logger.debug("Found ETag info on wrapped endpoint")
 return wrapped._etag_info

 # Check double wrapped (when multiple decorators are used)
 if hasattr(wrapped, "__wrapped__") and hasattr(wrapped.__wrapped__, "_etag_info"):
 logger.debug("Found ETag info on double-wrapped endpoint")
 return wrapped.__wrapped__._etag_info

 # Check if it's a dependency_injector wrapped function
 if hasattr(endpoint, "func") and hasattr(endpoint.func, "_etag_info"):
 logger.debug("Found ETag info on DI wrapped function")
 return endpoint.func._etag_info

 # Last resort: check all attributes
 for attr_name in dir(endpoint):
 if not attr_name.startswith('_'):
 attr = getattr(endpoint, attr_name, None)
 if attr and hasattr(attr, "_etag_info"):
 logger.debug(f"Found ETag info on attribute {attr_name}")
 return attr._etag_info

 logger.debug(f"No ETag info found for {request.url.path}")
 return None

 def _build_resource_context(self, path_params: Dict, etag_info: Dict[str,
     Callable]) -> Optional[Dict[str, str]]:
 """Build the resource context using the extractor functions from the decorator."""
 try:
 return {
 "type": etag_info["resource_type_func"](path_params),
 "id": etag_info["resource_id_func"](path_params),
 "branch": etag_info["branch_func"](path_params),
 }
 except (KeyError, Exception) as e:
 logger.error(f"Failed to build resource context from path_params: {path_params} and etag_info. Error: {e}")
 return None

 def _update_cache_effectiveness(self, resource_type: str):
 """Updates the Prometheus Gauge for cache effectiveness."""
 # This function can be simplified as Prometheus can compute ratios with `rate()`
 pass

 async def _get_adaptive_cache_headers(self, resource_ctx: Dict[str, str]) -> Dict[str,
     str]:
 """적응형 캐시 헤더 생성"""
 headers = {}

 if not self.adaptive_ttl_manager:
 # Fallback to default cache headers
 headers["Cache-Control"] = "public, max-age = 300, must-revalidate"
 return headers

 try:
 # 적응형 TTL 계산
 adaptive_ttl = await self.adaptive_ttl_manager.get_adaptive_ttl(
 resource_ctx["type"],
 resource_ctx["id"]
 )

 # Cache-Control 헤더 생성
 cache_control_parts = [
 "public",
 f"max-age={adaptive_ttl}",
 "must-revalidate"
 ]

 # 리소스 타입별 추가 설정
 resource_type = resource_ctx["type"]
 if resource_type == "schema":
 # 스키마는 상대적으로 안정적이므로 더 긴 캐싱 허용
 cache_control_parts.append("stale-while-revalidate = 300")
 elif resource_type == "document":
 # 문서는 변경이 있을 수 있으므로 검증 필수
 cache_control_parts.append("stale-if-error = 60")
 elif resource_type == "branch":
 # 브랜치는 변경이 빈번하므로 짧은 캐싱
 cache_control_parts.append("no-cache")

 headers["Cache-Control"] = ", ".join(cache_control_parts)

 # Vary 헤더 추가 (적응형 캐싱 지원)
 headers["Vary"] = "Accept, Accept-Encoding, Authorization"

 # X-Cache-Strategy 헤더 (디버깅용)
 headers["X-Cache-Strategy"] = f"adaptive-ttl-{adaptive_ttl}s"

 logger.debug(
 f"Generated adaptive cache headers for {resource_ctx['type']}:{resource_ctx['id']}",
 extra={
 "adaptive_ttl": adaptive_ttl,
 "cache_control": headers["Cache-Control"]
 }
 )

 except Exception as e:
 logger.warning(f"Failed to calculate adaptive cache headers: {e}")
 # Fallback to default
 headers["Cache-Control"] = "public, max-age = 300, must-revalidate"
 headers["X-Cache-Strategy"] = "fallback-default"

 return headers

# (The function to add the middleware to the app remains the same)
def configure_etag_middleware(app):
 """Adds the ETagMiddleware to the FastAPI application."""
 app.add_middleware(ETagMiddleware)
 logger.info("ETag middleware configured")
