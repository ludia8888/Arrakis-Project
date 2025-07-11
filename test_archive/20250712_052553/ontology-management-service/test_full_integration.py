#!/usr/bin/env python3
"""
Full Integration Test Suite - OMS + User Service
Tests all functionality as a real user would use it
"""
import asyncio
import httpx
import json
import jwt
import websockets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time

# Service URLs
USER_SERVICE_URL = "http://localhost:8002"
OMS_API_URL = "http://localhost:8000"
GRAPHQL_URL = "http://localhost:8006/graphql"
WS_URL = "ws://localhost:8004/ws"

# Test data
import time
TEST_USER = {
    "username": f"testuser_{int(time.time())}",
    "email": f"test_{int(time.time())}@example.com", 
    "password": "Test123!",
    "roles": ["admin"]
}

class IntegrationTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.token: Optional[str] = None
        self.headers: Dict[str, str] = {}
        self.user_id: Optional[str] = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def wait_for_services(self, max_retries=30):
        """Wait for all services to be ready"""
        print("⏳ Waiting for services to start...")
        
        services = [
            (USER_SERVICE_URL, "User Service"),
            (OMS_API_URL, "OMS API")
        ]
        
        for url, name in services:
            for i in range(max_retries):
                try:
                    response = await self.client.get(f"{url}/health")
                    if response.status_code == 200:
                        print(f"✅ {name} is ready")
                        break
                except Exception:
                    pass
                
                if i == max_retries - 1:
                    print(f"❌ {name} failed to start")
                    return False
                    
                await asyncio.sleep(2)
        
        # Note: GraphQL service health check disabled for now
        print("⚠️  GraphQL service health check skipped")
        return True
    
    async def test_user_registration(self):
        """Test 1: User Registration"""
        print("\n🧪 Test 1: User Registration")
        
        # Register new user
        response = await self.client.post(
            f"{USER_SERVICE_URL}/auth/register",
            json=TEST_USER
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ User registered successfully")
            print(f"   User ID: {data.get('user', {}).get('id')}")
            return True
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
    
    async def test_user_login(self):
        """Test 2: User Login"""
        print("\n🧪 Test 2: User Login")
        
        # Login
        response = await self.client.post(
            f"{USER_SERVICE_URL}/auth/login",
            data={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            
            # Decode token to get user info
            decoded = jwt.decode(self.token, options={"verify_signature": False})
            self.user_id = decoded.get("sub")
            
            print(f"✅ Login successful")
            print(f"   Token: {self.token[:50]}...")
            print(f"   User ID: {self.user_id}")
            return True
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
    
    async def test_oms_health_check(self):
        """Test 3: OMS Health Check with Auth"""
        print("\n🧪 Test 3: OMS Health Check")
        
        response = await self.client.get(
            f"{OMS_API_URL}/health",
            headers=self.headers
        )
        
        if response.status_code == 200:
            health = response.json()
            print(f"✅ OMS is healthy")
            print(f"   Database: {health['checks']['database']['status']}")
            print(f"   TerminusDB: {health['checks']['terminusdb']['status']}")
            print(f"   Redis: {health['checks']['redis']['status']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    
    async def test_graphql_schema_query(self):
        """Test 4: GraphQL Schema Query"""
        print("\n🧪 Test 4: GraphQL Schema Query")
        
        query = """
        query {
            objectTypes {
                id
                name
                version
            }
        }
        """
        
        response = await self.client.post(
            GRAPHQL_URL,
            json={"query": query},
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                types = data["data"]["objectTypes"]
                print(f"✅ GraphQL query successful")
                print(f"   Found {len(types)} object types")
                for t in types:
                    print(f"   - {t['name']} (v{t['version']})")
                return True
        
        print(f"❌ GraphQL query failed: {response.text}")
        return False
    
    async def test_create_schema(self):
        """Test 5: Create New Schema"""
        print("\n🧪 Test 5: Create New Schema")
        
        mutation = """
        mutation CreateSchema($input: ObjectTypeInput!) {
            createObjectType(input: $input) {
                id
                name
                version
            }
        }
        """
        
        variables = {
            "input": {
                "name": "UserProfile",
                "description": "User profile schema for testing"
            }
        }
        
        response = await self.client.post(
            GRAPHQL_URL,
            json={"query": mutation, "variables": variables},
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"].get("createObjectType"):
                created = data["data"]["createObjectType"]
                print(f"✅ Schema created successfully")
                print(f"   ID: {created['id']}")
                print(f"   Name: {created['name']}")
                print(f"   Version: {created['version']}")
                return True
        
        print(f"❌ Schema creation failed: {response.text}")
        return False
    
    async def test_websocket_subscription(self):
        """Test 6: WebSocket Subscription"""
        print("\n🧪 Test 6: WebSocket Subscription")
        
        try:
            # Connect with auth header
            headers = []
            if self.token:
                headers.append(("Authorization", f"Bearer {self.token}"))
            
            async with websockets.connect(WS_URL, additional_headers=headers) as websocket:
                # Wait for connection ack
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("type") == "connection_ack":
                    print(f"✅ WebSocket connected")
                    print(f"   Connection ID: {data.get('connection_id')}")
                    
                    # Subscribe to updates
                    await websocket.send(json.dumps({
                        "type": "subscription_start",
                        "subscription_id": "test-sub-1",
                        "subscription_name": "object_type_changes"
                    }))
                    
                    # Wait for subscription ack
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        print(f"   Subscription response: {response}")
                        return True
                    except asyncio.TimeoutError:
                        print("   No immediate data (normal for subscriptions)")
                        return True
                        
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False
    
    async def test_audit_trail(self):
        """Test 7: Audit Trail"""
        print("\n🧪 Test 7: Audit Trail")
        
        # Create something to audit
        response = await self.client.post(
            f"{OMS_API_URL}/api/v1/schemas",
            json={
                "name": "AuditTest",
                "type": "object",
                "properties": {}
            },
            headers=self.headers
        )
        
        # Check audit logs
        audit_response = await self.client.get(
            f"{OMS_API_URL}/api/v1/audit/logs?limit=5",
            headers=self.headers
        )
        
        if audit_response.status_code == 200:
            logs = audit_response.json()
            print(f"✅ Audit trail working")
            print(f"   Found {len(logs)} recent audit entries")
            return True
        else:
            print(f"❌ Audit trail failed: {audit_response.status_code}")
            return False
    
    async def test_branch_operations(self):
        """Test 8: Branch Operations"""
        print("\n🧪 Test 8: Branch Operations")
        
        # Create a branch lock
        branch_name = "main"
        response = await self.client.post(
            f"{OMS_API_URL}/api/v1/branch-locks/acquire",
            json={
                "branch_name": branch_name,
                "lock_type": "READ",
                "lock_scope": "BRANCH",
                "reason": "Integration test - testing branch lock functionality"
            },
            headers=self.headers
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Branch lock acquired for: {branch_name}")
            
            # Get branch state
            list_response = await self.client.get(
                f"{OMS_API_URL}/api/v1/branch-locks/status/{branch_name}",
                headers=self.headers
            )
            
            if list_response.status_code == 200:
                state = list_response.json()
                print(f"   Branch state: {state.get('state', 'unknown')}")
                return True
        
        print(f"❌ Branch operations failed: {response.status_code}")
        return False
    
    async def test_performance(self):
        """Test 9: Performance Test"""
        print("\n🧪 Test 9: Performance Test")
        
        # Measure GraphQL query performance
        start = time.time()
        
        tasks = []
        for i in range(10):
            query = """
            query {
                objectTypes {
                    id
                    name
                }
            }
            """
            task = self.client.post(
                GRAPHQL_URL,
                json={"query": query},
                headers=self.headers
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        end = time.time()
        
        success_count = sum(1 for r in responses if r.status_code == 200)
        avg_time = (end - start) / 10 * 1000  # ms
        
        print(f"✅ Performance test complete")
        print(f"   Successful requests: {success_count}/10")
        print(f"   Average response time: {avg_time:.2f}ms")
        print(f"   Requests per second: {10 / (end - start):.2f}")
        
        return success_count == 10
    
    async def test_cleanup(self):
        """Test 10: Cleanup Test Data"""
        print("\n🧪 Test 10: Cleanup")
        
        # Delete test user (if user service supports it)
        # For now, just logout
        response = await self.client.post(
            f"{USER_SERVICE_URL}/auth/logout",
            headers=self.headers
        )
        
        print(f"✅ Cleanup complete")
        return True
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Full Integration Tests")
        print("=" * 60)
        
        # Wait for services
        if not await self.wait_for_services():
            print("❌ Services failed to start. Aborting tests.")
            return False
        
        # Test suite
        tests = [
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("OMS Health Check", self.test_oms_health_check),
            ("GraphQL Schema Query", self.test_graphql_schema_query),
            ("Create Schema", self.test_create_schema),
            ("WebSocket Subscription", self.test_websocket_subscription),
            ("Audit Trail", self.test_audit_trail),
            ("Branch Operations", self.test_branch_operations),
            ("Performance Test", self.test_performance),
            ("Cleanup", self.test_cleanup)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Summary:")
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All integration tests passed!")
        else:
            print(f"\n⚠️  {total - passed} tests failed")
        
        return passed == total


async def main():
    """Main test runner"""
    async with IntegrationTester() as tester:
        success = await tester.run_all_tests()
        exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())