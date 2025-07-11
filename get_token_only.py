#!/usr/bin/env python3
"""Get token and print it"""
import requests
import base64

# Service URLs
user_url = "http://localhost:8080"

# 1. Get fresh service token
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
print(service_token)