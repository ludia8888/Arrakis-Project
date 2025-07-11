#!/usr/bin/env python3
"""
Test environment variable loading in audit service
"""
import os
import sys

# Set test environment variables
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "RS256"
os.environ["JWT_ISSUER"] = "user-service"
os.environ["JWT_AUDIENCE"] = "oms"
os.environ["JWT_PUBLIC_KEY_BASE64"] = "test-public-key-base64"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:password@localhost/audit_db"

# Add audit_service to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Testing Environment Variable Loading ===")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path[:3]}...")

# Test 1: Direct environment access
print("\n1. Direct os.environ access:")
for key in ["JWT_SECRET", "JWT_ALGORITHM", "JWT_ISSUER", "JWT_AUDIENCE", "JWT_PUBLIC_KEY_BASE64"]:
    print(f"  {key}: {os.environ.get(key, 'NOT_FOUND')}")

# Test 2: Settings loading
print("\n2. Testing Settings class:")
try:
    from audit_service.config import Settings, get_settings
    settings = get_settings()
    print(f"  JWT_SECRET: {settings.JWT_SECRET[:20]}...")
    print(f"  JWT_ALGORITHM: {settings.JWT_ALGORITHM}")
    print(f"  JWT_ISSUER: {settings.JWT_ISSUER}")
    print(f"  JWT_AUDIENCE: {settings.JWT_AUDIENCE}")
    print(f"  JWT_PUBLIC_KEY_BASE64: {settings.JWT_PUBLIC_KEY_BASE64[:20] if settings.JWT_PUBLIC_KEY_BASE64 else 'None'}...")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 3: LazySettings
print("\n3. Testing LazySettings:")
try:
    from audit_service.config import settings as lazy_settings
    print(f"  Type: {type(lazy_settings)}")
    print(f"  JWT_SECRET: {lazy_settings.JWT_SECRET[:20]}...")
    print(f"  JWT_ALGORITHM: {lazy_settings.JWT_ALGORITHM}")
    print(f"  get() method: {lazy_settings.get('JWT_ISSUER', 'default')}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 4: JWTConfig
print("\n4. Testing JWTConfig:")
try:
    from utils.auth import JWTConfig
    print(f"  get_jwt_secret(): {JWTConfig.get_jwt_secret()[:20]}...")
    print(f"  get_jwt_algorithm(): {JWTConfig.get_jwt_algorithm()}")
    print(f"  get_jwt_issuer(): {JWTConfig.get_jwt_issuer()}")
    print(f"  get_jwt_audience(): {JWTConfig.get_jwt_audience()}")
    print(f"  get_jwt_public_key_base64(): {JWTConfig.get_jwt_public_key_base64()[:20] if JWTConfig.get_jwt_public_key_base64() else 'None'}...")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Test Complete ===")