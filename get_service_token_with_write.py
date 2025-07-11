#!/usr/bin/env python3
"""
OMS 서비스 토큰 획득 (쓰기 권한 포함)
서비스간 인증을 통해 쓰기 권한을 가진 토큰을 획득합니다.
"""
import asyncio
import httpx
import json
import time
from datetime import datetime
import os
import base64

USER_SERVICE_URL = "http://localhost:8080"
OMS_URL = "http://localhost:8091"

# OMS 서비스 자격증명 (docker-compose.yml에서 가져옴)
OMS_CLIENT_ID = "oms-monolith-client"
OMS_CLIENT_SECRET = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"

async def get_service_token():
    """서비스간 인증으로 토큰 획득"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 서비스 토큰 교환 엔드포인트 시도
        print("서비스 토큰 교환 시도...")
        
        # Basic Auth 헤더 생성
        credentials = f"{OMS_CLIENT_ID}:{OMS_CLIENT_SECRET}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json"
        }
        
        # 서비스 토큰 요청
        token_data = {
            "client_id": OMS_CLIENT_ID,
            "client_secret": OMS_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "api:ontologies:write api:schemas:write api:documents:write"
        }
        
        try:
            # OAuth2 토큰 엔드포인트 시도
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/token",
                json=token_data,
                headers=headers
            )
            
            if resp.status_code == 200:
                token_resp = resp.json()
                access_token = token_resp.get("access_token")
                print("✅ 서비스 토큰 획득 성공")
                return access_token
            else:
                print(f"토큰 엔드포인트 응답: {resp.status_code}")
                print(f"응답 내용: {resp.text}")
        except Exception as e:
            print(f"토큰 엔드포인트 오류: {e}")
        
        # 2. 서비스 토큰 교환 API 시도
        print("\n서비스 토큰 교환 API 시도...")
        exchange_data = {
            "service_name": "oms-monolith",
            "client_id": OMS_CLIENT_ID,
            "client_secret": OMS_CLIENT_SECRET,
            "requested_scopes": ["api:ontologies:write", "api:schemas:write", "api:documents:write"]
        }
        
        try:
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/service-token",
                json=exchange_data
            )
            
            if resp.status_code == 200:
                token_resp = resp.json()
                access_token = token_resp.get("access_token")
                print("✅ 서비스 토큰 교환 성공")
                return access_token
            else:
                print(f"서비스 토큰 교환 응답: {resp.status_code}")
                print(f"응답 내용: {resp.text}")
        except Exception as e:
            print(f"서비스 토큰 교환 오류: {e}")
        
        # 3. 테스트 사용자로 직접 로그인 시도
        print("\n테스트 사용자 생성 및 로그인 시도...")
        
        # 테스트 사용자 생성
        test_user = {
            "username": f"oms_service_test_{int(time.time())}",
            "password": "ServiceTest123!@#",
            "email": f"oms_service_{int(time.time())}@test.com",
            "full_name": "OMS Service Test User"
        }
        
        resp = await client.post(
            f"{USER_SERVICE_URL}/auth/register",
            json=test_user
        )
        
        if resp.status_code == 201:
            print("✅ 테스트 사용자 생성 성공")
            
            # 로그인
            login_resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={
                    "username": test_user["username"],
                    "password": test_user["password"]
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
                        return complete_resp.json()["access_token"]
                else:
                    return login_data.get("access_token")
        
        return None

async def test_write_permission(token: str):
    """쓰기 권한 테스트"""
    print("\n쓰기 권한 테스트...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 스키마 생성 테스트
        test_schema = {
            "name": f"TestSchema_{int(time.time())}",
            "description": "Test schema for write permission",
            "properties": {}
        }
        
        resp = await client.post(
            f"{OMS_URL}/api/v1/schemas/main/object-types",
            headers=headers,
            json=test_schema
        )
        
        print(f"스키마 생성 응답: {resp.status_code}")
        if resp.status_code in [200, 201]:
            print("✅ 쓰기 권한 확인!")
            return True
        else:
            print(f"❌ 쓰기 권한 없음: {resp.text}")
            return False

async def main():
    """메인 실행 함수"""
    print("OMS 서비스 토큰 획득 (쓰기 권한 포함)")
    print("="*60)
    
    # 서비스 토큰 획득
    token = await get_service_token()
    
    if token:
        print(f"\n토큰 획득 성공!")
        print(f"토큰 길이: {len(token)}")
        
        # 토큰 저장
        result = {
            "access_token": token,
            "created_at": datetime.utcnow().isoformat(),
            "type": "service_token",
            "note": "OMS service token with write permissions"
        }
        
        with open("service_token_write.json", "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"\n토큰이 service_token_write.json에 저장되었습니다.")
        
        # 쓰기 권한 테스트
        has_write = await test_write_permission(token)
        
        if has_write:
            print("\n" + "="*60)
            print("성공! 쓰기 권한이 있는 토큰입니다.")
            print("백프레셔 테스트에 사용하세요:")
            print(f"export SERVICE_TOKEN={token}")
            print("="*60)
        else:
            print("\n⚠️  주의: 토큰은 획득했지만 쓰기 권한이 없습니다.")
            print("RBAC 설정을 확인하세요.")
    else:
        print("\n❌ 토큰 획득 실패")
        print("\n가능한 해결 방법:")
        print("1. User Service에 OAuth2 클라이언트 자격증명 플로우 구현")
        print("2. 서비스간 토큰 교환 API 구현")
        print("3. 관리자 계정으로 직접 로그인")

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))