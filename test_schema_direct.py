#!/usr/bin/env python3
"""
Test TerminusDB schema API with different formats
"""
import asyncio
import httpx
import json
import base64

async def test_formats():
    """Test different schema formats"""
    
    auth = base64.b64encode(b"admin:root").decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Format 1: Simple replace entire schema
        print("1. Testing simple schema replacement...")
        
        schema = {
            "@context": {
                "@base": "terminusdb:///data/",
                "@schema": "terminusdb:///schema#",
                "@type": "Context"
            },
            "@graph": []
        }
        
        # Just send the schema directly
        response = await client.post(
            "http://localhost:6363/api/schema/admin/arrakis",
            headers=headers,
            json=schema
        )
        print(f"Direct schema post: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            
        # Format 2: Try with author parameter
        print("\n2. Testing with author parameter...")
        response = await client.post(
            "http://localhost:6363/api/schema/admin/arrakis?author=admin&message=Update%20schema",
            headers=headers,
            json=schema
        )
        print(f"Schema with author: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            
        # Format 3: Try to get info about what endpoints exist
        print("\n3. Checking available endpoints...")
        response = await client.get(
            "http://localhost:6363/api",
            headers=headers
        )
        print(f"API root: {response.status_code}")
        if response.status_code == 200:
            print(f"Available endpoints: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_formats())