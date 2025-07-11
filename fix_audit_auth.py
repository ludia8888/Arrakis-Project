#!/usr/bin/env python3
"""
Audit Service 인증 문제 해결 스크립트
API 키 기반 인증을 추가하여 서비스 간 통신 가능하게 함
"""

# audit-service/utils/auth.py 파일에 추가해야 할 코드
AUDIT_SERVICE_AUTH_UPDATE = '''
# 기존 imports에 추가
import os
from typing import Optional

# 서비스 간 통신용 API 키
INTERNAL_API_KEYS = {
    "oms-monolith": os.getenv("OMS_API_KEY", "oms-internal-key-2025"),
    "user-service": os.getenv("USER_SERVICE_API_KEY", "user-internal-key-2025"),
}

async def get_current_user_or_service(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_service_account: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    JWT 토큰 또는 API 키를 통한 인증
    
    1. JWT 토큰이 있으면 사용자 인증
    2. API 키가 있으면 서비스 인증
    3. 둘 다 없으면 인증 실패
    """
    # 1. JWT 토큰 인증 시도
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            return await get_current_user(authorization)  # 기존 JWT 인증
        except HTTPException:
            pass  # JWT 실패 시 API 키 확인으로 진행
    
    # 2. API 키 인증 시도
    if x_api_key and x_service_account:
        expected_key = INTERNAL_API_KEYS.get(x_service_account)
        if expected_key and x_api_key == expected_key:
            # 서비스 계정으로 인증 성공
            return {
                "user_id": f"service:{x_service_account}",
                "username": x_service_account,
                "is_service_account": True,
                "service_name": x_service_account,
                "permissions": ["audit:write", "audit:read"]  # 서비스는 모든 권한
            }
    
    # 3. 인증 실패
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated - provide JWT token or API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

# 기존 API 엔드포인트 수정 예시
@router.post("/events/single")
async def create_single_event(
    event: AuditEventCreate,
    current_user: Dict[str, Any] = Depends(get_current_user_or_service),  # 변경된 부분
):
    """단일 감사 이벤트 생성"""
    # 서비스 계정인 경우 이벤트에 표시
    if current_user.get("is_service_account"):
        event.service_account = current_user["service_name"]
    
    # 나머지 로직은 동일...
'''

# OMS의 audit_client.py 수정
OMS_AUDIT_CLIENT_UPDATE = '''
class AuditServiceClient:
    """Audit Service HTTP 클라이언트"""
    
    def __init__(self):
        self.base_url = os.getenv('AUDIT_SERVICE_URL', 'http://audit-service:8002')
        self.api_key = os.getenv('AUDIT_SERVICE_API_KEY', 'oms-internal-key-2025')
        self.service_name = os.getenv('SERVICE_NAME', 'oms-monolith')
        # ... 나머지 초기화 코드
    
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 가져오기 (지연 초기화)"""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self.service_name}/audit-client",
                "X-Service-Account": self.service_name,  # 서비스 이름 추가
            }
            if self.api_key:
                headers["X-API-Key"] = self.api_key  # Authorization 대신 X-API-Key 사용
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
            )
        return self._client
'''

# docker-compose.yml 환경 변수 추가
DOCKER_COMPOSE_ENV = '''
  audit-service:
    environment:
      # 기존 환경 변수들...
      OMS_API_KEY: oms-internal-key-2025
      USER_SERVICE_API_KEY: user-internal-key-2025

  oms-monolith:
    environment:
      # 기존 환경 변수들...
      AUDIT_SERVICE_API_KEY: oms-internal-key-2025
      SERVICE_NAME: oms-monolith
'''

print("=== Audit Service 인증 해결 방안 ===\n")

print("1. Audit Service 수정 (audit-service/utils/auth.py):")
print("-" * 60)
print(AUDIT_SERVICE_AUTH_UPDATE)
print("\n")

print("2. OMS Audit Client 수정 (oms-monolith/shared/audit_client.py):")
print("-" * 60)
print(OMS_AUDIT_CLIENT_UPDATE)
print("\n")

print("3. Docker Compose 환경 변수 추가:")
print("-" * 60)
print(DOCKER_COMPOSE_ENV)
print("\n")

print("=== 구현 절차 ===")
print("1. Audit Service의 auth.py 파일에 get_current_user_or_service 함수 추가")
print("2. 모든 API 엔드포인트의 Depends를 get_current_user_or_service로 변경")
print("3. OMS의 audit_client.py에서 헤더 설정 변경 (X-API-Key, X-Service-Account)")
print("4. docker-compose.yml에 API 키 환경 변수 추가")
print("5. 서비스 재시작 후 테스트")