#!/usr/bin/env python
"""
Test all schema management API endpoints
"""
import httpx
import jwt
import asyncio
import json
from datetime import datetime, timedelta

# Generate JWT token
def generate_jwt():
    secret = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="
    payload = {
        "sub": "testuser",
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

async def test_api_endpoint(client, method, url, data=None, description=""):
    """Test a single API endpoint"""
    print(f"\n{'='*60}")
    print(f"{method} {url}")
    if description:
        print(f"Description: {description}")
    
    try:
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        elif method == "PUT":
            response = await client.put(url, json=data)
        elif method == "DELETE":
            response = await client.delete(url)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ Success: {json.dumps(result, indent=2)}")
            return True, result
        else:
            print(f"❌ Error: {response.text}")
            return False, None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, None

async def test_all_apis():
    """Test all schema management APIs"""
    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    base_url = "http://localhost:8002"
    
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        print("\n" + "="*80)
        print("TESTING ALL SCHEMA MANAGEMENT APIs")
        print("="*80)
        
        # Test Object Types
        print("\n### OBJECT TYPES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/object-types", 
                              description="List all object types")
        
        success, _ = await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/object-types",
                              data={"name": "Employee", "displayName": "Employee", "description": "Employee object type"},
                              description="Create new object type")
        
        if success:
            await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/object-types/Employee",
                                  description="Get specific object type")
        
        # Test Properties
        print("\n### PROPERTIES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/object-types/Customer/properties",
                              description="List properties of Customer object type")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/object-types/Customer/properties",
                              data={
                                  "name": "email",
                                  "displayName": "Email Address",
                                  "dataType": "xsd:string",
                                  "required": True,
                                  "indexed": True
                              },
                              description="Create property for Customer")
        
        # Test Shared Properties
        print("\n### SHARED PROPERTIES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/shared-properties",
                              description="List all shared properties")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/shared-properties",
                              data={
                                  "name": "phoneNumber",
                                  "displayName": "Phone Number",
                                  "dataType": "xsd:string",
                                  "constraints": "^\\+?[1-9]\\d{1,14}$"
                              },
                              description="Create shared property")
        
        # Test Link Types
        print("\n### LINK TYPES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/link-types",
                              description="List all link types")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/link-types",
                              data={
                                  "name": "CustomerOrders",
                                  "displayName": "Customer Orders",
                                  "sourceObjectType": "Customer",
                                  "targetObjectType": "Order",
                                  "cardinality": "one-to-many"
                              },
                              description="Create link type")
        
        # Test Action Types
        print("\n### ACTION TYPES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/action-types",
                              description="List all action types")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/action-types",
                              data={
                                  "name": "CancelOrder",
                                  "displayName": "Cancel Order",
                                  "targetTypes": ["Order"],
                                  "operations": ["set:status=cancelled", "set:cancelledAt=now()"]
                              },
                              description="Create action type")
        
        # Test Interfaces
        print("\n### INTERFACES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/interfaces",
                              description="List all interfaces")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/interfaces",
                              data={
                                  "name": "Auditable",
                                  "displayName": "Auditable",
                                  "description": "Interface for auditable objects",
                                  "sharedProperties": ["createdAt", "updatedAt"]
                              },
                              description="Create interface")
        
        # Test Semantic Types
        print("\n### SEMANTIC TYPES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/semantic-types",
                              description="List all semantic types")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/semantic-types",
                              data={
                                  "name": "EmailAddress",
                                  "displayName": "Email Address",
                                  "baseType": "xsd:string",
                                  "constraints": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                                  "examples": ["user@example.com"]
                              },
                              description="Create semantic type")
        
        # Test Struct Types
        print("\n### STRUCT TYPES ###")
        await test_api_endpoint(client, "GET", f"{base_url}/api/v1/schemas/main/struct-types",
                              description="List all struct types")
        
        await test_api_endpoint(client, "POST", f"{base_url}/api/v1/schemas/main/struct-types",
                              data={
                                  "name": "Address",
                                  "displayName": "Address",
                                  "fields": [
                                      {"name": "street", "displayName": "Street", "fieldType": "xsd:string", "required": True},
                                      {"name": "city", "displayName": "City", "fieldType": "xsd:string", "required": True},
                                      {"name": "zipCode", "displayName": "Zip Code", "fieldType": "xsd:string"}
                                  ]
                              },
                              description="Create struct type")
        
        print("\n" + "="*80)
        print("ALL API TESTS COMPLETED")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(test_all_apis())
