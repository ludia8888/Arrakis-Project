#!/usr/bin/env python3
"""Test token validation directly in audit service environment"""
import requests
import base64
import json

# Get a token
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
print(f"Token obtained: {token[:50]}...")

# Save token to file for container testing
with open('test_token.txt', 'w') as f:
    f.write(token)

print("\nToken saved to test_token.txt")
print("\nNow run this in audit-service container:")
print("docker-compose exec audit-service python -c \"")
print("import jwt")
print("import base64")
print("with open('/tmp/test_token.txt') as f:")
print("    token = f.read().strip()")
print("public_key_b64 = 'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=='")
print("public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')")
print("try:")
print("    payload = jwt.decode(token, public_key_pem, algorithms=['RS256'], issuer='user-service', audience='audit-service', leeway=36000)")
print("    print('Token valid!')")
print("    print(f'Subject: {payload.get(\\\"sub\\\")}')")
print("except Exception as e:")
print("    print(f'Validation failed: {type(e).__name__}: {e}')")
print("\"")