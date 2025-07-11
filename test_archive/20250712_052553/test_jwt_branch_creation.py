#!/usr/bin/env python3
"""
JWT를 직접 생성하여 브랜치 생성 테스트
"""
import jwt
import httpx
import asyncio
import time
from datetime import datetime, timedelta

# 서비스 설정
OMS_SERVICE_URL = "http://localhost:8091"
JWT_SECRET = "your_shared_secret_key_for_all_services_with_32_chars"

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def generate_test_token():
    """테스트용 JWT 토큰 생성"""
    now = datetime.utcnow()
    payload = {
        "sub": "test_user",
        "username": "test_user",
        "user_id": "test_user_123",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "aud": "oms",
        "iss": "user-service",
        "permissions": ["branch:create", "branch:read", "audit:write"]
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token


async def create_branch_with_jwt():
    """JWT 토큰으로 브랜치 생성"""
    token = generate_test_token()
    branch_name = f"jwt-test-{int(time.time())}"
    
    print(f"\n{BOLD}JWT 토큰으로 브랜치 생성 테스트{RESET}")
    print(f"Branch Name: {branch_name}")
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = await client.post(
                f"{OMS_SERVICE_URL}/api/v1/branches/",
                json={
                    "name": branch_name,
                    "from_branch": "main"
                },
                headers=headers,
                timeout=30.0
            )
            
            print(f"\n응답 상태: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print(f"{GREEN}✓ 브랜치 생성 성공!{RESET}")
                data = response.json()
                print(f"  ID: {data.get('id')}")
                print(f"  Name: {data.get('name')}")
                return True
            else:
                print(f"{RED}✗ 브랜치 생성 실패{RESET}")
                print(f"  Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
            return False


async def check_audit_logs():
    """감사 로그 확인"""
    print(f"\n{BOLD}OMS 감사 로그 확인:{RESET}")
    
    import subprocess
    result = subprocess.run(
        ["docker-compose", "logs", "--tail=50", "oms-monolith"],
        capture_output=True,
        text=True
    )
    
    audit_keywords = [
        "audit", "Audit", "record_event", "AuditServiceClient", 
        "JWT", "token", "branch.created", "Failed to record"
    ]
    
    found_logs = False
    for line in result.stdout.split('\n'):
        if any(keyword in line for keyword in audit_keywords):
            found_logs = True
            if 'error' in line.lower() or 'failed' in line.lower():
                print(f"{RED}  {line.strip()}{RESET}")
            elif 'recorded' in line.lower() or 'success' in line.lower():
                print(f"{GREEN}  {line.strip()}{RESET}")
            else:
                print(f"{YELLOW}  {line.strip()}{RESET}")
    
    if not found_logs:
        print(f"{YELLOW}  감사 관련 로그를 찾을 수 없음{RESET}")
    
    return found_logs


async def check_audit_service_logs():
    """Audit Service 로그 확인"""
    print(f"\n{BOLD}Audit Service 로그 확인:{RESET}")
    
    import subprocess
    result = subprocess.run(
        ["docker-compose", "logs", "--tail=30", "audit-service"],
        capture_output=True,
        text=True
    )
    
    for line in result.stdout.split('\n'):
        if "event" in line.lower() or "branch" in line.lower():
            print(f"  {line.strip()}")


async def main():
    """메인 테스트"""
    print(f"\n{BOLD}{GREEN}JWT 기반 브랜치 생성 및 감사 로그 테스트{RESET}")
    print(f"{YELLOW}시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    # 1. 브랜치 생성
    success = await create_branch_with_jwt()
    
    if success:
        # 2. 잠시 대기 (로그 생성 시간)
        print(f"\n{YELLOW}감사 로그 생성 대기 중...{RESET}")
        await asyncio.sleep(3)
        
        # 3. OMS 로그 확인
        await check_audit_logs()
        
        # 4. Audit Service 로그 확인
        await check_audit_service_logs()
        
        print(f"\n{BOLD}결과 분석:{RESET}")
        print("1. 'Audit event recorded' → 성공적으로 감사 로그 생성됨")
        print("2. 'Failed to record audit event' → JWT 인증은 성공했지만 Audit Service 연동 실패")
        print("3. 감사 로그가 없음 → 브랜치 생성 로직에서 audit_client 호출이 없을 수 있음")
    else:
        print(f"\n{RED}브랜치 생성 실패로 감사 로그 테스트 불가{RESET}")


if __name__ == "__main__":
    asyncio.run(main())