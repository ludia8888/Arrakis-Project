#!/usr/bin/env python
"""
Create OMS Schema in TerminusDB using WOQL
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from database.clients.terminus_db import TerminusDBClient

async def create_oms_schema():
    """Create OMS schema using proper TerminusDB approach"""
    print("Creating OMS Schema in TerminusDB...")
    
    client = TerminusDBClient()
    await client._initialize_client()
    
    try:
        # First, let's try adding schema documents directly
        # TerminusDB prefers adding schema through document insertion with proper @type
        
        # Method 1: Direct schema replacement
        schema_update = {
            "@context": {
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#"
            },
            "@graph": [
                {
                    "@id": "ObjectType",
                    "@type": "Class",
                    "@documentation": {
                        "@comment": "Base class for all object types",
                        "@properties": {
                            "name": "Unique name of the object type",
                            "displayName": "Human-readable display name",
                            "description": "Description of the object type"
                        }
                    },
                    "name": "xsd:string",
                    "displayName": "xsd:string", 
                    "description": "xsd:string"
                },
                {
                    "@id": "Property",
                    "@type": "Class",
                    "@documentation": {
                        "@comment": "Defines properties for object types"
                    },
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
                    "@documentation": {
                        "@comment": "Defines relationships between object types"
                    },
                    "name": "xsd:string",
                    "displayName": "xsd:string",
                    "description": "xsd:string",
                    "sourceObjectType": "ObjectType",
                    "targetObjectType": "ObjectType",
                    "cardinality": "xsd:string"
                }
            ]
        }
        
        # Try to update schema
        response = await client.client.put(
            f"{client.endpoint}/api/schema/admin/oms",
            json=schema_update,
            auth=("admin", "root"),
            params={"author": "oms_setup", "message": "Create OMS schema"}
        )
        
        if response.status_code == 200:
            print("✅ Schema created successfully using PUT")
            
            # Verify by getting schema back
            verify_response = await client.client.get(
                f"{client.endpoint}/api/schema/admin/oms",
                auth=("admin", "root")
            )
            
            if verify_response.status_code == 200:
                schema = verify_response.json()
                if "@graph" in schema and len(schema["@graph"]) > 0:
                    print("✅ Schema verified - found classes:")
                    for cls in schema.get("@graph", []):
                        if "@id" in cls:
                            print(f"  - {cls['@id']}")
            
            return True
        else:
            print(f"❌ Schema update failed: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try alternative: WOQL query
            print("\nTrying WOQL approach...")
            
            woql_query = {
                "@type": "And",
                "and": [
                    {
                        "@type": "AddTriple",
                        "subject": {"@type": "Node", "node": "terminusdb:///schema#ObjectType"},
                        "predicate": {"@type": "Node", "node": "rdf:type"},
                        "object": {"@type": "Node", "node": "sys:Class"}
                    },
                    {
                        "@type": "AddTriple",
                        "subject": {"@type": "Node", "node": "terminusdb:///schema#ObjectType"},
                        "predicate": {"@type": "Node", "node": "rdfs:label"},
                        "object": {"@type": "Value", "@value": "Object Type", "@language": "en"}
                    }
                ]
            }
            
            woql_response = await client.client.post(
                f"{client.endpoint}/api/woql/admin/oms",
                json={"query": woql_query, "commit_info": {"author": "oms", "message": "Add ObjectType class"}},
                auth=("admin", "root")
            )
            
            if woql_response.status_code == 200:
                print("✅ Schema created using WOQL")
                return True
            else:
                print(f"❌ WOQL failed: {woql_response.status_code}")
                print(f"Response: {woql_response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def test_schema_creation():
    """Test if we can create documents with the schema"""
    print("\n=== Testing Document Creation ===")
    
    client = TerminusDBClient()
    await client._initialize_client()
    
    try:
        # Create a test ObjectType document
        test_doc = {
            "@type": "ObjectType",
            "@id": "ObjectType/TestType",
            "name": "TestType",
            "displayName": "Test Type",
            "description": "A test object type"
        }
        
        response = await client.client.post(
            f"{client.endpoint}/api/document/admin/oms",
            json=[test_doc],
            auth=("admin", "root"),
            params={"author": "test", "message": "Create test ObjectType"}
        )
        
        if response.status_code == 200:
            print("✅ Test document created successfully")
            
            # Query it back
            query_response = await client.client.get(
                f"{client.endpoint}/api/document/admin/oms/ObjectType/TestType",
                auth=("admin", "root")
            )
            
            if query_response.status_code == 200:
                doc = query_response.json()
                print(f"✅ Retrieved document: {doc.get('name')} - {doc.get('description')}")
            
        else:
            print(f"❌ Document creation failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        await client.close()


async def main():
    """Main entry point"""
    print("=" * 60)
    print("OMS SCHEMA SETUP")
    print("=" * 60)
    
    # Create schema
    success = await create_oms_schema()
    
    if success:
        # Test document creation
        await test_schema_creation()
    else:
        print("\n❌ Schema creation failed")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())