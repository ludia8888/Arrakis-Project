#!/usr/bin/env python3
"""
브랜치 생성 테스트를 통한 Audit 로그 검증
"""
import asyncio
import httpx
import time
from datetime import datetime

# 서비스 설정
USER_SERVICE_URL = "http://localhost:8080"
OMS_SERVICE_URL = "http://localhost:8091"

# 테스트 사용자
TEST_USER = {
    "username": f"audit_tester_{int(time.time())}",
    "email": "audit_tester@example.com",
    "password": "Test1234!"
}

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


async def create_and_login_user():
    """사용자 생성 및 로그인"""
    async with httpx.AsyncClient() as client:
        # 1. 사용자 생성
        try:
            response = await client.post(
                f"{USER_SERVICE_URL}/auth/register",
                json={
                    "username": TEST_USER["username"],
                    "email": TEST_USER["email"],
                    "password": TEST_USER["password"]
                }
            )
            if response.status_code in [200, 201]:
                print(f"{GREEN}✓ 사용자 생성 성공: {TEST_USER['username']}{RESET}")
            elif response.status_code == 409:
                print(f"{YELLOW}사용자가 이미 존재함{RESET}")
            else:
                print(f"{RED}사용자 생성 실패: {response.status_code}{RESET}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"{RED}사용자 생성 실패: {e}{RESET}")
            
        # 2. 로그인
        response = await client.post(
            f"{USER_SERVICE_URL}/auth/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"{RED}로그인 실패: {response.status_code}{RESET}")
            print(f"Response: {response.text}")
            return None


async def create_branch_and_check_logs(token: str):
    """브랜치 생성 후 로그 확인"""
    branch_name = f"audit-test-{int(time.time())}"
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. 브랜치 생성
        print(f"\n{BOLD}브랜치 생성 시도: {branch_name}{RESET}")
        
        try:
            response = await client.post(
                f"{OMS_SERVICE_URL}/api/v1/branches/",
                json={
                    "name": branch_name,
                    "from_branch": "main",
                    "created_by": TEST_USER["username"]
                },
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                print(f"{GREEN}✓ 브랜치 생성 성공{RESET}")
                branch_data = response.json()
                print(f"  Branch ID: {branch_data.get('id')}")
                print(f"  Branch Name: {branch_data.get('name')}")
            else:
                print(f"{RED}✗ 브랜치 생성 실패: {response.status_code}{RESET}")
                print(f"  Response: {response.text}")
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
    
    return branch_name


async def check_oms_logs():
    """OMS 로그 확인"""
    print(f"\n{BOLD}OMS 로그 확인 (마지막 감사 이벤트 시도):{RESET}")
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker-compose", "logs", "--tail=30", "oms-monolith"],
            capture_output=True,
            text=True
        )
        
        # 감사 관련 로그 찾기
        for line in result.stdout.split('\n'):
            if any(keyword in line.lower() for keyword in ['audit', 'record_event', 'failed to record']):
                if 'error' in line.lower() or 'failed' in line.lower():
                    print(f"{RED}  {line.strip()}{RESET}")
                elif 'recorded' in line.lower() or 'success' in line.lower():
                    print(f"{GREEN}  {line.strip()}{RESET}")
                else:
                    print(f"{YELLOW}  {line.strip()}{RESET}")
                    
    except Exception as e:
        print(f"{RED}로그 확인 실패: {e}{RESET}")


async def main():
    """메인 테스트"""
    print(f"\n{BOLD}{GREEN}브랜치 생성을 통한 Audit 로그 테스트{RESET}")
    print(f"{YELLOW}테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    # 1. 사용자 생성 및 로그인
    print(f"\n{BOLD}1. 사용자 생성 및 로그인{RESET}")
    token = await create_and_login_user()
    
    if not token:
        print(f"{RED}로그인 실패로 테스트 중단{RESET}")
        return
    
    print(f"{GREEN}✓ 로그인 성공{RESET}")
    
    # 2. 브랜치 생성
    print(f"\n{BOLD}2. 브랜치 생성 및 감사 로그 생성 시도{RESET}")
    branch_name = await create_branch_and_check_logs(token)
    
    # 3. 잠시 대기 (로그 생성 시간)
    print(f"\n{YELLOW}감사 로그 생성 대기 중...{RESET}")
    await asyncio.sleep(3)
    
    # 4. OMS 로그 확인
    await check_oms_logs()
    
    print(f"\n{BOLD}결론:{RESET}")
    print("1. OMS 로그에서 'Audit event recorded' 메시지가 보이면 성공")
    print("2. 'Failed to record audit event' 메시지가 보이면 인증 문제 지속")
    print("3. JWT 토큰 생성 관련 에러가 보이면 JWT 구현 확인 필요")


if __name__ == "__main__":
    asyncio.run(main())