#!/usr/bin/env python3
"""Direct JWT verification test"""
import requests
import base64
import jwt

# Get service token first
USER_SERVICE_URL = "http://localhost:8080"

print("1. Getting service token...")
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
    print(f"Failed to get token: {exchange_resp.text}")
    exit(1)

token = exchange_resp.json()["access_token"]
print(f"✅ Got token: {token[:50]}...")

# Decode without verification first
print("\n2. Token contents:")
decoded_unverified = jwt.decode(token, options={"verify_signature": False})
print(f"   Algorithm: {jwt.get_unverified_header(token)['alg']}")
print(f"   Issuer: {decoded_unverified.get('iss')}")
print(f"   Audience: {decoded_unverified.get('aud')}")
print(f"   Subject: {decoded_unverified.get('sub')}")

# Get public key
print("\n3. Testing JWT verification with public key...")
public_key_base64 = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
public_key = base64.b64decode(public_key_base64).decode('utf-8')

try:
    # Try with RS256
    decoded = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer="user-service",
        audience="audit-service"
    )
    print("✅ Token is valid with RS256!")
    print(f"   Decoded: {decoded}")
except jwt.InvalidTokenError as e:
    print(f"❌ RS256 validation failed: {e}")

# Try with different audiences
print("\n4. Testing with different audiences...")
for audience in ["audit-service", "oms", None]:
    try:
        if audience:
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer="user-service",
                audience=audience
            )
        else:
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer="user-service"
            )
        print(f"✅ Valid with audience='{audience}'")
    except jwt.InvalidAudienceError as e:
        print(f"❌ Invalid with audience='{audience}': {e}")
    except Exception as e:
        print(f"❌ Failed with audience='{audience}': {e}")

# Try with HS256 and secret
print("\n5. Testing with HS256 (wrong algorithm)...")
secret = "your_shared_secret_key_for_all_services_with_32_chars"
try:
    decoded = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        issuer="user-service",
        audience="audit-service"
    )
    print("✅ Token is valid with HS256!")
except jwt.InvalidAlgorithmError as e:
    print(f"❌ HS256 validation failed (expected): {e}")
except jwt.InvalidTokenError as e:
    print(f"❌ HS256 validation failed (expected): {e}")