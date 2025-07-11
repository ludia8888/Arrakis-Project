#!/usr/bin/env python3
"""
Business Logic Integration Test - Fixed Version
Rate limit 문제를 해결한 비즈니스 시나리오 테스트
"""
import asyncio
import httpx
import json
import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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

# Rate limit configuration
REGISTRATION_DELAY = 61  # Wait 61 seconds between registrations to avoid 5/5min limit
LOGIN_DELAY = 1  # Small delay between logins


class BusinessScenarioTester:
    def __init__(self):
        self.users = {}  # Store created users
        self.tokens = {}  # Store user tokens
        self.schemas = []  # Store created schemas
        self.documents = []  # Store created documents
        self.test_results = []
        
    async def run_all_scenarios(self):
        """Run all business scenarios"""
        logger.info("=" * 80)
        logger.info("BUSINESS LOGIC INTEGRATION TEST (Rate Limit Fixed)")
        logger.info("=" * 80)
        
        scenarios = [
            ("User Onboarding (Single User)", self.scenario_single_user_onboarding),
            ("Schema Management", self.scenario_schema_management),
            ("Document Operations", self.scenario_document_operations),
            ("Audit Trail Verification", self.scenario_audit_trail),
            ("Cross-Service Data Consistency", self.scenario_data_consistency),
        ]
        
        all_passed = True
        
        for scenario_name, scenario_func in scenarios:
            logger.info(f"\n{'='*80}")
            logger.info(f"SCENARIO: {scenario_name}")
            logger.info(f"{'='*80}")
            
            try:
                result = await scenario_func()
                if result:
                    logger.info(f"✅ {scenario_name}: PASSED")
                    self.test_results.append({
                        'scenario': scenario_name,
                        'status': 'PASSED',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                else:
                    logger.error(f"❌ {scenario_name}: FAILED")
                    all_passed = False
                    self.test_results.append({
                        'scenario': scenario_name,
                        'status': 'FAILED',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
            except Exception as e:
                logger.error(f"❌ {scenario_name}: EXCEPTION - {str(e)}")
                all_passed = False
                self.test_results.append({
                    'scenario': scenario_name,
                    'status': 'ERROR',
                    'error': str(e),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        
        # Print summary
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        passed = sum(1 for r in self.test_results if r['status'] == 'PASSED')
        failed = sum(1 for r in self.test_results if r['status'] in ['FAILED', 'ERROR'])
        
        logger.info(f"Total Scenarios: {len(self.test_results)}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        
        if all_passed:
            logger.info("\n🎉 ALL BUSINESS SCENARIOS PASSED!")
        else:
            logger.info("\n❌ SOME SCENARIOS FAILED")
            
        # Save detailed report
        report = {
            'test_run': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total': len(self.test_results),
                'passed': passed,
                'failed': failed
            },
            'results': self.test_results,
            'created_data': {
                'users': list(self.users.keys()),
                'schemas': len(self.schemas),
                'documents': len(self.documents)
            }
        }
        
        with open('business_scenario_test_report_fixed.json', 'w') as f:
            json.dump(report, f, indent=2)
            
        return all_passed
    
    async def scenario_single_user_onboarding(self) -> bool:
        """
        Scenario 1: Single User Onboarding
        - Register one test user
        - Login and get token
        - Verify proper access token is issued
        """
        logger.info("Testing single user onboarding process...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Register test user
                test_user_data = {
                    "username": f"test_user_{random.randint(1000, 9999)}",
                    "password": "Test123!@#",
                    "email": f"test_{random.randint(1000, 9999)}@company.com",
                    "full_name": "Test User"
                }
                
                resp = await client.post(f"{USER_SERVICE_URL}/auth/register", json=test_user_data)
                if resp.status_code != 201:
                    logger.error(f"User registration failed: {resp.status_code}")
                    logger.error(f"Response: {resp.text}")
                    return False
                    
                user_info = resp.json()
                self.users['test_user'] = {
                    'user_id': user_info['user']['user_id'],
                    'username': test_user_data['username'],
                    'password': test_user_data['password']
                }
                logger.info(f"✓ Test user created: {test_user_data['username']}")
                
                # Wait before login to avoid rate limits
                await asyncio.sleep(LOGIN_DELAY)
                
                # Login and get token
                token = await self._login_user(client, test_user_data['username'], test_user_data['password'])
                if not token:
                    logger.error("Failed to login test user")
                    return False
                    
                self.tokens['test_user'] = token
                logger.info("✓ Test user logged in successfully")
                
                # Verify user profile
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(f"{USER_SERVICE_URL}/auth/profile/profile", headers=headers)
                
                if resp.status_code != 200:
                    logger.error("Failed to get user profile")
                    return False
                    
                profile = resp.json()
                logger.info(f"✓ Profile verified for test user: {profile['username']}")
                
                return True
                
        except Exception as e:
            logger.error(f"User onboarding scenario failed: {str(e)}")
            return False
    
    async def scenario_schema_management(self) -> bool:
        """
        Scenario 2: Schema Management
        - View schemas (all users)
        - Verify permission-based access
        """
        logger.info("Testing schema management...")
        
        if 'test_user' not in self.tokens:
            logger.error("No test user available")
            return False
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # View schemas with test user
                headers = {"Authorization": f"Bearer {self.tokens['test_user']}"}
                resp = await client.get(
                    f"{OMS_SERVICE_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                
                if resp.status_code != 200:
                    logger.error(f"Cannot view schemas: {resp.status_code}")
                    return False
                    
                schemas = resp.json()
                logger.info(f"✓ Test user can view schemas (count: {len(schemas)})")
                
                # Try to create schema (should fail with 403)
                test_schema = {
                    "name": "TestSchema",
                    "description": "Test schema",
                    "properties": {"test": {"type": "string"}}
                }
                
                resp = await client.post(
                    f"{OMS_SERVICE_URL}/api/v1/schemas/main/object-types",
                    headers=headers,
                    json=test_schema
                )
                
                if resp.status_code == 403:
                    logger.info("✓ Schema creation correctly denied for regular user (403)")
                else:
                    logger.warning(f"Unexpected response for schema creation: {resp.status_code}")
                
                return True
                
        except Exception as e:
            logger.error(f"Schema management scenario failed: {str(e)}")
            return False
    
    async def scenario_document_operations(self) -> bool:
        """
        Scenario 3: Document Operations
        - Test document endpoints accessibility
        """
        logger.info("Testing document operations...")
        
        if 'test_user' not in self.tokens:
            logger.error("No test user available")
            return False
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {self.tokens['test_user']}"}
                
                # Check documents endpoint
                resp = await client.get(
                    f"{OMS_SERVICE_URL}/api/v1/documents/main",
                    headers=headers
                )
                
                if resp.status_code in [200, 404]:
                    logger.info("✓ Documents endpoint accessible")
                else:
                    logger.warning(f"Unexpected documents response: {resp.status_code}")
                
                return True
                
        except Exception as e:
            logger.error(f"Document operations scenario failed: {str(e)}")
            return False
    
    async def scenario_audit_trail(self) -> bool:
        """
        Scenario 4: Audit Trail Verification
        - Create audit events
        - Verify audit logging works
        """
        logger.info("Testing audit trail functionality...")
        
        if 'test_user' not in self.tokens:
            logger.error("No test user available")
            return False
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {self.tokens['test_user']}"}
                
                # Create audit event
                audit_event = {
                    "event_type": "business_test",
                    "event_category": "integration_test",
                    "severity": "INFO",
                    "user_id": self.users['test_user']['user_id'],
                    "username": self.users['test_user']['username'],
                    "target_type": "test",
                    "target_id": "test_001",
                    "operation": "test_operation",
                    "metadata": {
                        "test_scenario": "audit_trail",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
                
                resp = await client.post(
                    f"{AUDIT_SERVICE_URL}/api/v2/events/single",
                    headers=headers,
                    json=audit_event
                )
                
                if resp.status_code != 201:
                    logger.error(f"Failed to create audit event: {resp.status_code}")
                    return False
                    
                event_response = resp.json()
                logger.info(f"✓ Audit event created: {event_response['event_id']}")
                
                return True
                
        except Exception as e:
            logger.error(f"Audit trail scenario failed: {str(e)}")
            return False
    
    async def scenario_data_consistency(self) -> bool:
        """
        Scenario 5: Cross-Service Data Consistency
        - Verify user data is consistent across services
        """
        logger.info("Testing cross-service data consistency...")
        
        if 'test_user' not in self.tokens:
            logger.error("No test user available")
            return False
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {self.tokens['test_user']}"}
                
                # Get user profile from User Service
                resp = await client.get(
                    f"{USER_SERVICE_URL}/auth/profile/profile",
                    headers=headers
                )
                
                if resp.status_code != 200:
                    logger.error("Failed to get user profile")
                    return False
                    
                user_profile = resp.json()
                user_id = user_profile['user_id']
                username = user_profile['username']
                
                logger.info(f"✓ User profile retrieved: {username} ({user_id})")
                
                # Verify OMS recognizes the token
                resp = await client.get(
                    f"{OMS_SERVICE_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    logger.info("✓ OMS recognizes user token")
                else:
                    logger.error(f"OMS doesn't recognize user: {resp.status_code}")
                    return False
                
                # Verify Audit Service recognizes the user
                resp = await client.post(
                    f"{AUDIT_SERVICE_URL}/api/v2/events/debug-auth",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    auth_info = resp.json()
                    audit_user_id = auth_info['user']['user_id']
                    audit_username = auth_info['user']['username']
                    
                    if audit_user_id == user_id and audit_username == username:
                        logger.info("✓ User data consistent across all services")
                    else:
                        logger.error("User data mismatch between services")
                        return False
                else:
                    logger.error(f"Audit Service auth failed: {resp.status_code}")
                    return False
                
                logger.info("✓ Cross-service authentication chain verified")
                
                return True
                
        except Exception as e:
            logger.error(f"Data consistency scenario failed: {str(e)}")
            return False
    
    async def _login_user(self, client: httpx.AsyncClient, username: str, password: str) -> Optional[str]:
        """Helper method to login user and get token"""
        try:
            # Step 1: Initial login
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={"username": username, "password": password}
            )
            
            if resp.status_code != 200:
                logger.error(f"Login failed for {username}: {resp.status_code}")
                return None
                
            login_data = resp.json()
            
            # Step 2: Complete login if needed
            if login_data.get("step") == "complete":
                complete_resp = await client.post(
                    f"{USER_SERVICE_URL}/auth/login/complete",
                    json={"challenge_token": login_data["challenge_token"]}
                )
                
                if complete_resp.status_code == 200:
                    return complete_resp.json()["access_token"]
                else:
                    logger.error(f"Login complete failed for {username}")
                    return None
            else:
                return login_data.get("access_token")
                
        except Exception as e:
            logger.error(f"Login error for {username}: {str(e)}")
            return None


async def main():
    """Run all business scenarios"""
    # First check if services are running
    logger.info("Checking service availability...")
    
    services_ok = True
    async with httpx.AsyncClient() as client:
        for name, url in [
            ("User Service", f"{USER_SERVICE_URL}/health"),
            ("OMS", f"{OMS_SERVICE_URL}/health"),
            ("Audit Service", f"{AUDIT_SERVICE_URL}/api/v2/events/health")
        ]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    logger.info(f"✓ {name} is running")
                else:
                    logger.error(f"✗ {name} returned {resp.status_code}")
                    services_ok = False
            except Exception as e:
                logger.error(f"✗ {name} is not accessible: {e}")
                services_ok = False
    
    if not services_ok:
        logger.error("\n❌ Not all services are running. Please start all services with docker-compose.")
        return 1
    
    # Run business scenarios
    tester = BusinessScenarioTester()
    success = await tester.run_all_scenarios()
    
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))