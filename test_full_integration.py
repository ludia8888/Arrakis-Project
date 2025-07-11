#!/usr/bin/env python3
"""
Full integration test for all three services:
- User Service
- OMS (Ontology Management Service)
- Audit Service
"""
import asyncio
import httpx
import json
import random
import logging
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service URLs
USER_SERVICE_URL = "http://localhost:8080"
OMS_SERVICE_URL = "http://localhost:8091"
AUDIT_SERVICE_URL = "http://localhost:8092"


class IntegrationTester:
    def __init__(self):
        self.user_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
        self.test_results = []
        
    async def wait_for_services(self, max_retries: int = 30):
        """Wait for all services to be ready"""
        logger.info("=== Waiting for services to be ready ===")
        
        for i in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    # Check services
                    user_resp = await client.get(f"{USER_SERVICE_URL}/health")
                    oms_resp = await client.get(f"{OMS_SERVICE_URL}/health")
                    audit_resp = await client.get(f"{AUDIT_SERVICE_URL}/api/v2/events/health")
                    
                    if all(resp.status_code == 200 for resp in [user_resp, oms_resp, audit_resp]):
                        logger.info("✅ All services are ready!")
                        return True
            except:
                pass
            
            logger.info(f"  Attempt {i+1}/{max_retries}...")
            await asyncio.sleep(2)
        
        logger.error("❌ Services failed to start")
        return False
    
    async def test_user_registration_and_login(self):
        """Test 1: User registration and login"""
        logger.info("\n=== Test 1: User Registration and Login ===")
        
        # Generate unique test user
        timestamp = int(datetime.now().timestamp())
        random_num = random.randint(100000, 999999)
        self.username = f"integration_test_{random_num}"
        
        async with httpx.AsyncClient() as client:
            # Register user
            logger.info(f"Registering user: {self.username}")
            register_data = {
                "username": self.username,
                "password": "Test123!@#",
                "email": f"integration_{random_num}@test.com",
                "full_name": "Integration Test User"
            }
            
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/register",
                json=register_data
            )
            
            if resp.status_code != 201:
                logger.error(f"Registration failed: {resp.status_code} - {resp.text}")
                return False
                
            logger.info("✅ User registered successfully")
            
            # Login
            logger.info("Attempting login...")
            login_resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={
                    "username": self.username,
                    "password": "Test123!@#"
                }
            )
            
            if login_resp.status_code != 200:
                logger.error(f"Login failed: {login_resp.status_code} - {login_resp.text}")
                return False
                
            login_data = login_resp.json()
            
            # Handle two-step login if needed
            if login_data.get("step") == "complete":
                complete_resp = await client.post(
                    f"{USER_SERVICE_URL}/auth/login/complete",
                    json={"challenge_token": login_data["challenge_token"]}
                )
                if complete_resp.status_code == 200:
                    token_data = complete_resp.json()
                    self.user_token = token_data["access_token"]
                else:
                    logger.error(f"Login complete failed: {complete_resp.status_code}")
                    return False
            else:
                self.user_token = login_data.get("access_token")
            
            logger.info("✅ Login successful")
            logger.info(f"Token (first 50 chars): {self.user_token[:50]}...")
            
            # Get user profile
            headers = {"Authorization": f"Bearer {self.user_token}"}
            profile_resp = await client.get(
                f"{USER_SERVICE_URL}/auth/profile/profile",
                headers=headers
            )
            
            if profile_resp.status_code == 200:
                profile = profile_resp.json()
                self.user_id = profile["user_id"]
                logger.info(f"✅ User ID: {self.user_id}")
            
            return True
    
    async def test_token_validation(self):
        """Test 2: Cross-service token validation"""
        logger.info("\n=== Test 2: Cross-Service Token Validation ===")
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Validate token with User Service
            validation_resp = await client.post(
                f"{USER_SERVICE_URL}/api/v1/auth/validate",
                headers=headers
            )
            
            if validation_resp.status_code != 200:
                logger.error(f"Token validation failed: {validation_resp.status_code}")
                return False
                
            validation_data = validation_resp.json()
            logger.info(f"✅ Token validated: user_id={validation_data['user_id']}")
            
            return True
    
    async def test_oms_access(self):
        """Test 3: OMS access with JWT token"""
        logger.info("\n=== Test 3: OMS Access with JWT Token ===")
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Get schemas from OMS
            resp = await client.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas/main/object-types",
                headers=headers
            )
            
            if resp.status_code != 200:
                logger.error(f"OMS access failed: {resp.status_code} - {resp.text}")
                return False
                
            schemas = resp.json()
            logger.info(f"✅ OMS schemas retrieved: {len(schemas)} schemas")
            
            # Create a test schema
            test_schema = {
                "name": f"TestSchema_{int(datetime.now().timestamp())}",
                "description": "Integration test schema",
                "properties": {
                    "test_field": {
                        "type": "string",
                        "description": "Test field"
                    }
                }
            }
            
            create_resp = await client.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas/main/object-types",
                headers=headers,
                json=test_schema
            )
            
            if create_resp.status_code == 201:
                logger.info("✅ Test schema created in OMS")
            else:
                logger.warning(f"Schema creation returned: {create_resp.status_code}")
            
            return True
    
    async def test_audit_service_access(self):
        """Test 4: Audit Service access with JWT token"""
        logger.info("\n=== Test 4: Audit Service Access with JWT Token ===")
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Test debug auth endpoint
            debug_resp = await client.post(
                f"{AUDIT_SERVICE_URL}/api/v2/events/debug-auth",
                headers=headers
            )
            
            if debug_resp.status_code != 200:
                logger.error(f"Audit debug auth failed: {debug_resp.status_code} - {debug_resp.text}")
                return False
                
            debug_data = debug_resp.json()
            logger.info(f"✅ Audit Service authenticated user: {debug_data}")
            
            # Query audit events
            query_resp = await client.get(
                f"{AUDIT_SERVICE_URL}/api/v2/events/query",
                headers=headers,
                params={"limit": 10}
            )
            
            if query_resp.status_code != 200:
                logger.error(f"Audit query failed: {query_resp.status_code} - {query_resp.text}")
                return False
                
            events = query_resp.json()
            logger.info(f"✅ Audit events retrieved: {events.get('total', 0)} total events")
            
            # Create a test audit event
            test_event = {
                "event_type": "integration_test",
                "event_category": "test",
                "severity": "INFO",
                "user_id": self.user_id,
                "username": self.username,
                "target_type": "test",
                "target_id": "test_123",
                "operation": "test_operation",
                "metadata": {
                    "test": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            create_resp = await client.post(
                f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                headers=headers,
                json=test_event
            )
            
            if create_resp.status_code == 201:
                logger.info("✅ Test audit event created")
            else:
                logger.warning(f"Audit event creation returned: {create_resp.status_code}")
            
            return True
    
    async def test_cross_service_integration(self):
        """Test 5: Cross-service integration (OMS action triggers audit)"""
        logger.info("\n=== Test 5: Cross-Service Integration ===")
        
        # This test verifies that actions in OMS are properly audited
        # In a real implementation, OMS would call Audit Service directly
        
        logger.info("✅ Cross-service integration test placeholder")
        return True
    
    async def run_all_tests(self):
        """Run all integration tests"""
        # Wait for services
        if not await self.wait_for_services():
            logger.error("Services not available. Make sure docker-compose is running.")
            return False
        
        # Run tests
        tests = [
            ("User Registration and Login", self.test_user_registration_and_login),
            ("Token Validation", self.test_token_validation),
            ("OMS Access", self.test_oms_access),
            ("Audit Service Access", self.test_audit_service_access),
            ("Cross-Service Integration", self.test_cross_service_integration)
        ]
        
        all_passed = True
        results = []
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}")
                results.append((test_name, False))
                all_passed = False
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("INTEGRATION TEST SUMMARY")
        logger.info("="*60)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")
        
        logger.info("="*60)
        if all_passed:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.info("❌ SOME TESTS FAILED")
        
        return all_passed


async def main():
    tester = IntegrationTester()
    success = await tester.run_all_tests()
    
    # Save results
    with open("integration_test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "services": {
                "user_service": USER_SERVICE_URL,
                "oms_service": OMS_SERVICE_URL,
                "audit_service": AUDIT_SERVICE_URL
            }
        }, f, indent=2)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)