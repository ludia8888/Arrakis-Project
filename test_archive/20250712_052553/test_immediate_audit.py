#!/usr/bin/env python3
"""Get fresh token and immediately test audit"""
import requests
import base64
import json
from datetime import datetime

# Service URLs
user_url = "http://localhost:8080"
audit_url = "http://localhost:8002"

print("Getting fresh token and testing immediately...")

# 1. Get fresh service token
client_id = "oms-monolith-client"
client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"
auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

token_response = requests.post(
    f"{user_url}/token/exchange",
    headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "grant_type": "client_credentials",
        "scope": "audit:write audit:read",
        "audience": "audit-service"
    }
)

if token_response.status_code != 200:
    print(f"Failed to get token: {token_response.text}")
    exit(1)

service_token = token_response.json()["access_token"]
print(f"Got fresh token")

# 2. Immediately test with audit service
import jwt
payload = jwt.decode(service_token, options={"verify_signature": False})
print(f"\nToken payload:")
print(f"  - Subject: {payload.get('sub')}")
print(f"  - Issuer: {payload.get('iss')}")
print(f"  - Audience: {payload.get('aud')}")
print(f"  - Algorithm: {jwt.get_unverified_header(service_token).get('alg')}")
print(f"  - Is Service Account: {payload.get('is_service_account')}")
print(f"  - Expires: {payload.get('exp')}")

# 3. Create audit event
audit_event = {
    "entity_type": "ontology",
    "entity_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "action": "create",
    "user_id": "service:oms-monolith",
    "user_email": "oms@system.local",
    "service_name": "oms-monolith",
    "details": {"test": True}
}

headers = {
    "Authorization": f"Bearer {service_token}",
    "Content-Type": "application/json"
}

print(f"\nTesting audit service...")
audit_response = requests.post(
    f"{audit_url}/api/v2/events/single",
    json=audit_event,
    headers=headers
)

print(f"Response: {audit_response.status_code}")
print(f"Body: {audit_response.text}")