#!/usr/bin/env python3
"""
테스트 사용자 권한 설정 스크립트
IAM 스코프와 OMS 권한을 적절히 매핑하여 테스트 사용자에게 부여
"""
import requests
import json
import jwt
import os
from datetime import datetime, timedelta

# 서비스 URL
USER_SERVICE_URL = "http://localhost:8001"
OMS_SERVICE_URL = "http://localhost:8000"

# JWT 설정
JWT_SECRET = os.getenv("JWT_SECRET", "shared-jwt-secret-for-integration-testing")
JWT_ISSUER = os.getenv("JWT_ISSUER", "iam.company")

def create_admin_token():
    """관리자 토큰 생성 (테스트용)"""
    payload = {
        "sub": "admin",
        "iss": JWT_ISSUER,
        "aud": "oms",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "scope": "api:system:admin api:ontologies:admin api:schemas:admin api:branches:write api:proposals:write api:audit:read",
        "roles": ["admin"],
        "permissions": [
            "system:*:admin",
            "ontology:*:admin", 
            "schema:*:admin",
            "branch:*:write",
            "proposal:*:write",
            "audit:*:read"
        ]
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_test_user_token(username="agent", scopes=None, permissions=None):
    """테스트 사용자 토큰 생성"""
    if scopes is None:
        scopes = "api:ontologies:read api:schemas:read api:branches:read api:branches:write api:proposals:read api:proposals:write"
    
    if permissions is None:
        permissions = [
            "ontology:*:read",
            "schema:*:read", 
            "branch:*:read",
            "branch:*:write",
            "proposal:*:read",
            "proposal:*:write"
        ]
    
    payload = {
        "sub": username,
        "iss": JWT_ISSUER,
        "aud": "oms",
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
        "scope": scopes,
        "roles": ["developer"],
        "permissions": permissions
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_oms_access(token):
    """OMS 접근 테스트"""
    print("\n=== OMS 접근 테스트 ===")
    
    # 브랜치 목록 조회
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 브랜치 목록
    response = requests.get(f"{OMS_SERVICE_URL}/api/v1/branches", headers=headers)
    print(f"브랜치 목록 조회: {response.status_code}")
    if response.status_code == 200:
        branches = response.json()
        print(f"브랜치 수: {len(branches.get('branches', []))}")
    else:
        print(f"에러: {response.text}")
    
    # 2. 스키마 정보
    response = requests.get(f"{OMS_SERVICE_URL}/api/v1/schemas/main", headers=headers)
    print(f"\n스키마 정보 조회: {response.status_code}")
    if response.status_code == 200:
        schema = response.json()
        print(f"스키마 이름: {schema.get('name', 'N/A')}")
    
    # 3. Health 체크 (권한 불필요)
    response = requests.get(f"{OMS_SERVICE_URL}/api/v1/health")
    print(f"\nHealth 체크: {response.status_code}")
    
    return response.status_code == 200

def main():
    print("=== 테스트 권한 설정 ===")
    
    # 1. 관리자 토큰으로 테스트
    print("\n1. 관리자 권한 테스트")
    admin_token = create_admin_token()
    print(f"관리자 토큰 생성 완료 (길이: {len(admin_token)})")
    
    if test_oms_access(admin_token):
        print("✓ 관리자 권한으로 OMS 접근 성공")
    else:
        print("✗ 관리자 권한으로 OMS 접근 실패")
    
    # 2. 일반 사용자 토큰으로 테스트
    print("\n\n2. 일반 사용자 권한 테스트")
    user_token = create_test_user_token()
    print(f"사용자 토큰 생성 완료 (길이: {len(user_token)})")
    
    if test_oms_access(user_token):
        print("✓ 사용자 권한으로 OMS 접근 성공")
    else:
        print("✗ 사용자 권한으로 OMS 접근 실패")
    
    # 3. 토큰 디코딩 정보 출력
    print("\n\n3. 토큰 정보")
    decoded = jwt.decode(user_token, JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
    print(f"사용자: {decoded['sub']}")
    print(f"스코프: {decoded['scope']}")
    print(f"권한: {json.dumps(decoded['permissions'], indent=2)}")
    print(f"만료: {datetime.fromtimestamp(decoded['exp'])}")
    
    # 토큰을 파일로 저장 (다른 테스트에서 사용)
    with open("test_tokens.json", "w") as f:
        json.dump({
            "admin_token": admin_token,
            "user_token": user_token,
            "created_at": datetime.utcnow().isoformat()
        }, f, indent=2)
    
    print("\n✓ 토큰이 test_tokens.json에 저장되었습니다.")

if __name__ == "__main__":
    main()