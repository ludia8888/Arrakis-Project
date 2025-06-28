#!/usr/bin/env python
"""
Test Schema Management with TerminusDB
Tests ObjectType, Property, and LinkType creation/retrieval
"""
import asyncio
import json
from datetime import datetime
from database.clients.terminus_db import TerminusDBClient

async def setup_base_schema():
    """Create base schema structure in TerminusDB"""
    print("=== Setting up Base Schema ===")
    
    client = TerminusDBClient(
        endpoint="http://localhost:6363",
        username="admin",
        password="root"
    )
    
    await client._initialize_client()
    
    # Create schema using TerminusDB schema API
    schema = {
        "@context": {
            "@base": "terminusdb:///data/",
            "@schema": "terminusdb:///schema#"
        },
        "@graph": [
            {
                "@id": "ObjectType",
                "@type": "Class",
                "@metadata": {
                    "label": "Object Type",
                    "description": "Base class for all object types in the system"
                },
                "name": "xsd:string",
                "displayName": "xsd:string",
                "description": {"@type": "Optional", "@class": "xsd:string"}
            },
            {
                "@id": "Property",
                "@type": "Class",
                "@metadata": {
                    "label": "Property",
                    "description": "Defines properties for object types"
                },
                "name": "xsd:string",
                "displayName": "xsd:string",
                "description": {"@type": "Optional", "@class": "xsd:string"},
                "dataType": "xsd:string",
                "objectType": "ObjectType",
                "required": {"@type": "Optional", "@class": "xsd:boolean"},
                "indexed": {"@type": "Optional", "@class": "xsd:boolean"}
            },
            {
                "@id": "LinkType",
                "@type": "Class",
                "@metadata": {
                    "label": "Link Type",
                    "description": "Defines relationships between object types"
                },
                "name": "xsd:string",
                "displayName": "xsd:string",
                "description": {"@type": "Optional", "@class": "xsd:string"},
                "sourceObjectType": "ObjectType",
                "targetObjectType": "ObjectType",
                "cardinality": {"@type": "Optional", "@class": "xsd:string"}
            }
        ]
    }
    
    try:
        # Update schema
        response = await client.client.post(
            f"{client.endpoint}/api/schema/admin/oms",
            json=schema,
            auth=("admin", "root")
        )
        
        if response.status_code == 200:
            print("✅ Base schema created successfully")
            return True
        else:
            print(f"❌ Schema creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
        return False
    finally:
        await client.close()


async def test_object_type_crud():
    """Test ObjectType creation and retrieval"""
    print("\n=== Testing ObjectType CRUD ===")
    
    client = TerminusDBClient()
    await client._initialize_client()
    
    try:
        # Create test ObjectTypes
        object_types = [
            {
                "@type": "ObjectType",
                "@id": "ObjectType/Customer",
                "name": "Customer",
                "displayName": "Customer",
                "description": "Customer entity for e-commerce"
            },
            {
                "@type": "ObjectType",
                "@id": "ObjectType/Product",
                "name": "Product",
                "displayName": "Product",
                "description": "Product catalog item"
            },
            {
                "@type": "ObjectType",
                "@id": "ObjectType/Order",
                "name": "Order",
                "displayName": "Order",
                "description": "Customer order"
            }
        ]
        
        # Insert ObjectTypes
        print("Creating ObjectTypes...")
        response = await client.client.post(
            f"{client.endpoint}/api/document/admin/oms",
            json=object_types,
            auth=("admin", "root"),
            params={"author": "test_script", "message": "Create test ObjectTypes"}
        )
        
        if response.status_code == 200:
            print("✅ ObjectTypes created successfully")
        else:
            print(f"❌ Failed to create ObjectTypes: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        # Query ObjectTypes
        print("\nQuerying ObjectTypes...")
        query_response = await client.client.get(
            f"{client.endpoint}/api/document/admin/oms",
            auth=("admin", "root"),
            params={"type": "ObjectType"}
        )
        
        if query_response.status_code == 200:
            # Parse NDJSON response
            results = []
            for line in query_response.text.strip().split('\n'):
                if line:
                    results.append(json.loads(line))
            
            print(f"✅ Found {len(results)} ObjectTypes:")
            for obj in results:
                print(f"  - {obj.get('name', 'Unknown')}: {obj.get('description', '')}")
        else:
            print(f"❌ Query failed: {query_response.status_code}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


async def test_property_management():
    """Test Property creation and association with ObjectTypes"""
    print("\n=== Testing Property Management ===")
    
    client = TerminusDBClient()
    await client._initialize_client()
    
    try:
        # Create Properties for Customer ObjectType
        properties = [
            {
                "@type": "Property",
                "@id": "Property/Customer_firstName",
                "name": "firstName",
                "displayName": "First Name",
                "description": "Customer's first name",
                "dataType": "xsd:string",
                "objectType": "ObjectType/Customer",
                "required": True
            },
            {
                "@type": "Property",
                "@id": "Property/Customer_lastName",
                "name": "lastName",
                "displayName": "Last Name",
                "description": "Customer's last name",
                "dataType": "xsd:string",
                "objectType": "ObjectType/Customer",
                "required": True
            },
            {
                "@type": "Property",
                "@id": "Property/Customer_email",
                "name": "email",
                "displayName": "Email",
                "description": "Customer's email address",
                "dataType": "xsd:string",
                "objectType": "ObjectType/Customer",
                "required": True,
                "indexed": True
            },
            {
                "@type": "Property",
                "@id": "Property/Product_sku",
                "name": "sku",
                "displayName": "SKU",
                "description": "Product SKU",
                "dataType": "xsd:string",
                "objectType": "ObjectType/Product",
                "required": True,
                "indexed": True
            },
            {
                "@type": "Property",
                "@id": "Property/Product_price",
                "name": "price",
                "displayName": "Price",
                "description": "Product price",
                "dataType": "xsd:decimal",
                "objectType": "ObjectType/Product",
                "required": True
            }
        ]
        
        # Insert Properties
        print("Creating Properties...")
        response = await client.client.post(
            f"{client.endpoint}/api/document/admin/oms",
            json=properties,
            auth=("admin", "root"),
            params={"author": "test_script", "message": "Create properties"}
        )
        
        if response.status_code == 200:
            print("✅ Properties created successfully")
        else:
            print(f"❌ Failed to create Properties: {response.status_code}")
            print(f"Response: {response.text}")
            return
            
        # Query Properties by ObjectType
        print("\nQuerying Properties by ObjectType...")
        
        # Use WOQL-like query to get properties for Customer
        woql_query = {
            "query": {
                "@type": "Triple",
                "subject": {"@type": "Variable", "name": "prop"},
                "predicate": "objectType",
                "object": "ObjectType/Customer"
            }
        }
        
        # For now, use simple document query
        prop_response = await client.client.get(
            f"{client.endpoint}/api/document/admin/oms",
            auth=("admin", "root"),
            params={"type": "Property"}
        )
        
        if prop_response.status_code == 200:
            all_props = []
            for line in prop_response.text.strip().split('\n'):
                if line:
                    all_props.append(json.loads(line))
            
            # Group by ObjectType
            props_by_type = {}
            for prop in all_props:
                obj_type = prop.get('objectType', 'Unknown')
                if obj_type not in props_by_type:
                    props_by_type[obj_type] = []
                props_by_type[obj_type].append(prop)
            
            print("✅ Properties by ObjectType:")
            for obj_type, props in props_by_type.items():
                print(f"\n  {obj_type}:")
                for prop in props:
                    print(f"    - {prop['name']} ({prop['dataType']}): {prop.get('description', '')}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


async def test_link_type_management():
    """Test LinkType creation for relationships"""
    print("\n=== Testing LinkType Management ===")
    
    client = TerminusDBClient()
    await client._initialize_client()
    
    try:
        # Create LinkTypes
        link_types = [
            {
                "@type": "LinkType",
                "@id": "LinkType/CustomerOrders",
                "name": "orders",
                "displayName": "Orders",
                "description": "Orders placed by customer",
                "sourceObjectType": "ObjectType/Customer",
                "targetObjectType": "ObjectType/Order",
                "cardinality": "one-to-many"
            },
            {
                "@type": "LinkType",
                "@id": "LinkType/OrderItems",
                "name": "items",
                "displayName": "Order Items",
                "description": "Products in an order",
                "sourceObjectType": "ObjectType/Order",
                "targetObjectType": "ObjectType/Product",
                "cardinality": "many-to-many"
            },
            {
                "@type": "LinkType",
                "@id": "LinkType/ProductRelated",
                "name": "relatedProducts",
                "displayName": "Related Products",
                "description": "Products related to this product",
                "sourceObjectType": "ObjectType/Product",
                "targetObjectType": "ObjectType/Product",
                "cardinality": "many-to-many"
            }
        ]
        
        # Insert LinkTypes
        print("Creating LinkTypes...")
        response = await client.client.post(
            f"{client.endpoint}/api/document/admin/oms",
            json=link_types,
            auth=("admin", "root"),
            params={"author": "test_script", "message": "Create link types"}
        )
        
        if response.status_code == 200:
            print("✅ LinkTypes created successfully")
        else:
            print(f"❌ Failed to create LinkTypes: {response.status_code}")
            print(f"Response: {response.text}")
            return
            
        # Query all LinkTypes
        print("\nQuerying LinkTypes...")
        link_response = await client.client.get(
            f"{client.endpoint}/api/document/admin/oms",
            auth=("admin", "root"),
            params={"type": "LinkType"}
        )
        
        if link_response.status_code == 200:
            links = []
            for line in link_response.text.strip().split('\n'):
                if line:
                    links.append(json.loads(line))
            
            print(f"✅ Found {len(links)} LinkTypes:")
            for link in links:
                print(f"  - {link['name']}: {link['sourceObjectType']} -> {link['targetObjectType']} ({link.get('cardinality', 'unknown')})")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


async def test_schema_via_api():
    """Test schema operations through OMS API endpoints"""
    print("\n=== Testing Schema via OMS API ===")
    
    # Note: This requires the OMS server to be running
    # For now, we'll just show the expected API calls
    print("Expected API endpoints:")
    print("  GET  /api/v1/schemas/{branch}/object-types")
    print("  POST /api/v1/schemas/{branch}/object-types")
    print("  GET  /api/v1/schemas/{branch}/object-types/{name}/properties")
    print("  POST /api/v1/schemas/{branch}/object-types/{name}/properties")
    print("  GET  /api/v1/schemas/{branch}/link-types")
    print("  POST /api/v1/schemas/{branch}/link-types")
    print("\nThese require authentication and a running OMS server.")


async def main():
    """Run all schema management tests"""
    print("=" * 60)
    print("SCHEMA MANAGEMENT TEST SUITE")
    print("=" * 60)
    
    # Setup base schema
    success = await setup_base_schema()
    if not success:
        print("\n❌ Base schema setup failed. Exiting.")
        return
    
    # Run tests
    await test_object_type_crud()
    await test_property_management()
    await test_link_type_management()
    await test_schema_via_api()
    
    print("\n" + "=" * 60)
    print("SCHEMA MANAGEMENT TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())