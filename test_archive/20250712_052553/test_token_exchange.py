#!/usr/bin/env python3
"""
토큰 교환 테스트
User Service의 토큰 교환 엔드포인트 테스트
"""
import httpx
import asyncio
import jwt
from datetime import datetime

# 서비스 설정
USER_SERVICE_URL = "http://localhost:8080"

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


async def test_token_exchange():
    """토큰 교환 테스트"""
    print(f"\n{BOLD}{BLUE}토큰 교환 테스트{RESET}")
    
    # OMS 클라이언트 자격증명
    client_id = "oms-monolith-client"
    client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
    
    async with httpx.AsyncClient() as client:
        # Basic Auth로 토큰 교환 요청
        auth = httpx.BasicAuth(client_id, client_secret)
        
        try:
            response = await client.post(
                f"{USER_SERVICE_URL}/token/exchange",
                data={
                    "grant_type": "client_credentials",
                    "scope": "audit:write audit:read"
                },
                auth=auth,
                timeout=10.0
            )
            
            print(f"\n응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                print(f"{GREEN}✓ 토큰 교환 성공!{RESET}")
                print(f"\n토큰 정보:")
                print(f"  Token Type: {token_data.get('token_type')}")
                print(f"  Expires In: {token_data.get('expires_in')} seconds")
                print(f"  Service Name: {token_data.get('service_name')}")
                print(f"  Scopes: {token_data.get('scope')}")
                
                # JWT 디코드 (검증 없이)
                access_token = token_data.get('access_token')
                try:
                    payload = jwt.decode(access_token, options={"verify_signature": False})
                    print(f"\n{BOLD}JWT 페이로드:{RESET}")
                    print(f"  Subject: {payload.get('sub')}")
                    print(f"  Service Account: {payload.get('is_service_account')}")
                    print(f"  Permissions: {payload.get('permissions')}")
                    print(f"  Expires: {datetime.fromtimestamp(payload.get('exp'))}")
                except Exception as e:
                    print(f"{YELLOW}JWT 디코드 실패: {e}{RESET}")
                
                return access_token
            else:
                print(f"{RED}✗ 토큰 교환 실패{RESET}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
            return None


async def test_audit_with_exchanged_token(token: str):
    """교환된 토큰으로 Audit Service 테스트"""
    print(f"\n{BOLD}{BLUE}교환된 토큰으로 Audit Service 접근 테스트{RESET}")
    
    AUDIT_SERVICE_URL = "http://localhost:8002"
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 테스트 이벤트
        test_event = {
            "event_type": "test.token_exchange",
            "event_category": "system",
            "user_id": "service:oms-monolith",
            "username": "oms-monolith",
            "target_type": "test",
            "target_id": "token_exchange_test",
            "operation": "create",
            "severity": "INFO",
            "metadata": {
                "test": True,
                "method": "token_exchange"
            }
        }
        
        try:
            response = await client.post(
                f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                json=test_event,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"{GREEN}✓ Audit 이벤트 생성 성공!{RESET}")
                result = response.json()
                print(f"  Event ID: {result.get('event_id')}")
                return True
            else:
                print(f"{RED}✗ Audit 이벤트 생성 실패: {response.status_code}{RESET}")
                print(f"  Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
            return False


async def main():
    """메인 테스트"""
    print(f"\n{BOLD}{GREEN}서비스 간 토큰 교환 통합 테스트{RESET}")
    print(f"{YELLOW}시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    # 1. 토큰 교환
    token = await test_token_exchange()
    
    if token:
        # 2. 교환된 토큰으로 Audit Service 접근
        success = await test_audit_with_exchanged_token(token)
        
        if success:
            print(f"\n{GREEN}✅ 토큰 교환 방식 통합 성공!{RESET}")
            print("OMS → User Service (토큰 교환) → Audit Service (감사 로그 생성)")
        else:
            print(f"\n{YELLOW}⚠️ 토큰은 발급되었으나 Audit Service 접근 실패{RESET}")
    else:
        print(f"\n{RED}❌ 토큰 교환 실패{RESET}")
        print("\n가능한 원인:")
        print("1. User Service에 service_clients 테이블이 없음")
        print("2. 클라이언트 자격증명이 잘못됨")
        print("3. 토큰 교환 엔드포인트가 아직 배포되지 않음")


if __name__ == "__main__":
    asyncio.run(main())