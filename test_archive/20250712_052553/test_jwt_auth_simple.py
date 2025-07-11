#!/usr/bin/env python3
"""
Simple JWT Authentication Test
"""
import requests
import json
import base64

# Service URLs
USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8002"

def test_jwt_auth():
    print("=== JWT Authentication Test ===\n")
    
    # Step 1: Login with existing user (created earlier)
    print("1. Login with existing user...")
    login_data = {
        "username": "admin",
        "password": "admin123!"  # common default password
    }
    
    login_resp = requests.post(f"{USER_SERVICE_URL}/auth/login", json=login_data)
    if login_resp.status_code != 200:
        print(f"❌ Login failed: {login_resp.status_code}")
        print(f"Response: {login_resp.text}")
        return
    
    user_token = login_resp.json()["access_token"]
    print(f"✅ Login successful")
    print(f"   Token: {user_token[:50]}...")
    
    # Step 2: Get service token for OMS
    print("\n2. Getting service token...")
    
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
    
    exchange_resp = requests.post(
        f"{USER_SERVICE_URL}/token/exchange",
        data=exchange_data,
        headers=headers
    )
    
    if exchange_resp.status_code != 200:
        print(f"❌ Token exchange failed: {exchange_resp.status_code}")
        print(f"Response: {exchange_resp.text}")
        return
    
    service_token = exchange_resp.json()["access_token"]
    print(f"✅ Service token obtained")
    print(f"   Token: {service_token[:50]}...")
    
    # Step 3: Check audit service JWT config
    print("\n3. Checking audit service JWT config...")
    config_resp = requests.get(f"{AUDIT_SERVICE_URL}/api/v2/events/debug-jwt-config")
    if config_resp.status_code == 200:
        config = config_resp.json()
        print("   JWT Configuration:")
        print(f"   - Algorithm: {config.get('JWT_ALGORITHM')}")
        print(f"   - Issuer: {config.get('JWT_ISSUER')}")
        print(f"   - Audience: {config.get('JWT_AUDIENCE')}")
        print(f"   - Public Key: {'Present' if config.get('JWT_PUBLIC_KEY_BASE64') else 'Missing'}")
        
        # Check environment variables
        env_check = config.get('ENV_CHECK_DIRECT', {})
        print("\n   Environment Variables:")
        print(f"   - JWT_ALGORITHM: {env_check.get('JWT_ALGORITHM')}")
        print(f"   - JWT_AUDIENCE: {env_check.get('JWT_AUDIENCE')}")
        print(f"   - JWT_PUBLIC_KEY_BASE64: {'Present' if env_check.get('JWT_PUBLIC_KEY_BASE64') else 'Missing'}")
    
    # Step 4: Test audit service with service token
    print("\n4. Testing audit service with service token...")
    
    audit_event = {
        "event_type": "test.authentication",
        "event_category": "system",
        "user_id": "service-test",
        "username": "oms-service",
        "target_type": "authentication",
        "target_id": "jwt-test",
        "operation": "test"
    }
    
    headers = {"Authorization": f"Bearer {service_token}"}
    
    audit_resp = requests.post(
        f"{AUDIT_SERVICE_URL}/api/v2/events/single",
        json=audit_event,
        headers=headers
    )
    
    if audit_resp.status_code == 201:
        print("✅ Audit event created successfully!")
        print(f"   Event ID: {audit_resp.json().get('event_id')}")
    else:
        print(f"❌ Failed: {audit_resp.status_code}")
        print(f"Response: {audit_resp.text}")
        
        # Debug auth
        print("\n   Debugging authentication...")
        debug_resp = requests.post(
            f"{AUDIT_SERVICE_URL}/api/v2/events/debug-auth",
            headers=headers
        )
        if debug_resp.status_code == 200:
            print(f"   User info: {json.dumps(debug_resp.json(), indent=2)}")
        else:
            print(f"   Debug failed: {debug_resp.status_code}")
            print(f"   Response: {debug_resp.text}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_jwt_auth()