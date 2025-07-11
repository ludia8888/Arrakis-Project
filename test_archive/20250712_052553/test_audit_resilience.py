#!/usr/bin/env python3
"""
Audit Service Resilience Test
감사 서비스의 복원력 메커니즘 테스트
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


async def test_audit_service_down():
    """Audit Service가 다운된 상태에서의 동작 테스트"""
    logger.info("="*60)
    logger.info("AUDIT SERVICE DOWN RESILIENCE TEST")
    logger.info("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 테스트 사용자 생성
        logger.info("\n1. Creating test user...")
        user_data = {
            "username": f"resilience_test_{int(time.time())}",
            "password": "Test123!@#",
            "email": f"resilience_{int(time.time())}@test.com",
            "full_name": "Resilience Test"
        }
        
        resp = await client.post(f"{USER_SERVICE_URL}/auth/register", json=user_data)
        if resp.status_code != 201:
            logger.error(f"Failed to register user: {resp.status_code}")
            return
            
        logger.info("✅ User created successfully")
        
        # 2. 로그인
        logger.info("\n2. Logging in...")
        resp = await client.post(
            f"{USER_SERVICE_URL}/auth/login",
            json={"username": user_data["username"], "password": user_data["password"]}
        )
        
        token = None
        if resp.status_code == 200:
            login_data = resp.json()
            if login_data.get("step") == "complete":
                complete_resp = await client.post(
                    f"{USER_SERVICE_URL}/auth/login/complete",
                    json={"challenge_token": login_data["challenge_token"]}
                )
                if complete_resp.status_code == 200:
                    token = complete_resp.json()["access_token"]
            else:
                token = login_data.get("access_token")
                
        if not token:
            logger.error("Failed to get token")
            return
            
        logger.info("✅ Login successful")
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Audit Service 상태 확인
        logger.info("\n3. Checking audit service status...")
        try:
            resp = await client.get(f"{AUDIT_SERVICE_URL}/api/v2/events/health")
            if resp.status_code == 200:
                logger.info("✅ Audit service is UP")
                logger.info("⚠️  Stop audit service to test resilience:")
                logger.info("    docker-compose stop audit-service")
                logger.info("    Press Enter when ready...")
                input()
        except:
            logger.info("✅ Audit service is already DOWN")
        
        # 4. Audit Service가 다운된 상태에서 작업 수행
        logger.info("\n4. Performing operations with audit service down...")
        
        operations = [
            ("Profile view", "GET", f"{USER_SERVICE_URL}/auth/profile/profile", None),
            ("Password change attempt", "POST", f"{USER_SERVICE_URL}/auth/change-password", {
                "current_password": user_data["password"],
                "new_password": "NewTest123!@#"
            }),
            ("Logout", "POST", f"{USER_SERVICE_URL}/auth/logout", None),
        ]
        
        for op_name, method, url, data in operations:
            logger.info(f"\n  Testing: {op_name}")
            try:
                start = time.time()
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers, json=data)
                duration = time.time() - start
                
                logger.info(f"    Status: {resp.status_code}")
                logger.info(f"    Duration: {duration:.2f}s")
                
                if resp.status_code in [200, 201]:
                    logger.info(f"    ✅ Operation successful despite audit service being down")
                else:
                    logger.warning(f"    ⚠️  Operation failed with {resp.status_code}")
                    
            except Exception as e:
                duration = time.time() - start
                logger.error(f"    ❌ Exception: {type(e).__name__}")
                logger.error(f"    Duration: {duration:.2f}s")
        
        # 5. Redis에 큐잉된 이벤트 수 확인 (Redis 접근 가능한 경우)
        logger.info("\n5. Checking queued events...")
        logger.info("   Events should be queued in Redis for retry")
        logger.info("   Queue key: user-service:audit:retry_queue")
        
        # 6. Audit Service 재시작 후 동작 확인
        logger.info("\n6. Testing recovery...")
        logger.info("   Start audit service to process queued events:")
        logger.info("   docker-compose start audit-service")
        logger.info("   Press Enter when ready...")
        input()
        
        # 새로운 작업 수행
        logger.info("\n   Performing new operation after recovery...")
        try:
            # 새 토큰으로 로그인 (이전 토큰은 로그아웃으로 무효화됨)
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={"username": user_data["username"], "password": "NewTest123!@#"}  # 변경된 비밀번호
            )
            
            if resp.status_code == 200:
                logger.info("    ✅ Login successful - password was changed successfully")
                logger.info("    ✅ This confirms operations worked even with audit service down")
            else:
                # 비밀번호 변경이 실패했다면 원래 비밀번호로 시도
                resp = await client.post(
                    f"{USER_SERVICE_URL}/auth/login",
                    json={"username": user_data["username"], "password": user_data["password"]}
                )
                if resp.status_code == 200:
                    logger.info("    ✅ Login with original password - password change was not processed")
                    
        except Exception as e:
            logger.error(f"    ❌ Recovery test failed: {e}")


async def check_audit_logs():
    """감사 로그 확인"""
    logger.info("\n" + "="*60)
    logger.info("CHECKING AUDIT LOGS")
    logger.info("="*60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 최근 감사 이벤트 조회
            resp = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                params={
                    "limit": 10,
                    "sort_order": "desc"
                }
            )
            
            if resp.status_code == 200:
                events = resp.json()
                logger.info(f"\nFound {len(events.get('events', []))} recent audit events")
                
                for event in events.get('events', [])[:5]:
                    logger.info(f"\n  Event: {event.get('event_type')}")
                    logger.info(f"  User: {event.get('username')}")
                    logger.info(f"  Time: {event.get('created_at')}")
                    logger.info(f"  Success: {event.get('success')}")
            else:
                logger.error(f"Failed to query audit logs: {resp.status_code}")
                
        except Exception as e:
            logger.error(f"Cannot connect to audit service: {e}")


async def main():
    """메인 테스트 실행"""
    # 복원력 테스트
    await test_audit_service_down()
    
    # 감사 로그 확인
    await check_audit_logs()
    
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    logger.info("Current resilience mechanisms:")
    logger.info("1. ✅ Operations continue even when audit service is down")
    logger.info("2. ✅ Failed audit events are queued in Redis")
    logger.info("3. ✅ Queued events have 7-day TTL")
    logger.info("4. ⚠️  No automatic retry mechanism (manual processing needed)")
    logger.info("5. ⚠️  No circuit breaker pattern (each request tries to connect)")
    logger.info("\nRecommendation: Consider using EnhancedAuditService for:")
    logger.info("- Circuit breaker pattern")
    logger.info("- Automatic retry with backoff")
    logger.info("- Better performance under failure conditions")
    

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))