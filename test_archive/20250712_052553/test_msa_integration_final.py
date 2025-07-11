#!/usr/bin/env python3
"""
완전한 MSA 통합 테스트
공통 라이브러리와 Mock 서비스를 사용한 100% 통합 테스트
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import logging

# 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MSAIntegrationTester:
    """MSA 통합 테스트"""
    
    def __init__(self):
        # Mock 서비스 URL (새로운 포트)
        self.user_service_url = "http://localhost:8012"
        self.audit_service_url = "http://localhost:8011"
        self.oms_url = "http://localhost:8010"
        
        self.test_results = []
        self.test_user = {
            "username": "test_integration_user",
            "password": "TestPassword123!",
            "email": "test@integration.com"
        }
        self.access_token = None
        
    def log_test(self, test_name: str, status: str, details: str = "", duration_ms: int = 0):
        """테스트 결과 로깅"""
        result = {
            "test_name": test_name,
            "status": status,
            "details": details,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.test_results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌"
        logger.info(f"{status_emoji} {test_name}: {status} ({duration_ms}ms)")
        if details:
            logger.info(f"   Details: {details}")
    
    async def test_service_health(self):
        """서비스 헬스 체크"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # User Service 헬스 체크
                response = await client.get(f"{self.user_service_url}/health")
                assert response.status_code == 200
                user_health = response.json()
                
                # Audit Service 헬스 체크
                response = await client.get(f"{self.audit_service_url}/health")
                assert response.status_code == 200
                audit_health = response.json()
                
                # OMS 헬스 체크
                response = await client.get(f"{self.oms_url}/health")
                assert response.status_code == 200
                oms_health = response.json()
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test(
                "서비스 헬스 체크", 
                "PASS", 
                f"모든 서비스 정상: User({user_health['status']}), Audit({audit_health['status']}), OMS({oms_health['status']})",
                duration
            )
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("서비스 헬스 체크", "FAIL", str(e), duration)
            return False
    
    async def test_user_registration(self):
        """사용자 등록 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.user_service_url}/auth/register",
                    json=self.test_user
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] == True
                assert "user_id" in data
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("사용자 등록", "PASS", f"사용자 ID: {data['user_id']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("사용자 등록", "FAIL", str(e), duration)
            return False
    
    async def test_user_login(self):
        """사용자 로그인 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.user_service_url}/auth/login",
                    json={
                        "username": self.test_user["username"],
                        "password": self.test_user["password"]
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data
                assert data["token_type"] == "bearer"
                
                self.access_token = data["access_token"]
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("사용자 로그인", "PASS", "JWT 토큰 획득 성공", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("사용자 로그인", "FAIL", str(e), duration)
            return False
    
    async def test_jwks_endpoint(self):
        """JWKS 엔드포인트 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.user_service_url}/.well-known/jwks.json")
                
                assert response.status_code == 200
                jwks = response.json()
                assert "keys" in jwks
                assert len(jwks["keys"]) > 0
                
                # JWKS 구조 검증
                key = jwks["keys"][0]
                assert key["kty"] == "RSA"
                assert "kid" in key
                assert "use" in key
                assert "alg" in key
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("JWKS 엔드포인트", "PASS", f"키 개수: {len(jwks['keys'])}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("JWKS 엔드포인트", "FAIL", str(e), duration)
            return False
    
    async def test_authenticated_oms_access(self):
        """인증된 OMS 접근 테스트"""
        start_time = time.time()
        
        if not self.access_token:
            self.log_test("인증된 OMS 접근", "SKIP", "액세스 토큰 없음", 0)
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                
                # 스키마 조회
                response = await client.get(f"{self.oms_url}/api/v1/schemas", headers=headers)
                assert response.status_code == 200
                schemas = response.json()
                assert "schemas" in schemas
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("인증된 OMS 접근", "PASS", f"스키마 개수: {len(schemas['schemas'])}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("인증된 OMS 접근", "FAIL", str(e), duration)
            return False
    
    async def test_schema_creation(self):
        """스키마 생성 테스트"""
        start_time = time.time()
        
        if not self.access_token:
            self.log_test("스키마 생성", "SKIP", "액세스 토큰 없음", 0)
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                schema_data = {
                    "name": f"test_schema_{int(time.time())}",
                    "description": "통합 테스트용 스키마"
                }
                
                response = await client.post(
                    f"{self.oms_url}/api/v1/schemas", 
                    headers=headers,
                    json=schema_data
                )
                
                assert response.status_code == 200
                schema = response.json()
                assert "id" in schema
                assert schema["name"] == schema_data["name"]
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("스키마 생성", "PASS", f"스키마 ID: {schema['id']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("스키마 생성", "FAIL", str(e), duration)
            return False
    
    async def test_branch_creation(self):
        """브랜치 생성 테스트"""
        start_time = time.time()
        
        if not self.access_token:
            self.log_test("브랜치 생성", "SKIP", "액세스 토큰 없음", 0)
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                branch_data = {
                    "name": f"test_branch_{int(time.time())}",
                    "description": "통합 테스트용 브랜치"
                }
                
                response = await client.post(
                    f"{self.oms_url}/api/v1/branches", 
                    headers=headers,
                    json=branch_data
                )
                
                assert response.status_code == 200
                branch = response.json()
                assert "id" in branch
                assert branch["name"] == branch_data["name"]
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("브랜치 생성", "PASS", f"브랜치 ID: {branch['id']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("브랜치 생성", "FAIL", str(e), duration)
            return False
    
    async def test_audit_logging(self):
        """감사 로깅 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                audit_data = {
                    "event_type": "integration.test",
                    "user_id": "test-user-123",
                    "action": "test_audit_logging",
                    "resource_type": "test",
                    "result": "success",
                    "details": {"test": "audit_integration"}
                }
                
                response = await client.post(
                    f"{self.audit_service_url}/api/v1/audit/logs",
                    json=audit_data
                )
                
                assert response.status_code == 200
                result = response.json()
                assert result["success"] == True
                assert "log_id" in result
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("감사 로깅", "PASS", f"로그 ID: {result['log_id']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("감사 로깅", "FAIL", str(e), duration)
            return False
    
    async def test_audit_retrieval(self):
        """감사 로그 조회 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.audit_service_url}/api/v1/audit/logs")
                
                assert response.status_code == 200
                logs = response.json()
                assert "logs" in logs
                assert "total" in logs
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("감사 로그 조회", "PASS", f"로그 수: {logs['total']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("감사 로그 조회", "FAIL", str(e), duration)
            return False
    
    async def test_cross_service_audit(self):
        """서비스 간 감사 연동 테스트"""
        start_time = time.time()
        
        if not self.access_token:
            self.log_test("서비스 간 감사 연동", "SKIP", "액세스 토큰 없음", 0)
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                
                # OMS에서 감사 이벤트 조회
                response = await client.get(f"{self.oms_url}/api/v1/audit/events", headers=headers)
                
                assert response.status_code == 200
                events = response.json()
                assert "events" in events
                assert "total" in events
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("서비스 간 감사 연동", "PASS", f"이벤트 수: {events['total']}", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("서비스 간 감사 연동", "FAIL", str(e), duration)
            return False
    
    async def test_error_handling(self):
        """에러 처리 테스트"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # 존재하지 않는 엔드포인트 테스트
                response = await client.get(f"{self.oms_url}/api/v1/nonexistent")
                assert response.status_code == 404
                
                # 인증 없이 보호된 리소스 접근
                response = await client.get(f"{self.oms_url}/api/v1/schemas")
                assert response.status_code == 401
            
            duration = int((time.time() - start_time) * 1000)
            self.log_test("에러 처리", "PASS", "올바른 HTTP 상태 코드 반환", duration)
            return True
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self.log_test("에러 처리", "FAIL", str(e), duration)
            return False
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("🚀 MSA 통합 테스트 시작")
        logger.info("=" * 60)
        
        total_start = time.time()
        
        # 테스트 목록
        tests = [
            self.test_service_health,
            self.test_jwks_endpoint,
            self.test_user_registration,
            self.test_user_login,
            self.test_authenticated_oms_access,
            self.test_schema_creation,
            self.test_branch_creation,
            self.test_audit_logging,
            self.test_audit_retrieval,
            self.test_cross_service_audit,
            self.test_error_handling
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                logger.error(f"테스트 실행 중 오류: {e}")
                results.append(False)
            
            # 테스트 간 간격
            await asyncio.sleep(0.5)
        
        total_duration = int((time.time() - total_start) * 1000)
        
        # 결과 요약
        passed = sum(results)
        total = len(results)
        success_rate = (passed / total) * 100 if total > 0 else 0
        
        logger.info("=" * 60)
        logger.info(f"📊 테스트 완료: {passed}/{total} 통과 ({success_rate:.1f}%)")
        logger.info(f"⏱️  총 소요시간: {total_duration}ms")
        
        # 상세 결과 저장
        report = {
            "summary": {
                "total_tests": total,
                "passed_tests": passed,
                "success_rate": success_rate,
                "total_duration_ms": total_duration,
                "timestamp": datetime.utcnow().isoformat()
            },
            "test_results": self.test_results
        }
        
        # 결과 파일 저장
        report_file = f"msa_integration_test_final_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 상세 보고서 저장: {report_file}")
        
        if success_rate == 100:
            logger.info("🎉 모든 테스트 통과! MSA 시스템이 완벽히 작동합니다!")
        else:
            logger.warning(f"⚠️  {total - passed}개 테스트 실패. 추가 수정이 필요합니다.")
        
        return success_rate == 100


async def main():
    """메인 실행 함수"""
    tester = MSAIntegrationTester()
    success = await tester.run_all_tests()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit_code = 0 if success else 1
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("테스트가 중단되었습니다.")
        exit(1)
    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {e}")
        exit(1)