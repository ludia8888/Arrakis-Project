#!/usr/bin/env python3
"""
Test TerminusDB in schemaless mode
"""
import asyncio
import httpx
import json
import base64

async def test_schemaless():
    """Test schemaless operations"""
    
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Create a schemaless database
        print("1. Creating schemaless database...")
        
        db_payload = {
            "label": "Arrakis Schemaless",
            "comment": "Schemaless database for OMS",
            "schema": False  # This should make it schemaless
        }
        
        response = await client.post(
            "http://localhost:6363/api/db/admin/arrakis_schemaless",
            headers=headers,
            json=db_payload
        )
        print(f"Create DB response: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            
        # 2. Insert document without schema
        if response.status_code == 200 or "already exists" in response.text:
            print("\n2. Inserting document into schemaless DB...")
            
            doc = {
                "@type": "TestDoc",
                "@id": "TestDoc/1",
                "name": "Test Document",
                "value": 42
            }
            
            response = await client.post(
                "http://localhost:6363/api/document/admin/arrakis_schemaless?author=test@example.com&message=Insert%20test",
                headers=headers,
                json=[doc]
            )
            print(f"Insert doc response: {response.status_code}")
            if response.status_code == 200:
                print("✅ Success! Document inserted without schema")
                print(f"Response: {response.json()}")
            else:
                print(f"❌ Error: {response.text[:300]}")

if __name__ == "__main__":
    asyncio.run(test_schemaless())