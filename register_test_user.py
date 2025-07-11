#!/usr/bin/env python3
"""Register test user for integration testing"""
import asyncio
import httpx
import json

async def register_test_user():
    async with httpx.AsyncClient() as client:
        user_data = {
            "username": "integrationtest",
            "email": "integration@test.com",
            "password": "TestPass123@",
            "full_name": "Integration Test User"
        }
        
        try:
            response = await client.post(
                "http://localhost:8080/auth/register",
                json=user_data,
                timeout=10.0
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 201:
                print("✅ User created successfully")
                return True
            else:
                print("❌ User creation failed")
                return False
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(register_test_user())