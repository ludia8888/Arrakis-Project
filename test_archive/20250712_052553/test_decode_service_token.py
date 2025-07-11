#!/usr/bin/env python3
"""Decode and verify service token"""
import jwt
import json
import base64

# The token from the response
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlOm9tcy1tb25vbGl0aCIsImlhdCI6MTc1MjA1NTE4NSwiZXhwIjoxNzUyMDU4Nzg1LCJhdWQiOiJvbXMiLCJpc3MiOiJ1c2VyLXNlcnZpY2UiLCJjbGllbnRfaWQiOiJvbXMtbW9ub2xpdGgtY2xpZW50Iiwic2VydmljZV9uYW1lIjoib21zLW1vbm9saXRoIiwiaXNfc2VydmljZV9hY2NvdW50Ijp0cnVlLCJncmFudF90eXBlIjoiY2xpZW50X2NyZWRlbnRpYWxzIiwic2NvcGVzIjpbImF1ZGl0OndyaXRlIiwiYXVkaXQ6cmVhZCJdLCJwZXJtaXNzaW9ucyI6WyJhdWRpdDp3cml0ZSIsImF1ZGl0OnJlYWQiXSwidXNlcl9pZCI6InNlcnZpY2U6b21zLW1vbm9saXRoIiwidXNlcm5hbWUiOiJvbXMtbW9ub2xpdGgiLCJ0b2tlbl90eXBlIjoic2VydmljZSIsInZlcnNpb24iOiIxLjAifQ.pveWGlXnOziFSw1Fp-GM6etglKJGKdVA3R1r71vPe3p6yYteQi78Qa4aUENoE5hU2u-yb2-FX8fbjwLpF081RqtKoX6qihxbhlCIdWXGG5FyzBUVuMO0I-0YTYUgkyPs4Rmy6la_8MAC8wu5XTxKwO1d93SBM5c-3dXo0H-NjcgJvr5qIMdY9g_AhCV_JemL8_cgYVnq2wJy6cqPPqVSzXaYuBfxDhPttDTv3yVHAEkfeBrc_tuOF0cEBiGCOpKBcATrjNfzE-NKbySoypVcdCnefB4BQsfJH2HuqwPrXbVOrYK-qssTYNghYB8uKEawlIFEIroMIE2pcfX0b9AbAg"

# Public key for verification
public_key_b64 = "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF3RXluUDYzNHhraytNTWVHQWI4aAo4SmZpNlludTRGODZCeHNrb3JWc0MvRkxiTkNCUGY1ZlU3OGdQV3Y2cU1PNStBYXZnK2xBbUFOMzl3eHFzQitBCjlCNXk5OXA4V3V6YUk1NXczdHlld1g1OFQxcEQzUWNWY00zNzlvdDFLVFlPNE1sam5RcUhnYy8xc0lTQjhZSkMKSWdMajJ0d21DZ3hnVmM5djJDbExJc21LYVV1ZmFaVnUyQkpidE1wV0gzdFNLOVdSQmJoUEJxS3VieXZNQldkegpuSkIrMVo0R05JczAvSVkrMUJTMVYwNkx1amZEd01JRHBaamYwMWJMUjgrNXNJakRqTlNMbWVaU2JBSTQ0Q1VqCm1oZjB3Q2FCVGtjOU5BMTB4NlFFeGs5YTFhMUVvOUVoSGN2ZXgvRlROdTNkSkJSQW00OTlyOTUvTWF1TGdtY2gKTndJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="
public_key = base64.b64decode(public_key_b64).decode('utf-8')

print("Decoding service token...")
print("=" * 60)

# Decode without verification first to see the payload
try:
    unverified_payload = jwt.decode(token, options={"verify_signature": False})
    print("Token payload (unverified):")
    print(json.dumps(unverified_payload, indent=2))
except Exception as e:
    print(f"Error decoding: {e}")

print("\n" + "=" * 60)
print("Verifying token signature...")

# Verify with public key
try:
    verified_payload = jwt.decode(
        token, 
        public_key, 
        algorithms=["RS256"],
        audience="oms",
        issuer="user-service"
    )
    print("✓ Token signature verified successfully!")
    print("\nVerified payload:")
    print(json.dumps(verified_payload, indent=2))
except jwt.ExpiredSignatureError:
    print("✗ Token has expired")
except jwt.InvalidTokenError as e:
    print(f"✗ Token verification failed: {e}")
except Exception as e:
    print(f"✗ Error: {e}")