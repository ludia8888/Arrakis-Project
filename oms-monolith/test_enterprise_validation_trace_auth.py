#!/usr/bin/env python3
"""
Test script to trace Enterprise Validation issues with authentication
"""
import asyncio
import httpx
import json
from datetime import datetime
import jwt
import uuid

def create_test_token():
    """Create a test JWT token"""
    secret_key = "test-secret-key-for-development-only"
    
    payload = {
        "sub": str(uuid.uuid4()),
        "username": "test_user",
        "email": "test@example.com",
        "roles": ["admin", "user"],
        "permissions": ["*"],
        "teams": ["engineering"],
        "exp": int(datetime.now().timestamp()) + 3600,
        "iat": int(datetime.now().timestamp()),
        "jti": str(uuid.uuid4())
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

async def test_validation_flow():
    """Test various endpoints to see validation behavior"""
    
    base_url = "http://localhost:8002"
    token = create_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Test cases with intentionally bad data
    test_cases = [
        {
            "name": "link_type_missing_required_fields",
            "endpoint": "/api/v1/schemas/main/link-types",
            "method": "POST",
            "data": {
                "name": "TestLink",
                # Missing displayName, sourceObjectType, targetObjectType
            },
            "expected": "Should trigger validation for missing required fields"
        },
        {
            "name": "interface_invalid_name",
            "endpoint": "/api/v1/schemas/main/interfaces", 
            "method": "POST",
            "data": {
                "name": "123Invalid!Name",  # Invalid name format
                "displayName": "Test Interface",
                "properties": []
            },
            "expected": "Should trigger validation for invalid name format"
        },
        {
            "name": "property_invalid_data_type",
            "endpoint": "/api/v1/schemas/main/object-types/TestObject/properties",
            "method": "POST",
            "data": {
                "name": "testProp",
                "displayName": "Test Property",
                "dataType": "invalid_type"  # Invalid data type
            },
            "expected": "Should trigger validation for invalid data type"
        },
        {
            "name": "struct_type_empty_fields",
            "endpoint": "/api/v1/schemas/main/struct-types",
            "method": "POST",
            "data": {
                "name": "TestStruct",
                "displayName": "Test Struct",
                "fields": []  # Empty fields array
            },
            "expected": "Should trigger validation for empty struct"
        },
        {
            "name": "semantic_type_invalid_base",
            "endpoint": "/api/v1/schemas/main/semantic-types",
            "method": "POST",
            "data": {
                "name": "TestSemantic",
                "displayName": "Test Semantic",
                "baseType": "invalid_base"  # Invalid base type
            },
            "expected": "Should trigger validation for invalid base type"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        print("=" * 80)
        print("TESTING ENTERPRISE VALIDATION FLOW")
        print("=" * 80)
        
        for test in test_cases:
            print(f"\n\nTest: {test['name']}")
            print(f"Endpoint: {test['endpoint']}")
            print(f"Method: {test['method']}")
            print(f"Data: {json.dumps(test['data'], indent=2)}")
            print(f"Expected: {test['expected']}")
            print("-" * 40)
            
            try:
                if test['method'] == 'POST':
                    response = await client.post(
                        f"{base_url}{test['endpoint']}",
                        json=test['data'],
                        headers=headers
                    )
                
                print(f"Status Code: {response.status_code}")
                
                # Pretty print response
                try:
                    response_json = response.json()
                    print(f"Response Body:\n{json.dumps(response_json, indent=2)}")
                except:
                    print(f"Response Body: {response.text}")
                
                # Analyze the response
                if response.status_code == 400:
                    response_text = response.text
                    if "request_id" in response_text:
                        print("✓ Enterprise Validation Middleware was triggered")
                    elif "detail" in response_text and isinstance(response_json.get("detail"), list):
                        print("✗ FastAPI/Pydantic validation was triggered instead")
                        print("  This means Enterprise Validation was bypassed!")
                    else:
                        print("✗ Standard HTTPException was raised")
                elif response.status_code == 422:
                    print("✗ FastAPI Request Validation Error (Pydantic)")
                    print("  Enterprise Validation Middleware did NOT run!")
                elif response.status_code == 500:
                    if "request_id" in response.text:
                        print("✓ Enterprise Validation Middleware caught error")
                    else:
                        print("✗ Unhandled server error")
                
            except Exception as e:
                print(f"Error: {type(e).__name__}: {str(e)}")
        
        # Test metrics endpoint to see if validation metrics are being collected
        print("\n\n" + "=" * 80)
        print("CHECKING VALIDATION METRICS")
        print("=" * 80)
        
        try:
            metrics_response = await client.get(f"{base_url}/metrics", headers=headers)
            print(f"Metrics Status: {metrics_response.status_code}")
            
            # Look for validation-related metrics
            metrics_text = metrics_response.text
            validation_metrics = [
                line for line in metrics_text.split('\n') 
                if 'validation' in line.lower() and not line.startswith('#')
            ]
            
            if validation_metrics:
                print("\nValidation Metrics Found:")
                for metric in validation_metrics:
                    print(f"  {metric}")
            else:
                print("\n✗ No validation metrics found!")
                
        except Exception as e:
            print(f"Metrics Error: {type(e).__name__}: {str(e)}")
        
        # Test specific endpoint middleware order
        print("\n\n" + "=" * 80)
        print("TESTING MIDDLEWARE EXECUTION ORDER")
        print("=" * 80)
        
        # Send request with debug headers
        debug_response = await client.post(
            f"{base_url}/api/v1/schemas/main/link-types",
            json={"invalid": "data"},
            headers={**headers, "X-Debug-Trace": "true"}
        )
        
        print(f"Debug Request Status: {debug_response.status_code}")
        print(f"Debug Response: {debug_response.text[:200]}...")

if __name__ == "__main__":
    asyncio.run(test_validation_flow())