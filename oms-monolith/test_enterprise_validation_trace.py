#!/usr/bin/env python3
"""
Test script to trace Enterprise Validation issues
"""
import asyncio
import httpx
import json
from datetime import datetime

async def test_validation_flow():
    """Test various endpoints to see validation behavior"""
    
    base_url = "http://localhost:8002"
    
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
                        headers={"Content-Type": "application/json"}
                    )
                
                print(f"Status Code: {response.status_code}")
                print(f"Response Headers: {dict(response.headers)}")
                
                # Pretty print response
                try:
                    response_json = response.json()
                    print(f"Response Body:\n{json.dumps(response_json, indent=2)}")
                except:
                    print(f"Response Body: {response.text}")
                
                # Check if validation middleware was triggered
                if response.status_code == 400:
                    if "request_id" in response.text:
                        print("✓ Enterprise Validation Middleware was triggered")
                    else:
                        print("✗ Standard FastAPI validation was triggered instead")
                
            except Exception as e:
                print(f"Error: {type(e).__name__}: {str(e)}")
        
        # Test metrics endpoint to see if validation metrics are being collected
        print("\n\n" + "=" * 80)
        print("CHECKING VALIDATION METRICS")
        print("=" * 80)
        
        try:
            metrics_response = await client.get(f"{base_url}/metrics")
            print(f"Metrics Status: {metrics_response.status_code}")
            
            # Look for validation-related metrics
            metrics_text = metrics_response.text
            validation_metrics = [
                line for line in metrics_text.split('\n') 
                if 'validation' in line and not line.startswith('#')
            ]
            
            if validation_metrics:
                print("\nValidation Metrics Found:")
                for metric in validation_metrics:
                    print(f"  {metric}")
            else:
                print("\n✗ No validation metrics found!")
                
        except Exception as e:
            print(f"Metrics Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_validation_flow())