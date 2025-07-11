#!/usr/bin/env python3
"""
서비스 클라이언트 설정 스크립트
토큰 교환을 위한 클라이언트 자격증명 생성
"""
import secrets
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_client_credentials(service_name: str):
    """서비스 클라이언트 자격증명 생성"""
    client_secret = secrets.token_urlsafe(32)
    client_secret_hash = pwd_context.hash(client_secret)
    
    print(f"\n=== {service_name} 클라이언트 자격증명 ===")
    print(f"Client Secret (평문 - 환경변수용): {client_secret}")
    print(f"Client Secret Hash (DB 저장용): {client_secret_hash}")
    
    return client_secret, client_secret_hash

# 각 서비스별 자격증명 생성
services = [
    ("oms-monolith", "oms-monolith-client"),
    ("audit-service", "audit-service-client")
]

print("서비스 클라이언트 자격증명 생성")
print("=" * 60)

credentials = {}
for service_name, client_id in services:
    secret, hash_val = generate_client_credentials(service_name)
    credentials[service_name] = {
        "client_id": client_id,
        "client_secret": secret,
        "client_secret_hash": hash_val
    }

# Docker Compose 환경 변수 설정
print("\n\n=== Docker Compose 환경 변수 설정 ===")
print("docker-compose.yml에 추가할 환경 변수:")
print("\noms-monolith:")
print(f"  OMS_CLIENT_ID: {credentials['oms-monolith']['client_id']}")
print(f"  OMS_CLIENT_SECRET: {credentials['oms-monolith']['client_secret']}")

print("\naudit-service:")
print(f"  AUDIT_CLIENT_ID: {credentials['audit-service']['client_id']}")
print(f"  AUDIT_CLIENT_SECRET: {credentials['audit-service']['client_secret']}")

# SQL 업데이트 문
print("\n\n=== 데이터베이스 업데이트 SQL ===")
print("User Service 데이터베이스에서 실행:")
for service_name, creds in credentials.items():
    print(f"""
UPDATE service_clients 
SET client_secret_hash = '{creds['client_secret_hash']}'
WHERE client_id = '{creds['client_id']}';
""")

print("\n주의: 생성된 client_secret은 안전하게 보관하고, 프로덕션 환경에서는 더 강력한 비밀키를 사용하세요.")