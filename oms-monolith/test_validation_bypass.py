#!/usr/bin/env python3
"""
Direct test to show Enterprise Validation bypass issue
"""
import os
os.environ["JWT_SECRET"] = "test-secret-key-for-development-only"
os.environ["JWT_LOCAL_VALIDATION"] = "true"

import asyncio
import httpx
import json
from datetime import datetime, timezone
import jwt
import uuid

def create_test_token():
    """Create a test JWT token"""
    secret_key = os.environ["JWT_SECRET"]
    
    payload = {
        "sub": str(uuid.uuid4()),
        "username": "test_user",
        "email": "test@example.com",
        "roles": ["admin", "user"],
        "permissions": ["*"],
        "teams": ["engineering"],
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": str(uuid.uuid4())
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

from datetime import timedelta

async def test_pydantic_vs_enterprise():
    """Test to show Pydantic validation vs Enterprise validation"""
    
    base_url = "http://localhost:8002"
    token = create_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    test_cases = [
        {
            "name": "Test 1: Pydantic Model Validation (BaseModel)",
            "endpoint": "/api/v1/schemas/main/semantic-types",
            "data": {
                "name": "TestSemantic",
                "displayName": "Test Semantic", 
                "baseType": "INVALID_BASE_TYPE"  # This should fail validation
            },
            "description": "SemanticTypeCreateRequest has a Pydantic validator that checks baseType"
        },
        {
            "name": "Test 2: Missing Required Field",
            "endpoint": "/api/v1/schemas/main/link-types",
            "data": {
                "name": "TestLink"
                # Missing: displayName, sourceObjectType, targetObjectType
            },
            "description": "LinkTypeCreateRequest requires these fields"
        },
        {
            "name": "Test 3: Invalid Field Pattern", 
            "endpoint": "/api/v1/schemas/main/object-types/TestObject/properties",
            "data": {
                "name": "123-invalid-name!",  # PropertyCreateRequest has pattern validation
                "displayName": "Test Property",
                "dataType": "xsd:string"
            },
            "description": "PropertyCreateRequest has a pattern validator for 'name'"
        }
    ]
    
    print("ENTERPRISE VALIDATION BYPASS DEMONSTRATION")
    print("=" * 80)
    print("\nThe issue: Pydantic model validation runs BEFORE middleware")
    print("This means Enterprise Validation Middleware never gets a chance to run!\n")
    
    async with httpx.AsyncClient() as client:
        for test in test_cases:
            print(f"\n{test['name']}")
            print("-" * 80)
            print(f"Endpoint: {test['endpoint']}")
            print(f"Description: {test['description']}")
            print(f"Request Body: {json.dumps(test['data'], indent=2)}")
            
            try:
                response = await client.post(
                    f"{base_url}{test['endpoint']}",
                    json=test['data'],
                    headers=headers
                )
                
                print(f"\nResponse Status: {response.status_code}")
                
                # Analyze the response
                if response.status_code == 422:
                    print("❌ PYDANTIC VALIDATION ERROR (FastAPI default)")
                    print("   -> Enterprise Validation Middleware was NEVER called!")
                    detail = response.json()
                    print(f"   -> Error: {json.dumps(detail, indent=6)}")
                    
                elif response.status_code == 400:
                    response_data = response.json()
                    if "request_id" in response_data:
                        print("✅ Enterprise Validation Middleware response")
                        print(f"   -> Request ID: {response_data.get('request_id')}")
                    else:
                        print("❓ HTTPException from endpoint (not Enterprise Validation)")
                        print(f"   -> Detail: {response_data.get('detail')}")
                        
                else:
                    print(f"   -> Response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"Error: {e}")
    
    print("\n\n" + "=" * 80)
    print("ANALYSIS:")
    print("=" * 80)
    print("""
1. When Pydantic BaseModel validation fails (e.g., @validator decorators),
   FastAPI returns a 422 Unprocessable Entity BEFORE middleware runs
   
2. The Enterprise Validation Middleware only runs if the Pydantic model
   validation passes first
   
3. This means:
   - Information disclosure prevention doesn't work for Pydantic errors
   - Metrics aren't collected for failed Pydantic validations
   - Custom validation rules in Enterprise Service aren't applied
   - Error messages aren't sanitized
   
4. The middleware execution order in main.py doesn't matter because
   Pydantic validation happens during request parsing, not in middleware!
""")

if __name__ == "__main__":
    asyncio.run(test_pydantic_vs_enterprise())