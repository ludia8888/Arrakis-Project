#!/usr/bin/env python3
"""
마이크로서비스 모드 검증 스크립트
점진적 마이그레이션 상태를 확인하고 게이트웨이 모드 작동을 검증
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Tuple
import sys
import os

# 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class MicroservicesVerifier:
 def __init__(self):
 self.results = {
 "timestamp": datetime.now().isoformat(),
 "infrastructure": {},
 "microservices": {},
 "gateway_mode": {},
 "integration": {},
 "summary": {}
 }

 async def check_service_health(self, session: aiohttp.ClientSession, name: str, url: str) -> Tuple[bool, str]:
 """서비스 헬스체크"""
 try:
 async with session.get(url, timeout = aiohttp.ClientTimeout(total = 5)) as response:
 if response.status == 200:
 data = await response.json()
 return True, f"Healthy - {data.get('status', 'OK')}"
 else:
 return False, f"Unhealthy - Status: {response.status}"
 except asyncio.TimeoutError:
 return False, "Timeout"
 except Exception as e:
 return False, f"Error: {str(e)}"

 async def verify_infrastructure(self, session: aiohttp.ClientSession):
 """인프라 서비스 확인"""
 print(f"\n{BLUE}1. 인프라 서비스 확인{RESET}")
 print("=" * 50)

 services = {
 "TerminusDB": "http://localhost:6363/api/status",
 "User Service": "http://localhost:8081/health",
 "Redis": None, # 별도 체크 필요
 "PostgreSQL": None, # 별도 체크 필요
 "NATS": "http://localhost:8222/varz" # NATS monitoring endpoint
 }

 for name, url in services.items():
 if url:
 success, message = await self.check_service_health(session, name, url)
 self.results["infrastructure"][name] = {
 "status": "healthy" if success else "unhealthy",
 "message": message
 }
 status_icon = "✅" if success else "❌"
 print(f"{status_icon} {name}: {message}")
 else:
 print(f"⚠️ {name}: 별도 확인 필요")

 async def verify_microservices(self, session: aiohttp.ClientSession):
 """마이크로서비스 상태 확인"""
 print(f"\n{BLUE}2. 마이크로서비스 상태 확인{RESET}")
 print("=" * 50)

 services = {
 "Data Kernel Gateway": "http://localhost:8082/health",
 "Embedding Service": "http://localhost:8001/health",
 "Scheduler Service": "http://localhost:8002/health",
 "Event Gateway": "http://localhost:8003/health",
 "OMS Monolith": "http://localhost:8083/health"
 }

 for name, url in services.items():
 success, message = await self.check_service_health(session, name, url)
 self.results["microservices"][name] = {
 "status": "healthy" if success else "unhealthy",
 "message": message
 }
 status_icon = "✅" if success else "❌"
 print(f"{status_icon} {name}: {message}")

 async def verify_gateway_mode(self, session: aiohttp.ClientSession):
 """게이트웨이 모드 작동 확인"""
 print(f"\n{BLUE}3. Data Kernel Gateway 모드 검증{RESET}")
 print("=" * 50)

 # OMS의 설정 확인
 try:
 async with session.get("http://localhost:8083/api/v1/config/gateway-mode") as response:
 if response.status == 200:
 data = await response.json()
 gateway_enabled = data.get("gateway_mode_enabled", False)
 mode = data.get("mode", "unknown")

 self.results["gateway_mode"]["enabled"] = gateway_enabled
 self.results["gateway_mode"]["mode"] = mode

 if gateway_enabled:
 print(f"✅ Gateway 모드 활성화됨: {mode}")
 else:
 print(f"❌ Gateway 모드 비활성화됨")
 else:
 print(f"⚠️ Gateway 모드 상태 확인 실패")
 except Exception as e:
 print(f"❌ Gateway 모드 확인 오류: {e}")

 # Data Kernel 직접 테스트
 try:
 test_data = {
 "@type": "Test",
 "@id": "test/microservice_verification",
 "timestamp": datetime.now().isoformat()
 }

 async with session.post(
 "http://localhost:8082/api/v1/db/test_db/doc",
 json = test_data,
 headers={"X-Commit-Author": "verifier", "X-Commit-Message": "Microservice test"}
 ) as response:
 if response.status in [200, 201]:
 print(f"✅ Data Kernel 직접 접근 테스트 성공")
 self.results["gateway_mode"]["direct_access"] = "success"
 else:
 print(f"❌ Data Kernel 직접 접근 테스트 실패: {response.status}")
 self.results["gateway_mode"]["direct_access"] = "failed"
 except Exception as e:
 print(f"❌ Data Kernel 테스트 오류: {e}")
 self.results["gateway_mode"]["direct_access"] = f"error: {str(e)}"

 async def verify_integration(self, session: aiohttp.ClientSession):
 """통합 테스트"""
 print(f"\n{BLUE}4. 마이크로서비스 통합 테스트{RESET}")
 print("=" * 50)

 # Embedding Service 테스트
 try:
 test_text = "마이크로서비스 아키텍처 테스트"
 async with session.post(
 "http://localhost:8001/api/v1/embeddings",
 json={"text": test_text, "model": "default"}
 ) as response:
 if response.status == 200:
 data = await response.json()
 if "embedding" in data and len(data["embedding"]) > 0:
 print(f"✅ Embedding Service 통합 테스트 성공")
 self.results["integration"]["embedding"] = "success"
 else:
 print(f"❌ Embedding Service 응답 형식 오류")
 self.results["integration"]["embedding"] = "invalid_response"
 else:
 print(f"❌ Embedding Service 통합 테스트 실패: {response.status}")
 self.results["integration"]["embedding"] = f"failed: {response.status}"
 except Exception as e:
 print(f"❌ Embedding Service 테스트 오류: {e}")
 self.results["integration"]["embedding"] = f"error: {str(e)}"

 # Scheduler Service 테스트
 try:
 test_job = {
 "name": "test_microservice_job",
 "schedule": "*/5 * * * *",
 "task_type": "test",
 "enabled": False
 }
 async with session.post(
 "http://localhost:8002/api/v1/jobs",
 json = test_job
 ) as response:
 if response.status in [200, 201]:
 print(f"✅ Scheduler Service 통합 테스트 성공")
 self.results["integration"]["scheduler"] = "success"
 else:
 print(f"❌ Scheduler Service 통합 테스트 실패: {response.status}")
 self.results["integration"]["scheduler"] = f"failed: {response.status}"
 except Exception as e:
 print(f"❌ Scheduler Service 테스트 오류: {e}")
 self.results["integration"]["scheduler"] = f"error: {str(e)}"

 # Event Gateway 테스트
 try:
 test_event = {
 "event_type": "microservice.test",
 "payload": {"test": True},
 "source": "verifier"
 }
 async with session.post(
 "http://localhost:8003/api/v1/events",
 json = test_event
 ) as response:
 if response.status in [200, 201, 202]:
 print(f"✅ Event Gateway 통합 테스트 성공")
 self.results["integration"]["event_gateway"] = "success"
 else:
 print(f"❌ Event Gateway 통합 테스트 실패: {response.status}")
 self.results["integration"]["event_gateway"] = f"failed: {response.status}"
 except Exception as e:
 print(f"❌ Event Gateway 테스트 오류: {e}")
 self.results["integration"]["event_gateway"] = f"error: {str(e)}"

 def generate_summary(self):
 """검증 요약"""
 print(f"\n{BLUE}5. 검증 요약{RESET}")
 print("=" * 50)

 # 인프라 상태
 infra_healthy = sum(1 for s in self.results["infrastructure"].values()
 if isinstance(s, dict) and s.get("status") == "healthy")
 infra_total = len([s for s in self.results["infrastructure"].values() if isinstance(s, dict)])

 # 마이크로서비스 상태
 ms_healthy = sum(1 for s in self.results["microservices"].values()
 if s.get("status") == "healthy")
 ms_total = len(self.results["microservices"])

 # 통합 테스트 결과
 integration_success = sum(1 for s in self.results["integration"].values()
 if s == "success")
 integration_total = len(self.results["integration"])

 # Gateway 모드
 gateway_enabled = self.results["gateway_mode"].get("enabled", False)

 self.results["summary"] = {
 "infrastructure_health": f"{infra_healthy}/{infra_total}",
 "microservices_health": f"{ms_healthy}/{ms_total}",
 "integration_tests": f"{integration_success}/{integration_total}",
 "gateway_mode_enabled": gateway_enabled,
 "migration_status": "active" if gateway_enabled and ms_healthy > 0 else "inactive"
 }

 print(f"📊 인프라 상태: {infra_healthy}/{infra_total} 정상")
 print(f"🚀 마이크로서비스 상태: {ms_healthy}/{ms_total} 정상")
 print(f"🔗 통합 테스트: {integration_success}/{integration_total} 성공")
 print(f"🎯 Gateway 모드: {'활성화' if gateway_enabled else '비활성화'}")

 migration_score = (
 (infra_healthy / infra_total * 25) +
 (ms_healthy / ms_total * 35) +
 (integration_success / integration_total * 30) +
 (10 if gateway_enabled else 0)
 )

 self.results["summary"]["migration_score"] = round(migration_score, 2)

 print(f"\n{'='*50}")
 if migration_score >= 90:
 print(f"{GREEN}✨ 마이그레이션 점수: {migration_score:.1f}/100 - 우수!{RESET}")
 print(f"{GREEN}🎉 마이크로서비스 모드가 성공적으로 작동 중입니다!{RESET}")
 elif migration_score >= 70:
 print(f"{YELLOW}📈 마이그레이션 점수: {migration_score:.1f}/100 - 양호{RESET}")
 print(f"{YELLOW}⚠️ 일부 서비스 확인이 필요합니다.{RESET}")
 else:
 print(f"{RED}❌ 마이그레이션 점수: {migration_score:.1f}/100 - 개선 필요{RESET}")
 print(f"{RED}🔧 마이크로서비스 구성을 확인해주세요.{RESET}")

 async def run(self):
 """전체 검증 실행"""
 print(f"{BLUE}🔍 Arrakis MSA - 마이크로서비스 모드 검증 시작{RESET}")
 print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

 async with aiohttp.ClientSession() as session:
 await self.verify_infrastructure(session)
 await self.verify_microservices(session)
 await self.verify_gateway_mode(session)
 await self.verify_integration(session)

 self.generate_summary()

 # 결과 저장
 filename = f"microservice_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
 with open(filename, 'w', encoding = 'utf-8') as f:
 json.dump(self.results, f, ensure_ascii = False, indent = 2)
 print(f"\n📄 상세 결과가 {filename}에 저장되었습니다.")

async def main():
 verifier = MicroservicesVerifier()
 await verifier.run()

if __name__ == "__main__":
 asyncio.run(main())
