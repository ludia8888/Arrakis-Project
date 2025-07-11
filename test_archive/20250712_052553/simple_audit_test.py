#!/usr/bin/env python3
"""
간단한 Audit 로그 테스트 - OMS 내부에서 직접 확인
"""
import subprocess
import time

# 색상 코드
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

print(f"\n{BOLD}{GREEN}OMS Audit 로그 실시간 모니터링{RESET}")
print(f"{YELLOW}브랜치 API를 호출하면서 감사 로그 생성을 확인합니다.{RESET}\n")

# 1. 현재 로그 상태 확인
print(f"{BOLD}1. 현재 OMS 로그에서 최근 Audit 관련 메시지:{RESET}")
result = subprocess.run(
    ["docker-compose", "logs", "--tail=100", "oms-monolith"],
    capture_output=True,
    text=True
)

audit_logs = []
for line in result.stdout.split('\n'):
    if any(keyword in line for keyword in ['audit', 'Audit', 'record_event', 'AuditServiceClient', 'JWT']):
        audit_logs.append(line.strip())

if audit_logs:
    for log in audit_logs[-10:]:  # 최근 10개만
        if 'error' in log.lower() or 'failed' in log.lower():
            print(f"{RED}  {log}{RESET}")
        elif 'success' in log.lower() or 'recorded' in log.lower():
            print(f"{GREEN}  {log}{RESET}")
        else:
            print(f"{YELLOW}  {log}{RESET}")
else:
    print(f"{YELLOW}  Audit 관련 로그를 찾을 수 없음{RESET}")

# 2. API 호출 (인증 없이 - 401 에러여도 감사 시도는 발생할 수 있음)
print(f"\n{BOLD}2. 브랜치 목록 API 호출 (인증 없이):{RESET}")
import requests

try:
    response = requests.get("http://localhost:8091/api/v1/branches/", timeout=5)
    print(f"  API 응답: {response.status_code} {response.reason}")
except Exception as e:
    print(f"{RED}  API 호출 실패: {e}{RESET}")

# 3. Health check (감사 로그 없어야 함)
print(f"\n{BOLD}3. Health Check API 호출:{RESET}")
try:
    response = requests.get("http://localhost:8091/health", timeout=5)
    print(f"  API 응답: {response.status_code} {response.reason}")
except Exception as e:
    print(f"{RED}  API 호출 실패: {e}{RESET}")

# 4. 잠시 대기
time.sleep(3)

# 5. 로그 재확인
print(f"\n{BOLD}4. API 호출 후 새로운 Audit 로그:{RESET}")
result = subprocess.run(
    ["docker-compose", "logs", "--tail=50", "oms-monolith"],
    capture_output=True,
    text=True
)

new_audit_logs = []
for line in result.stdout.split('\n'):
    if any(keyword in line for keyword in ['audit', 'Audit', 'record_event', 'AuditServiceClient', 'JWT', 'token']):
        if line.strip() not in audit_logs:  # 새로운 로그만
            new_audit_logs.append(line.strip())

if new_audit_logs:
    print(f"{GREEN}새로운 Audit 관련 로그 발견:{RESET}")
    for log in new_audit_logs[-10:]:
        if 'error' in log.lower() or 'failed' in log.lower():
            print(f"{RED}  {log}{RESET}")
        elif 'success' in log.lower() or 'recorded' in log.lower():
            print(f"{GREEN}  {log}{RESET}")
        else:
            print(f"{YELLOW}  {log}{RESET}")
else:
    print(f"{YELLOW}  새로운 Audit 로그가 생성되지 않음{RESET}")

# 6. 결론
print(f"\n{BOLD}결론:{RESET}")
print("• JWT 생성 성공 → 감사 이벤트 전송 성공 → Audit Service가 이벤트를 기록")
print("• JWT 생성 실패 → PyJWT 라이브러리 또는 환경 변수 문제")
print("• 감사 이벤트 전송 실패 → 네트워크 또는 인증 문제")
print("• Audit 로그가 전혀 없음 → 브랜치 API에서 audit_client 호출이 없을 수 있음")

print(f"\n{YELLOW}추가 확인 필요 사항:{RESET}")
print("1. docker-compose exec oms-monolith env | grep JWT")
print("2. docker-compose logs audit-service --tail=50")
print("3. OMS 코드에서 실제로 audit_client.record_event()가 호출되는지 확인")