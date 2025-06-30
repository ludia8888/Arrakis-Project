"""
Resource Permission Checker
OMS 내부에서 사용하는 최소한의 권한 체크 모듈
실제 인증/인가는 외부 IdP에 위임
"""
import os
from typing import List, Optional, Dict, Any
from shared.clients.unified_http_client import get_unified_http_client
from pydantic import BaseModel
from functools import lru_cache
from datetime import datetime, timezone

from shared.utils.logger import get_logger
from core.integrations.user_service_client import validate_jwt_token
from core.auth import UserContext  # 통합된 UserContext 사용
# Moved permissions inline since models.permissions was removed
from enum import Enum

class ResourceType(str, Enum):
    SCHEMA = "schema"
    OBJECT_TYPE = "object_type"
    PROPERTY = "property"
    LINK_TYPE = "link_type"
    BRANCH = "branch"
    PROPOSAL = "proposal"
    AUDIT = "audit"

class Action(str, Enum):
    READ = "read"
    write = "write"
    delete = "delete"
    execute = "execute"

logger = get_logger(__name__)


class ResourcePermissionChecker:
    """
    리소스 권한 체커
    - JWT 토큰에서 사용자 정보 추출
    - 리소스별 권한 체크
    - IdP 연동 (선택적)
    """
    
    def __init__(
        self,
        idp_endpoint: Optional[str] = None,
        cache_ttl: int = 300  # 5분
    ):
        # JWT validation is now delegated to MSA
        self.http_client = get_unified_http_client() if idp_endpoint else None
        self.idp_endpoint = idp_endpoint or os.getenv("IDP_ENDPOINT")
        self.cache_ttl = cache_ttl
        
        # 기본 권한 매핑 (Role -> Permissions)
        self.role_permissions = {
            "admin": ["*"],  # 모든 권한
            "developer": [
                "schema:*:read",
                "schema:*:create",
                "schema:*:update",
                "validation:*:*",
                "branch:*:create",
                "branch:*:read",
                "branch:*:merge"
            ],
            "reviewer": [
                "schema:*:read",
                "validation:*:read",
                "branch:*:read",
                "branch:*:approve"
            ],
            "viewer": [
                "*:*:read"  # 모든 리소스 읽기 권한
            ]
        }
    
    async def extract_user_from_token(self, token: str) -> Optional[UserContext]:
        """
        JWT 토큰에서 사용자 정보 추출 - MSA를 통해 검증
        """
        try:
            # Bearer 토큰 처리
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Delegate JWT validation to user service MSA
            user_context = await validate_jwt_token(token)
            
            # Add token expiration if available
            if user_context and hasattr(user_context, 'metadata') and user_context.metadata:
                user_context.token_exp = user_context.metadata.get('exp')
            
            return user_context
            
        except ValueError as e:
            logger.error(f"Invalid token format: {e}")
            return None
        except RuntimeError as e:
            logger.error(f"Runtime error extracting user from token via MSA: {e}")
            return None
    
    def check_permission(
        self,
        user: UserContext,
        resource_type: ResourceType,
        resource_id: str,
        action: Action
    ) -> bool:
        """
        권한 체크
        
        Args:
            user: 사용자 컨텍스트
            resource_type: 리소스 타입
            resource_id: 리소스 ID (* for all)
            action: 수행하려는 액션
            
        Returns:
            권한 여부
        """
        if not user.is_authenticated:
            return False
        
        # Admin은 모든 권한
        if "admin" in user.roles:
            return True
        
        # 필요한 권한 문자열 생성
        required_permissions = [
            f"{resource_type}:{resource_id}:{action}",
            f"{resource_type}:*:{action}",
            f"{resource_type}:{resource_id}:*",
            f"{resource_type}:*:*",
            f"*:*:{action}",
            f"*:*:*"
        ]
        
        # 사용자 권한 확인
        user_permissions = set(user.permissions)
        
        # Role 기반 권한 추가
        for role in user.roles:
            if role in self.role_permissions:
                user_permissions.update(self.role_permissions[role])
        
        # 권한 매칭
        for required in required_permissions:
            if required in user_permissions:
                logger.debug(f"Permission granted: {required} for user {user.username}")
                return True
        
        logger.debug(
            f"Permission denied for user {user.username}: "
            f"{resource_type}:{resource_id}:{action}"
        )
        return False
    
    async def check_permission_with_idp(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """
        IdP를 통한 권한 체크 (캐싱 적용)
        
        실제 운영환경에서는 IdP 서비스를 호출하여 권한 확인
        """
        if not self.idp_endpoint:
            # IdP 설정이 없으면 로컬 체크만 수행
            return True
        
        try:
            # IdP API 호출
            response = await self.http_client.post(
                f"{self.idp_endpoint}/check-permission",
                json={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action
                }
            )
            
            if response.status_code == 200:
                return response.json().get("allowed", False)
            else:
                logger.error(f"IdP permission check failed: {response.status_code}")
                return False
                
        except ConnectionError as e:
            logger.error(f"Connection error checking permission with IdP: {e}")
            # IdP 장애시 기본 거부
            return False
        except TimeoutError as e:
            logger.error(f"Timeout checking permission with IdP: {e}")
            # IdP 장애시 기본 거부
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error checking permission with IdP: {e}")
            # IdP 장애시 기본 거부
            return False
    
    def get_user_resources(
        self,
        user: UserContext,
        resource_type: ResourceType,
        action: Action
    ) -> List[str]:
        """
        사용자가 특정 액션을 수행할 수 있는 리소스 목록 조회
        
        Returns:
            리소스 ID 목록 (빈 리스트면 권한 없음, ["*"]이면 모든 리소스)
        """
        if not user.is_authenticated:
            return []
        
        # Admin은 모든 리소스
        if "admin" in user.roles:
            return ["*"]
        
        # 사용자 권한 수집
        user_permissions = set(user.permissions)
        for role in user.roles:
            if role in self.role_permissions:
                user_permissions.update(self.role_permissions[role])
        
        # 매칭되는 리소스 찾기
        resources = set()
        for perm in user_permissions:
            parts = perm.split(":")
            if len(parts) != 3:
                continue
            
            perm_type, perm_resource, perm_action = parts
            
            # 타입과 액션이 매칭되는지 확인
            type_match = perm_type == resource_type or perm_type == "*"
            action_match = perm_action == action or perm_action == "*"
            
            if type_match and action_match:
                resources.add(perm_resource)
        
        # "*" 권한이 있으면 모든 리소스
        if "*" in resources:
            return ["*"]
        
        return list(resources)


# 싱글톤 인스턴스
_permission_checker: Optional[ResourcePermissionChecker] = None


def get_permission_checker() -> ResourcePermissionChecker:
    """권한 체커 인스턴스 반환"""
    global _permission_checker
    if not _permission_checker:
        _permission_checker = ResourcePermissionChecker()
    return _permission_checker


# 편의 함수
async def check_permission(
    token: str,
    resource_type: ResourceType,
    resource_id: str,
    action: Action
) -> bool:
    """
    토큰 기반 권한 체크 편의 함수
    
    Args:
        token: JWT 토큰
        resource_type: 리소스 타입
        resource_id: 리소스 ID
        action: 액션
        
    Returns:
        권한 여부
    """
    checker = get_permission_checker()
    user = await checker.extract_user_from_token(token)
    
    if not user:
        return False
    
    return checker.check_permission(user, resource_type, resource_id, action)