#!/usr/bin/env python3
"""Test audit authentication exactly as audit service does it"""
import requests
import base64
import jwt
import json

# Get a fresh token
user_url = "http://localhost:8080"
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
print("Got token successfully")

# Decode it without verification
unverified_header = jwt.get_unverified_header(service_token)
unverified_payload = jwt.decode(service_token, options={"verify_signature": False})

print(f"\nToken algorithm: {unverified_header.get('alg')}")
print(f"Token audience: {unverified_payload.get('aud')}")
print(f"Token issuer: {unverified_payload.get('iss')}")

# Now try to verify it as audit service would
public_key_b64 = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')

print("\nVerifying token...")
try:
    # This is what audit service does
    payload = jwt.decode(
        service_token,
        public_key_pem,
        algorithms=["RS256"],
        issuer="user-service",
        audience="audit-service"
    )
    print("✓ Token verification passed locally")
except Exception as e:
    print(f"✗ Token verification failed: {type(e).__name__}: {e}")
    exit(1)

# Now test with audit service
print("\nTesting with audit service...")
audit_event = {
    "event_type": "test_event",
    "event_category": "test",
    "user_id": "service:oms-monolith",
    "username": "oms-monolith",
    "target_type": "test_target",
    "target_id": "test123",
    "operation": "test_operation",
    "severity": "INFO"
}

response = requests.post(
    "http://localhost:8002/api/v2/events/single",
    json=audit_event,
    headers={
        "Authorization": f"Bearer {service_token}",
        "Content-Type": "application/json"
    }
)

print(f"Response status: {response.status_code}")
print(f"Response body: {response.text}")

if response.status_code != 201:
    # Let's also test the health endpoint with auth
    print("\nTesting health endpoint with auth...")
    health_response = requests.get(
        "http://localhost:8002/api/v2/events/health",
        headers={"Authorization": f"Bearer {service_token}"}
    )
    print(f"Health response: {health_response.status_code} - {health_response.text}")