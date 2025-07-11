#!/usr/bin/env python3
"""
Complete JWT Authentication Test
Tests the full flow of JWT authentication between services
"""
import requests
import json
import base64
import time
from datetime import datetime

# Service URLs
USER_SERVICE_URL = "http://localhost:8080"
OMS_SERVICE_URL = "http://localhost:8091"
AUDIT_SERVICE_URL = "http://localhost:8002"

def test_jwt_authentication():
    """Test complete JWT authentication flow"""
    
    print("=" * 80)
    print("JWT Authentication Complete Test")
    print("=" * 80)
    
    # Step 1: Create test user and login
    print("\n1. Creating test user and logging in...")
    
    # Register user
    user_data = {
        "username": f"test_user_{int(time.time())}",
        "email": f"test_{int(time.time())}@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }
    
    register_resp = requests.post(f"{USER_SERVICE_URL}/auth/register", json=user_data)
    if register_resp.status_code not in [200, 201]:
        print(f"❌ Failed to register user: {register_resp.status_code}")
        print(f"Response: {register_resp.text}")
        return
    print("✅ User registered successfully")
    
    # Login to get user token
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }
    
    login_resp = requests.post(f"{USER_SERVICE_URL}/auth/login", data=login_data)
    if login_resp.status_code != 200:
        print(f"❌ Failed to login: {login_resp.status_code}")
        print(f"Response: {login_resp.text}")
        return
    
    user_token = login_resp.json()["access_token"]
    print(f"✅ User logged in successfully")
    print(f"   Token (first 50 chars): {user_token[:50]}...")
    
    # Step 2: Test OMS service token exchange
    print("\n2. Testing OMS service token exchange...")
    
    # OMS client credentials
    oms_client_id = "oms-monolith-client"
    oms_client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
    
    # Create Basic Auth header
    credentials = base64.b64encode(f"{oms_client_id}:{oms_client_secret}".encode()).decode()
    
    # Exchange for service token
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
        print(f"❌ Failed to exchange token: {exchange_resp.status_code}")
        print(f"Response: {exchange_resp.text}")
        return
    
    service_token = exchange_resp.json()["access_token"]
    print(f"✅ Service token obtained successfully")
    print(f"   Token (first 50 chars): {service_token[:50]}...")
    
    # Step 3: Test audit service authentication
    print("\n3. Testing audit service authentication...")
    
    # First check JWT config
    print("\n   3a. Checking JWT configuration...")
    config_resp = requests.get(f"{AUDIT_SERVICE_URL}/api/v2/events/debug-jwt-config")
    if config_resp.status_code == 200:
        config = config_resp.json()
        print("   JWT Configuration:")
        print(f"     - Algorithm: {config.get('JWT_ALGORITHM')}")
        print(f"     - Issuer: {config.get('JWT_ISSUER')}")
        print(f"     - Audience: {config.get('JWT_AUDIENCE')}")
        print(f"     - Public Key: {'Present' if config.get('JWT_PUBLIC_KEY_BASE64') else 'Missing'}")
        print(f"     - Environment: {config.get('ENVIRONMENT')}")
    
    # Test with service token
    print("\n   3b. Testing with service token...")
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
        print("✅ Audit event created successfully with service token!")
        print(f"   Event ID: {audit_resp.json().get('event_id')}")
    else:
        print(f"❌ Failed to create audit event: {audit_resp.status_code}")
        print(f"Response: {audit_resp.text}")
        
        # Try debug endpoint
        print("\n   Testing debug auth endpoint...")
        debug_resp = requests.post(
            f"{AUDIT_SERVICE_URL}/api/v2/events/debug-auth",
            headers=headers
        )
        if debug_resp.status_code == 200:
            print(f"Debug auth response: {json.dumps(debug_resp.json(), indent=2)}")
        else:
            print(f"Debug auth failed: {debug_resp.status_code}")
            print(f"Response: {debug_resp.text}")
    
    # Step 4: Test with user token
    print("\n4. Testing with user token...")
    headers = {"Authorization": f"Bearer {user_token}"}
    
    audit_event["user_id"] = "user-test"
    audit_event["username"] = user_data["username"]
    
    audit_resp = requests.post(
        f"{AUDIT_SERVICE_URL}/api/v2/events/single",
        json=audit_event,
        headers=headers
    )
    
    if audit_resp.status_code == 201:
        print("✅ Audit event created successfully with user token!")
        print(f"   Event ID: {audit_resp.json().get('event_id')}")
    else:
        print(f"❌ Failed with user token: {audit_resp.status_code}")
        print(f"Response: {audit_resp.text}")
    
    # Step 5: Test OMS to Audit Service integration
    print("\n5. Testing OMS to Audit Service integration...")
    
    # Create a branch in OMS (which should trigger audit event)
    branch_data = {
        "branch_id": f"test-branch-{int(time.time())}",
        "description": "Test branch for JWT auth"
    }
    
    headers = {"Authorization": f"Bearer {user_token}"}
    
    branch_resp = requests.post(
        f"{OMS_SERVICE_URL}/api/v1/branches",
        json=branch_data,
        headers=headers
    )
    
    if branch_resp.status_code in [200, 201]:
        print("✅ Branch created in OMS successfully")
        print("   This should have triggered an audit event")
    else:
        print(f"❌ Failed to create branch: {branch_resp.status_code}")
        print(f"Response: {branch_resp.text}")
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    test_jwt_authentication()