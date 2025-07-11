#!/usr/bin/env python3
"""
Container-to-container integration test
Tests communication between services inside Docker network
"""
import asyncio
import httpx
import json
import sys

async def test_integration():
    """Test service integration inside containers"""
    
    # Get token from user service
    async with httpx.AsyncClient() as client:
        # Login
        resp = await client.post(
            "http://user-service:8000/auth/login",
            json={"username": "jwttest", "password": "Test123!"}
        )
        
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code}")
            return False
            
        token_data = resp.json()
        if token_data.get("step") == "complete":
            complete_resp = await client.post(
                "http://user-service:8000/auth/login/complete",
                json={"challenge_token": token_data["challenge_token"]}
            )
            if complete_resp.status_code == 200:
                token = complete_resp.json()["access_token"]
            else:
                print(f"Complete failed: {complete_resp.status_code}")
                return False
        else:
            token = token_data.get("access_token")
            
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test OMS
        resp = await client.get(
            "http://oms-monolith:8091/api/v1/schemas/main/object-types",
            headers=headers
        )
        print(f"OMS schemas: {resp.status_code}")
        
        # Test Audit Service
        resp = await client.post(
            "http://audit-service:8002/api/v2/events/debug-auth",
            headers=headers
        )
        print(f"Audit debug-auth: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Response: {resp.json()}")
        else:
            print(f"Error: {resp.text}")
            
        # Test audit query
        resp = await client.get(
            "http://audit-service:8002/api/v2/events/query",
            headers=headers,
            params={"limit": 10}
        )
        print(f"Audit query: {resp.status_code}")
        
        return True

if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)