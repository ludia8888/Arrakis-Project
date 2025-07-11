#!/usr/bin/env python3
import asyncio
import httpx

async def get_token():
    async with httpx.AsyncClient() as client:
        # Login
        login_resp = await client.post(
            "http://localhost:8080/auth/login",
            json={"username": "jwttest", "password": "Test123!"}
        )
        
        if login_resp.status_code != 200:
            print(f"Login failed: {login_resp.status_code}")
            return None
            
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
                return None
        else:
            token = token_data.get("access_token")
            
        return token

async def main():
    token = await get_token()
    if token:
        print(token)

if __name__ == "__main__":
    asyncio.run(main())