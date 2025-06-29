"""
Service Client for Microservice Communication
"""
import logging
import os
from typing import Optional

import httpx

from core.auth import UserContext as User

logger = logging.getLogger(__name__)


class ServiceClient:
    """마이크로서비스 클라이언트"""

    def __init__(self):
        self.schema_service_url = os.getenv("SCHEMA_SERVICE_URL", "http://schema-service:8000")
        self.branch_service_url = os.getenv("BRANCH_SERVICE_URL", "http://branch-service:8000")
        self.validation_service_url = os.getenv("VALIDATION_SERVICE_URL", "http://validation-service:8000")

    async def get_auth_headers(self, user: Optional[User]) -> dict:
        """인증 헤더 생성"""
        if user and hasattr(user, 'access_token'):
            return {"Authorization": f"Bearer {user.access_token}"}
        elif user:
            # Fallback to user_id for testing
            return {"Authorization": f"Bearer {user.user_id}"}
        return {}

    async def call_service(self, url: str, method: str = "GET", json_data: dict = None, user: Optional[User] = None):
        """서비스 호출"""
        headers = await self.get_auth_headers(user)
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, json=json_data, headers=headers)
            response.raise_for_status()
            return response.json()


service_client = ServiceClient()