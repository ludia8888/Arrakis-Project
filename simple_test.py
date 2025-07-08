#\!/usr/bin/env python3
"""
간단한 통합 테스트
"""
import asyncio
import httpx
import json

async def main():
    print("=== 간단한 통합 테스트 시작 ===\n")
    
    # 1. 서비스 상태 확인
    print("1. 서비스 상태 확인")
    services = [
        ("NGINX Gateway", "http://localhost"),
    ]
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for name, url in services:
            try:
                # docs 엔드포인트로 확인
                resp = await client.get(f"{url}/docs", timeout=5.0)
                if resp.status_code in [200, 404, 401]:
                    print(f"✓ {name}: Running")
                else:
                    print(f"✗ {name}: Status {resp.status_code}")
            except Exception as e:
                print(f"✗ {name}: {e}")
    
    print("\n2. User Service 로그인 테스트")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 로그인 시도
        resp = await client.post(
            "http://localhost/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        print(f"   로그인 응답: {resp.status_code}")
        if resp.status_code == 200:
            challenge = resp.json().get("challenge_token")
            print(f"   Challenge token 받음: {challenge[:20]}...")
            
            # 로그인 완료
            resp = await client.post(
                "http://localhost/auth/login/complete",
                json={"challenge_token": challenge, "mfa_code": "000000"}
            )
            print(f"   로그인 완료: {resp.status_code}")
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                print(f"   JWT 토큰 받음: {token[:50]}...")
                
                # 3. OMS API 호출
                print("\n3. OMS API 호출 테스트")
                headers = {"Authorization": f"Bearer {token}"}
                
                # 브랜치 목록 조회
                resp = await client.get(
                    "http://localhost/api/v1/branches",
                    headers=headers
                )
                print(f"   브랜치 목록 조회: {resp.status_code}")
                if resp.status_code == 200:
                    print(f"   브랜치 개수: {len(resp.json())}")
                elif resp.status_code == 401:
                    print("   인증 실패 - JWT 토큰이 거부됨")
                elif resp.status_code == 403:
                    print("   권한 부족")
                
                # 4. Health check OMS
                print("\n4. OMS Health Check")
                resp = await client.get(
                    "http://localhost/api/v1/health",
                    headers=headers
                )
                print(f"   Health check: {resp.status_code}")
                if resp.status_code == 200:
                    health = resp.json()
                    print(f"   Status: {health}")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    asyncio.run(main())