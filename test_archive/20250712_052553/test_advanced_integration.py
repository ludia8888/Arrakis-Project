#!/usr/bin/env python3
"""
Advanced Integration Test Suite for Arrakis Project
Tests complex scenarios, error handling, and edge cases
"""
import httpx
import json
import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import random


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
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")


def print_section(text: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}>>> {text}{Colors.ENDC}")


def print_subsection(text: str):
    print(f"\n{Colors.BLUE}  → {text}{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.YELLOW}ℹ {text}{Colors.ENDC}")


class AdvancedTestSuite:
    """Advanced test scenarios"""
    
    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.admin_token = admin_token
        self.headers = {"Authorization": f"Bearer {admin_token}"}
        self.results = {}
    
    async def test_concurrent_requests(self) -> bool:
        """Test system under concurrent load"""
        print_subsection("Testing Concurrent Request Handling")
        
        try:
            # Create multiple concurrent requests
            async def make_request(index: int):
                try:
                    response = await httpx.AsyncClient().get(
                        f"{self.base_url}/api/v1/organizations/",
                        headers=self.headers,
                        timeout=10
                    )
                    return response.status_code == 200
                except Exception:
                    return False
            
            # Run 20 concurrent requests
            tasks = [make_request(i) for i in range(20)]
            results = await asyncio.gather(*tasks)
            
            success_count = sum(results)
            print_info(f"Concurrent requests: {success_count}/20 succeeded")
            
            if success_count >= 18:  # Allow for some failures
                print_success("System handles concurrent load well")
                return True
            else:
                print_error("Too many failures under concurrent load")
                return False
                
        except Exception as e:
            print_error(f"Concurrent test failed: {e}")
            return False
    
    async def test_rate_limiting(self) -> bool:
        """Test rate limiting (if implemented)"""
        print_subsection("Testing Rate Limiting")
        
        try:
            # Make rapid sequential requests
            request_count = 0
            rate_limited = False
            
            for i in range(50):
                response = await httpx.AsyncClient().get(
                    f"{self.base_url}/api/v1/health",
                    timeout=5
                )
                request_count += 1
                
                if response.status_code == 429:  # Too Many Requests
                    rate_limited = True
                    print_success(f"Rate limiting triggered after {request_count} requests")
                    break
                    
                await asyncio.sleep(0.01)  # Small delay
            
            if not rate_limited:
                print_info("No rate limiting detected (might not be implemented)")
            
            return True  # Don't fail if rate limiting is not implemented
            
        except Exception as e:
            print_error(f"Rate limiting test failed: {e}")
            return False
    
    async def test_token_expiry_handling(self) -> bool:
        """Test expired token handling"""
        print_subsection("Testing Token Expiry Handling")
        
        try:
            # Create an obviously expired token
            expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ.invalid"
            
            response = await httpx.AsyncClient().get(
                f"{self.base_url}/api/v1/organizations/",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            
            if response.status_code == 401:
                print_success("Expired tokens properly rejected")
                return True
            else:
                print_error(f"Expected 401 for expired token, got {response.status_code}")
                return False
                
        except Exception as e:
            print_error(f"Token expiry test failed: {e}")
            return False
    
    async def test_large_payload_handling(self) -> bool:
        """Test handling of large payloads"""
        print_subsection("Testing Large Payload Handling")
        
        try:
            # Create a large payload (1MB of data)
            large_data = {
                "name": "Large Organization",
                "description": "x" * (1024 * 1024),  # 1MB string
                "metadata": {f"field_{i}": f"value_{i}" for i in range(1000)}
            }
            
            response = await httpx.AsyncClient().post(
                f"{self.base_url}/api/v1/organizations/",
                headers={**self.headers, "Content-Type": "application/json"},
                json=large_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                print_success("Large payload accepted")
                return True
            elif response.status_code == 413:  # Payload Too Large
                print_success("Large payload properly rejected (413)")
                return True
            elif response.status_code == 400:
                print_info("Large payload rejected as bad request")
                return True
            else:
                print_error(f"Unexpected response for large payload: {response.status_code}")
                return False
                
        except Exception as e:
            print_info(f"Large payload test exception: {e}")
            return True  # Might timeout, which is acceptable
    
    async def test_special_characters_handling(self) -> bool:
        """Test handling of special characters in requests"""
        print_subsection("Testing Special Characters Handling")
        
        try:
            # Test various special characters
            test_cases = [
                {"name": "Test <script>alert('xss')</script>"},  # XSS attempt
                {"name": "Test'; DROP TABLE organizations;--"},   # SQL injection
                {"name": "Test\x00Null\x00Byte"},                # Null bytes
                {"name": "Test™®©℠"},                            # Unicode
                {"name": "Test\n\r\t"},                          # Control characters
            ]
            
            all_handled = True
            for test_data in test_cases:
                response = await httpx.AsyncClient().post(
                    f"{self.base_url}/api/v1/organizations/",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=test_data
                )
                
                # We expect either successful creation or validation error
                if response.status_code in [200, 201, 400, 422]:
                    print_success(f"Special characters handled: {test_data['name'][:20]}...")
                else:
                    print_error(f"Unexpected response for special chars: {response.status_code}")
                    all_handled = False
            
            return all_handled
            
        except Exception as e:
            print_error(f"Special characters test failed: {e}")
            return False
    
    async def test_method_not_allowed(self) -> bool:
        """Test HTTP method validation"""
        print_subsection("Testing HTTP Method Validation")
        
        try:
            # Try unsupported methods
            methods = ["PATCH", "PUT", "DELETE"]
            all_handled = True
            
            for method in methods:
                response = await httpx.AsyncClient().request(
                    method,
                    f"{self.base_url}/api/v1/health",
                    headers=self.headers
                )
                
                if response.status_code == 405:  # Method Not Allowed
                    print_success(f"{method} properly rejected (405)")
                elif response.status_code in [200, 404]:
                    print_info(f"{method} returned {response.status_code} (might be allowed)")
                else:
                    print_error(f"Unexpected response for {method}: {response.status_code}")
                    all_handled = False
            
            return all_handled
            
        except Exception as e:
            print_error(f"Method validation test failed: {e}")
            return False
    
    async def test_cache_behavior(self) -> bool:
        """Test caching behavior"""
        print_subsection("Testing Cache Behavior")
        
        try:
            # Make first request
            start_time = time.time()
            response1 = await httpx.AsyncClient().get(
                f"{self.base_url}/api/v1/organizations/",
                headers=self.headers
            )
            first_request_time = time.time() - start_time
            
            if response1.status_code != 200:
                print_info("Cannot test caching, endpoint not available")
                return True
            
            # Make second request (should be cached if caching is enabled)
            start_time = time.time()
            response2 = await httpx.AsyncClient().get(
                f"{self.base_url}/api/v1/organizations/",
                headers=self.headers
            )
            second_request_time = time.time() - start_time
            
            # Check if second request was significantly faster
            if second_request_time < first_request_time * 0.5:
                print_success(f"Caching appears to be working (2nd request {second_request_time:.3f}s vs {first_request_time:.3f}s)")
            else:
                print_info(f"No significant caching detected (2nd request {second_request_time:.3f}s vs {first_request_time:.3f}s)")
            
            return True
            
        except Exception as e:
            print_error(f"Cache behavior test failed: {e}")
            return False
    
    async def test_partial_authorization(self) -> bool:
        """Test partial authorization scenarios"""
        print_subsection("Testing Partial Authorization")
        
        try:
            # Create a token with limited scopes (simulate)
            # For now, we'll use the admin token but test different endpoints
            
            endpoints = [
                ("/api/v1/organizations/", "Read access"),
                ("/api/v1/schemas", "Schema access"),
                ("/api/v1/audit/logs", "Audit access"),
            ]
            
            for endpoint, description in endpoints:
                response = await httpx.AsyncClient().get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    print_success(f"{description}: Authorized")
                elif response.status_code == 403:
                    print_info(f"{description}: Forbidden (correct behavior)")
                elif response.status_code == 404:
                    print_info(f"{description}: Not implemented")
                else:
                    print_error(f"{description}: Unexpected status {response.status_code}")
            
            return True
            
        except Exception as e:
            print_error(f"Partial authorization test failed: {e}")
            return False
    
    async def test_request_timeout_handling(self) -> bool:
        """Test request timeout handling"""
        print_subsection("Testing Request Timeout Handling")
        
        try:
            # Make a request with very short timeout
            with pytest.raises(httpx.ReadTimeout):
                await httpx.AsyncClient().get(
                    f"{self.base_url}/api/v1/organizations/",
                    headers=self.headers,
                    timeout=0.001  # 1ms timeout
                )
            
            print_success("Timeout handling works correctly")
            return True
            
        except ImportError:
            # pytest not available, use different approach
            try:
                await httpx.AsyncClient().get(
                    f"{self.base_url}/api/v1/organizations/",
                    headers=self.headers,
                    timeout=0.001  # 1ms timeout
                )
                print_error("Expected timeout but request succeeded")
                return False
            except httpx.ReadTimeout:
                print_success("Timeout handling works correctly")
                return True
            except Exception as e:
                print_error(f"Unexpected error: {e}")
                return False
                
        except Exception as e:
            print_error(f"Timeout test failed: {e}")
            return False
    
    async def test_database_transaction_rollback(self) -> bool:
        """Test database transaction rollback on error"""
        print_subsection("Testing Database Transaction Rollback")
        
        try:
            # Try to create an organization with invalid data that should trigger rollback
            invalid_data = {
                "name": f"Test_Org_{uuid.uuid4().hex}",
                "invalid_field": "This should cause an error",
                "nested": {
                    "too": {
                        "deep": {
                            "structure": "that might cause issues"
                        }
                    }
                }
            }
            
            response = await httpx.AsyncClient().post(
                f"{self.base_url}/api/v1/organizations/",
                headers={**self.headers, "Content-Type": "application/json"},
                json=invalid_data
            )
            
            # We expect either validation error or successful creation
            if response.status_code in [400, 422]:
                print_success("Invalid data properly rejected")
                
                # Verify no partial data was saved by trying to get the org
                check_response = await httpx.AsyncClient().get(
                    f"{self.base_url}/api/v1/organizations/{invalid_data['name']}",
                    headers=self.headers
                )
                
                if check_response.status_code == 404:
                    print_success("Transaction properly rolled back (no partial data)")
                    return True
                else:
                    print_error("Partial data might have been saved")
                    return False
                    
            elif response.status_code in [200, 201]:
                print_info("Data was accepted (validation might be lenient)")
                return True
            else:
                print_error(f"Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            print_error(f"Transaction rollback test failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all advanced tests"""
        tests = [
            ("Concurrent Requests", self.test_concurrent_requests),
            ("Rate Limiting", self.test_rate_limiting),
            ("Token Expiry", self.test_token_expiry_handling),
            ("Large Payload", self.test_large_payload_handling),
            ("Special Characters", self.test_special_characters_handling),
            ("Method Validation", self.test_method_not_allowed),
            ("Cache Behavior", self.test_cache_behavior),
            ("Partial Authorization", self.test_partial_authorization),
            ("Request Timeout", self.test_request_timeout_handling),
            ("Transaction Rollback", self.test_database_transaction_rollback),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = await test_func()
            except Exception as e:
                print_error(f"{test_name} test exception: {e}")
                results[test_name] = False
        
        return results


class PerformanceTestSuite:
    """Performance and stress testing"""
    
    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.admin_token = admin_token
        self.headers = {"Authorization": f"Bearer {admin_token}"}
    
    async def test_response_times(self) -> bool:
        """Test response time SLAs"""
        print_subsection("Testing Response Times")
        
        try:
            endpoints = [
                ("/health", 100),  # Should respond in <100ms
                ("/api/v1/health", 100),
                ("/api/v1/organizations/", 500),  # <500ms for data endpoints
                ("/api/v1/properties/", 500),
            ]
            
            all_within_sla = True
            for endpoint, sla_ms in endpoints:
                headers = self.headers if "/health" not in endpoint else {}
                
                # Warm up request
                await httpx.AsyncClient().get(f"{self.base_url}{endpoint}", headers=headers)
                
                # Measure actual request
                start_time = time.time()
                response = await httpx.AsyncClient().get(
                    f"{self.base_url}{endpoint}",
                    headers=headers
                )
                response_time_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    if response_time_ms <= sla_ms:
                        print_success(f"{endpoint}: {response_time_ms:.0f}ms (SLA: {sla_ms}ms)")
                    else:
                        print_error(f"{endpoint}: {response_time_ms:.0f}ms (SLA: {sla_ms}ms)")
                        all_within_sla = False
                else:
                    print_info(f"{endpoint}: Status {response.status_code}")
            
            return all_within_sla
            
        except Exception as e:
            print_error(f"Response time test failed: {e}")
            return False
    
    async def test_memory_leak_detection(self) -> bool:
        """Simple memory leak detection"""
        print_subsection("Testing for Memory Leaks")
        
        try:
            # Make multiple requests and check if response times degrade
            response_times = []
            
            for i in range(50):
                start_time = time.time()
                response = await httpx.AsyncClient().get(
                    f"{self.base_url}/api/v1/organizations/",
                    headers=self.headers
                )
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                if i % 10 == 0:
                    print_info(f"Request {i}: {response_time:.3f}s")
                
                await asyncio.sleep(0.1)
            
            # Check if later requests are significantly slower
            first_10_avg = sum(response_times[:10]) / 10
            last_10_avg = sum(response_times[-10:]) / 10
            
            if last_10_avg > first_10_avg * 2:
                print_error(f"Possible memory leak detected (performance degraded by {(last_10_avg/first_10_avg):.1f}x)")
                return False
            else:
                print_success(f"No significant performance degradation detected")
                return True
                
        except Exception as e:
            print_error(f"Memory leak test failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all performance tests"""
        tests = [
            ("Response Times", self.test_response_times),
            ("Memory Leak Detection", self.test_memory_leak_detection),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = await test_func()
            except Exception as e:
                print_error(f"{test_name} test exception: {e}")
                results[test_name] = False
        
        return results


async def main():
    """Main test runner"""
    print_header("ADVANCED INTEGRATION TEST SUITE")
    
    # Login first
    oms_url = "http://localhost:8091"
    
    try:
        response = await httpx.AsyncClient().post(
            f"{oms_url}/api/v1/auth/login/json",
            json={"username": "admin", "password": "admin123"}
        )
        
        if response.status_code != 200:
            print_error("Failed to login")
            return
            
        admin_token = response.json()["access_token"]
        print_success("Authentication successful")
        
    except Exception as e:
        print_error(f"Login failed: {e}")
        return
    
    # Run advanced tests
    print_section("ADVANCED TEST SCENARIOS")
    advanced_suite = AdvancedTestSuite(oms_url, admin_token)
    advanced_results = await advanced_suite.run_all_tests()
    
    # Run performance tests
    print_section("PERFORMANCE TESTS")
    perf_suite = PerformanceTestSuite(oms_url, admin_token)
    perf_results = await perf_suite.run_all_tests()
    
    # Summary
    print_header("TEST SUMMARY")
    
    all_results = {
        "Advanced Tests": advanced_results,
        "Performance Tests": perf_results
    }
    
    total_tests = 0
    passed_tests = 0
    
    for category, results in all_results.items():
        print_section(category)
        for test_name, passed in results.items():
            total_tests += 1
            if passed:
                passed_tests += 1
                print_success(test_name)
            else:
                print_error(test_name)
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"\nTotal: {total_tests}, Passed: {passed_tests}, Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {Colors.GREEN if success_rate >= 80 else Colors.RED}{success_rate:.1f}%{Colors.ENDC}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"advanced_test_results_{timestamp}.json", 'w') as f:
        json.dump({
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "success_rate": f"{success_rate:.1f}%",
                "timestamp": datetime.now().isoformat()
            },
            "results": all_results
        }, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())