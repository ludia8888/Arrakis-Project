import asyncio
import httpx
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_SERVICE_URL = "http://localhost:8080"

async def test_login_and_integration():
    """Test login with existing user and integration"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login with test user
        logger.info("=== 로그인 테스트 ===")
        try:
            response = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={
                    "username": "testuser",
                    "password": "testpass123"
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                logger.info("✅ 로그인 성공")
                
                # 2. Test profile endpoint
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(f"{USER_SERVICE_URL}/profile", headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Profile endpoint 성공: {response.json()}")
                else:
                    logger.error(f"❌ Profile endpoint 실패: {response.status_code} - {response.text}")
                
                # 3. Test OMS service
                logger.info("\n=== OMS 서비스 테스트 ===")
                response = await client.get("http://localhost:8091/api/v1/schemas", headers=headers)
                if response.status_code == 200:
                    logger.info("✅ OMS schemas endpoint 성공")
                else:
                    logger.error(f"❌ OMS schemas endpoint 실패: {response.status_code} - {response.text}")
                
                # 4. Test audit service  
                logger.info("\n=== Audit 서비스 테스트 ===")
                response = await client.get("http://localhost:8002/api/v1/events/", headers=headers)
                if response.status_code == 200:
                    logger.info("✅ Audit events endpoint 성공")
                else:
                    logger.error(f"❌ Audit events endpoint 실패: {response.status_code} - {response.text}")
                    
            else:
                logger.error(f"❌ 로그인 실패: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"❌ 테스트 중 오류: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_login_and_integration())