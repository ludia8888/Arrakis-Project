#!/usr/bin/env python3
"""Test service token exchange only"""
import requests
import base64
import json

USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8002"

print("=== Service Token Exchange Test ===\n")

# Step 1: Get service token
print("1. Getting service token for OMS...")

oms_client_id = "oms-monolith-client"
oms_client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
credentials = base64.b64encode(f"{oms_client_id}:{oms_client_secret}".encode()).decode()

exchange_data = {
    "grant_type": "client_credentials",
    "audience": "audit-service",
    "scope": "audit:write audit:read"
}

headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/x-www-form-urlencoded"
}

print(f"   Client ID: {oms_client_id}")
print(f"   Audience: {exchange_data['audience']}")

exchange_resp = requests.post(
    f"{USER_SERVICE_URL}/token/exchange",
    data=exchange_data,
    headers=headers
)

if exchange_resp.status_code != 200:
    print(f"\n❌ Token exchange failed: {exchange_resp.status_code}")
    print(f"Response: {exchange_resp.text}")
    exit(1)

token_data = exchange_resp.json()
service_token = token_data["access_token"]
print(f"\n✅ Service token obtained successfully!")
print(f"   Token type: {token_data.get('token_type', 'Bearer')}")
print(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
print(f"   Token: {service_token[:50]}...")

# Step 2: Decode token to check contents
print("\n2. Decoding token to verify contents...")
try:
    import jwt
    # Decode without verification to see contents
    decoded = jwt.decode(service_token, options={"verify_signature": False})
    print("   Token contents:")
    print(f"   - Subject (sub): {decoded.get('sub')}")
    print(f"   - Issuer (iss): {decoded.get('iss')}")
    print(f"   - Audience (aud): {decoded.get('aud')}")
    print(f"   - Service Account: {decoded.get('is_service_account')}")
    print(f"   - Service Name: {decoded.get('service_name')}")
    print(f"   - Client ID: {decoded.get('client_id')}")
    print(f"   - Scopes: {decoded.get('scopes', [])}")
except Exception as e:
    print(f"   Failed to decode: {e}")

# Step 3: Check audit service JWT config
print("\n3. Checking audit service JWT configuration...")
config_resp = requests.get(f"{AUDIT_SERVICE_URL}/api/v2/events/debug-jwt-config")
if config_resp.status_code == 200:
    config = config_resp.json()
    print("   Configuration from JWTConfig:")
    print(f"   - Algorithm: {config.get('JWT_ALGORITHM')}")
    print(f"   - Issuer: {config.get('JWT_ISSUER')}")
    print(f"   - Audience: {config.get('JWT_AUDIENCE')}")
    print(f"   - Public Key: {'Present' if config.get('JWT_PUBLIC_KEY_BASE64') else 'Missing'}")
    
    # Check direct environment variables
    env_check = config.get('ENV_CHECK_DIRECT', {})
    if env_check:
        print("\n   Direct Environment Variables:")
        print(f"   - JWT_ALGORITHM: {env_check.get('JWT_ALGORITHM')}")
        print(f"   - JWT_AUDIENCE: {env_check.get('JWT_AUDIENCE')}")
        print(f"   - JWT_PUBLIC_KEY_BASE64: {'Present' if env_check.get('JWT_PUBLIC_KEY_BASE64') else 'Missing'}")

# Step 4: Test authentication with service token
print("\n4. Testing audit service authentication...")

audit_event = {
    "event_type": "service.test",
    "event_category": "system",
    "user_id": "oms-service",
    "username": "oms-service",
    "target_type": "test",
    "target_id": "auth-test",
    "operation": "verify"
}

headers = {"Authorization": f"Bearer {service_token}"}

# First try debug auth endpoint
print("\n   4a. Testing debug auth endpoint...")
debug_resp = requests.post(
    f"{AUDIT_SERVICE_URL}/api/v2/events/debug-auth",
    headers=headers
)

if debug_resp.status_code == 200:
    print("   ✅ Authentication successful!")
    user_info = debug_resp.json().get("user", {})
    print(f"   User ID: {user_info.get('user_id')}")
    print(f"   Username: {user_info.get('username')}")
    print(f"   Is Service Account: {user_info.get('is_service_account')}")
    print(f"   Service Name: {user_info.get('service_name')}")
    print(f"   Permissions: {user_info.get('permissions', [])}")
else:
    print(f"   ❌ Authentication failed: {debug_resp.status_code}")
    print(f"   Response: {debug_resp.text}")

# Now try actual audit event
print("\n   4b. Creating audit event...")
audit_resp = requests.post(
    f"{AUDIT_SERVICE_URL}/api/v2/events/single",
    json=audit_event,
    headers=headers
)

if audit_resp.status_code == 201:
    print("   ✅ Audit event created successfully!")
    print(f"   Event ID: {audit_resp.json().get('event_id')}")
else:
    print(f"   ❌ Failed to create audit event: {audit_resp.status_code}")
    print(f"   Response: {audit_resp.text}")

print("\n=== Test Complete ===")