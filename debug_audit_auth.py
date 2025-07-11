import asyncio
import httpx
import sys

async def test_auth():
    """JWT 인증 테스트"""
    # 1. 로그인
    async with httpx.AsyncClient() as client:
        # 로그인
        login_resp = await client.post(
            "http://localhost:8080/auth/login",
            json={"username": "jwttest", "password": "Test123!"}
        )
        
        if login_resp.status_code != 200:
            print(f"Login failed: {login_resp.status_code}")
            return
            
        token_data = login_resp.json()
        if token_data.get("step") == "complete":
            complete_resp = await client.post(
                "http://localhost:8080/auth/login/complete",
                json={"challenge_token": token_data["challenge_token"]}
            )
            if complete_resp.status_code == 200:
                token = complete_resp.json()["access_token"]
            else:
                print(f"Complete failed: {complete_resp.status_code}")
                return
        else:
            token = token_data.get("access_token")
            
        print(f"Got token: {token[:50]}...")
        
        # 2. Health check (no auth required)
        resp = await client.get("http://localhost:8002/api/v2/events/health")
        print(f"Health check: {resp.status_code}")
        
        # 3. Test with token
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try debug endpoint
        try:
            resp = await client.post("http://localhost:8002/api/v2/events/debug-auth", headers=headers)
            print(f"Debug auth: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Debug auth error: {e}")
            
        # Try query endpoint  
        try:
            resp = await client.get("http://localhost:8002/api/v2/events/query", headers=headers)
            print(f"Query: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Query error: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth())