#!/usr/bin/env python3
"""
Fix TerminusDB integration by setting up proper schemas
"""
import asyncio
import httpx
import json
import base64

async def setup_base_schemas():
    """Setup base schemas in TerminusDB"""
    
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. First create/ensure database exists
        print("1. Ensuring database exists...")
        response = await client.post(
            "http://localhost:6363/api/db/admin/arrakis",
            headers=headers,
            json={"label": "Arrakis Database", "comment": "OMS Database"}
        )
        if response.status_code == 200:
            print("✅ Database created")
        elif "already exists" in response.text:
            print("✅ Database already exists")
        else:
            print(f"❌ Failed to create database: {response.text}")
            return
            
        # 2. Get current schema
        print("\n2. Getting current schema...")
        response = await client.get(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers
        )
        current_schema = response.json() if response.status_code == 200 else {"@context": {}, "@graph": []}
        
        # 3. Create base schema with OMS types
        print("\n3. Creating OMS schema types...")
        
        # Define our schema types
        schema_classes = [
            {
                "@id": "ObjectType",
                "@type": "Class",
                "@key": {"@type": "Lexical", "@fields": ["name"]},
                "name": "xsd:string",
                "displayName": {"@type": "Optional", "@class": "xsd:string"},
                "description": {"@type": "Optional", "@class": "xsd:string"},
                "createdBy": "xsd:string",
                "createdAt": "xsd:dateTime",
                "modifiedBy": "xsd:string",
                "modifiedAt": "xsd:dateTime",
                "versionHash": "xsd:string",
                "isActive": "xsd:boolean"
            },
            {
                "@id": "ObjectTypeMetadata",
                "@type": "Class",
                "@key": {"@type": "Lexical", "@fields": ["name"]},
                "name": "xsd:string",
                "displayName": {"@type": "Optional", "@class": "xsd:string"},
                "description": {"@type": "Optional", "@class": "xsd:string"},
                "createdBy": "xsd:string",
                "createdAt": "xsd:dateTime",
                "modifiedBy": "xsd:string",
                "modifiedAt": "xsd:dateTime",
                "versionHash": "xsd:string",
                "properties": {"@type": "List", "@class": "xsd:string"},
                "isActive": "xsd:boolean",
                "status": {"@type": "Optional", "@class": "xsd:string"},
                "deletedBy": {"@type": "Optional", "@class": "xsd:string"},
                "deletedAt": {"@type": "Optional", "@class": "xsd:dateTime"}
            },
            {
                "@id": "Document",  
                "@type": "Class",
                "@key": {"@type": "Lexical", "@fields": ["id"]},
                "id": "xsd:string",
                "name": "xsd:string",
                "object_type": "xsd:string",
                "branch": "xsd:string",
                "description": {"@type": "Optional", "@class": "xsd:string"},
                "metadata": {"@type": "Optional", "@class": "xsd:string"},
                "tags": {"@type": "List", "@class": "xsd:string"},
                "created_by": "xsd:string",
                "created_at": "xsd:dateTime",
                "modified_by": "xsd:string",
                "modified_at": "xsd:dateTime",
                "version_hash": "xsd:string",
                "is_active": "xsd:boolean"
            },
            {
                "@id": "Branch",
                "@type": "Class", 
                "@key": {"@type": "Lexical", "@fields": ["name"]},
                "id": "xsd:string",
                "name": "xsd:string",
                "displayName": "xsd:string",
                "parentBranch": {"@type": "Optional", "@class": "xsd:string"},
                "createdAt": "xsd:dateTime",
                "createdBy": "xsd:string",
                "modifiedAt": "xsd:dateTime",
                "modifiedBy": "xsd:string",
                "isProtected": "xsd:boolean",
                "isActive": "xsd:boolean",
                "versionHash": "xsd:string",
                "description": {"@type": "Optional", "@class": "xsd:string"}
            }
        ]
        
        # Update schema
        new_schema = {
            "@context": current_schema.get("@context", {
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#",
                "@type": "Context"
            }),
            "@graph": schema_classes
        }
        
        # First try direct post
        response = await client.post(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers,
            json=new_schema
        )
        
        if response.status_code == 200:
            print("✅ Schema created successfully!")
        else:
            print(f"❌ Failed to create schema: {response.status_code}")
            print(f"Error: {response.text[:500]}")
            
            # Try with replace
            print("\n4. Trying schema replace...")
            response = await client.put(
                "http://localhost:6363/api/schema/admin/arrakis",
                headers=headers,
                json=new_schema
            )
            
            if response.status_code == 200:
                print("✅ Schema replaced successfully!")
            else:
                print(f"❌ Failed to replace schema: {response.status_code}")
                print(f"Error: {response.text[:500]}")
        
        # 5. Verify schema
        print("\n5. Verifying schema...")
        response = await client.get(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers
        )
        if response.status_code == 200:
            schema = response.json()
            if "@graph" in schema:
                print(f"✅ Schema has {len(schema['@graph'])} classes")
                for cls in schema["@graph"]:
                    if "@id" in cls:
                        print(f"  - {cls['@id']}")

if __name__ == "__main__":
    asyncio.run(setup_base_schemas())