#!/usr/bin/env python
"""Initialize TerminusDB schema using direct document approach"""
import asyncio
import httpx
import json

async def create_oms_schema():
    """Create OMS schema using schema graph manipulation"""
    
    print("Initializing OMS Schema in TerminusDB...")
    
    async with httpx.AsyncClient() as client:
        # Method 1: Try using schema graph directly
        # TerminusDB stores schema in the schema graph
        
        # First, let's create schema documents
        schema_docs = [
            {
                "@id": "terminusdb:///schema#ObjectType",
                "@type": "sys:Class",
                "rdfs:label": {"@value": "Object Type", "@type": "xsd:string"},
                "rdfs:comment": {"@value": "Base class for object types", "@type": "xsd:string"},
                "sys:documentation": {
                    "@type": "sys:Documentation",
                    "@comment": "Defines object types in the system",
                    "@properties": {
                        "name": "Unique identifier for the object type",
                        "displayName": "Human-readable name",
                        "description": "Description of the object type"
                    }
                }
            },
            {
                "@id": "terminusdb:///schema#name",
                "@type": "sys:Property",
                "rdfs:label": {"@value": "Name", "@type": "xsd:string"},
                "rdfs:domain": "terminusdb:///schema#ObjectType",
                "rdfs:range": "xsd:string"
            },
            {
                "@id": "terminusdb:///schema#displayName",
                "@type": "sys:Property",
                "rdfs:label": {"@value": "Display Name", "@type": "xsd:string"},
                "rdfs:domain": "terminusdb:///schema#ObjectType",
                "rdfs:range": "xsd:string"
            },
            {
                "@id": "terminusdb:///schema#description",
                "@type": "sys:Property",
                "rdfs:label": {"@value": "Description", "@type": "xsd:string"},
                "rdfs:domain": "terminusdb:///schema#ObjectType",
                "rdfs:range": "xsd:string"
            }
        ]
        
        # Try to insert into schema graph
        print("\nAttempting to create schema using document insertion...")
        
        for doc in schema_docs:
            response = await client.post(
                "http://localhost:6363/api/document/admin/oms",
                json=[doc],
                auth=("admin", "root"),
                params={
                    "graph_type": "schema",
                    "author": "init_script",
                    "message": f"Add schema element: {doc['@id']}"
                }
            )
            
            print(f"Schema doc {doc['@id'].split('#')[-1]}: {response.status_code}")
            if response.status_code != 200:
                print(f"  Error: {response.text[:100]}...")
        
        # Method 2: Try simplified schema format
        print("\n\nTrying simplified schema format...")
        
        simple_schema = {
            "@context": {
                "@type": "@context",
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#"
            },
            "@graph": [
                {
                    "@id": "ObjectType",
                    "@type": "Class",
                    "@key": {"@type": "Lexical", "@fields": ["name"]},
                    "name": "xsd:string",
                    "displayName": "xsd:string",
                    "description": "xsd:string"
                },
                {
                    "@id": "Property", 
                    "@type": "Class",
                    "@key": {"@type": "Lexical", "@fields": ["name", "objectType"]},
                    "name": "xsd:string",
                    "displayName": "xsd:string",
                    "description": "xsd:string",
                    "dataType": "xsd:string",
                    "objectType": "ObjectType",
                    "required": "xsd:boolean",
                    "indexed": "xsd:boolean"
                },
                {
                    "@id": "LinkType",
                    "@type": "Class", 
                    "@key": {"@type": "Lexical", "@fields": ["name"]},
                    "name": "xsd:string",
                    "displayName": "xsd:string",
                    "description": "xsd:string",
                    "sourceObjectType": "ObjectType",
                    "targetObjectType": "ObjectType",
                    "cardinality": "xsd:string"
                }
            ]
        }
        
        # Replace entire schema
        response = await client.post(
            "http://localhost:6363/api/db/admin/oms/schema",
            json=simple_schema,
            auth=("admin", "root"),
            headers={"Content-Type": "application/json"},
            params={"author": "init", "message": "Initialize OMS schema"}
        )
        
        print(f"Schema replacement response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Schema created successfully!")
            
            # Verify
            verify_response = await client.get(
                "http://localhost:6363/api/schema/admin/oms",
                auth=("admin", "root")
            )
            
            if verify_response.status_code == 200:
                schema_data = verify_response.json()
                print("\nCurrent schema structure:")
                if isinstance(schema_data, dict):
                    for key in schema_data:
                        if key not in ["@context", "@type"]:
                            print(f"  - {key}")
        else:
            print(f"Error: {response.text}")
            
            # Last resort: Try raw WOQL
            print("\n\nTrying raw WOQL query...")
            
            woql_query = {
                "commit_info": {
                    "author": "init",
                    "message": "Create ObjectType class"
                },
                "query": {
                    "@context": {
                        "@schema": "terminusdb:///schema#"
                    },
                    "@type": "InsertDocument",
                    "document": {
                        "@id": "ObjectType",
                        "@type": "Class",
                        "name": "xsd:string"
                    },
                    "graph": "schema"
                }
            }
            
            woql_response = await client.post(
                "http://localhost:6363/api/woql/admin/oms",
                json=woql_query,
                auth=("admin", "root")
            )
            
            print(f"WOQL response: {woql_response.status_code}")
            if woql_response.status_code == 200:
                print("✅ Schema created via WOQL!")
            else:
                print(f"WOQL error: {woql_response.text[:200]}")

if __name__ == "__main__":
    asyncio.run(create_oms_schema())