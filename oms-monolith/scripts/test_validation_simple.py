#!/usr/bin/env python
"""
Simple validation test to verify basic functionality
"""
import httpx
import jwt
import asyncio
from datetime import datetime, timedelta, timezone

# JWT 토큰 생성
def generate_jwt():
    secret = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="
    payload = {
        "sub": "testuser",
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

async def test_basic_validation():
    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        print("\n=== BASIC VALIDATION TEST ===\n")
        
        # Test 1: Valid request
        print("1. Testing valid request...")
        response = await client.post(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            json={
                "name": "TestObject",
                "displayName": "Test Object",
                "description": "A valid test object"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 2: Invalid name (SQL injection attempt)
        print("\n2. Testing SQL injection...")
        response = await client.post(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            json={
                "name": "Test'; DROP TABLE users; --",
                "displayName": "Test"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 3: XSS attempt
        print("\n3. Testing XSS...")
        response = await client.post(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            json={
                "name": "Test<script>alert('XSS')</script>",
                "displayName": "Test"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 4: Check validation metrics
        print("\n4. Checking validation metrics...")
        response = await client.get(
            "http://localhost:8002/api/v1/validation/metrics"
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Metrics: {response.json()}")

if __name__ == "__main__":
    asyncio.run(test_basic_validation())