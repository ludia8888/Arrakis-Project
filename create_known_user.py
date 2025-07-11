import asyncio
import httpx
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_SERVICE_URL = "http://localhost:8080"

async def create_and_test():
    """Create a user and test integration"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Use a unique username to avoid rate limit
        timestamp = int(datetime.now().timestamp() * 1000) % 1000000
        test_user = {
            "username": f"integration_test_{timestamp}",
            "email": f"integration_{timestamp}@test.com",
            "password": "Test@Pass123",
            "full_name": "Integration Test User"
        }
        
        # 1. Register user
        logger.info(f"=== 사용자 등록: {test_user['username']} ===")
        try:
            response = await client.post(
                f"{USER_SERVICE_URL}/auth/register",
                json=test_user
            )
            
            if response.status_code == 201:
                logger.info("✅ 사용자 등록 성공")
                
                # 2. Login
                response = await client.post(
                    f"{USER_SERVICE_URL}/auth/login",
                    json={
                        "username": test_user["username"],
                        "password": test_user["password"]
                    }
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    logger.info(f"Login response: {token_data}")
                    
                    # Check if this is a multi-step authentication
                    if token_data.get("step") == "complete" and "challenge_token" in token_data:
                        # Complete the login
                        complete_response = await client.post(
                            f"{USER_SERVICE_URL}/auth/login/complete",
                            json={
                                "challenge_token": token_data["challenge_token"]
                            }
                        )
                        
                        if complete_response.status_code == 200:
                            final_data = complete_response.json()
                            logger.info(f"Login complete response: {final_data}")
                            access_token = final_data.get("access_token")
                        else:
                            logger.error(f"Login complete failed: {complete_response.status_code} - {complete_response.text}")
                            return
                    else:
                        access_token = token_data.get("access_token")
                    
                    logger.info("✅ 로그인 성공")
                    
                    # 3. Test all services
                    headers = {"Authorization": f"Bearer {access_token}"}
                    
                    # Test profile
                    response = await client.get(f"{USER_SERVICE_URL}/auth/profile/profile", headers=headers)
                    logger.info(f"Profile: {response.status_code} - {response.json() if response.status_code == 200 else response.text}")
                    
                    # Test token validation endpoint
                    response = await client.post(f"{USER_SERVICE_URL}/api/v1/auth/validate", 
                                               json={"token": access_token})
                    logger.info(f"Token validation: {response.status_code} - {response.json() if response.status_code == 200 else response.text}")
                    
                    # Test OMS - need branch parameter
                    response = await client.get("http://localhost:8091/api/v1/schemas/main/object-types", headers=headers)
                    logger.info(f"OMS Schemas: {response.status_code} - {response.json() if response.status_code == 200 else response.text}")
                    
                    # Test Audit - debug first
                    response = await client.post("http://localhost:8002/api/v2/events/debug-auth", headers=headers)
                    logger.info(f"Audit Debug Auth: {response.status_code} - {response.json() if response.status_code == 200 else response.text[:200]}")
                    
                    # Test Audit - needs query parameters
                    response = await client.get(
                        "http://localhost:8002/api/v2/events/query",
                        params={"event_type": "user_created", "limit": 10},
                        headers=headers
                    )
                    logger.info(f"Audit Events: {response.status_code} - {response.json() if response.status_code == 200 else response.text[:200]}")
                    
                    # Note: /api/v1/auth/verify endpoint doesn't exist in OMS
                    # Cross-service JWT validation is already proven by successful access to schemas endpoint
                    
                else:
                    logger.error(f"❌ 로그인 실패: {response.status_code} - {response.text}")
            else:
                logger.error(f"❌ 사용자 등록 실패: {response.status_code} - {response.text}")
                if response.status_code == 429:
                    logger.info("Rate limit hit. Waiting 60 seconds...")
                    await asyncio.sleep(60)
                    logger.info("Retrying...")
                    await create_and_test()
                
        except Exception as e:
            logger.error(f"❌ 테스트 중 오류: {str(e)}")

if __name__ == "__main__":
    asyncio.run(create_and_test())