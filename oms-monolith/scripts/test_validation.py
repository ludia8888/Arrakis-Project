#!/usr/bin/env python
"""
Test validation features in OMS API
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

async def test_validation():
    """Test validation features"""
    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    base_url = "http://localhost:8002"
    
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        print("\n" + "="*80)
        print("TESTING VALIDATION FEATURES")
        print("="*80)
        
        # Test 1: SQL Injection attempt in name
        print("\n1. Testing SQL Injection Prevention")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "Test'; DROP TABLE users; --",
                "displayName": "Normal Display Name",
                "description": "Testing SQL injection"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 2: XSS attempt
        print("\n2. Testing XSS Prevention")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "Test<script>alert('XSS')</script>",
                "displayName": "<img src=x onerror=alert('XSS')>",
                "description": "Testing XSS"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 3: Invalid characters in name
        print("\n3. Testing Invalid Characters")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "Test@#$%^&*()",
                "displayName": "Test Object",
                "description": "Testing invalid chars"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 4: Empty/null values
        print("\n4. Testing Empty Values")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "",
                "displayName": "Test"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 5: Duplicate name
        print("\n5. Testing Duplicate Prevention")
        # First create a valid object
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "UniqueTest",
                "displayName": "Unique Test",
                "description": "First object"
            }
        )
        print(f"First create - Status: {response.status_code}")
        
        # Try to create duplicate
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "UniqueTest",
                "displayName": "Duplicate Test",
                "description": "Should fail"
            }
        )
        print(f"Duplicate attempt - Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 6: Property with invalid data type
        print("\n6. Testing Invalid Data Type")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types/Customer/properties",
            json={
                "name": "testProp",
                "displayName": "Test Property",
                "dataType": "invalid:type",
                "required": True
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 7: Link type with non-existent object types
        print("\n7. Testing Link Type Validation")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/link-types",
            json={
                "name": "InvalidLink",
                "displayName": "Invalid Link",
                "sourceObjectType": "NonExistentType",
                "targetObjectType": "Customer",
                "cardinality": "one-to-many"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 8: Command injection attempt
        print("\n8. Testing Command Injection Prevention")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "Test`rm -rf /`",
                "displayName": "Test$(whoami)",
                "description": "Testing command injection"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 9: Unicode attacks
        print("\n9. Testing Unicode Attack Prevention")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "Test\u200b\u200c\u200d",  # Zero-width characters
                "displayName": "Test\u202e\u202d",  # Right-to-left override
                "description": "Testing unicode attacks"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # Test 10: Valid creation after all attacks
        print("\n10. Testing Valid Creation Still Works")
        response = await client.post(
            f"{base_url}/api/v1/schemas/main/object-types",
            json={
                "name": "ValidTestObject",
                "displayName": "Valid Test Object",
                "description": "This should work fine"
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Valid object created successfully!")
        else:
            print(f"Response: {response.text[:200]}")
        
        print("\n" + "="*80)
        print("VALIDATION TESTS COMPLETED")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(test_validation())
