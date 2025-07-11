#!/usr/bin/env python3
"""
Three Service Integration Test
user-service, audit-service, ontology-management-service 통합 테스트
"""

import asyncio
import json
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 서비스 URL 설정
USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8002"
OMS_SERVICE_URL = "http://localhost:8091"
NGINX_URL = "http://localhost:80"

class ServiceIntegrationTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token = None
        self.user_id = None
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "services": {
                "user-service": {"status": "unknown", "issues": []},
                "audit-service": {"status": "unknown", "issues": []},
                "oms-service": {"status": "unknown", "issues": []},
                "integration": {"status": "unknown", "issues": []}
            }
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def check_service_health(self):
        """각 서비스의 헬스체크"""
        logger.info("=== 서비스 헬스체크 시작 ===")
        
        # User Service 헬스체크
        try:
            response = await self.client.get(f"{USER_SERVICE_URL}/health")
            if response.status_code == 200:
                logger.info("✅ User Service: 정상")
                self.test_results["services"]["user-service"]["status"] = "healthy"
            else:
                logger.error(f"❌ User Service: 비정상 (상태코드: {response.status_code})")
                self.test_results["services"]["user-service"]["issues"].append(
                    f"Health check failed with status {response.status_code}"
                )
        except Exception as e:
            logger.error(f"❌ User Service: 연결 실패 - {str(e)}")
            self.test_results["services"]["user-service"]["status"] = "unreachable"
            self.test_results["services"]["user-service"]["issues"].append(str(e))
        
        # Audit Service 헬스체크
        try:
            response = await self.client.get(f"{AUDIT_SERVICE_URL}/api/v1/health/")
            if response.status_code == 200:
                logger.info("✅ Audit Service: 정상")
                self.test_results["services"]["audit-service"]["status"] = "healthy"
            else:
                logger.error(f"❌ Audit Service: 비정상 (상태코드: {response.status_code})")
                self.test_results["services"]["audit-service"]["issues"].append(
                    f"Health check failed with status {response.status_code}"
                )
        except Exception as e:
            logger.error(f"❌ Audit Service: 연결 실패 - {str(e)}")
            self.test_results["services"]["audit-service"]["status"] = "unreachable"
            self.test_results["services"]["audit-service"]["issues"].append(str(e))
        
        # OMS Service 헬스체크
        try:
            response = await self.client.get(f"{OMS_SERVICE_URL}/health")
            if response.status_code == 200:
                logger.info("✅ OMS Service: 정상")
                self.test_results["services"]["oms-service"]["status"] = "healthy"
            else:
                logger.error(f"❌ OMS Service: 비정상 (상태코드: {response.status_code})")
                self.test_results["services"]["oms-service"]["issues"].append(
                    f"Health check failed with status {response.status_code}"
                )
        except Exception as e:
            logger.error(f"❌ OMS Service: 연결 실패 - {str(e)}")
            self.test_results["services"]["oms-service"]["status"] = "unreachable"
            self.test_results["services"]["oms-service"]["issues"].append(str(e))
    
    async def test_user_registration_and_login(self):
        """사용자 등록 및 로그인 테스트"""
        logger.info("\n=== 사용자 등록 및 로그인 테스트 ===")
        
        # 1. 사용자 등록
        timestamp = int(datetime.now().timestamp())
        test_user = {
            "username": f"testuser{timestamp}",
            "email": f"test_{timestamp}@example.com",
            "password": "TestPass123!",
            "full_name": "Test User"
        }
        
        try:
            response = await self.client.post(
                f"{USER_SERVICE_URL}/auth/register",
                json=test_user
            )
            
            if response.status_code == 201:
                user_data = response.json()
                # Extract user_id from the nested user object
                user_info = user_data.get("user", {})
                self.user_id = user_info.get("user_id")
                logger.info(f"✅ 사용자 등록 성공: {test_user['username']} (ID: {self.user_id})")
            else:
                logger.error(f"❌ 사용자 등록 실패: {response.status_code} - {response.text}")
                self.test_results["services"]["user-service"]["issues"].append(
                    f"Registration failed: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"❌ 사용자 등록 중 오류: {str(e)}")
            self.test_results["services"]["user-service"]["issues"].append(
                f"Registration error: {str(e)}"
            )
            return False
        
        # 2. 로그인
        try:
            response = await self.client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={
                    "username": test_user["username"],
                    "password": test_user["password"]
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                logger.info("✅ 로그인 성공")
                return True
            else:
                logger.error(f"❌ 로그인 실패: {response.status_code} - {response.text}")
                self.test_results["services"]["user-service"]["issues"].append(
                    f"Login failed: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"❌ 로그인 중 오류: {str(e)}")
            self.test_results["services"]["user-service"]["issues"].append(
                f"Login error: {str(e)}"
            )
            return False
    
    async def test_oms_with_auth(self):
        """인증된 상태로 OMS 서비스 테스트"""
        logger.info("\n=== OMS 서비스 인증 테스트 ===")
        
        if not self.access_token:
            logger.error("❌ 액세스 토큰이 없습니다")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # 1. 브랜치 생성 테스트
        branch_data = {
            "branch_id": f"test_branch_{datetime.now().timestamp()}",
            "description": "Integration test branch"
        }
        
        try:
            response = await self.client.post(
                f"{OMS_SERVICE_URL}/api/v1/branches",
                json=branch_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ OMS 브랜치 생성 성공")
                
                # Audit 로그 확인
                await asyncio.sleep(1)  # Audit 로그가 생성될 시간을 줌
                
                # 2. 스키마 조회 테스트
                response = await self.client.get(
                    f"{OMS_SERVICE_URL}/api/v1/schemas",
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info("✅ OMS 스키마 조회 성공")
                else:
                    logger.error(f"❌ OMS 스키마 조회 실패: {response.status_code}")
                    self.test_results["services"]["oms-service"]["issues"].append(
                        f"Schema query failed: {response.status_code}"
                    )
                
                return True
            else:
                logger.error(f"❌ OMS 브랜치 생성 실패: {response.status_code} - {response.text}")
                self.test_results["services"]["oms-service"]["issues"].append(
                    f"Branch creation failed: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"❌ OMS 테스트 중 오류: {str(e)}")
            self.test_results["services"]["oms-service"]["issues"].append(
                f"OMS test error: {str(e)}"
            )
            return False
    
    async def test_audit_logs(self):
        """Audit 로그 확인"""
        logger.info("\n=== Audit 로그 확인 ===")
        
        if not self.access_token:
            logger.error("❌ 액세스 토큰이 없습니다")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # Audit 이벤트 조회
            response = await self.client.get(
                f"{AUDIT_SERVICE_URL}/api/v1/events",
                headers=headers,
                params={
                    "limit": 10,
                    "offset": 0
                }
            )
            
            if response.status_code == 200:
                events = response.json()
                logger.info(f"✅ Audit 이벤트 조회 성공: {len(events.get('items', []))}개의 이벤트")
                
                # 최근 이벤트 확인
                if events.get('items'):
                    for event in events['items'][:3]:
                        logger.info(f"  - {event.get('event_type')}: {event.get('timestamp')}")
                
                return True
            else:
                logger.error(f"❌ Audit 이벤트 조회 실패: {response.status_code} - {response.text}")
                self.test_results["services"]["audit-service"]["issues"].append(
                    f"Event query failed: {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"❌ Audit 로그 확인 중 오류: {str(e)}")
            self.test_results["services"]["audit-service"]["issues"].append(
                f"Audit log error: {str(e)}"
            )
            return False
    
    async def test_cross_service_integration(self):
        """서비스 간 통합 테스트"""
        logger.info("\n=== 서비스 간 통합 테스트 ===")
        
        # 1. Nginx를 통한 라우팅 테스트
        try:
            # User Service 경로 테스트 - profile endpoint
            response = await self.client.get(f"{USER_SERVICE_URL}/profile", 
                                           headers={"Authorization": f"Bearer {self.access_token}"})
            if response.status_code == 200:
                logger.info("✅ User Service profile endpoint 성공")
            else:
                logger.error(f"❌ User Service profile endpoint 실패: {response.status_code}")
                self.test_results["services"]["integration"]["issues"].append(
                    "User Service profile endpoint failed"
                )
            
            # OMS Service 경로 테스트
            response = await self.client.get(f"{NGINX_URL}/api/v1/schemas",
                                           headers={"Authorization": f"Bearer {self.access_token}"})
            if response.status_code == 200:
                logger.info("✅ Nginx → OMS Service 라우팅 성공")
            else:
                logger.error(f"❌ Nginx → OMS Service 라우팅 실패: {response.status_code}")
                self.test_results["services"]["integration"]["issues"].append(
                    "Nginx to OMS Service routing failed"
                )
        except Exception as e:
            logger.error(f"❌ Nginx 라우팅 테스트 중 오류: {str(e)}")
            self.test_results["services"]["integration"]["issues"].append(
                f"Nginx routing error: {str(e)}"
            )
        
        # 2. JWT 토큰 검증 테스트
        logger.info("\n--- JWT 토큰 교차 검증 테스트 ---")
        
        # OMS에서 User Service 토큰 검증
        if self.access_token:
            try:
                response = await self.client.get(
                    f"{OMS_SERVICE_URL}/api/v1/auth/verify",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                if response.status_code == 200:
                    logger.info("✅ OMS에서 User Service JWT 토큰 검증 성공")
                else:
                    logger.error(f"❌ OMS에서 JWT 토큰 검증 실패: {response.status_code}")
                    self.test_results["services"]["integration"]["issues"].append(
                        "JWT validation failed in OMS"
                    )
            except Exception as e:
                logger.error(f"❌ JWT 검증 테스트 중 오류: {str(e)}")
                self.test_results["services"]["integration"]["issues"].append(
                    f"JWT validation error: {str(e)}"
                )
    
    def generate_report(self):
        """테스트 결과 리포트 생성"""
        logger.info("\n=== 테스트 결과 요약 ===")
        
        # 전체 상태 결정
        all_healthy = True
        for service, data in self.test_results["services"].items():
            if data["status"] != "healthy" or data["issues"]:
                all_healthy = False
                break
        
        self.test_results["overall_status"] = "success" if all_healthy else "failure"
        
        # 결과 출력
        for service, data in self.test_results["services"].items():
            status_icon = "✅" if data["status"] == "healthy" and not data["issues"] else "❌"
            logger.info(f"{status_icon} {service}: {data['status']}")
            if data["issues"]:
                for issue in data["issues"]:
                    logger.info(f"   - {issue}")
        
        # JSON 파일로 저장
        report_filename = f"three_service_integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"\n📄 상세 리포트 저장됨: {report_filename}")
        
        return self.test_results

async def main():
    """메인 테스트 실행"""
    async with ServiceIntegrationTester() as tester:
        # 1. 서비스 헬스체크
        await tester.check_service_health()
        
        # 2. 사용자 등록 및 로그인
        login_success = await tester.test_user_registration_and_login()
        
        if login_success:
            # 3. OMS 서비스 테스트
            await tester.test_oms_with_auth()
            
            # 4. Audit 로그 확인
            await tester.test_audit_logs()
            
            # 5. 서비스 간 통합 테스트
            await tester.test_cross_service_integration()
        
        # 6. 리포트 생성
        report = tester.generate_report()
        
        # 전체 결과 반환
        return report["overall_status"] == "success"

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)