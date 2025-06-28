#!/usr/bin/env python
"""
Test OMS API with valid JWT token
"""
import httpx
import jwt
import asyncio
from datetime import datetime, timedelta

# Generate JWT token
def generate_jwt():
    secret = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="
    payload = {
        "sub": "testuser",
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

async def test_oms_api():
    """Test OMS API endpoints"""
    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        print("\n1. Testing GET /api/v1/schemas/main/object-types")
        response = await client.get(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            headers=headers
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
        
        print("\n2. Testing POST /api/v1/schemas/main/object-types")
        response = await client.post(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            headers=headers,
            json={
                "name": "Invoice",
                "displayName": "Invoice",
                "description": "Invoice object type"
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_oms_api())
