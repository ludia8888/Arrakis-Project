#!/usr/bin/env python3
"""Create a test user for JWT testing"""
import requests
import json

USER_SERVICE_URL = "http://localhost:8080"

# Simple test user data
user_data = {
    "username": "jwttest",
    "email": "jwttest@example.com",
    "password": "Test123!",
    "full_name": "JWT Test User"
}

print("Creating test user...")
print(f"Username: {user_data['username']}")
print(f"Password: {user_data['password']}")

# Register user
resp = requests.post(f"{USER_SERVICE_URL}/auth/register", json=user_data)
print(f"\nResponse status: {resp.status_code}")
print(f"Response: {resp.text}")

if resp.status_code in [200, 201]:
    print("\n✅ User created successfully!")
    
    # Try to login
    print("\nTrying to login...")
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }
    
    login_resp = requests.post(f"{USER_SERVICE_URL}/auth/login", json=login_data)
    print(f"Login response: {login_resp.status_code}")
    if login_resp.status_code == 200:
        token = login_resp.json().get("access_token", "")
        print(f"✅ Login successful!")
        print(f"Token: {token[:50]}...")
    else:
        print(f"❌ Login failed: {login_resp.text}")
else:
    print(f"\n❌ User creation failed!")