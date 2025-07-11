#!/usr/bin/env python3
"""
Basic Audit Service Integration Test
기본적인 감사 서비스 연동 테스트 - OMS 내부에서 감사 로그가 생성되는지 확인
"""
import asyncio
import httpx
import json
from datetime import datetime

# 서비스 설정
OMS_SERVICE_URL = "http://localhost:8091"
AUDIT_SERVICE_URL = "http://localhost:8002"

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


async def test_direct_audit_without_auth():
    """인증 없이 Audit Service 직접 테스트"""
    print(f"\n{BOLD}{BLUE}1. Audit Service 인증 우회 테스트{RESET}")
    
    async with httpx.AsyncClient() as client:
        # Audit Service는 내부 서비스 간 통신을 위해 인증이 필요없을 수 있음
        test_event = {
            "event_type": "test.basic",
            "event_category": "system",
            "user_id": "system",
            "username": "system",
            "target_type": "test",
            "target_id": "basic_test_1",
            "operation": "test",
            "severity": "INFO",
            "service_account": "oms-monolith",
            "metadata": {
                "test": True,
                "source": "basic_test"
            }
        }
        
        try:
            # API 키를 헤더에 추가하여 시도
            headers = {
                "X-Service-Account": "oms-monolith",
                "X-Internal-Request": "true"
            }
            
            response = await client.post(
                f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                json=test_event,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"{GREEN}✓ 서비스 계정으로 감사 이벤트 생성 성공{RESET}")
                event_id = response.json().get("event_id")
                print(f"  Event ID: {event_id}")
                return True
            else:
                print(f"{RED}✗ 감사 이벤트 생성 실패: {response.status_code}{RESET}")
                print(f"  Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
            return False


async def test_oms_internal_audit():
    """OMS 내부에서 Audit 로그 생성 확인"""
    print(f"\n{BOLD}{BLUE}2. OMS 내부 Audit 로그 생성 테스트{RESET}")
    
    # 먼저 Audit Service의 현재 이벤트 수 확인
    async with httpx.AsyncClient() as client:
        try:
            # OMS의 health 체크 (인증 필요 없음)
            response = await client.get(f"{OMS_SERVICE_URL}/health")
            if response.status_code == 200:
                print(f"{GREEN}✓ OMS 서비스 정상 작동{RESET}")
            
            # 브랜치 목록 조회 (인증 없이) - 이것이 실패하더라도 로그는 생성될 수 있음
            try:
                response = await client.get(f"{OMS_SERVICE_URL}/api/v1/branches/")
                print(f"  브랜치 조회 시도: Status {response.status_code}")
            except:
                pass
            
            # Audit Service에서 직접 이벤트 조회 (서비스 계정으로)
            headers = {
                "X-Service-Account": "oms-monolith",
                "X-Internal-Request": "true"
            }
            
            response = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                params={"limit": 10, "target_type": "branch"},
                headers=headers
            )
            
            if response.status_code == 200:
                events = response.json().get("events", [])
                print(f"{GREEN}✓ 감사 이벤트 조회 성공: {len(events)}개 이벤트{RESET}")
                
                # 최근 이벤트 표시
                if events:
                    print(f"\n{BOLD}최근 브랜치 관련 감사 이벤트:{RESET}")
                    for event in events[:3]:
                        print(f"  - {event.get('event_type')} | {event.get('operation')} | {event.get('timestamp')}")
                
                return True
            else:
                print(f"{YELLOW}⚠ 감사 이벤트 조회 실패: {response.status_code}{RESET}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 오류 발생: {e}{RESET}")
            return False


async def test_audit_service_health():
    """Audit Service 상태 확인"""
    print(f"\n{BOLD}{BLUE}3. Audit Service 상태 확인{RESET}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AUDIT_SERVICE_URL}/api/v2/events/health")
            if response.status_code == 200:
                data = response.json()
                print(f"{GREEN}✓ Audit Service 정상 작동{RESET}")
                print(f"  Service: {data.get('service')}")
                print(f"  API Version: {data.get('api_version')}")
                print(f"  Integration: {data.get('integration')}")
                return True
            else:
                print(f"{RED}✗ Audit Service 상태 확인 실패{RESET}")
                return False
        except Exception as e:
            print(f"{RED}✗ 연결 실패: {e}{RESET}")
            return False


async def check_oms_logs():
    """OMS 로그에서 Audit 관련 메시지 확인"""
    print(f"\n{BOLD}{BLUE}4. OMS 로그 확인 권장사항{RESET}")
    print("다음 명령어로 OMS 로그를 확인하세요:")
    print(f"{YELLOW}docker-compose logs --tail=50 oms-monolith | grep -i audit{RESET}")
    print("\n찾아볼 내용:")
    print("- 'Audit event recorded' 메시지")
    print("- 'Failed to record audit event' 에러")
    print("- 'AuditServiceClient' 관련 로그")


async def main():
    """메인 테스트 실행"""
    print(f"\n{BOLD}{GREEN}Basic Audit Service Integration Test{RESET}")
    print(f"{YELLOW}테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    
    results = []
    
    # 1. Audit Service 상태 확인
    results.append(await test_audit_service_health())
    
    # 2. 인증 우회 테스트
    results.append(await test_direct_audit_without_auth())
    
    # 3. OMS 내부 감사 로그 확인
    results.append(await test_oms_internal_audit())
    
    # 4. 로그 확인 안내
    await check_oms_logs()
    
    # 결과 요약
    print(f"\n{BOLD}{BLUE}테스트 결과 요약{RESET}")
    passed = sum(1 for r in results if r)
    total = len(results)
    
    if passed == total:
        print(f"{GREEN}✅ 모든 테스트 통과 ({passed}/{total}){RESET}")
    else:
        print(f"{RED}❌ 일부 테스트 실패 ({passed}/{total}){RESET}")
    
    print(f"\n{BOLD}권장 조치:{RESET}")
    if passed < total:
        print("1. Audit Service의 인증 설정 확인")
        print("2. OMS의 환경 변수 USE_AUDIT_SERVICE=true 확인")
        print("3. OMS 코드에서 실제로 audit_client.record_event() 호출되는지 확인")
        print("4. docker-compose logs로 상세 로그 확인")


if __name__ == "__main__":
    asyncio.run(main())