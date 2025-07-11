#!/usr/bin/env python3
"""
Audit Service Integration Test
감사 서비스 통합 테스트 - OMS와 Audit Service 간의 연동 검증
"""
import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# 서비스 설정
USER_SERVICE_URL = "http://localhost:8080"
OMS_SERVICE_URL = "http://localhost:8091"
AUDIT_SERVICE_URL = "http://localhost:8002"

# 테스트 사용자 정보
TEST_USER = {
    "username": "audit_test_user",
    "email": "audit_test@example.com",
    "password": "Test1234!"
}

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_section(title: str):
    """섹션 헤더 출력"""
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}{title:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")


def print_result(success: bool, message: str, details: str = ""):
    """테스트 결과 출력"""
    status = f"{GREEN}✓ PASS{RESET}" if success else f"{RED}✗ FAIL{RESET}"
    print(f"{status} {message}")
    if details:
        print(f"  {YELLOW}→ {details}{RESET}")


async def wait_for_service(url: str, service_name: str, max_retries: int = 30):
    """서비스가 준비될 때까지 대기"""
    print(f"⏳ {service_name} 서비스 대기 중...")
    
    # 서비스별 health endpoint
    health_endpoints = {
        "Audit Service": "/api/v2/events/health",
        "User Service": "/health",
        "OMS": "/health"
    }
    
    health_endpoint = health_endpoints.get(service_name, "/health")
    
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            try:
                response = await client.get(f"{url}{health_endpoint}", timeout=5.0)
                if response.status_code == 200:
                    print(f"{GREEN}✓ {service_name} 서비스 준비 완료{RESET}")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
    
    print(f"{RED}✗ {service_name} 서비스 연결 실패{RESET}")
    return False


async def login_user(username: str, password: str) -> Dict[str, Any]:
    """사용자 로그인"""
    async with httpx.AsyncClient() as client:
        # 1. 먼저 사용자 생성 시도 (이미 있을 수 있음)
        try:
            await client.post(
                f"{USER_SERVICE_URL}/auth/register",
                json={
                    "username": username,
                    "email": TEST_USER["email"],
                    "password": password
                }
            )
        except:
            pass  # 이미 존재할 수 있음
        
        # 2. 로그인 (OAuth2 form data 형식)
        response = await client.post(
            f"{USER_SERVICE_URL}/auth/login",
            data={
                "username": username,
                "password": password,
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Login failed: {response.status_code}")


async def test_audit_service_direct():
    """Audit Service 직접 테스트"""
    print_section("1. Audit Service 직접 테스트")
    
    results = []
    
    async with httpx.AsyncClient() as client:
        # 1. Health Check
        try:
            response = await client.get(f"{AUDIT_SERVICE_URL}/api/v2/events/health")
            success = response.status_code == 200
            results.append(success)
            print_result(success, "Audit Service Health Check", 
                        f"Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "Audit Service Health Check", str(e))
        
        # 2. 테스트 이벤트 생성
        try:
            test_event = {
                "event_type": "test.integration",
                "event_category": "system",
                "user_id": "test_user_123",
                "username": "test_user",
                "target_type": "test",
                "target_id": "test_123",
                "operation": "create",
                "severity": "INFO",
                "metadata": {
                    "test": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            response = await client.post(
                f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                json=test_event
            )
            success = response.status_code == 200
            results.append(success)
            
            if success:
                event_id = response.json().get("event_id")
                print_result(success, "Audit Event 생성", 
                            f"Event ID: {event_id}")
            else:
                print_result(success, "Audit Event 생성", 
                            f"Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "Audit Event 생성", str(e))
        
        # 3. 이벤트 조회
        try:
            response = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                params={"limit": 10}
            )
            success = response.status_code == 200
            results.append(success)
            
            if success:
                data = response.json()
                event_count = len(data.get("events", []))
                print_result(success, "Audit Event 조회", 
                            f"Found {event_count} events")
            else:
                print_result(success, "Audit Event 조회", 
                            f"Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "Audit Event 조회", str(e))
    
    return all(results)


async def test_oms_audit_integration():
    """OMS에서 Audit Service 연동 테스트"""
    print_section("2. OMS → Audit Service 연동 테스트")
    
    results = []
    
    # 로그인
    try:
        auth_data = await login_user(TEST_USER["username"], TEST_USER["password"])
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print_result(True, "사용자 인증", f"Token obtained")
    except Exception as e:
        print_result(False, "사용자 인증", str(e))
        return False
    
    async with httpx.AsyncClient() as client:
        # 1. OMS Audit API Health Check
        try:
            response = await client.get(
                f"{OMS_SERVICE_URL}/api/v1/audit/health",
                headers=headers
            )
            success = response.status_code == 200
            results.append(success)
            print_result(success, "OMS Audit API Health Check", 
                        f"Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "OMS Audit API Health Check", str(e))
        
        # 2. 브랜치 생성 (감사 로그 생성 트리거)
        branch_name = f"test-audit-{int(time.time())}"
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
            success = response.status_code in [200, 201]
            results.append(success)
            print_result(success, "브랜치 생성", 
                        f"Branch: {branch_name}, Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "브랜치 생성", str(e))
        
        # 3. 잠시 대기 (감사 로그 생성 시간)
        await asyncio.sleep(2)
        
        # 4. OMS를 통한 감사 로그 조회
        try:
            response = await client.get(
                f"{OMS_SERVICE_URL}/api/v1/audit/events",
                params={
                    "target_type": "branch",
                    "operation": "create",
                    "limit": 10
                },
                headers=headers
            )
            success = response.status_code == 200
            results.append(success)
            
            if success:
                data = response.json()
                events = data.get("events", [])
                
                # 방금 생성한 브랜치의 감사 로그 찾기
                branch_audit_found = any(
                    event.get("target_id") == branch_name 
                    for event in events
                )
                
                print_result(success, "OMS를 통한 감사 로그 조회", 
                            f"Found {len(events)} events, Branch audit: {branch_audit_found}")
                
                if not branch_audit_found:
                    print(f"  {YELLOW}⚠ 브랜치 생성에 대한 감사 로그를 찾을 수 없음{RESET}")
                    results.append(False)
            else:
                print_result(success, "OMS를 통한 감사 로그 조회", 
                            f"Status: {response.status_code}")
        except Exception as e:
            results.append(False)
            print_result(False, "OMS를 통한 감사 로그 조회", str(e))
    
    return all(results)


async def test_audit_event_creation_from_oms():
    """OMS 작업이 Audit Service에 기록되는지 검증"""
    print_section("3. OMS 작업 → Audit Service 기록 검증")
    
    results = []
    
    # 로그인
    try:
        auth_data = await login_user(TEST_USER["username"], TEST_USER["password"])
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print_result(False, "사용자 인증", str(e))
        return False
    
    async with httpx.AsyncClient() as client:
        # 1. Audit Service에서 현재 이벤트 수 확인
        try:
            response = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                params={"limit": 1000}
            )
            initial_count = len(response.json().get("events", []))
            print(f"📊 초기 감사 이벤트 수: {initial_count}")
        except:
            initial_count = 0
        
        # 2. OMS에서 여러 작업 수행
        operations = []
        
        # 2.1 브랜치 목록 조회
        try:
            response = await client.get(
                f"{OMS_SERVICE_URL}/api/v1/branches/",
                headers=headers
            )
            success = response.status_code == 200
            operations.append(("브랜치 목록 조회", success))
        except:
            operations.append(("브랜치 목록 조회", False))
        
        # 2.2 스키마 목록 조회
        try:
            response = await client.get(
                f"{OMS_SERVICE_URL}/api/v1/schema/object-types",
                headers=headers
            )
            success = response.status_code == 200
            operations.append(("스키마 목록 조회", success))
        except:
            operations.append(("스키마 목록 조회", False))
        
        # 2.3 새 브랜치 생성 (중요 작업)
        test_branch = f"audit-test-{int(time.time())}"
        try:
            response = await client.post(
                f"{OMS_SERVICE_URL}/api/v1/branches/",
                json={
                    "name": test_branch,
                    "from_branch": "main"
                },
                headers=headers
            )
            success = response.status_code in [200, 201]
            operations.append(("브랜치 생성", success))
        except:
            operations.append(("브랜치 생성", False))
        
        # 작업 결과 출력
        for op_name, op_success in operations:
            print_result(op_success, f"OMS 작업: {op_name}")
        
        # 3. 잠시 대기 후 Audit Service에서 새 이벤트 확인
        await asyncio.sleep(3)
        
        try:
            response = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                params={"limit": 1000}
            )
            final_count = len(response.json().get("events", []))
            new_events = final_count - initial_count
            
            print(f"\n📊 최종 감사 이벤트 수: {final_count}")
            print(f"📈 새로 생성된 이벤트: {new_events}")
            
            # 최근 이벤트 확인
            if new_events > 0:
                events = response.json().get("events", [])
                recent_events = events[-new_events:]
                
                print(f"\n{BOLD}최근 감사 이벤트:{RESET}")
                for event in recent_events[-5:]:  # 최근 5개만 표시
                    print(f"  - {event.get('event_type')} | "
                          f"{event.get('target_type')} | "
                          f"{event.get('operation')} | "
                          f"{event.get('username', 'N/A')}")
                
                # 브랜치 생성 이벤트 확인
                branch_event_found = any(
                    event.get("target_type") == "branch" and 
                    event.get("operation") == "create"
                    for event in recent_events
                )
                
                results.append(branch_event_found)
                print_result(branch_event_found, 
                           "브랜치 생성 감사 로그 확인",
                           "브랜치 생성이 감사 로그에 기록됨" if branch_event_found 
                           else "브랜치 생성 감사 로그를 찾을 수 없음")
            else:
                results.append(False)
                print_result(False, "새 감사 이벤트 생성 확인", 
                           "OMS 작업에 대한 감사 로그가 생성되지 않음")
                
        except Exception as e:
            results.append(False)
            print_result(False, "감사 이벤트 확인", str(e))
    
    return all(results) if results else False


async def main():
    """메인 테스트 실행"""
    print(f"\n{BOLD}{GREEN}Audit Service Integration Test{RESET}")
    print(f"{YELLOW}테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    # 서비스 대기
    services = [
        (USER_SERVICE_URL, "User Service"),
        (OMS_SERVICE_URL, "OMS"),
        (AUDIT_SERVICE_URL, "Audit Service")
    ]
    
    print(f"\n{BOLD}서비스 상태 확인:{RESET}")
    for url, name in services:
        if not await wait_for_service(url, name):
            print(f"\n{RED}❌ {name} 서비스를 시작할 수 없습니다.{RESET}")
            return
    
    # 테스트 실행
    test_results = []
    
    # 1. Audit Service 직접 테스트
    result1 = await test_audit_service_direct()
    test_results.append(("Audit Service 직접 테스트", result1))
    
    # 2. OMS → Audit Service 연동 테스트
    result2 = await test_oms_audit_integration()
    test_results.append(("OMS → Audit Service 연동", result2))
    
    # 3. OMS 작업 → Audit Service 기록 검증
    result3 = await test_audit_event_creation_from_oms()
    test_results.append(("OMS 작업 감사 로그 생성", result3))
    
    # 최종 결과
    print_section("테스트 결과 요약")
    
    total_tests = len(test_results)
    passed_tests = sum(1 for _, result in test_results if result)
    
    for test_name, result in test_results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {status} - {test_name}")
    
    print(f"\n{BOLD}전체 결과: {passed_tests}/{total_tests} 테스트 통과{RESET}")
    
    if passed_tests == total_tests:
        print(f"\n{GREEN}✅ 모든 테스트 통과! Audit Service 연동이 정상 작동합니다.{RESET}")
    else:
        print(f"\n{RED}❌ 일부 테스트 실패. Audit Service 연동을 확인하세요.{RESET}")
        print(f"\n{YELLOW}💡 문제 해결 팁:{RESET}")
        print(f"  1. docker-compose logs audit-service 로 로그 확인")
        print(f"  2. OMS 코드에서 audit_service.record_event() 호출 확인")
        print(f"  3. 환경 변수 USE_AUDIT_SERVICE=true 설정 확인")


if __name__ == "__main__":
    asyncio.run(main())