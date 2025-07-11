#!/usr/bin/env python3
"""
Create an admin test user for backpressure testing
관리자 권한을 가진 테스트 사용자 생성
"""
import asyncio
import httpx
import json
import time
from datetime import datetime

USER_SERVICE_URL = "http://localhost:8080"

async def create_admin_user():
    """관리자 권한을 가진 테스트 사용자 생성"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 관리자 사용자 생성
        admin_user_data = {
            "username": f"oms_admin_test_{int(time.time())}",
            "password": "AdminTest123!@#",
            "email": f"oms_admin_{int(time.time())}@test.com",
            "full_name": "OMS Admin Test User",
            "roles": ["admin", "oms_admin"]  # 관리자 역할 추가
        }
        
        print(f"Creating admin user: {admin_user_data['username']}")
        
        # 사용자 등록
        resp = await client.post(
            f"{USER_SERVICE_URL}/auth/register",
            json=admin_user_data
        )
        
        if resp.status_code != 201:
            print(f"Failed to create admin user: {resp.status_code}")
            print(f"Response: {resp.text}")
            return None
            
        print("✅ Admin user created successfully")
        
        # 2. 로그인하여 토큰 획득
        login_resp = await client.post(
            f"{USER_SERVICE_URL}/auth/login",
            json={
                "username": admin_user_data["username"],
                "password": admin_user_data["password"]
            }
        )
        
        if login_resp.status_code == 200:
            login_data = login_resp.json()
            
            # MFA 처리
            if login_data.get("step") == "complete":
                complete_resp = await client.post(
                    f"{USER_SERVICE_URL}/auth/login/complete",
                    json={"challenge_token": login_data["challenge_token"]}
                )
                if complete_resp.status_code == 200:
                    token_data = complete_resp.json()
                    access_token = token_data["access_token"]
                else:
                    print(f"Failed to complete login: {complete_resp.status_code}")
                    return None
            else:
                access_token = login_data.get("access_token")
        else:
            print(f"Failed to login: {login_resp.status_code}")
            return None
            
        if not access_token:
            print("Failed to get access token")
            return None
            
        print("✅ Access token obtained")
        
        # 3. 사용자 권한 업데이트 (관리자 스코프 추가)
        # 주의: 실제 환경에서는 다른 관리자가 이 작업을 수행해야 함
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 사용자 정보 조회
        user_info_resp = await client.get(
            f"{USER_SERVICE_URL}/users/me",
            headers=headers
        )
        
        if user_info_resp.status_code == 200:
            user_info = user_info_resp.json()
            print(f"User info: {json.dumps(user_info, indent=2)}")
        
        # 4. 권한 정보 저장
        result = {
            "username": admin_user_data["username"],
            "password": admin_user_data["password"],
            "access_token": access_token,
            "created_at": datetime.utcnow().isoformat(),
            "note": "Admin test user for OMS backpressure testing"
        }
        
        # 파일에 저장
        with open("admin_test_credentials.json", "w") as f:
            json.dump(result, f, indent=2)
            
        print("\n" + "="*60)
        print("Admin Test User Created Successfully!")
        print("="*60)
        print(f"Username: {result['username']}")
        print(f"Password: {result['password']}")
        print(f"Token saved to: admin_test_credentials.json")
        print("\nUse this token for backpressure testing:")
        print(f"export ADMIN_TOKEN={access_token}")
        print("="*60)
        
        return result

async def test_admin_permissions(token: str):
    """관리자 권한 테스트"""
    print("\n테스팅 admin permissions...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # OMS에 대한 쓰기 권한 테스트
        test_data = {
            "name": "AdminTestObject",
            "description": "Testing admin write permissions",
            "properties": {}
        }
        
        resp = await client.post(
            "http://localhost:8091/api/v1/schemas/main/object-types",
            headers=headers,
            json=test_data
        )
        
        if resp.status_code in [200, 201]:
            print("✅ Admin write permissions confirmed!")
        else:
            print(f"⚠️  Write test failed: {resp.status_code}")
            print(f"Response: {resp.text}")

async def main():
    """메인 실행 함수"""
    print("Creating admin test user for OMS backpressure testing...")
    
    result = await create_admin_user()
    
    if result and result.get("access_token"):
        await test_admin_permissions(result["access_token"])
    else:
        print("Failed to create admin user")
        return 1
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))