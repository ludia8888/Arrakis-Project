#!/usr/bin/env python3
"""Test OMS to Audit Service integration with token exchange"""
import requests
import json
from datetime import datetime

# Service URLs
oms_url = "http://localhost:8091"
audit_url = "http://localhost:8002"
user_url = "http://localhost:8080"

print("Testing OMS to Audit Service integration...")
print("=" * 60)

# First, create a test ontology operation in OMS
print("\n1. Creating ontology via OMS API...")
ontology_data = {
    "name": f"test-ontology-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "description": "Test ontology for integration testing",
    "domain": "test",
    "tags": ["test", "integration"]
}

headers = {
    "Content-Type": "application/json",
    "X-User-ID": "test-user",
    "X-User-Email": "test@example.com"
}

try:
    response = requests.post(
        f"{oms_url}/ontologies",
        json=ontology_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
    
    if response.status_code == 200:
        ontology = response.json()
        print(f"✓ Ontology created: {ontology.get('id', 'N/A')}")
    else:
        print("✗ Failed to create ontology")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# Check if audit was logged
print("\n2. Checking audit logs...")
try:
    # Query audit logs directly
    audit_response = requests.get(
        f"{audit_url}/audit/events",
        params={
            "entity_type": "ontology",
            "limit": 5
        }
    )
    
    print(f"Audit query status: {audit_response.status_code}")
    
    if audit_response.status_code == 200:
        events = audit_response.json()
        print(f"Found {len(events)} audit events")
        
        if events:
            latest_event = events[0]
            print(f"\nLatest audit event:")
            print(f"  - ID: {latest_event.get('id')}")
            print(f"  - Action: {latest_event.get('action')}")
            print(f"  - Entity: {latest_event.get('entity_type')} ({latest_event.get('entity_id')})")
            print(f"  - User: {latest_event.get('user_id')}")
            print(f"  - Service: {latest_event.get('service_name', 'N/A')}")
            print(f"  - Timestamp: {latest_event.get('timestamp')}")
    else:
        print(f"Failed to query audit logs: {audit_response.text}")
        
except Exception as e:
    print(f"Error querying audit: {type(e).__name__}: {e}")

# Test token validation endpoint
print("\n3. Testing token validation...")
try:
    # First get a token from User Service
    import base64
    client_id = "oms-monolith-client"
    client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
    
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    token_response = requests.post(
        f"{user_url}/token/exchange",
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials", "scope": "audit:write audit:read"}
    )
    
    if token_response.status_code == 200:
        token_data = token_response.json()
        access_token = token_data["access_token"]
        
        # Validate the token
        validate_response = requests.post(
            f"{user_url}/token/validate",
            data={"token": access_token}
        )
        
        print(f"Token validation status: {validate_response.status_code}")
        if validate_response.status_code == 200:
            validation_data = validate_response.json()
            print("✓ Token is valid:")
            print(f"  - Service: {validation_data.get('service_name')}")
            print(f"  - Scopes: {validation_data.get('scopes')}")
            print(f"  - Valid: {validation_data.get('valid')}")
        else:
            print("✗ Token validation failed")
    else:
        print("✗ Failed to get token")
        
except Exception as e:
    print(f"Error with token validation: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Integration test complete!")