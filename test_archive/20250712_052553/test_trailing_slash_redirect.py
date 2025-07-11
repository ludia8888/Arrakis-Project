#!/usr/bin/env python3
"""
Test script to verify trailing slash redirect behavior for organizations and properties endpoints
"""
import httpx
import asyncio

OMS_URL = "http://localhost:8000"

async def test_endpoints():
    """Test organizations and properties endpoints for redirect behavior"""
    
    # Test endpoints without trailing slashes
    test_urls = [
        "/api/v1/organizations",
        "/api/v1/properties"
    ]
    
    async with httpx.AsyncClient(follow_redirects=False) as client:
        print("Testing endpoints WITHOUT trailing slashes:")
        print("-" * 60)
        
        for url in test_urls:
            try:
                response = await client.get(f"{OMS_URL}{url}")
                print(f"\nURL: {url}")
                print(f"Status Code: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status_code in [301, 302, 303, 307, 308]:
                    print(f"Redirect Location: {response.headers.get('location', 'N/A')}")
                    
            except Exception as e:
                print(f"\nURL: {url}")
                print(f"Error: {e}")
        
        print("\n" + "=" * 60 + "\n")
        print("Testing endpoints WITH trailing slashes:")
        print("-" * 60)
        
        # Test with trailing slashes
        for url in test_urls:
            url_with_slash = url + "/"
            try:
                response = await client.get(f"{OMS_URL}{url_with_slash}")
                print(f"\nURL: {url_with_slash}")
                print(f"Status Code: {response.status_code}")
                
                # Try with a dummy token to see if it gets past redirect
                headers = {"Authorization": "Bearer dummy_token"}
                response_with_auth = await client.get(f"{OMS_URL}{url_with_slash}", headers=headers)
                print(f"Status Code (with auth header): {response_with_auth.status_code}")
                
            except Exception as e:
                print(f"\nURL: {url_with_slash}")
                print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing OMS Endpoints for Trailing Slash Redirect Behavior")
    print("=" * 60)
    asyncio.run(test_endpoints())