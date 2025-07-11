#!/usr/bin/env python3
"""Test complete authentication flow"""
import requests
import json
from datetime import datetime

# Service URLs
user_url = "http://localhost:8080"
oms_url = "http://localhost:8091"
audit_url = "http://localhost:8002"

print("Testing complete authentication flow...")
print("=" * 60)

# 1. Login as test user to get JWT token
print("\n1. Login as test user...")
login_data = {
    "username": "testuser",
    "password": "testpass123"
}

try:
    login_response = requests.post(
        f"{user_url}/auth/login",
        json=login_data  # JSON data
    )
    
    print(f"Login status: {login_response.status_code}")
    
    if login_response.status_code == 200:
        auth_data = login_response.json()
        access_token = auth_data.get("access_token")
        print(f"✓ Login successful, got access token")
        print(f"  Token type: {auth_data.get('token_type')}")
        print(f"  Expires in: {auth_data.get('expires_in')} seconds")
    else:
        print(f"✗ Login failed: {login_response.text}")
        exit(1)
        
except Exception as e:
    print(f"Error during login: {type(e).__name__}: {e}")
    exit(1)

# 2. Create ontology using the JWT token
print("\n2. Creating ontology with JWT token...")
ontology_data = {
    "name": f"test-ontology-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "description": "Test ontology for integration testing",
    "domain": "test",
    "tags": ["test", "integration"]
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}"
}

try:
    ontology_response = requests.post(
        f"{oms_url}/ontologies",
        json=ontology_data,
        headers=headers
    )
    
    print(f"Create ontology status: {ontology_response.status_code}")
    
    if ontology_response.status_code in [200, 201]:
        ontology = ontology_response.json()
        ontology_id = ontology.get('id', 'N/A')
        print(f"✓ Ontology created successfully")
        print(f"  ID: {ontology_id}")
        print(f"  Name: {ontology.get('name')}")
    else:
        print(f"✗ Failed to create ontology: {ontology_response.text}")
        
except Exception as e:
    print(f"Error creating ontology: {type(e).__name__}: {e}")

# 3. Check audit logs
print("\n3. Checking audit logs...")
try:
    # Wait a moment for audit to be processed
    import time
    time.sleep(2)
    
    audit_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    audit_response = requests.get(
        f"{audit_url}/audit/events",
        params={
            "entity_type": "ontology",
            "limit": 5
        },
        headers=audit_headers
    )
    
    print(f"Audit query status: {audit_response.status_code}")
    
    if audit_response.status_code == 200:
        events = audit_response.json()
        print(f"✓ Found {len(events)} audit events")
        
        if events:
            # Find our created ontology event
            latest_create = None
            for event in events:
                if event.get('action') == 'create' and event.get('entity_type') == 'ontology':
                    latest_create = event
                    break
                    
            if latest_create:
                print(f"\nLatest ontology creation audit:")
                print(f"  - ID: {latest_create.get('id')}")
                print(f"  - Entity ID: {latest_create.get('entity_id')}")
                print(f"  - User: {latest_create.get('user_id')}")
                print(f"  - Service: {latest_create.get('service_name', 'N/A')}")
                print(f"  - Timestamp: {latest_create.get('timestamp')}")
                print(f"  - IP: {latest_create.get('ip_address', 'N/A')}")
            else:
                print("  No recent ontology creation events found")
    else:
        print(f"✗ Failed to query audit logs: {audit_response.text}")
        
except Exception as e:
    print(f"Error querying audit: {type(e).__name__}: {e}")

# 4. Test service-to-service authentication
print("\n4. Testing service-to-service token exchange...")
import base64

client_id = "oms-monolith-client"
client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

try:
    token_response = requests.post(
        f"{user_url}/token/exchange",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials",
            "scope": "audit:write audit:read"
        }
    )
    
    print(f"Token exchange status: {token_response.status_code}")
    
    if token_response.status_code == 200:
        service_token = token_response.json()
        print(f"✓ Service token obtained successfully")
        print(f"  Token type: {service_token.get('token_type')}")
        print(f"  Service: {service_token.get('service_name')}")
        print(f"  Scopes: {service_token.get('scope')}")
    else:
        print(f"✗ Token exchange failed: {token_response.text}")
        
except Exception as e:
    print(f"Error in token exchange: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Integration test complete!")