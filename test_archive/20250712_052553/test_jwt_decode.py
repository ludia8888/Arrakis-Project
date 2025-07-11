#!/usr/bin/env python3
import os
import sys
import jwt
import base64
import json

def test_jwt_decode():
    # Read token from stdin
    token = input().strip()
    
    # Get JWT public key
    jwt_public_key_base64 = os.getenv("JWT_PUBLIC_KEY_BASE64")
    if not jwt_public_key_base64:
        print("ERROR: JWT_PUBLIC_KEY_BASE64 not set")
        return
        
    # Decode base64
    try:
        public_key = base64.b64decode(jwt_public_key_base64).decode('utf-8')
        print(f"Public key decoded successfully")
        print(f"First 100 chars: {public_key[:100]}")
    except Exception as e:
        print(f"ERROR decoding base64: {e}")
        return
        
    # Get unverified header
    try:
        header = jwt.get_unverified_header(token)
        print(f"Token header: {json.dumps(header, indent=2)}")
    except Exception as e:
        print(f"ERROR getting header: {e}")
        return
        
    # Try to decode
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer="user-service",
            audience="oms",
            options={"verify_exp": False}  # Ignore expiration for testing
        )
        print(f"SUCCESS! Payload: {json.dumps(payload, indent=2)}")
    except jwt.InvalidSignatureError as e:
        print(f"ERROR: Invalid signature - {e}")
    except jwt.DecodeError as e:
        print(f"ERROR: Decode error - {e}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jwt_decode()