#!/usr/bin/env python3
"""
Test minimal TerminusDB operations
"""
import asyncio
import httpx
import json
import base64

async def test_minimal():
    """Test minimal TerminusDB operations"""
    
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Just insert a document without schema
        print("1. Testing document insert without schema...")
        
        doc = {
            "@type": "TestDoc",
            "@id": "TestDoc/1",
            "name": "Test Document",
            "value": 42
        }
        
        # Try different URL formats
        urls = [
            "http://localhost:6363/api/document/admin/arrakis",
            "http://localhost:6363/api/document/admin/arrakis/main"
        ]
        
        for url in urls:
            print(f"\nTrying URL: {url}")
            
            # Method 1: Direct document with author
            response = await client.post(
                f"{url}?author=test@example.com&message=Insert%20test%20document",
                headers=headers,
                json=doc
            )
            print(f"Direct doc: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")
                
            # Method 2: Array of documents with author
            response = await client.post(
                f"{url}?author=test@example.com&message=Insert%20test%20document",
                headers=headers,
                json=[doc]
            )
            print(f"Array of docs: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")
                
            # Method 3: With instance wrapper and author
            response = await client.post(
                f"{url}?author=test@example.com&message=Insert%20test%20document",
                headers=headers,
                json={"instance": [doc]}
            )
            print(f"Instance wrapper: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")

if __name__ == "__main__":
    asyncio.run(test_minimal())