#!/usr/bin/env python3
"""Debug token validation issue"""
import os
import jwt
import base64
from datetime import datetime
import requests

# Get a token first
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

token = token_response.json()["access_token"]

# Decode and check timestamps
payload = jwt.decode(token, options={"verify_signature": False})
current_time = datetime.utcnow().timestamp()

print("Token Analysis:")
print(f"  Current UTC time: {datetime.utcnow()} ({int(current_time)})")
print(f"  Token iat: {datetime.fromtimestamp(payload['iat'])} ({payload['iat']})")
print(f"  Token exp: {datetime.fromtimestamp(payload['exp'])} ({payload['exp']})")
print(f"  Time diff (iat - now): {payload['iat'] - current_time:.2f} seconds")

if payload['iat'] > current_time:
    print("\n⚠️  WARNING: Token 'iat' is in the future!")
    print("  This might be causing the validation to fail.")
    print("  PyJWT may reject tokens with future 'iat' timestamps.")

# Try to decode with leeway
print("\nTrying to verify with time leeway...")
public_key_b64 = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')

try:
    # Try with leeway for clock skew
    decoded = jwt.decode(
        token,
        public_key_pem,
        algorithms=["RS256"],
        issuer="user-service",
        audience="audit-service",
        leeway=36000  # 10 hours leeway
    )
    print("✓ Verification passed with leeway")
except Exception as e:
    print(f"✗ Even with leeway, verification failed: {e}")