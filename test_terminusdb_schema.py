#!/usr/bin/env python3
"""
Test TerminusDB schema API directly
"""
import asyncio
import httpx
import json
import base64

async def test_schema_api():
    """Test TerminusDB schema API"""
    
    # Create auth header
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Check current schema
        print("1. Getting current schema...")
        response = await client.get(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers
        )
        print(f"Get schema response: {response.status_code}")
        if response.status_code == 200:
            current_schema = response.json()
            print(f"Current schema: {json.dumps(current_schema, indent=2)}")
        
        # 2. Test schema update with proper Class definition
        print("\n2. Testing schema update...")
        
        # TerminusDB schema format - try a minimal class definition
        schema_payload = {
            "@context": {
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#",
                "@type": "Context"
            },
            "@graph": [
                {
                    "@id": "terminusdb:///schema#Car",
                    "@type": "sys:Class",
                    "sys:documentation": {
                        "@label": "Car",
                        "@comment": "A car object type"
                    }
                }
            ]
        }
        
        # Update to match the expected payload format
        payload = {
            "schema": schema_payload,
            "commit_info": {"message": "Create Car schema"}
        }
        
        response = await client.post(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers,
            json=payload
        )
        print(f"Schema update response: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        else:
            print("Schema updated successfully!")
            
        # 3. Verify schema was created
        print("\n3. Verifying schema...")
        response = await client.get(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers
        )
        if response.status_code == 200:
            new_schema = response.json()
            # Check if Car class exists
            if "@graph" in new_schema:
                car_class = next((cls for cls in new_schema["@graph"] if cls.get("@id") == "Car"), None)
                if car_class:
                    print("✅ Car class found in schema!")
                    print(f"Car class: {json.dumps(car_class, indent=2)}")
                else:
                    print("❌ Car class not found in schema")

if __name__ == "__main__":
    asyncio.run(test_schema_api())