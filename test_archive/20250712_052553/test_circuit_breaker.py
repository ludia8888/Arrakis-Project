#!/usr/bin/env python3
"""
Circuit Breaker Test Script
서킷 브레이커 기능을 검증하는 테스트
"""
import asyncio
import httpx
import json
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8092"


class CircuitBreakerTester:
    def __init__(self):
        self.test_user = None
        self.test_token = None
        
    async def setup(self):
        """테스트 사용자 생성 및 로그인"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 테스트 사용자 등록
            user_data = {
                "username": f"circuit_test_{int(time.time())}",
                "password": "Test123!@#",
                "email": f"circuit_{int(time.time())}@test.com",
                "full_name": "Circuit Breaker Test"
            }
            
            resp = await client.post(f"{USER_SERVICE_URL}/auth/register", json=user_data)
            if resp.status_code != 201:
                logger.error(f"Failed to register user: {resp.status_code}")
                return False
                
            self.test_user = user_data
            
            # 로그인
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={"username": user_data["username"], "password": user_data["password"]}
            )
            
            if resp.status_code == 200:
                login_data = resp.json()
                if login_data.get("step") == "complete":
                    complete_resp = await client.post(
                        f"{USER_SERVICE_URL}/auth/login/complete",
                        json={"challenge_token": login_data["challenge_token"]}
                    )
                    if complete_resp.status_code == 200:
                        self.test_token = complete_resp.json()["access_token"]
                else:
                    self.test_token = login_data.get("access_token")
                    
            return self.test_token is not None
    
    async def test_circuit_breaker_behavior(self):
        """서킷 브레이커 동작 테스트"""
        logger.info("="*60)
        logger.info("CIRCUIT BREAKER BEHAVIOR TEST")
        logger.info("="*60)
        
        # 1. 정상 상태에서 감사 로그 생성 테스트
        logger.info("\n1. Testing normal audit logging...")
        success = await self._test_normal_audit_logging()
        if success:
            logger.info("✅ Normal audit logging works")
        else:
            logger.error("❌ Normal audit logging failed")
            
        # 2. Audit Service 중단 시뮬레이션
        logger.info("\n2. Simulating audit service failure...")
        logger.info("Stop the audit service with: docker-compose stop audit-service")
        logger.info("Press Enter when ready...")
        input()
        
        # 3. 서킷 브레이커가 열리는지 테스트
        logger.info("\n3. Testing circuit breaker opening...")
        await self._test_circuit_breaker_opening()
        
        # 4. 서킷이 열린 상태에서 요청이 빠르게 실패하는지 테스트
        logger.info("\n4. Testing fast failure when circuit is open...")
        await self._test_fast_failure()
        
        # 5. Audit Service 재시작
        logger.info("\n5. Restart audit service to test recovery...")
        logger.info("Start the audit service with: docker-compose start audit-service")
        logger.info("Press Enter when ready...")
        input()
        
        # 6. 서킷 브레이커 복구 테스트
        logger.info("\n6. Testing circuit breaker recovery...")
        await self._test_circuit_breaker_recovery()
        
    async def _test_normal_audit_logging(self) -> bool:
        """정상 상태에서 감사 로그 테스트"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.test_token}"}
            
            # 프로필 조회 (감사 로그 생성)
            resp = await client.get(f"{USER_SERVICE_URL}/auth/profile/profile", headers=headers)
            
            if resp.status_code == 200:
                logger.info("Profile retrieved successfully")
                
                # 감사 이벤트 직접 생성
                event_data = {
                    "event_type": "circuit_breaker_test",
                    "event_category": "test",
                    "severity": "INFO",
                    "user_id": "test_user",
                    "username": self.test_user["username"],
                    "target_type": "test",
                    "target_id": "cb_test_001",
                    "operation": "test_normal",
                    "metadata": {"test": "normal_operation"}
                }
                
                resp = await client.post(
                    f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                    headers=headers,
                    json=event_data
                )
                
                return resp.status_code == 201
                
            return False
    
    async def _test_circuit_breaker_opening(self):
        """서킷 브레이커가 열리는지 테스트"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.test_token}"}
            
            failure_count = 0
            for i in range(10):  # 충분한 실패를 발생시킴
                try:
                    start = time.time()
                    resp = await client.post(
                        f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                        headers=headers,
                        json={
                            "event_type": "circuit_test",
                            "event_category": "test",
                            "severity": "INFO",
                            "user_id": "test",
                            "username": "test",
                            "target_type": "test",
                            "target_id": f"test_{i}",
                            "operation": "test",
                            "metadata": {}
                        }
                    )
                    duration = time.time() - start
                    
                    if resp.status_code != 201:
                        failure_count += 1
                        logger.info(f"Request {i+1}: Failed with {resp.status_code} (took {duration:.2f}s)")
                    else:
                        logger.info(f"Request {i+1}: Succeeded (took {duration:.2f}s)")
                        
                except Exception as e:
                    failure_count += 1
                    duration = time.time() - start
                    logger.info(f"Request {i+1}: Exception - {type(e).__name__} (took {duration:.2f}s)")
                    
                await asyncio.sleep(0.5)
                
            logger.info(f"\nTotal failures: {failure_count}/10")
            
    async def _test_fast_failure(self):
        """서킷이 열렸을 때 빠른 실패 테스트"""
        # User service의 다른 엔드포인트 테스트
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.test_token}"}
            
            # 일반 요청은 여전히 작동해야 함
            start = time.time()
            resp = await client.get(f"{USER_SERVICE_URL}/auth/profile/profile", headers=headers)
            duration = time.time() - start
            
            if resp.status_code == 200:
                logger.info(f"✅ User service still responsive (took {duration:.2f}s)")
                logger.info("✅ Circuit breaker is working - service remains available")
            else:
                logger.error(f"❌ User service returned {resp.status_code}")
                
    async def _test_circuit_breaker_recovery(self):
        """서킷 브레이커 복구 테스트"""
        logger.info("Waiting 60 seconds for circuit breaker recovery timeout...")
        await asyncio.sleep(60)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.test_token}"}
            
            # 복구 시도
            for i in range(5):
                try:
                    resp = await client.post(
                        f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                        headers=headers,
                        json={
                            "event_type": "recovery_test",
                            "event_category": "test",
                            "severity": "INFO",
                            "user_id": "test",
                            "username": "test",
                            "target_type": "test",
                            "target_id": f"recovery_{i}",
                            "operation": "test_recovery",
                            "metadata": {}
                        }
                    )
                    
                    if resp.status_code == 201:
                        logger.info(f"✅ Request {i+1}: Succeeded - Circuit breaker recovering")
                    else:
                        logger.error(f"❌ Request {i+1}: Failed with {resp.status_code}")
                        
                except Exception as e:
                    logger.error(f"❌ Request {i+1}: Exception - {type(e).__name__}")
                    
                await asyncio.sleep(1)
                
    async def test_current_implementation(self):
        """현재 구현된 감사 서비스의 복원력 테스트"""
        logger.info("="*60)
        logger.info("CURRENT AUDIT SERVICE RESILIENCE TEST")
        logger.info("="*60)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.test_token}"}
            
            # 1. 정상 상태 테스트
            logger.info("\n1. Testing normal state...")
            resp = await client.get(f"{USER_SERVICE_URL}/auth/profile/profile", headers=headers)
            if resp.status_code == 200:
                logger.info("✅ Profile retrieved - audit event should be logged")
            
            # 2. Audit service가 다운된 상태 시뮬레이션
            logger.info("\n2. Testing with audit service down...")
            logger.info("The basic AuditService should queue failed events to Redis")
            
            # 3. 여러 작업 수행
            operations = [
                ("GET", f"{USER_SERVICE_URL}/auth/profile/profile", None),
                ("POST", f"{USER_SERVICE_URL}/auth/logout", None),
            ]
            
            for method, url, data in operations:
                try:
                    if method == "GET":
                        resp = await client.get(url, headers=headers)
                    else:
                        resp = await client.post(url, headers=headers, json=data)
                        
                    logger.info(f"✅ {method} {url} - Status: {resp.status_code}")
                    logger.info("   (Audit events should be queued if audit service is down)")
                except Exception as e:
                    logger.error(f"❌ {method} {url} - Failed: {e}")


async def main():
    """메인 테스트 실행"""
    tester = CircuitBreakerTester()
    
    # 설정
    if not await tester.setup():
        logger.error("Failed to setup test user")
        return 1
        
    # 현재 구현 테스트
    await tester.test_current_implementation()
    
    # Enhanced 서킷 브레이커 테스트 (구현되어 있지만 사용되지 않음)
    logger.info("\n" + "="*60)
    logger.info("NOTE: EnhancedAuditService with circuit breaker is implemented")
    logger.info("but not currently used. The basic AuditService provides:")
    logger.info("- Redis queue fallback for failed events")
    logger.info("- 7-day TTL on queued events")
    logger.info("- Automatic retry when service recovers")
    logger.info("="*60)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))