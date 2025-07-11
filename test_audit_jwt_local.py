#!/usr/bin/env python3
"""Test Audit Service JWT Configuration Locally"""
import os
import sys
import json

# Set environment variables as they would be in Docker
os.environ["JWT_AUDIENCE"] = "audit-service"
os.environ["JWT_ALGORITHM"] = "RS256"
os.environ["JWT_ISSUER"] = "user-service"
os.environ["JWT_PUBLIC_KEY_BASE64"] = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
os.environ["JWT_SECRET"] = "your_shared_secret_key_for_all_services_with_32_chars"
os.environ["DOCKER_CONTAINER"] = "true"  # Simulate Docker environment

# Add the audit-service directory to the path
sys.path.insert(0, os.path.abspath("audit-service"))

# Test 1: Direct environment variable access
print("Test 1: Direct Environment Variable Access")
print("-" * 50)
print(f"JWT_AUDIENCE from os.environ: {os.environ.get('JWT_AUDIENCE', 'NOT FOUND')}")
print(f"JWT_ALGORITHM from os.environ: {os.environ.get('JWT_ALGORITHM', 'NOT FOUND')}")
print(f"JWT_ISSUER from os.environ: {os.environ.get('JWT_ISSUER', 'NOT FOUND')}")
print(f"JWT_PUBLIC_KEY_BASE64 from os.environ: {os.environ.get('JWT_PUBLIC_KEY_BASE64', 'NOT FOUND')[:50]}...")
print(f"DOCKER_CONTAINER from os.environ: {os.environ.get('DOCKER_CONTAINER', 'NOT FOUND')}")

# Test 2: Import and test config
print("\nTest 2: Pydantic Settings Configuration")
print("-" * 50)
try:
    from audit_service.config import get_settings
    settings = get_settings()
    print(f"JWT_AUDIENCE from settings: {settings.JWT_AUDIENCE}")
    print(f"JWT_ALGORITHM from settings: {settings.JWT_ALGORITHM}")
    print(f"JWT_ISSUER from settings: {settings.JWT_ISSUER}")
    print(f"JWT_PUBLIC_KEY_BASE64 from settings: {settings.JWT_PUBLIC_KEY_BASE64[:50] if settings.JWT_PUBLIC_KEY_BASE64 else 'EMPTY'}...")
