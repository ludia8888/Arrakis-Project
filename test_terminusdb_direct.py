#!/usr/bin/env python3
"""
Direct TerminusDB test to debug the 400 error
"""
import asyncio
import httpx
import json
import base64

async def test_terminusdb():
    """Test TerminusDB directly"""
    
    # Create auth header
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Check database exists
        print("1. Checking if database exists...")
        response = await client.get(
            "http://localhost:6363/api/db/admin/arrakis",
            headers=headers
        )
        print(f"Database check: {response.status_code}")
        if response.status_code == 200:
            print(f"Database info: {response.json()}")
        
        # 2. Check branches
        print("\n2. Checking branches...")
        response = await client.get(
            "http://localhost:6363/api/branch/admin/arrakis",
            headers=headers
        )
        print(f"Branches response: {response.status_code}")
        if response.status_code == 200:
            print(f"Branches: {response.json()}")
        
        # 3. Try simple document insert with proper format
        print("\n3. Testing document insert...")
        
        # TerminusDB expects an array of documents
        payload = {
            "author": "test@terminusdb",
            "message": "Test document insert",
            "instance": [{
                "@type": "Test",
                "@id": "Test/1",
                "name": "Test Document"
            }]
        }
        
        response = await client.post(
            "http://localhost:6363/api/document/admin/arrakis",
            headers=headers,
            json=payload
        )
        print(f"Document insert response: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        else:
            print("Success!")
            
        # 4. Try with different payload format
        print("\n4. Testing with commit_info format...")
        payload2 = {
            "commit_info": {
                "author": "test@terminusdb",
                "message": "Test document insert"
            },
            "instance": [{
                "@type": "Test2",
                "@id": "Test2/1", 
                "name": "Test Document 2"
            }]
        }
        
        response = await client.post(
            "http://localhost:6363/api/document/admin/arrakis",
            headers=headers,
            json=payload2
        )
        print(f"Document insert v2 response: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        else:
            print("Success!")

if __name__ == "__main__":
    asyncio.run(test_terminusdb())