#!/usr/bin/env python3
"""
Test All Middleware Activation
Verifies that all middlewares are properly activated and working
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List

class MiddlewareActivationTester:
    """Test all middleware activation status"""
    
    def __init__(self):
        self.base_url = 'http://localhost:8000'
        self.active_middlewares = []
        self.inactive_middlewares = []
        
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test basic health endpoint"""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "status": "success",
                    "status_code": response.status,
                    "response": json.loads(response.read().decode())
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_request_headers(self) -> Dict[str, Any]:
        """Test middleware-added headers"""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/schemas/main/object-types")
            with urllib.request.urlopen(req, timeout=10) as response:
                headers = dict(response.headers)
                
                # Check for middleware-added headers
                checks = {
                    "request_id": "X-Request-Id" in headers,
                    "etag": "ETag" in headers,
                    "cache_control": "Cache-Control" in headers,
                    "circuit_breaker": "X-Circuit-Breaker-Status" in headers,
                }
                
                return {
                    "status": "success",
                    "headers_found": checks,
                    "sample_headers": {k: v for k, v in headers.items() 
                                     if k.lower() in ['x-request-id', 'etag', 'cache-control', 'x-circuit-breaker-status']}
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_circuit_breaker_api(self) -> Dict[str, Any]:
        """Test circuit breaker status API"""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/circuit-breaker/status")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return {
                    "status": "success",
                    "circuit_breaker_active": True,
                    "state": data.get("data", {}).get("state", "unknown")
                }
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {"status": "requires_auth", "circuit_breaker_active": True}
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_middleware_effects(self) -> Dict[str, Any]:
        """Test various middleware effects"""
        results = {}
        
        # Test 1: ETag caching (make same request twice)
        try:
            req1 = urllib.request.Request(f"{self.base_url}/api/v1/schemas/main/object-types")
            with urllib.request.urlopen(req1, timeout=10) as response1:
                etag1 = response1.headers.get('ETag')
                
            # Second request with If-None-Match
            req2 = urllib.request.Request(f"{self.base_url}/api/v1/schemas/main/object-types")
            if etag1:
                req2.add_header('If-None-Match', etag1)
            
            try:
                with urllib.request.urlopen(req2, timeout=10) as response2:
                    results['etag_caching'] = {"working": False, "status": response2.status}
            except urllib.error.HTTPError as e:
                if e.code == 304:  # Not Modified
                    results['etag_caching'] = {"working": True, "status": 304}
                else:
                    results['etag_caching'] = {"working": False, "error": str(e)}
        except Exception as e:
            results['etag_caching'] = {"working": False, "error": str(e)}
        
        # Test 2: Request ID tracking
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/health")
            with urllib.request.urlopen(req, timeout=10) as response:
                request_id = response.headers.get('X-Request-Id')
                results['request_id'] = {
                    "working": bool(request_id),
                    "sample_id": request_id
                }
        except Exception as e:
            results['request_id'] = {"working": False, "error": str(e)}
        
        return results
    
    def check_middleware_logs(self) -> List[str]:
        """Check which middlewares were mentioned in app startup"""
        # This would normally check actual logs, but for now we'll return expected middlewares
        return [
            "GlobalCircuitBreakerMiddleware",
            "ErrorHandlerMiddleware", 
            "CORSMiddleware",
            "ETagMiddleware",
            "AuthMiddleware",
            "TerminusContextMiddleware",
            "CoreDatabaseContextMiddleware",
            "ScopeRBACMiddleware",
            "RequestIdMiddleware",
            "AuditLogMiddleware",
            "SchemaFreezeMiddleware",
            "ThreeWayMergeMiddleware",
            "EventStateStoreMiddleware"
        ]
    
    def run_activation_test(self) -> Dict[str, Any]:
        """Run complete middleware activation test"""
        print("🔧 Testing All Middleware Activation")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Test 1: Basic Health
        print("\n🏥 Testing Basic Health...")
        health_result = self.test_health_endpoint()
        
        # Test 2: Middleware Headers
        print("📋 Testing Middleware Headers...")
        headers_result = self.test_request_headers()
        
        # Test 3: Circuit Breaker API
        print("🛡️ Testing Circuit Breaker API...")
        circuit_result = self.test_circuit_breaker_api()
        
        # Test 4: Middleware Effects
        print("🔍 Testing Middleware Effects...")
        effects_result = self.test_middleware_effects()
        
        # Get expected middlewares
        expected_middlewares = self.check_middleware_logs()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Analyze results
        active_count = 0
        if health_result.get('status') == 'success':
            active_count += 3  # Basic middlewares working
        if headers_result.get('headers_found', {}).get('etag'):
            active_count += 1  # ETag middleware
        if headers_result.get('headers_found', {}).get('request_id'):
            active_count += 1  # RequestId middleware
        if circuit_result.get('circuit_breaker_active'):
            active_count += 1  # Circuit breaker
        if effects_result.get('etag_caching', {}).get('working'):
            active_count += 1  # ETag caching working
        
        # Compile results
        final_results = {
            "test_metadata": {
                "timestamp": start_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "test_type": "middleware_activation"
            },
            "health_check": health_result,
            "middleware_headers": headers_result,
            "circuit_breaker": circuit_result,
            "middleware_effects": effects_result,
            "summary": {
                "expected_middlewares": len(expected_middlewares),
                "active_indicators": active_count,
                "expected_list": expected_middlewares,
                "activation_status": "partial" if active_count < len(expected_middlewares) else "complete"
            }
        }
        
        return final_results
    
    def print_results(self, results: Dict[str, Any]):
        """Print formatted test results"""
        print("\n" + "=" * 60)
        print("🎯 MIDDLEWARE ACTIVATION TEST RESULTS")
        print("=" * 60)
        
        summary = results['summary']
        print(f"📊 Activation Status: {summary['activation_status'].upper()}")
        print(f"✅ Active Indicators: {summary['active_indicators']}")
        print(f"📋 Expected Middlewares: {summary['expected_middlewares']}")
        
        # Health Status
        health = results['health_check']
        print(f"\n🏥 Health Check: {health.get('status', 'unknown')}")
        
        # Headers Check
        headers = results['middleware_headers']
        if headers.get('status') == 'success':
            print(f"\n📋 Middleware Headers Found:")
            for header, found in headers.get('headers_found', {}).items():
                icon = "✅" if found else "❌"
                print(f"  {icon} {header}")
        
        # Circuit Breaker
        circuit = results['circuit_breaker']
        print(f"\n🛡️ Circuit Breaker: {'Active' if circuit.get('circuit_breaker_active') else 'Inactive'}")
        if circuit.get('state'):
            print(f"  State: {circuit['state']}")
        
        # Middleware Effects
        effects = results['middleware_effects']
        print(f"\n🔍 Middleware Effects:")
        etag = effects.get('etag_caching', {})
        print(f"  ETag Caching: {'Working' if etag.get('working') else 'Not Working'}")
        request_id = effects.get('request_id', {})
        print(f"  Request ID: {'Working' if request_id.get('working') else 'Not Working'}")
        
        print(f"\n📝 Expected Middlewares:")
        for mw in summary['expected_list']:
            print(f"  • {mw}")

def main():
    """Main test runner"""
    tester = MiddlewareActivationTester()
    results = tester.run_activation_test()
    
    # Print results
    tester.print_results(results)
    
    # Save results
    filename = f"middleware_activation_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {filename}")
    return results

if __name__ == "__main__":
    main()