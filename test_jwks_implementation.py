#!/usr/bin/env python3
"""
JWKS 패턴 구현 테스트
User Service JWKS 엔드포인트와 OMS JWKS 검증 테스트
"""
import sys
import os
import asyncio
import httpx
import json
import time
from pathlib import Path

# 환경 변수 설정
os.environ.update({
    'USER_SERVICE_URL': 'http://localhost:8000',
    'OMS_SERVICE_URL': 'http://localhost:8003',
    'JWT_ISSUER': 'user-service',
    'JWT_AUDIENCE': 'oms',
    'JWT_ALGORITHMS': 'RS256',
    'ENVIRONMENT': 'development',
    'LOG_LEVEL': 'INFO'
})


async def test_user_service_jwks():
    """User Service JWKS 엔드포인트 테스트"""
    print("🔑 1. User Service JWKS 엔드포인트 테스트...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # JWKS 엔드포인트 테스트
            jwks_response = await client.get("http://localhost:8000/.well-known/jwks.json")
            
            if jwks_response.status_code == 200:
                jwks_data = jwks_response.json()
                print(f"  ✅ JWKS 엔드포인트 응답 성공")
                print(f"  📋 키 개수: {len(jwks_data.get('keys', []))}")
                
                # JWKS 형식 검증
                keys = jwks_data.get('keys', [])
                if keys:
                    key = keys[0]
                    required_fields = ['kty', 'kid', 'use', 'alg', 'n', 'e']
                    missing_fields = [field for field in required_fields if field not in key]
                    
                    if not missing_fields:
                        print(f"  ✅ JWKS 형식 검증 통과")
                        print(f"  🔑 Key ID: {key['kid']}")
                        print(f"  🔐 Algorithm: {key['alg']}")
                        return True
                    else:
                        print(f"  ❌ JWKS 형식 오류 - 누락된 필드: {missing_fields}")
                        return False
                else:
                    print(f"  ❌ JWKS에 키가 없음")
                    return False
            else:
                print(f"  ❌ JWKS 엔드포인트 실패: {jwks_response.status_code}")
                print(f"  📋 응답: {jwks_response.text}")
                return False
                
    except Exception as e:
        print(f"  ❌ JWKS 테스트 오류: {e}")
        return False


async def test_user_authentication():
    """User Service 인증 테스트"""
    print("\n🔐 2. User Service 인증 테스트...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 로그인 시도
            login_data = {
                "username": "admin",
                "password": "admin123"
            }
            
            login_response = await client.post(
                "http://localhost:8000/auth/login",
                data=login_data
            )
            
            if login_response.status_code == 200:
                auth_data = login_response.json()
                access_token = auth_data.get('access_token')
                
                if access_token:
                    print(f"  ✅ 로그인 성공")
                    print(f"  🎫 토큰 길이: {len(access_token)} chars")
                    return access_token
                else:
                    print(f"  ❌ 토큰이 응답에 없음")
                    return None
            else:
                print(f"  ❌ 로그인 실패: {login_response.status_code}")
                print(f"  📋 응답: {login_response.text}")
                return None
                
    except Exception as e:
        print(f"  ❌ 인증 테스트 오류: {e}")
        return None


async def test_oms_jwks_validation(access_token):
    """OMS JWKS 검증 테스트"""
    print("\n🔍 3. OMS JWKS 토큰 검증 테스트...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # OMS Branch API 호출
            oms_response = await client.get(
                "http://localhost:8003/api/v1/branches/",
                headers=headers
            )
            
            print(f"  📊 OMS 응답 상태: {oms_response.status_code}")
            
            if oms_response.status_code == 200:
                branches = oms_response.json()
                print(f"  ✅ OMS JWKS 검증 성공!")
                print(f"  📋 브랜치 개수: {len(branches)}")
                return True
            elif oms_response.status_code == 401:
                print(f"  ❌ OMS 인증 실패 (JWKS 검증 실패)")
                print(f"  📋 응답: {oms_response.text}")
                return False
            else:
                print(f"  ❌ OMS 호출 실패: {oms_response.status_code}")
                print(f"  📋 응답: {oms_response.text}")
                return False
                
    except Exception as e:
        print(f"  ❌ OMS 검증 테스트 오류: {e}")
        return False


async def test_jwks_key_rotation():
    """JWKS 키 회전 테스트"""
    print("\n🔄 4. JWKS 키 회전 테스트...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 키 회전 전 JWKS 조회
            jwks_before = await client.get("http://localhost:8000/.well-known/jwks.json")
            before_kid = jwks_before.json()['keys'][0]['kid']
            print(f"  🔑 회전 전 Key ID: {before_kid}")
            
            # 키 회전 실행 (실제 운영에서는 관리자 인증 필요)
            rotate_response = await client.post("http://localhost:8000/.well-known/rotate-keys")
            
            if rotate_response.status_code == 200:
                print(f"  ✅ 키 회전 성공")
                
                # 짧은 대기 후 새 JWKS 조회
                await asyncio.sleep(1)
                jwks_after = await client.get("http://localhost:8000/.well-known/jwks.json")
                after_kid = jwks_after.json()['keys'][0]['kid']
                print(f"  🔑 회전 후 Key ID: {after_kid}")
                
                if before_kid != after_kid:
                    print(f"  ✅ 키 회전 검증 성공 - Key ID 변경됨")
                    return True
                else:
                    print(f"  ❌ 키 회전 실패 - Key ID 동일함")
                    return False
            else:
                print(f"  ❌ 키 회전 실패: {rotate_response.status_code}")
                return False
                
    except Exception as e:
        print(f"  ❌ 키 회전 테스트 오류: {e}")
        return False


async def test_openid_discovery():
    """OpenID Connect Discovery 테스트"""
    print("\n🔍 5. OpenID Connect Discovery 테스트...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            discovery_response = await client.get(
                "http://localhost:8000/.well-known/openid_configuration"
            )
            
            if discovery_response.status_code == 200:
                config = discovery_response.json()
                print(f"  ✅ Discovery 엔드포인트 성공")
                print(f"  🔑 JWKS URI: {config.get('jwks_uri')}")
                print(f"  🎯 Issuer: {config.get('issuer')}")
                print(f"  🔐 지원 알고리즘: {config.get('id_token_signing_alg_values_supported')}")
                return True
            else:
                print(f"  ❌ Discovery 실패: {discovery_response.status_code}")
                return False
                
    except Exception as e:
        print(f"  ❌ Discovery 테스트 오류: {e}")
        return False


async def run_comprehensive_test():
    """포괄적인 JWKS 구현 테스트"""
    print("🎯 JWKS 패턴 구현 검증 테스트")
    print("=" * 50)
    
    results = []
    
    # 1. JWKS 엔드포인트 테스트
    jwks_test = await test_user_service_jwks()
    results.append(("JWKS 엔드포인트", jwks_test))
    
    # 2. 인증 테스트
    access_token = await test_user_authentication()
    auth_test = access_token is not None
    results.append(("User Service 인증", auth_test))
    
    # 3. JWKS 검증 테스트 (토큰이 있는 경우에만)
    if access_token:
        jwks_validation = await test_oms_jwks_validation(access_token)
        results.append(("OMS JWKS 검증", jwks_validation))
    else:
        results.append(("OMS JWKS 검증", False))
    
    # 4. 키 회전 테스트
    rotation_test = await test_jwks_key_rotation()
    results.append(("JWKS 키 회전", rotation_test))
    
    # 5. OpenID Discovery 테스트
    discovery_test = await test_openid_discovery()
    results.append(("OpenID Discovery", discovery_test))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("🎉 모든 테스트 통과! JWKS 패턴 구현 성공!")
        return True
    else:
        print("💥 일부 테스트 실패 - 추가 디버깅 필요")
        return False


if __name__ == "__main__":
    print("🚀 JWKS 패턴 구현 테스트 시작")
    print("User Service와 OMS 간 JWKS 기반 JWT 검증 테스트")
    print()
    
    success = asyncio.run(run_comprehensive_test())
    exit(0 if success else 1)