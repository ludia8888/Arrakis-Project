#!/usr/bin/env python3
"""
REAL Service-to-Service Integration Test
Tests actual API calls, JWT tokens, and service communication
"""
import asyncio
import httpx
import json
import sys
import jwt
from datetime import datetime

# Service URLs - ACTUAL exposed ports
USER_SERVICE_URL = "http://localhost:8080"  # User service exposed port
OMS_SERVICE_URL = "http://localhost:8091"   # OMS exposed port
NGINX_GATEWAY_URL = "http://localhost:80"   # Gateway port

# Test credentials for real JWT - use existing testuser but check default password
TEST_USER = {
    "username": "testuser_correct", 
    "password": "TestPassword123!"  # Will try multiple common passwords
}

POSSIBLE_PASSWORDS = ["TestPassword123!", "Test123!", "testpass123", "password", "test123", "admin", "123456"]

class RealIntegrationTester:
    def __init__(self):
        self.user_token = None
        self.test_results = []
        
    def log_test(self, test_name: str, status: str, details: str):
        """Log test results"""
        result = {
            "test": test_name,
            "status": status, 
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"[{status}] {test_name}: {details}")
    
    async def test_user_service_direct_access(self):
        """Test 1: Direct access to user-service container"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{USER_SERVICE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    self.log_test("User Service Direct", "PASS", f"Health check: {response.status_code}")
                    return True
                else:
                    self.log_test("User Service Direct", "FAIL", f"Health check failed: {response.status_code}")
                    return False
        except Exception as e:
            self.log_test("User Service Direct", "ERROR", f"Connection failed: {str(e)}")
            return False
    
    async def test_oms_service_direct_access(self):
        """Test 2: Direct access to OMS service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{OMS_SERVICE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    self.log_test("OMS Service Direct", "PASS", f"Health check: {response.status_code}, DB: {data.get('checks', {}).get('database', {}).get('status')}")
                    return True
                else:
                    self.log_test("OMS Service Direct", "FAIL", f"Health check failed: {response.status_code}")
                    return False
        except Exception as e:
            self.log_test("OMS Service Direct", "ERROR", f"Connection failed: {str(e)}")
            return False
    
    async def test_user_service_login(self):
        """Test 3: User service authentication - GET REAL JWT TOKEN"""
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Login with username/password
                login_data = {
                    "username": TEST_USER["username"],
                    "password": TEST_USER["password"]
                }
                
                response = await client.post(f"{USER_SERVICE_URL}/auth/login", json=login_data, timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("step") == "complete" and data.get("challenge_token"):
                        # Step 2: Complete login with challenge token (no MFA)
                        complete_data = {
                            "challenge_token": data["challenge_token"],
                            "mfa_code": None  # No MFA for test user
                        }
                        
                        response2 = await client.post(f"{USER_SERVICE_URL}/auth/login/complete", json=complete_data, timeout=5.0)
                        
                        if response2.status_code == 200:
                            token_data = response2.json()
                            self.user_token = token_data.get("access_token") or token_data.get("token")
                            if self.user_token:
                                self.log_test("User Service Login", "PASS", f"Got JWT token: {self.user_token[:20]}...")
                                
                                # Decode and analyze JWT token contents
                                try:
                                    # Decode without verification to inspect contents
                                    decoded_token = jwt.decode(self.user_token, options={"verify_signature": False})
                                    print(f"\n🔍 JWT Token Analysis:")
                                    print(f"   - Algorithm: {jwt.get_unverified_header(self.user_token).get('alg', 'unknown')}")
                                    print(f"   - Token Type: {jwt.get_unverified_header(self.user_token).get('typ', 'unknown')}")
                                    print(f"   - Payload:")
                                    for key, value in decoded_token.items():
                                        print(f"     * {key}: {value}")
                                    
                                    # Check critical claims for OMS compatibility
                                    critical_claims = ['sub', 'user_id', 'roles', 'scope', 'exp', 'iat']
                                    missing_claims = [claim for claim in critical_claims if claim not in decoded_token]
                                    if missing_claims:
                                        print(f"\n   ⚠️  Missing critical claims: {missing_claims}")
                                    
                                    # Save decoded token for analysis
                                    with open("jwt_token_analysis.json", "w") as f:
                                        json.dump({
                                            "header": jwt.get_unverified_header(self.user_token),
                                            "payload": decoded_token,
                                            "raw_token": self.user_token,
                                            "timestamp": datetime.now().isoformat()
                                        }, f, indent=2)
                                    print(f"   📄 Full analysis saved to: jwt_token_analysis.json\n")
                                    
                                except Exception as e:
                                    print(f"\n   ⚠️  Failed to decode JWT: {str(e)}\n")
                                
                                return True
                            else:
                                self.log_test("User Service Login", "FAIL", f"No access_token in response")
                                return False
                        else:
                            self.log_test("User Service Login", "FAIL", f"Step 2 failed: {response2.status_code} - {response2.text}")
                            return False
                    else:
                        self.log_test("User Service Login", "FAIL", f"Step 1 unexpected response: {data}")
                        return False
                elif response.status_code == 401:
                    self.log_test("User Service Login", "FAIL", f"Invalid credentials")
                    return False
                else:
                    self.log_test("User Service Login", "ERROR", f"Step 1 error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            self.log_test("User Service Login", "ERROR", f"Login request failed: {str(e)}")
            return False
    
    async def test_organization_api_real_call(self):
        """Test 4: REAL Organization API call with JWT"""
        if not self.user_token:
            self.log_test("Organization API", "SKIP", "No JWT token available")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.user_token}"}
                response = await client.get(f"{USER_SERVICE_URL}/api/v1/organizations/", headers=headers, timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_test("Organization API", "PASS", f"Got {len(data)} organizations")
                    return True
                elif response.status_code == 401:
                    self.log_test("Organization API", "FAIL", "JWT token rejected")
                    return False
                else:
                    self.log_test("Organization API", "FAIL", f"API call failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            self.log_test("Organization API", "ERROR", f"API request failed: {str(e)}")
            return False
    
    async def test_oms_property_api_with_user_token(self):
        """Test 5: OMS Property API with User Service JWT - CROSS-SERVICE"""
        if not self.user_token:
            self.log_test("OMS Property API", "SKIP", "No JWT token available")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.user_token}"}
                response = await client.get(f"{OMS_SERVICE_URL}/api/v1/properties/", headers=headers, timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_test("OMS Property API", "PASS", f"Cross-service JWT accepted, got {len(data) if isinstance(data, list) else 'response'}")
                    return True
                elif response.status_code == 401:
                    self.log_test("OMS Property API", "FAIL", "Cross-service JWT token rejected")
                    return False
                else:
                    self.log_test("OMS Property API", "FAIL", f"API call failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            self.log_test("OMS Property API", "ERROR", f"Cross-service API request failed: {str(e)}")
            return False
    
    async def test_nginx_gateway_routing(self):
        """Test 6: Nginx Gateway routing"""
        try:
            async with httpx.AsyncClient() as client:
                # Test if Nginx is routing to services
                response = await client.get(f"{NGINX_GATEWAY_URL}/health", timeout=5.0)
                
                if response.status_code == 200:
                    self.log_test("Nginx Gateway", "PASS", f"Gateway routing works: {response.status_code}")
                    return True
                else:
                    self.log_test("Nginx Gateway", "FAIL", f"Gateway failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_test("Nginx Gateway", "ERROR", f"Gateway connection failed: {str(e)}")
            return False
    
    async def run_complete_integration_test(self):
        """Run complete real integration test"""
        print("\\n=== 🔥 REAL Service-to-Service Integration Test ===\\n")
        
        # Test sequence - each depends on previous
        tests = [
            self.test_user_service_direct_access,
            self.test_oms_service_direct_access,
            self.test_user_service_login,
            self.test_organization_api_real_call,
            self.test_oms_property_api_with_user_token,
            self.test_nginx_gateway_routing
        ]
        
        results = []
        
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                print(f"Test {test.__name__} crashed: {e}")
                results.append(False)
        
        # Results analysis
        passed = sum(results)
        total = len(results)
        success_rate = (passed / total) * 100
        
        print(f"\\n=== 📊 Real Integration Test Results ===")
        print(f"🎯 Success Rate: {success_rate:.1f}% ({passed}/{total})")
        
        for result in self.test_results:
            print(f"  {result['status']}: {result['test']} - {result['details']}")
        
        # Save detailed results
        with open("real_integration_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\\n📄 Detailed results: real_integration_test_results.json")
        
        # Critical assessment
        if success_rate == 100:
            print("\\n🎉 EXCELLENT: True service integration achieved!")
        elif success_rate >= 80:
            print("\\n✅ GOOD: Most integrations working")
        elif success_rate >= 60:
            print("\\n⚠️ MODERATE: Significant integration issues")
        else:
            print("\\n🚨 POOR: Integration fundamentally broken")
        
        return success_rate

async def main():
    """Main execution"""
    print("🚀 Starting REAL Service Integration Test...")
    tester = RealIntegrationTester()
    success_rate = await tester.run_complete_integration_test()
    
    exit_code = 0 if success_rate >= 80 else 1
    print(f"\\n🎯 Exit Code: {exit_code} (Success Rate: {success_rate:.1f}%)")
    return exit_code

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)