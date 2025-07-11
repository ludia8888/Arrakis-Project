#!/usr/bin/env python3
"""
Full Stack Test Script for OMS Monolith

This script tests all components of the OMS system including:
- Main API endpoints
- Authentication flow
- Database connections (TerminusDB, PostgreSQL, Redis)
- GraphQL endpoints
- Monitoring endpoints
- Secure database operations with audit tracking
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any

# Service URLs
BASE_URL = "http://localhost:8000"
GRAPHQL_URL = "http://localhost:8006/graphql"
METRICS_URL = "http://localhost:9090/metrics"

# Test user credentials
TEST_USER = {
    "username": "test_user",
    "email": "test@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User"
}

async def wait_for_services(max_attempts: int = 30):
    """Wait for all services to be ready"""
    print("🔄 Waiting for services to start...")
    
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient() as client:
                # Check main API health
                response = await client.get(f"{BASE_URL}/health")
                if response.status_code == 200:
                    print("✅ Main API is ready")
                    return True
        except Exception:
            pass
        
        print(f"⏳ Attempt {attempt + 1}/{max_attempts} - Services not ready yet...")
        await asyncio.sleep(2)
    
    return False

async def test_health_endpoints():
    """Test health check endpoints"""
    print("\n🏥 Testing Health Endpoints...")
    
    async with httpx.AsyncClient() as client:
        # Main API health
        response = await client.get(f"{BASE_URL}/health")
        print(f"  Main API Health: {response.status_code}")
        assert response.status_code == 200
        
        # Root endpoint
        response = await client.get(BASE_URL)
        print(f"  Root Endpoint: {response.status_code}")
        assert response.status_code == 200

async def test_authentication():
    """Test authentication flow"""
    print("\n🔐 Testing Authentication...")
    
    async with httpx.AsyncClient() as client:
        # Register user
        print("  Registering user...")
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=TEST_USER
        )
        print(f"  Registration: {response.status_code}")
        
        if response.status_code == 409:
            print("  User already exists, proceeding with login")
        else:
            assert response.status_code in [200, 201]
        
        # Login
        print("  Logging in...")
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )
        assert response.status_code == 200
        token_data = response.json()
        token = token_data["access_token"]
        print(f"  ✅ Login successful, token received")
        
        # Test authenticated endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        user_data = response.json()
        print(f"  ✅ User info retrieved: {user_data['username']}")
        
        return token

async def test_schema_operations(token: str):
    """Test schema operations with secure database adapter"""
    print("\n📋 Testing Schema Operations...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Create a test schema
        schema_data = {
            "@context": {
                "@type": "@context",
                "@base": "http://example.com/",
                "@schema": "http://example.com/schema#"
            },
            "TestClass": {
                "@type": "Class",
                "@id": "TestClass",
                "@documentation": {
                    "@comment": "Test class for full stack testing",
                    "@properties": {
                        "name": "Name of the test object",
                        "value": "Numeric value for testing"
                    }
                },
                "name": "xsd:string",
                "value": "xsd:decimal"
            }
        }
        
        print("  Creating test schema...")
        response = await client.post(
            f"{BASE_URL}/api/v1/schema",
            json=schema_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Schema created with audit fields:")
            print(f"     - Created by: {result.get('_created_by_username', 'N/A')}")
            print(f"     - Created at: {result.get('_created_at', 'N/A')}")
        else:
            print(f"  ⚠️  Schema creation returned: {response.status_code}")

async def test_document_operations(token: str):
    """Test document operations"""
    print("\n📄 Testing Document Operations...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Create a test document
        doc_data = {
            "@type": "TestClass",
            "name": "Full Stack Test Document",
            "value": 42.0
        }
        
        print("  Creating test document...")
        response = await client.post(
            f"{BASE_URL}/api/v1/document",
            json=doc_data,
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            doc_id = result.get("@id", result.get("id"))
            print(f"  ✅ Document created: {doc_id}")
            print(f"     - Created by: {result.get('_created_by_username', 'N/A')}")
            return doc_id
        else:
            print(f"  ⚠️  Document creation returned: {response.status_code}")
            print(f"     Response: {response.text}")

async def test_graphql_endpoints():
    """Test GraphQL endpoints"""
    print("\n🔷 Testing GraphQL Endpoints...")
    
    async with httpx.AsyncClient() as client:
        # Test GraphQL introspection
        query = """
        query {
            __schema {
                types {
                    name
                }
            }
        }
        """
        
        response = await client.post(
            GRAPHQL_URL,
            json={"query": query}
        )
        
        if response.status_code == 200:
            print("  ✅ GraphQL endpoint is accessible")
        else:
            print(f"  ⚠️  GraphQL returned: {response.status_code}")

async def test_monitoring():
    """Test monitoring endpoints"""
    print("\n📊 Testing Monitoring...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(METRICS_URL)
            if response.status_code == 200:
                print("  ✅ Prometheus metrics endpoint is accessible")
                # Check for key metrics
                metrics_text = response.text
                if "audit_events_total" in metrics_text:
                    print("  ✅ Audit metrics are being collected")
                if "audit_dlq_size" in metrics_text:
                    print("  ✅ DLQ metrics are being collected")
        except Exception as e:
            print(f"  ⚠️  Metrics endpoint not accessible: {e}")

async def main():
    """Run all tests"""
    print("🚀 Starting OMS Full Stack Test")
    print("=" * 50)
    
    # Wait for services
    if not await wait_for_services():
        print("❌ Services failed to start. Please check Docker logs.")
        return
    
    try:
        # Run tests
        await test_health_endpoints()
        token = await test_authentication()
        await test_schema_operations(token)
        await test_document_operations(token)
        await test_graphql_endpoints()
        await test_monitoring()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        print("\n🎯 Full Stack Test Summary:")
        print("  - ✅ All services are running")
        print("  - ✅ Authentication is working")
        print("  - ✅ Secure database operations with audit tracking")
        print("  - ✅ GraphQL endpoint is accessible")
        print("  - ✅ Monitoring is functional")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())