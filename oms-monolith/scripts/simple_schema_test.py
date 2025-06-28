#!/usr/bin/env python
"""Simple schema test for TerminusDB"""
import asyncio
import httpx
import json

async def main():
    print("Testing TerminusDB schema creation...")
    
    # Simple schema definition
    schema = {
        "@context": {
            "@base": "terminusdb:///data/",
            "@schema": "terminusdb:///schema#",
            "@type": "Context"
        },
        "ObjectType": {
            "@type": "Class",
            "@key": {
                "@type": "Lexical",
                "@fields": ["name"]
            },
            "name": "xsd:string",
            "displayName": "xsd:string", 
            "description": "xsd:string"
        }
    }
    
    async with httpx.AsyncClient() as client:
        # Try schema update
        print("\n1. Attempting schema update...")
        response = await client.post(
            "http://localhost:6363/api/schema/admin/oms",
            json=schema,
            auth=("admin", "root"),
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Schema updated successfully!")
        else:
            print(f"Response body: {response.text}")
            
        # Check current schema
        print("\n2. Checking current schema...")
        get_response = await client.get(
            "http://localhost:6363/api/schema/admin/oms",
            auth=("admin", "root")
        )
        
        if get_response.status_code == 200:
            current_schema = get_response.json()
            print("Current schema:")
            print(json.dumps(current_schema, indent=2))
            
        # Try creating a document
        print("\n3. Testing document creation...")
        test_doc = {
            "@type": "ObjectType",
            "name": "Customer",
            "displayName": "Customer",
            "description": "Customer entity"
        }
        
        doc_response = await client.post(
            "http://localhost:6363/api/document/admin/oms",
            json=[test_doc],
            auth=("admin", "root"),
            params={"author": "test", "message": "Create Customer ObjectType"}
        )
        
        print(f"Document creation response: {doc_response.status_code}")
        if doc_response.status_code == 200:
            print("✅ Document created!")
        else:
            print(f"Error: {doc_response.text[:200]}")

if __name__ == "__main__":
    asyncio.run(main())