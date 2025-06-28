#!/usr/bin/env python
"""Test Schema Management API with proper authentication"""
import asyncio
import httpx
import jwt
import json
from datetime import datetime, timezone, timedelta

JWT_SECRET = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="

def generate_jwt_token():
    """Generate a valid JWT token with all required fields"""
    payload = {
        'sub': 'test-user',
        'user_id': '123',
        'username': 'testuser',
        'email': 'test@example.com',
        'exp': datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

async def test_schema_api():
    """Test schema management through OMS API"""
    print("=== Schema Management API Test ===\n")
    
    token = generate_jwt_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Get current ObjectTypes
        print("1. Getting current ObjectTypes...")
        response = await client.get(
            'http://localhost:8002/api/v1/schemas/main/object-types',
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data.get('objectTypes', []))} ObjectTypes:")
            for obj in data.get('objectTypes', []):
                print(f"  - {obj.get('name', 'Unknown')}: {obj.get('description', '')}")
        else:
            print(f"Response: {response.text}")
        
        # 2. Create new ObjectType
        print("\n2. Creating Invoice ObjectType...")
        invoice_data = {
            "name": "Invoice",
            "displayName": "Invoice", 
            "description": "Invoice entity for billing"
        }
        
        create_response = await client.post(
            'http://localhost:8002/api/v1/schemas/main/object-types',
            headers=headers,
            json=invoice_data
        )
        
        print(f"Status: {create_response.status_code}")
        if create_response.status_code == 200:
            print("✅ Invoice ObjectType created successfully!")
            result = create_response.json()
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print(f"Error: {create_response.text}")
        
        # 3. Verify creation
        print("\n3. Verifying creation...")
        verify_response = await client.get(
            'http://localhost:8002/api/v1/schemas/main/object-types',
            headers=headers
        )
        
        if verify_response.status_code == 200:
            data = verify_response.json()
            object_types = data.get('objectTypes', [])
            invoice_found = any(obj.get('name') == 'Invoice' for obj in object_types)
            
            if invoice_found:
                print("✅ Invoice ObjectType verified in database!")
            else:
                print("❌ Invoice ObjectType not found")
        
        # 4. Test direct TerminusDB query
        print("\n4. Direct TerminusDB verification...")
        direct_response = await client.get(
            'http://localhost:6363/api/document/admin/oms',
            auth=('admin', 'root'),
            params={'type': 'ObjectType'}
        )
        
        if direct_response.status_code == 200:
            results = []
            for line in direct_response.text.strip().split('\n'):
                if line:
                    results.append(json.loads(line))
            
            print(f"✅ Direct query found {len(results)} ObjectTypes in TerminusDB")
            for obj in results:
                if obj.get('name') == 'Invoice':
                    print(f"  ✅ Invoice found: {obj}")

if __name__ == "__main__":
    import os
    os.environ['JWT_SECRET'] = JWT_SECRET
    asyncio.run(test_schema_api())