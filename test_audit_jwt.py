import asyncio
import httpx

async def test_audit_jwt():
    # 1. 먼저 사용자 등록
    async with httpx.AsyncClient() as client:
        import time
        username = f"test_audit_{int(time.time())}"
        
        register_response = await client.post(
            "http://localhost:8080/auth/register",
            json={
                "username": username,
                "email": f"{username}@test.com",
                "password": "Test@Pass123",
                "full_name": "Test User"
            }
        )
        
        if register_response.status_code != 201:
            print(f"Registration failed: {register_response.text}")
            return
            
        print(f"User registered: {username}")
        
        # 2. 로그인해서 토큰 받기
        login_response = await client.post(
            "http://localhost:8080/auth/login",
            json={"username": username, "password": "Test@Pass123"}
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            if token_data.get("step") == "complete":
                # Complete login
                complete_response = await client.post(
                    "http://localhost:8080/auth/login/complete",
                    json={"challenge_token": token_data["challenge_token"]}
                )
                if complete_response.status_code == 200:
                    access_token = complete_response.json()["access_token"]
                else:
                    print(f"Login complete failed: {complete_response.text}")
                    return
            else:
                access_token = token_data.get("access_token")
        else:
            print(f"Login failed: {login_response.text}")
            return
        
        print(f"Got token: {access_token[:50]}...")
        
        # 2. Audit health check (no auth)
        response = await client.get("http://localhost:8002/api/v2/events/health")
        print(f"Health check: {response.status_code}")
        
        # 3. Debug JWT config (no auth)
        response = await client.get("http://localhost:8002/api/v2/events/debug-jwt-config")
        print(f"JWT Config: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        
        # 4. Debug auth endpoint (requires auth)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.post("http://localhost:8002/api/v2/events/debug-auth", headers=headers)
        print(f"Debug Auth: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_audit_jwt())