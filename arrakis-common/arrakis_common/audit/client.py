"""
통합 감사 로깅 클라이언트
모든 MSA 서비스에서 감사 로그를 중앙화하여 처리
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AuditClient:
    """감사 서비스 클라이언트"""

    def __init__(
        self,
        audit_service_url: str = None,
        service_name: str = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.audit_service_url = audit_service_url or os.getenv(
            "AUDIT_SERVICE_URL", "http://localhost:8001"
        )
        self.service_name = service_name or os.getenv("SERVICE_NAME", "unknown")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None
        self._async_client = None

    @property
    def client(self) -> httpx.Client:
        """동기 HTTP 클라이언트"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.audit_service_url, timeout=self.timeout
            )
        return self._client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """비동기 HTTP 클라이언트"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.audit_service_url, timeout=self.timeout
            )
        return self._async_client

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        action: str = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None,
        data_classification: str = "internal",
    ) -> Optional[Dict[str, Any]]:
        """감사 이벤트 로깅 (동기)"""

        event_data = {
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "service": self.service_name,
            "action": action or event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "compliance_tags": compliance_tags or [],
            "data_classification": data_classification,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # None 값 제거
        event_data = {k: v for k, v in event_data.items() if v is not None}

        for attempt in range(self.max_retries):
            try:
                response = self.client.post("/api/v2/events", json=event_data)

                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.warning(
                        f"Audit service returned {response.status_code}: {response.text}"
                    )

            except Exception as e:
                logger.error(f"Failed to send audit event (attempt {attempt + 1}): {e}")

                if attempt < self.max_retries - 1:
                    # 재시도 대기
                    import time

                    time.sleep(2**attempt)

        return None

    async def log_event_async(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        action: str = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None,
        data_classification: str = "internal",
    ) -> Optional[Dict[str, Any]]:
        """감사 이벤트 로깅 (비동기)"""

        event_data = {
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "service": self.service_name,
            "action": action or event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "compliance_tags": compliance_tags or [],
            "data_classification": data_classification,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # None 값 제거
        event_data = {k: v for k, v in event_data.items() if v is not None}

        for attempt in range(self.max_retries):
            try:
                response = await self.async_client.post(
                    "/api/v2/events", json=event_data
                )

                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.warning(
                        f"Audit service returned {response.status_code}: {response.text}"
                    )

            except Exception as e:
                logger.error(f"Failed to send audit event (attempt {attempt + 1}): {e}")

                if attempt < self.max_retries - 1:
                    # 재시도 대기
                    await asyncio.sleep(2**attempt)

        return None

    def create_audit_trail(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        changes: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """감사 추적 생성"""

        return self.log_event(
            event_type=f"{entity_type}.{action}",
            action=action,
            resource_type=entity_type,
            resource_id=entity_id,
            user_id=user_id,
            details={"changes": changes or {}, "metadata": metadata or {}},
        )

    def __del__(self):
        """클라이언트 정리"""
        if self._client:
            self._client.close()
        if self._async_client:
            asyncio.create_task(self._async_client.aclose())


# 전역 클라이언트 인스턴스
_default_client = None


@lru_cache(maxsize=1)
def get_audit_client() -> AuditClient:
    """기본 감사 클라이언트 가져오기 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = AuditClient()
    return _default_client


# 편의 함수들
def audit_log(
    event_type: str,
    user_id: Optional[str] = None,
    action: str = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    result: str = "success",
    details: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """감사 로그 기록 (간편 함수)"""
    client = get_audit_client()
    return client.log_event(
        event_type=event_type,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        details=details,
        **kwargs,
    )


async def audit_log_async(
    event_type: str,
    user_id: Optional[str] = None,
    action: str = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    result: str = "success",
    details: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """감사 로그 기록 (비동기 간편 함수)"""
    client = get_audit_client()
    return await client.log_event_async(
        event_type=event_type,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        details=details,
        **kwargs,
    )


def log_event(event_type: str, **kwargs) -> Optional[Dict[str, Any]]:
    """이벤트 로깅 (audit_log의 별칭)"""
    return audit_log(event_type, **kwargs)


def create_audit_trail(
    action: str, entity_type: str, entity_id: str, **kwargs
) -> Optional[Dict[str, Any]]:
    """감사 추적 생성"""
    client = get_audit_client()
    return client.create_audit_trail(
        action=action, entity_type=entity_type, entity_id=entity_id, **kwargs
    )