except Exception as e:
    print(f"Error loading settings: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Import and test JWTConfig
print("\nTest 3: JWTConfig Class")
print("-" * 50)
try:
    from utils.auth import JWTConfig
    print(f"JWT_SECRET from JWTConfig: {JWTConfig.get_jwt_secret()[:20]}...")
    print(f"JWT_ALGORITHM from JWTConfig: {JWTConfig.get_jwt_algorithm()}")
    print(f"JWT_ISSUER from JWTConfig: {JWTConfig.get_jwt_issuer()}")
    print(f"JWT_AUDIENCE from JWTConfig: {JWTConfig.get_jwt_audience()}")
    print(f"JWT_PUBLIC_KEY_BASE64 from JWTConfig: {JWTConfig.get_jwt_public_key_base64()[:50]}...")
    
    # Check verification key
    verification_key = JWTConfig.get_verification_key()
    print(f"\nVerification key type: {type(verification_key)}")
    print(f"Verification key starts with: {verification_key[:50]}...")
except Exception as e:
    print(f"Error with JWTConfig: {e}")
    import traceback
    traceback.print_exc()

# Test 4: JWT Token validation
print("\nTest 4: JWT Token Validation")
print("-" * 50)
try:
    import jwt
    import base64
    from datetime import datetime, timedelta
    
    # Create a test token with RS256
    private_key_base64 = "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2d0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktrd2dnU2xBZ0VBQW9JQkFRREFUS2MvcmZqR1NUNHcKeDRZQnZ5SHdsK0xwaWU3Z1h6b0hHeVNpdFd3TDhVdHMwSUU5L2w5VHZ5QTlhL3FvdzduNEJxK0Q2VUNZQTNmMwpER3F3SDREMEhuTDMybnhhN05vam5uRGUzSjdCZm54UFdrUGRCeFZ3emZ2MmkzVXBOZzdneVdPZENvZUJ6L1d3CmhJSHhna0lpQXVQYTNDWUtER0JWejIvWUtVc2l5WXBwUzU5cGxXN1lFbHUweWxZZmUxSXIxWkVGdUU4R29xNXYKSzh3RlozT2NrSDdWbmdZMGl6VDhoajdVRkxWWFRvdTZOOFBBd2dPbG1OL1RWc3RIejdtd2lNT00xSXVaNWxKcwpBampnSlNPYUYvVEFKb0ZPUnowMERYVEhwQVRHVDFyVnJVU2owU0VkeTk3SDhWTTI3ZDBrRkVDYmozMnYzbjh4CnE0dUNaeUUzQWdNQkFBRUNnZ0VBR1IxSnV6Ylk1cE5QNmRDbnhKaExuSitjUDl6eHFPQmhuenVoSEJaRDlMRlYKcFBIOFFjdWV5VHkzdjEzWUFFSXVYN2F4SmR5emxodzBodWJhYU5oM0g5VjVpcnVWckhoWGdFOE9pd1NzUCtBVQpQY3d2cGNacGtKc2pwNDQzY0hqc3dOaDhjb09hc1U1UmdQVmxWU25WRjVwaUJodVBaT3VRaWY4aFZTS3cwSlkyCkpxNzF6bHRNSU12TUVxL0NQRUQxQjJVQW96clZSbFVScURuY2VMUlZRMVNYTExRYkxyZytIRTIxWmJyYjFpUFAKZlpmSktoS1BIOVgydFAwZXArZTYwTHRJRlJWbGUwU0FGc0crZXBLQkRUbTBEeGw4RU40bSt3WTZjei8xMjR4eQpiZHNPSGdxVkNKSUkxR0UyaGxLMGRjaXk1anVKbE5hYzdMSFlWcEl2blFLQmdRRGUzMUFtRXZ2Y2h3Tlh6cWMyCmxJMk43NWxWeTU3VXE0U01vNzgrUkFJb0ROdGdMS3BTZnJhMjYzZ25uRE5IMTYwNmxQU2VoYncxdVM0Q2w0R0kKQTZicUh3TllJL1J0NkJmbm1TTjlySlRxVWFmQWE1OXUzZmQvbnA2V1FudlhUYWY3OWxTKzVWNFNpMnYyVGhNbwpkZjhqbUZSRXBqY1krdDZZTkdQTHBQQ2p2UUtCZ1FEYzRmelFzd1doUDZZS3ZSOFZNWkxSZ25KZ1lLVEtnMmZLCkVrT1hnUVExeGIwQ3Z1TWJERE5wQWt6VnNFSXErWmkwUWliTEpjUHNSUkVCUkJ6NTcvOWxBeDZPZWtEa0hTdjkKQWlseGFRcS94aUFKMytlRkpCSWNsejhQU2NUNFFJeXNEZ0ZJU0RpcjRzM2FiNlhDdVBXelBzeFNST2ErTnZ3NwpCQWxtK01KdUF3S0JnUURXN2FKY1pWaFA3ai95RU04K21ubjhWQUNhTlhoaGZWcWhTbFJtbHExQnRFeG03Z3YrCjdFWUdGd1JUcHBYcGhYdUFFQi9yTStzeUgvZlg5Z1dyaG1JVVMzNHRKTmRXbWtsYlJscHNtdDh0TFR2S0c3K3YKNmcwQkhKV3hNRUkvZXBzeUovYkg5V2dJR0Q0d1ZGQ3paejk2TXkrbzJHWXdCOVpjRDhIaHBKbVFQUUtCZ1FDLwpPR1ZGeDdYNEFzSWNTZDIrMjB2ZlZLN3dBTHFwRjFtaTltek5uRU9veWFiMzJZbUN3TzFBMjF6cEljNG1waTRzCjM1ZjJCcHUyejVRSkpJNXhVZlFuM3F0MWJTRUFXc0RhS0NUNHFaZEVycURONjZqaStuY3ppVHh1WDg3Rm5Cd3MKVjNPRXdBRlB6T21wVVQ2UGROQkFmUDBsdThDR3E5Tnd3KzNmMXp0N1FRS0JnUUNhcE5QMDRSM1BSVzZ5cml6dApIeDZKRXpnRmRhRVFKQmZxNzN1UCt1Z0RnOWNvdU9BWUt2S1MvdHl0bkZsa3p0SFUyM1VwcnFQZldpd1JuZFltCjVIQTRzK0RpaWNLS2E2blE4NGlZVWx6ZkluSnFPaFc3eUJQbEhwaSsvcldjazcvWm5Ca3oxQll3aWdoK1IyY1kKNCtnSEN1Qm9oejNQdStTZEpHRkJIcHA5a0E9PQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg=="
    private_key = base64.b64decode(private_key_base64).decode('utf-8')
    
    # Create token with correct audience
    payload = {
        "sub": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "roles": ["admin"],
        "permissions": ["audit:read", "audit:write"],
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iss": "user-service",
        "aud": "audit-service"  # Correct audience for audit-service
    }
    
    test_token = jwt.encode(payload, private_key, algorithm="RS256")
    print(f"Generated test token: {test_token[:50]}...")
    
    # Try to decode it using JWTConfig
    if 'JWTConfig' in globals() and 'verification_key' in locals():
        try:
            decoded = jwt.decode(
                test_token,
                verification_key,
                algorithms=["RS256"],
                issuer="user-service",
                audience="audit-service"
            )
            print("\nSuccessfully decoded token!")
            print(f"Payload: {json.dumps(decoded, indent=2, default=str)}")
        except Exception as e:
            print(f"\nError decoding token: {e}")
    else:
        print("\nSkipping token decode test (JWTConfig not available)")
        
except Exception as e:
    print(f"Error in token test: {e}")
    import traceback
    traceback.print_exc()