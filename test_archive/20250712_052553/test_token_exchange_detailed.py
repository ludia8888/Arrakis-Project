#!/usr/bin/env python3
"""Test token exchange with detailed debugging"""
import base64
import requests

# Service client credentials from docker-compose.yml
client_id = "oms-monolith-client"
client_secret = "syZ6etlkN7S4BgguNYpn13QTUJy5MRoPQtwfC4rDv8s"

# User Service URL
user_service_url = "http://localhost:8080"

print("Testing token exchange with detailed debugging...")
print(f"Client ID: {client_id}")
print(f"Client Secret: {client_secret[:10]}...")

# Create Basic Auth header
auth_string = f"{client_id}:{client_secret}"
auth_bytes = auth_string.encode('utf-8')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

print(f"\nAuth string: {client_id}:{client_secret[:10]}...")
print(f"Base64 encoded: {auth_b64[:20]}...")

# Test with requests library
headers = {
    "Authorization": f"Basic {auth_b64}",
    "Content-Type": "application/x-www-form-urlencoded"
}

data = {
    "grant_type": "client_credentials",
    "scope": "audit:write audit:read"
}

print("\nRequest details:")
print(f"URL: {user_service_url}/token/exchange")
print(f"Headers: {headers}")
print(f"Data: {data}")

try:
    response = requests.post(
        f"{user_service_url}/token/exchange",
        headers=headers,
        data=data
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        token_data = response.json()
        print("\nToken exchange successful!")
        print(f"Access Token: {token_data.get('access_token', 'N/A')[:50]}...")
        print(f"Token Type: {token_data.get('token_type', 'N/A')}")
        print(f"Expires In: {token_data.get('expires_in', 'N/A')} seconds")
    else:
        print("\nToken exchange failed!")
        
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")

# Also test with curl for comparison
print("\n\nCurl command for comparison:")
curl_cmd = f'''curl -X POST http://localhost:8080/token/exchange \\
  -H "Authorization: Basic {auth_b64}" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "grant_type=client_credentials&scope=audit:write+audit:read" \\
  -v'''
print(curl_cmd)