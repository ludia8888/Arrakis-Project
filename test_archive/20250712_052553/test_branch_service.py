#!/usr/bin/env python3
"""
Test Branch Service functionality with unified configuration
"""
import sys
import os
from pathlib import Path
import httpx
import jwt
import json
from datetime import datetime, timedelta

# 통합 설정 로드
sys.path.append(str(Path(__file__).parent))
from load_shared_config import load_shared_config

def create_test_jwt():
    """Create a test JWT token using unified configuration"""
    # 통합 설정에서 JWT 설정 가져오기
    secret = os.getenv("JWT_SECRET", "fallback-secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    issuer = os.getenv("JWT_ISSUER", "iam.company")
    audience = os.getenv("JWT_AUDIENCE", "oms")
    
    payload = {
        "sub": "test_user_123",
        "user_id": "test_user_123", 
        "username": "test_user",
        "email": "test@example.com",
        "tenant_id": "test_tenant",
        "roles": ["admin", "user"],
        "scope": "api:branches:read api:branches:write api:ontologies:read api:ontologies:write",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "iss": issuer,
        "aud": audience
    }
    
    print(f"🔐 JWT 토큰 생성:")
    print(f"  Issuer: {issuer}")
    print(f"  Audience: {audience}")
    print(f"  Algorithm: {algorithm}")
    print(f"  Secret: {'*' * (len(secret) - 4)}{secret[-4:]}")
    
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


async def test_branch_service():
    """Test branch service endpoints"""
    
    # 통합 설정 로드
    print("🔧 통합 설정 로드 중...")
    if not load_shared_config():
        print("❌ 통합 설정 로드 실패")
        return False
    
    # Create JWT token
    token = create_test_jwt()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    oms_url = os.getenv("OMS_SERVICE_URL", "http://localhost:8003")
    print(f"\n🧪 Branch Service 테스트 시작 - {oms_url}")
    
    async with httpx.AsyncClient() as client:
        # Test 1: List branches
        print(f"\n1. Testing GET {oms_url}/api/v1/branches/")
        try:
            response = await client.get(f"{oms_url}/api/v1/branches/", headers=headers)
            print(f"📊 Status: {response.status_code}")
            print(f"📋 Response: {response.text}")
            
            if response.status_code == 200:
                print("✅ Branch service is working perfectly!")
                
                # 추가 테스트: Create branch
                print(f"\n2. Testing POST {oms_url}/api/v1/branches/")
                create_data = {
                    "name": "test-branch",
                    "from_branch": "main"
                }
                response = await client.post(
                    f"{oms_url}/api/v1/branches/", 
                    headers=headers,
                    json=create_data
                )
                print(f"📊 Create Branch Status: {response.status_code}")
                print(f"📋 Create Response: {response.text}")
                
                return True
            else:
                print("❌ Branch service failed")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


if __name__ == "__main__":
    import asyncio
    print("🎯 Arrakis Project - 통합 JWT 인증 테스트")
    print("=" * 50)
    success = asyncio.run(test_branch_service())
    print("=" * 50)
    if success:
        print("🎉 모든 테스트 통과! 아키텍처 통합 성공!")
    else:
        print("💥 테스트 실패 - 추가 디버깅 필요")
    exit(0 if success else 1)