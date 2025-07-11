#!/usr/bin/env python3
"""Test JWT validation with audit service configuration"""
import jwt
import base64
import os

# Token from test_immediate_audit.py output
token = """eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlOm9tcy1tb25vbGl0aCIsImlhdCI6MTczNjQyMDg1MCwiZXhwIjoxNzUyMDYwNDUwLCJhdWQiOiJhdWRpdC1zZXJ2aWNlIiwiaXNzIjoidXNlci1zZXJ2aWNlIiwiY2xpZW50X2lkIjoib21zLW1vbm9saXRoLWNsaWVudCIsInNlcnZpY2VfbmFtZSI6Im9tcy1tb25vbGl0aCIsImlzX3NlcnZpY2VfYWNjb3VudCI6dHJ1ZSwiZ3JhbnRfdHlwZSI6ImNsaWVudF9jcmVkZW50aWFscyIsInNjb3BlcyI6WyJhdWRpdDp3cml0ZSIsImF1ZGl0OnJlYWQiXSwicGVybWlzc2lvbnMiOlsiYXVkaXQ6d3JpdGUiLCJhdWRpdDpyZWFkIl0sInVzZXJfaWQiOiJzZXJ2aWNlOm9tcy1tb25vbGl0aCIsInVzZXJuYW1lIjoib21zLW1vbm9saXRoIiwidG9rZW5fdHlwZSI6InNlcnZpY2UiLCJ2ZXJzaW9uIjoiMS4wIn0.IwNRdE7S-SgzwrJhMG_87QiR6AWRgN4C-PNvIMOI7hJGmJRNJWxKoEJKAGUEcP4LFAI0SV6ztBa1iSkxJSdm-2lElQJKPGPNXQQrvXUw51qRh1BLOyJeJOJQTiTFqaC53KSNhddKhRpZ-fwM6fU-LqKGJH6pP6SXGC7XJ0G8C-0fJo5DT5v2Y30BXN33qNxAyONgH2n9Gya-0x-iLNdR8b3HcGdJPeJTGW3GxBzHaJ8YpQg-2N_a4JCLQjGu3lnHB1mL3n_bUiEOzSQvyT18Ay9g6D6gPfTqQxCnCn4VxXQ-Hg0jn5lQN2UQfVyQhp1mOQ8Sw_S8RvXPk4V_FWfBxQ"""

# Get the latest token from user
print("Please run test_immediate_audit.py and paste the service token here:")
print("(Press Enter twice when done)")
lines = []
while True:
    line = input()
    if line == "":
        break
    lines.append(line)
if lines:
    token = lines[0].strip()

# Decode without verification to see contents
try:
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    
    print("\nToken Header:")
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