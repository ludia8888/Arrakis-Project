#!/usr/bin/env python3
"""
Setup simple schema that works with TerminusDB
"""
import asyncio
import httpx
import json
import base64
from urllib.parse import quote

async def setup_simple_schema():
    """Setup a minimal working schema"""
    
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Try the documented schema update endpoint format
        print("1. Testing schema update with commit info...")
        
        # Simple minimal schema
        schema_payload = {
            "@context": {
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#",
                "@type": "@context"
            },
            "Document": {
                "@type": "Class"
            },
            "ObjectType": {
                "@type": "Class"
            }
        }
        
        # URL with parameters
        author = quote("oms@arrakis")
        message = quote("Create base schema")
        url = f"http://localhost:6363/api/schema/admin/arrakis?author={author}&message={message}"
        
        response = await client.post(
            url,
            headers=headers,
            json=schema_payload
        )
        
        print(f"Schema update response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Schema created successfully!")
        else:
            print(f"Error: {response.text[:500]}")
            
        # Test inserting a document now
        print("\n2. Testing document insert...")
        doc = {
            "@type": "Document",
            "@id": "Document/test1",
            "data": "test"
        }
        
        doc_url = f"http://localhost:6363/api/document/admin/arrakis?author={author}&message={quote('Test document')}"
        response = await client.post(
            doc_url,
            headers=headers,
            json=[doc]
        )
        
        print(f"Document insert response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Document inserted successfully!")
        else:
            print(f"Error: {response.text[:500]}")

if __name__ == "__main__":
    asyncio.run(setup_simple_schema())