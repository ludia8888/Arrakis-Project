#!/usr/bin/env python3
"""서비스 통합 테스트"""

import httpx
import asyncio
import json

async def test_services():
    """각 서비스의 health check 엔드포인트 테스트"""
    
    services = [
        ("User Service", "http://localhost:8101/health"),
        ("Audit Service", "http://localhost:8002/health"),
        ("OMS Monolith", "http://localhost:8000/api/v1/health"),
    ]
    
    print("Testing all services...\n")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services:
            try:
                print(f"Testing {name} at {url}...")
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"✅ {name}: OK")
                    print(f"   Response: {response.json()}")
                else:
                    print(f"❌ {name}: Failed (Status: {response.status_code})")
                    print(f"   Response: {response.text}")
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
            print()
    
    # Test authentication flow
    print("\nTesting authentication flow...")
    try:
        # 1. User Service에서 토큰 얻기 (실제로는 로그인 엔드포인트를 사용해야 함)
        print("Note: Full authentication test requires login endpoint implementation")
        
        # 2. OMS Monolith의 인증이 필요한 엔드포인트 테스트
        print("Testing OMS protected endpoint without auth...")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/api/v1/schemas")
            if response.status_code == 401:
                print("✅ Authentication required as expected")
            else:
                print(f"❓ Unexpected response: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Auth test error: {e}")

if __name__ == "__main__":
    asyncio.run(test_services())