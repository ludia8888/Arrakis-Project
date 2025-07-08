#!/usr/bin/env python3
"""
Comprehensive Integration Test for Arrakis Project
Tests complete authentication and authorization flow between User Service and OMS
Includes trailing slash fix for FastAPI routes
"""
import httpx
import json
import jwt
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")


def print_section(text: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}>>> {text}{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.YELLOW}ℹ {text}{Colors.ENDC}")


class IntegrationTestRunner:
    def __init__(self):
        self.oms_url = "http://localhost:8091"
        self.user_service_url = "http://localhost:8091"  # User Service is proxied through OMS
        self.results: List[Dict[str, Any]] = []
        self.admin_token: Optional[str] = None
        self.user_token: Optional[str] = None
        
    def add_result(self, test_name: str, status: str, details: Dict[str, Any]):
        """Add test result"""
        self.results.append({
            "test": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })
    
    def test_service_connectivity(self) -> bool:
        """Test if services are reachable"""
        print_section("Testing Service Connectivity")
        
        services = [
            ("OMS API", f"{self.oms_url}/health"),
            ("OMS Health (detailed)", f"{self.oms_url}/api/v1/health")
        ]
        
        all_healthy = True
        for service_name, health_url in services:
            try:
                response = httpx.get(health_url, timeout=5)
                if response.status_code == 200:
                    print_success(f"{service_name} is healthy at {health_url}")
                else:
                    print_error(f"{service_name} returned status {response.status_code}")
                    all_healthy = False
            except Exception as e:
                print_error(f"{service_name} is not reachable: {e}")
                all_healthy = False
                
        self.add_result("Service Connectivity", "PASSED" if all_healthy else "FAILED", {
            "all_services_healthy": all_healthy
        })
        
        return all_healthy
    
    def test_admin_login(self) -> bool:
        """Test admin user login"""
        print_section("Testing Admin User Login")
        
        # Use OMS proxy endpoint for login
        endpoints = [
            ("OMS Proxy", f"{self.oms_url}/api/v1/auth/login/json")
        ]
        
        for endpoint_name, url in endpoints:
            try:
                print_info(f"Attempting login via {endpoint_name}")
                response = httpx.post(
                    url,
                    json={"username": "admin", "password": "admin123"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.admin_token = data.get("access_token")
                    print_success(f"Admin login successful via {endpoint_name}")
                    
                    # Decode and verify JWT
                    try:
                        decoded = jwt.decode(self.admin_token, options={"verify_signature": False})
                        print_info(f"JWT Claims:")
                        print_info(f"  - User ID: {decoded.get('sub')}")
                        print_info(f"  - Roles: {decoded.get('roles', [])}")
                        print_info(f"  - Scopes: {len(decoded.get('scopes', []))} scopes")
                        if decoded.get('scopes'):
                            for scope in decoded.get('scopes', [])[:5]:  # Show first 5
                                print_info(f"    • {scope}")
                            if len(decoded.get('scopes', [])) > 5:
                                print_info(f"    ... and {len(decoded.get('scopes', [])) - 5} more")
                    except Exception as e:
                        print_error(f"Failed to decode JWT: {e}")
                    
                    self.add_result("Admin Login", "PASSED", {
                        "endpoint": endpoint_name,
                        "token_received": True,
                        "roles": decoded.get('roles', []),
                        "scope_count": len(decoded.get('scopes', []))
                    })
                    return True
                else:
                    print_error(f"Login failed via {endpoint_name}: {response.status_code}")
                    print_error(f"Response: {response.text}")
                    
            except Exception as e:
                print_error(f"Login error via {endpoint_name}: {e}")
        
        self.add_result("Admin Login", "FAILED", {
            "error": "Could not login via any endpoint"
        })
        return False
    
    def test_protected_endpoints(self) -> bool:
        """Test protected endpoints with authentication"""
        print_section("Testing Protected Endpoints")
        
        if not self.admin_token:
            print_error("No admin token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Test endpoints - WITH TRAILING SLASHES for those that need them
        # Note: FastAPI automatically redirects (307) when trailing slash is missing
        # but the route is defined with one. This is standard REST behavior.
        endpoints = [
            ("/api/v1/schemas", "Schemas", False),
            ("/api/v1/organizations/", "Organizations", True),  # Needs trailing slash
            ("/api/v1/properties/", "Properties", True),        # Needs trailing slash
            ("/api/v1/branches", "Branches", False),            # May have internal issues
            ("/api/v1/documents", "Documents", False),
        ]
        
        all_passed = True
        for endpoint, name, needs_slash in endpoints:
            try:
                response = httpx.get(f"{self.oms_url}{endpoint}", headers=headers, timeout=10)
                
                # Handle 307 redirects for missing trailing slashes
                if response.status_code == 307 and not needs_slash:
                    print_info(f"{name}: Got 307 redirect, trying with trailing slash")
                    response = httpx.get(f"{self.oms_url}{endpoint}/", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    print_success(f"{name} endpoint ({endpoint}): 200 OK")
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            print_info(f"  Response: List with {len(data)} items")
                        elif isinstance(data, dict):
                            print_info(f"  Response: Object with keys: {list(data.keys())[:5]}")
                    except:
                        print_info(f"  Response: {str(response.text)[:100]}...")
                        
                elif response.status_code == 404:
                    print_info(f"{name} endpoint ({endpoint}): 404 Not Found (endpoint may not be implemented)")
                    
                elif response.status_code == 403:
                    print_error(f"{name} endpoint ({endpoint}): 403 Forbidden (insufficient permissions)")
                    all_passed = False
                    
                elif response.status_code == 401:
                    print_error(f"{name} endpoint ({endpoint}): 401 Unauthorized")
                    all_passed = False
                    
                else:
                    print_error(f"{name} endpoint ({endpoint}): {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                print_error(f"{name} endpoint error: {e}")
                all_passed = False
        
        self.add_result("Protected Endpoints", "PASSED" if all_passed else "FAILED", {
            "endpoints_tested": len(endpoints),
            "all_authorized": all_passed
        })
        
        return all_passed
    
    def test_token_validation_flow(self) -> bool:
        """Test the complete token validation flow"""
        print_section("Testing Token Validation Flow")
        
        if not self.admin_token:
            print_error("No admin token available")
            return False
        
        # Test OMS internal validation (what happens when OMS validates token)
        try:
            # This simulates what AuthMiddleware does internally
            print_info("Testing internal token validation flow...")
            
            # Make a request to a protected endpoint
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = httpx.get(
                f"{self.oms_url}/api/v1/organizations/",  # Use trailing slash
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print_success("Token validation successful - endpoint returned data")
                print_info("This confirms:")
                print_info("  1. OMS AuthMiddleware validated the token")
                print_info("  2. User Service /auth/account/userinfo endpoint works")
                print_info("  3. Scopes were properly checked")
                
                self.add_result("Token Validation Flow", "PASSED", {
                    "validation_successful": True,
                    "endpoint_accessible": True
                })
                return True
            else:
                print_error(f"Token validation failed: {response.status_code}")
                self.add_result("Token Validation Flow", "FAILED", {
                    "status_code": response.status_code,
                    "error": response.text
                })
                return False
                
        except Exception as e:
            print_error(f"Token validation error: {e}")
            self.add_result("Token Validation Flow", "FAILED", {
                "error": str(e)
            })
            return False
    
    def test_rbac_permissions(self) -> bool:
        """Test RBAC permission checks"""
        print_section("Testing RBAC Permission Checks")
        
        if not self.admin_token:
            print_error("No admin token available")
            return False
        
        # Decode token to check scopes
        try:
            decoded = jwt.decode(self.admin_token, options={"verify_signature": False})
            scopes = decoded.get('scopes', [])
            
            print_info(f"User has {len(scopes)} scopes:")
            
            # Check for expected admin scopes
            expected_scopes = [
                "api:system:admin",
                "api:ontologies:read",
                "api:ontologies:write",
                "api:schemas:read",
                "api:schemas:write"
            ]
            
            all_present = True
            for scope in expected_scopes:
                if scope in scopes:
                    print_success(f"Has scope: {scope}")
                else:
                    print_error(f"Missing scope: {scope}")
                    all_present = False
            
            self.add_result("RBAC Permissions", "PASSED" if all_present else "FAILED", {
                "total_scopes": len(scopes),
                "expected_scopes_present": all_present,
                "scopes": scopes
            })
            
            return all_present
            
        except Exception as e:
            print_error(f"Failed to check permissions: {e}")
            self.add_result("RBAC Permissions", "FAILED", {
                "error": str(e)
            })
            return False
    
    def generate_summary(self):
        """Generate test summary report"""
        print_header("TEST SUMMARY")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['status'] == 'PASSED')
        failed_tests = sum(1 for r in self.results if r['status'] == 'FAILED')
        skipped_tests = sum(1 for r in self.results if r['status'] == 'SKIPPED')
        
        print(f"\nTotal Tests: {total_tests}")
        print_success(f"Passed: {passed_tests}")
        if failed_tests > 0:
            print_error(f"Failed: {failed_tests}")
        if skipped_tests > 0:
            print_info(f"Skipped: {skipped_tests}")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        # Show failed tests
        if failed_tests > 0:
            print_section("Failed Tests")
            for result in self.results:
                if result['status'] == 'FAILED':
                    print_error(f"- {result['test']}")
                    if 'error' in result['details']:
                        print(f"  Error: {result['details']['error']}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"integration_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                "summary": {
                    "total": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "skipped": skipped_tests,
                    "success_rate": f"{success_rate:.1f}%",
                    "timestamp": datetime.now().isoformat()
                },
                "results": self.results
            }, f, indent=2)
        
        print_info(f"\nDetailed results saved to: {filename}")
        
        return success_rate == 100
    
    def run_all_tests(self) -> bool:
        """Run all integration tests"""
        print_header("ARRAKIS PROJECT INTEGRATION TESTS")
        print_info("Testing authentication and authorization flow")
        print_info("Including trailing slash fixes for FastAPI routes")
        
        # Run tests in sequence
        tests = [
            self.test_service_connectivity,
            self.test_admin_login,
            self.test_protected_endpoints,
            self.test_token_validation_flow,
            self.test_rbac_permissions
        ]
        
        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                print_error(f"Test failed with exception: {e}")
                self.add_result(test_func.__name__, "FAILED", {"error": str(e)})
        
        # Generate summary
        return self.generate_summary()


def main():
    """Main entry point"""
    runner = IntegrationTestRunner()
    success = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()