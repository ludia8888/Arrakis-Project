#!/usr/bin/env python3
"""Test JWT validation with audit service configuration"""
import jwt
import base64
import os

# Read token from file
with open('token.txt', 'r') as f:
    token = f.read().strip()

# Decode without verification to see contents
try:
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    
    print("Token Header:")
    print(f"  Algorithm: {header.get('alg')}")
    print(f"  Type: {header.get('typ')}")
    
    print("\nToken Payload:")
    for key, value in payload.items():
        print(f"  {key}: {value}")
    
    # Now verify with audit service's configuration
    public_key_b64 = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
    
    print("\n\nVerifying with audit service configuration...")
    
    # Decode public key
    public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')
    
    # Verify the token
    try:
        verified_payload = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            audience="audit-service",
            issuer="user-service"
        )
        print("✓ Token verification PASSED!")
        
    except jwt.InvalidAudienceError as e:
        print(f"✗ Audience mismatch: {e}")
        print(f"  Token audience: {payload.get('aud')}")
        print(f"  Expected: audit-service")
        
    except jwt.InvalidIssuerError as e:
        print(f"✗ Issuer mismatch: {e}")
        print(f"  Token issuer: {payload.get('iss')}")
        print(f"  Expected: user-service")
        
    except jwt.ExpiredSignatureError:
        print("✗ Token has expired")
        
    except jwt.InvalidSignatureError:
        print("✗ Invalid signature - key mismatch")
        
    except Exception as e:
        print(f"✗ Verification failed: {type(e).__name__}: {e}")
        
except Exception as e:
    print(f"Error decoding token: {e}")