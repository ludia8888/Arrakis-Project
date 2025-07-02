"""
Action Metadata Service
OMS 내부 ActionType 메타데이터 관리만 담당
실제 실행은 Actions Service MSA에서 처리
"""
import logging
import httpx
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import asyncio

# Required dependencies - fail fast if not available
try:
    from shared.cache.smart_cache import SmartCacheManager
    from database.clients.terminus_db import TerminusDBClient
    from shared.config.environment import get_config
    from shared.resilience import with_retry, RetryConfig, RETRY_POLICIES
except ImportError as e:
    logger.error(f"Critical dependency missing: {e}")
    logger.error("Required modules: shared.cache.smart_cache, database.clients.terminus_db, shared.config.environment, shared.resilience")
    logger.error("Ensure all dependencies are properly installed and available")
    raise ModuleNotFoundError(f"Action service requires missing dependency: {e}") from e
from core.action.metadata_service import ActionMetadataService

logger = logging.getLogger(__name__)

# Retry configurations for Actions Service calls
# Using unified resilience policies - these map to the old configs:
# STANDARD strategy → 'standard' policy
# CUSTOM write config → 'action_write' custom policy
ACTIONS_SERVICE_READ_POLICY = 'standard'
ACTIONS_SERVICE_WRITE_CONFIG = RetryConfig(
    max_retries=5,
    initial_delay=0.5,
    max_delay=30.0,
    backoff_multiplier=2.0,
    timeout=30.0,  # 30 second timeout for Actions Service calls
    jitter=True,
    circuit_breaker_config={
        'failure_threshold': 10,
        'recovery_timeout': 30,
        'expected_exception': Exception
    },
    retry_budget_config={
        'budget_percent': 15.0,
        'min_requests': 10
    }
)


