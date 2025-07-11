#!/usr/bin/env python3
"""Test Audit Service with service token"""
import requests
import base64
import json
from datetime import datetime

# Service URLs
user_url = "http://localhost:8080"
audit_url = "http://localhost:8002"

print("Testing Audit Service with service token...")
print("=" * 60)

# 1. Get service token through token exchange
print("\n1. Getting service token via token exchange...")
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
        token_data = token_response.json()
        service_token = token_data["access_token"]
        print(f"✓ Service token obtained successfully")
        print(f"  Service: {token_data.get('service_name')}")
        print(f"  Scopes: {token_data.get('scope')}")
    else:
        print(f"✗ Token exchange failed: {token_response.text}")
        exit(1)
        
except Exception as e:
    print(f"Error in token exchange: {type(e).__name__}: {e}")
    exit(1)

# 2. Create an audit event using the service token
print("\n2. Creating audit event with service token...")
audit_event = {
    "entity_type": "ontology",
    "entity_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "action": "create",
    "user_id": "service:oms-monolith",
    "user_email": "oms@system.local",
    "service_name": "oms-monolith",
    "details": {
        "test": True,
        "description": "Test audit event from service token"
    }
}

headers = {
    "Authorization": f"Bearer {service_token}",
    "Content-Type": "application/json"
}

try:
    # Try the single event endpoint
    audit_response = requests.post(
        f"{audit_url}/api/v2/events/single",
        json=audit_event,
        headers=headers
    )
    
    print(f"Audit event creation status: {audit_response.status_code}")
    
    if audit_response.status_code in [200, 201]:
        result = audit_response.json()
        print(f"✓ Audit event created successfully")
        print(f"  Event ID: {result.get('event_id', 'N/A')}")
    else:
        print(f"✗ Failed to create audit event: {audit_response.text}")
        
except Exception as e:
    print(f"Error creating audit event: {type(e).__name__}: {e}")

# 3. Query audit events
print("\n3. Querying audit events...")
try:
    query_response = requests.get(
        f"{audit_url}/api/v2/events",
        params={
            "entity_type": "ontology",
            "limit": 5
        },
        headers=headers
    )
    
    print(f"Query status: {query_response.status_code}")
    
    if query_response.status_code == 200:
        events = query_response.json()
        print(f"✓ Found {len(events)} events")
        
        if events and isinstance(events, list):
            latest = events[0]
            print(f"\nLatest event:")
            print(f"  - ID: {latest.get('id')}")
            print(f"  - Action: {latest.get('action')}")
            print(f"  - Entity: {latest.get('entity_type')} ({latest.get('entity_id')})")
            print(f"  - Service: {latest.get('service_name')}")
    else:
        print(f"✗ Failed to query events: {query_response.text}")
        
except Exception as e:
    print(f"Error querying events: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Test complete!")