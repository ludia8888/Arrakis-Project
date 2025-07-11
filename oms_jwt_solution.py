#!/usr/bin/env python3
"""
OMS에서 JWT를 생성하여 Audit Service와 통신하는 대안
"""

# OMS의 audit_client.py에 JWT 생성 로직 추가
OMS_JWT_SOLUTION = '''
import jwt
from datetime import datetime, timedelta

class AuditServiceClient:
    """Audit Service HTTP 클라이언트"""
    
    def __init__(self):
        self.base_url = os.getenv('AUDIT_SERVICE_URL', 'http://audit-service:8002')
        self.jwt_secret = os.getenv('JWT_SECRET', 'your_shared_secret_key_for_all_services_with_32_chars')
        self.jwt_audience = os.getenv('JWT_AUDIENCE', 'oms')
        self.jwt_issuer = os.getenv('JWT_ISSUER', 'oms-monolith')
        self.service_name = os.getenv('SERVICE_NAME', 'oms-monolith')
        # ... 나머지 초기화 코드
    
    def _generate_service_token(self) -> str:
        """서비스 계정용 JWT 토큰 생성"""
        now = datetime.utcnow()
        payload = {
            "sub": f"service:{self.service_name}",
            "username": self.service_name,
            "user_id": f"service:{self.service_name}",
            "is_service_account": True,
            "iat": now,
            "exp": now + timedelta(minutes=5),  # 5분 유효
            "aud": self.jwt_audience,
            "iss": self.jwt_issuer,
            "permissions": ["audit:write", "audit:read"]
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return token
    
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 가져오기 (지연 초기화)"""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self.service_name}/audit-client",
            }
            
            # JWT 토큰 생성 및 헤더에 추가
            token = self._generate_service_token()
            headers["Authorization"] = f"Bearer {token}"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
            )
        return self._client
    
    async def record_event(self, event: AuditEvent) -> str:
        """단일 감사 이벤트 기록 (매 요청마다 새 토큰 생성)"""
        if not self._check_circuit_breaker():
            raise Exception("Audit service circuit breaker is open")
        
        # 매 요청마다 새로운 토큰 생성 (토큰 만료 대비)
        token = self._generate_service_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        client = await self._get_client()
        
        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    "/api/v2/events/single",
                    json=event.to_dict(),
                    headers=headers  # 요청별 헤더 오버라이드
                )
                response.raise_for_status()
                result = response.json()
                
                self._record_success()
                return result.get("event_id", "unknown")
                
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == self.max_retries - 1:
                    self._record_failure()
                    raise Exception(f"Failed to record audit event after {self.max_retries} attempts: {e}")
                
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
'''

# requirements.txt에 추가 필요
REQUIREMENTS_UPDATE = '''
# OMS requirements.txt에 추가
PyJWT==2.8.0  # JWT 생성을 위한 라이브러리
'''

print("=== OMS JWT 생성 방안 ===\n")

print("1. OMS Audit Client 수정 (JWT 생성 추가):")
print("-" * 60)
print(OMS_JWT_SOLUTION)
print("\n")

print("2. OMS requirements.txt 추가:")
print("-" * 60)
print(REQUIREMENTS_UPDATE)
print("\n")

print("=== 장단점 비교 ===")
print("\n방안 1 (API 키 인증 추가) - 권장:")
print("✅ 장점:")
print("  - 서비스 간 통신에 적합한 간단한 인증")
print("  - 성능 오버헤드 없음")
print("  - 구현이 명확하고 디버깅 용이")
print("❌ 단점:")
print("  - Audit Service 수정 필요")
print("  - 두 가지 인증 방식 유지 필요")

print("\n방안 2 (OMS에서 JWT 생성):")
print("✅ 장점:")
print("  - Audit Service 수정 불필요")
print("  - 기존 인증 체계 유지")
print("❌ 단점:")
print("  - 매 요청마다 JWT 생성 오버헤드")
print("  - 토큰 만료 관리 복잡성")
print("  - JWT 라이브러리 의존성 추가")