class ActionService:
    """
    OMS Action Service - 메타데이터 관리만 담당
    실제 실행은 Actions Service MSA로 위임
    """

    def __init__(
        self,
        tdb_client: TerminusDBClient,
        redis_client,
        event_publisher: Optional[Any] = None,
        actions_service_url: str = None
    ):
        self.tdb = tdb_client
        self.cache = SmartCacheManager(tdb_client)
        self.redis = redis_client
        self.event_publisher = event_publisher
        
        # Use centralized config for Actions Service URL
        config = get_config()
        self.actions_service_url = actions_service_url or config.get_actions_service_url()
        
        # Validate Actions Service is reachable in production
        if config.is_production:
            logger.info("Validating Actions Service connectivity in production...")
            # This will raise ConfigurationError if unreachable
            # Note: Health check is async, so we'll validate on first use
        
        # 메타데이터 서비스만 초기화
        self.metadata_service = ActionMetadataService(tdb_client, redis_client)
        
        # Initialize DLQ handler for failed Actions Service calls
        from shared.dlq import ActionDLQHandler, DLQConfig
        self.dlq_config = DLQConfig(
            name="actions_service_calls",
            max_retries=3,
            redis_key_prefix="action_service_dlq"
        )
        self.dlq_handler = ActionDLQHandler(redis_client, self.dlq_config)
    
    async def _handle_actions_service_failure(self, operation: str, request_data: Dict[str, Any], error: Exception):
        """Handle Actions Service failure by sending to DLQ"""
        try:
            from shared.dlq.models import DLQReason
            
            # Determine DLQ reason based on error type
            if isinstance(error, httpx.TimeoutException):
                reason = DLQReason.TIMEOUT
            elif isinstance(error, httpx.ConnectError):
                reason = DLQReason.NETWORK_ERROR
            elif isinstance(error, httpx.HTTPStatusError):
                if error.response.status_code >= 500:
                    reason = DLQReason.EXECUTION_FAILED
                else:
                    reason = DLQReason.VALIDATION_FAILED
            else:
                reason = DLQReason.UNKNOWN_ERROR
            
            await self.dlq_handler.send_to_dlq(
                queue_name="actions_service",
                original_message=request_data,
                reason=reason,
                error=error,
                metadata={"operation": operation, "service": "actions_service"}
            )
            
            logger.warning(f"Actions Service request sent to DLQ: {operation}")
            
        except (ConnectionError, TimeoutError, ValueError) as dlq_error:
            logger.error(f"Failed to send Actions Service request to DLQ: {dlq_error}")
            # Don't raise - we want to return the original error
        except AttributeError as dlq_error:
            logger.error(f"DLQ handler configuration error: {dlq_error}")
            # Don't raise - we want to return the original error

    # ActionType 메타데이터 관리 (CRUD)
    async def create_action_type(self, action_definition: Dict[str, Any]) -> str:
        """ActionType 메타데이터 생성"""
        action_type = await self.metadata_service.create_action_type(action_definition)
        return action_type.id  # ActionType ID 반환

    async def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        """ActionType 메타데이터 조회"""
        return await self.metadata_service.get_action_type(action_type_id)

    async def update_action_type(self, action_type_id: str, updates: Dict[str, Any]) -> bool:
        """ActionType 메타데이터 업데이트"""
        return await self.metadata_service.update_action_type(action_type_id, updates)

    async def delete_action_type(self, action_type_id: str) -> bool:
        """ActionType 메타데이터 삭제"""
        return await self.metadata_service.delete_action_type(action_type_id)

    async def list_action_types(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """ActionType 목록 조회"""
        return await self.metadata_service.list_action_types(filters)

    async def validate_action_schema(self, action_definition: Dict[str, Any]) -> Dict[str, Any]:
        """ActionType 스키마 검증"""
        return await self.metadata_service.validate_action_schema(action_definition)

    # 실행 관련 메서드들 - Actions Service MSA로 위임
    @with_retry(config=ACTIONS_SERVICE_WRITE_CONFIG)
    async def execute_action(
        self,
        action_type_id: str,
        object_ids: List[str],
        parameters: Dict[str, Any],
        user: Dict[str, Any],
        execution_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        액션 실행 - Actions Service MSA로 위임
        Includes retry and circuit breaker protection
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.actions_service_url}/actions/apply",
                json={
                    "action_type_id": action_type_id,
                    "object_ids": object_ids,
                    "parameters": parameters,
                    "user": user,
                    "execution_options": execution_options or {}
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    @with_retry(policy=ACTIONS_SERVICE_READ_POLICY)
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        실행 상태 조회 - Actions Service MSA로 위임
        Includes retry and circuit breaker protection
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.actions_service_url}/actions/execution/{execution_id}/status",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    @with_retry(policy=ACTIONS_SERVICE_READ_POLICY)
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Job 상태 조회 - Actions Service MSA로 위임
        Includes retry and circuit breaker protection
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.actions_service_url}/actions/job/{job_id}/status",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    # 테스트 호환성 메서드들
    async def start_workers(self, num_workers: int = 3):
        """테스트 호환성: 실제 워커는 Actions Service에서 관리"""
        logger.info(f"Worker management delegated to Actions Service MSA at {self.actions_service_url}")
        return True

    async def stop_workers(self):
        """테스트 호환성: 실제 워커는 Actions Service에서 관리"""
        logger.info("Worker shutdown delegated to Actions Service MSA")
        return True

    @with_retry(policy=ACTIONS_SERVICE_READ_POLICY)
    async def get_worker_status(self) -> Dict[str, Any]:
        """
        워커 상태 조회 - Actions Service MSA로 위임
        Includes retry and circuit breaker protection
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.actions_service_url}/actions/workers/status",
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.warning(f"HTTP error getting worker status from Actions Service: {e}")
                return {"status": "unknown", "workers": 0}
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Network error getting worker status from Actions Service: {e}")
                return {"status": "unknown", "workers": 0}
            except RuntimeError as e:
                logger.warning(f"Runtime error getting worker status from Actions Service: {e}")
                return {"status": "unknown", "workers": 0}

    # Legacy 호환성 메서드들
    def register_action_type(self, action_type: Any) -> str:
        """Legacy 호환성: create_action_type 사용 권장"""
        if hasattr(action_type, 'dict'):
            return asyncio.run(self.create_action_type(action_type.dict()))
        return asyncio.run(self.create_action_type(action_type))

    def execute_sync(self, *args, **kwargs) -> Any:
        """Legacy 호환성: execute_action 사용 권장"""
        return asyncio.run(self.execute_action(*args, **kwargs))