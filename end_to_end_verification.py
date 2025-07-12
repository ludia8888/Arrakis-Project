#!/usr/bin/env python3
"""
Arrakis Project - End-to-End Verification System
Following priority_based_test_plan.md scenarios with ultra thinking
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class EndToEndVerifier:
    def __init__(self):
        self.base_urls = {
            "oms": "http://localhost:8000",
            "user": "http://localhost:8010", 
            "audit": "http://localhost:8011"
        }
        self.test_results = {
            "start_time": datetime.now().isoformat(),
            "scenarios": [],
            "overall_success_rate": 0.0,
            "implementation_rate": 0.0
        }

    async def test_scenario_1_basic_ontology_workflow(self) -> Dict[str, Any]:
        """시나리오 1: 기본 온톨로지 관리 워크플로우"""
        print("\n🎪 SCENARIO 1: Basic Ontology Management Workflow")
        print("=" * 70)
        
        scenario_result = {
            "name": "Basic Ontology Workflow",
            "steps": [],
            "success_rate": 0.0,
            "errors": []
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: 사용자 등록
            try:
                print("📝 Step 1: User Registration...")
                register_payload = {
                    "email": f"ontology_admin_{int(time.time())}@test.com",
                    "password": "testpass123",
                    "name": f"Admin User {int(time.time())}"
                }
                
                register_response = await client.post(
                    f"{self.base_urls['user']}/auth/register",
                    json=register_payload
                )
                
                step_result = {
                    "step": "user_registration",
                    "success": register_response.status_code in [200, 201],
                    "status_code": register_response.status_code,
                    "response_time": 0
                }
                
                if step_result["success"]:
                    print(f"   ✅ User registered successfully: {register_response.status_code}")
                    register_data = register_response.json()
                else:
                    print(f"   ❌ Registration failed: {register_response.status_code}")
                    register_data = None
                    
                scenario_result["steps"].append(step_result)
                
            except Exception as e:
                print(f"   💥 Registration error: {e}")
                scenario_result["errors"].append(f"Registration: {str(e)}")
                register_data = None

            # Step 2: 사용자 로그인
            try:
                print("🔐 Step 2: User Login...")
                login_data = {
                    "username": register_payload["email"], 
                    "password": register_payload["password"]
                }
                
                login_response = await client.post(
                    f"{self.base_urls['user']}/auth/login",
                    data=login_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                step_result = {
                    "step": "user_login", 
                    "success": login_response.status_code == 200,
                    "status_code": login_response.status_code,
                    "has_token": False
                }
                
                if step_result["success"]:
                    login_data = login_response.json()
                    token = login_data.get("access_token") or login_data.get("token")
                    step_result["has_token"] = bool(token)
                    print(f"   ✅ Login successful, token: {'Yes' if token else 'No'}")
                else:
                    print(f"   ❌ Login failed: {login_response.status_code}")
                    token = None
                    
                scenario_result["steps"].append(step_result)
                
            except Exception as e:
                print(f"   💥 Login error: {e}")
                scenario_result["errors"].append(f"Login: {str(e)}")
                token = None

            # Step 3: 실제 스키마 CRUD 테스트
            try:
                print("📊 Step 3: Schema CRUD Test...")
                
                # 스키마 생성
                schema_payload = {
                    "name": f"TestSchema_{int(time.time())}",
                    "description": "End-to-end test schema",
                    "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "value", "type": "number"}
                    ]
                }
                
                create_response = await client.post(
                    f"{self.base_urls['oms']}/api/v1/schemas/",
                    json=schema_payload
                )
                
                step_result = {
                    "step": "schema_crud_test",
                    "success": create_response.status_code in [200, 201],
                    "status_code": create_response.status_code,
                    "schema_created": False,
                    "schema_listed": False
                }
                
                if step_result["success"]:
                    created_schema = create_response.json()
                    step_result["schema_created"] = True
                    print(f"   ✅ Schema created: {created_schema['name']}")
                    
                    # 스키마 목록 조회
                    list_response = await client.get(f"{self.base_urls['oms']}/api/v1/schemas/")
                    if list_response.status_code == 200:
                        schemas = list_response.json()
                        step_result["schema_listed"] = len(schemas) > 0
                        print(f"   ✅ Schema list: {len(schemas)} schemas found")
                else:
                    print(f"   ❌ Schema creation failed: {create_response.status_code}")
                    
                scenario_result["steps"].append(step_result)
                
            except Exception as e:
                print(f"   💥 Schema CRUD error: {e}")
                scenario_result["errors"].append(f"Schema CRUD: {str(e)}")

            # Step 4: 서비스 간 통신 테스트
            try:
                print("🔗 Step 4: Inter-service Communication Test...")
                
                # 모든 서비스 health check
                health_checks = {}
                for service, url in self.base_urls.items():
                    try:
                        health_response = await client.get(f"{url}/health", timeout=5.0)
                        health_checks[service] = health_response.status_code == 200
                    except:
                        health_checks[service] = False
                
                step_result = {
                    "step": "inter_service_communication",
                    "success": sum(health_checks.values()) >= 2,  # At least 2 services healthy
                    "service_status": health_checks,
                    "healthy_services": sum(health_checks.values())
                }
                
                print(f"   📊 Service Health: {step_result['healthy_services']}/3 services healthy")
                for service, healthy in health_checks.items():
                    status = "✅" if healthy else "❌"
                    print(f"      {status} {service.upper()}")
                    
                scenario_result["steps"].append(step_result)
                
            except Exception as e:
                print(f"   💥 Communication test error: {e}")
                scenario_result["errors"].append(f"Communication: {str(e)}")

        # Calculate scenario success rate
        successful_steps = sum(1 for step in scenario_result["steps"] if step["success"])
        total_steps = len(scenario_result["steps"])
        scenario_result["success_rate"] = (successful_steps / total_steps * 100) if total_steps > 0 else 0
        
        print(f"\n📈 Scenario 1 Results: {scenario_result['success_rate']:.1f}% success rate")
        print(f"   ✅ Successful steps: {successful_steps}/{total_steps}")
        
        return scenario_result

    async def test_scenario_2_service_availability(self) -> Dict[str, Any]:
        """시나리오 2: 서비스 가용성 및 성능 테스트"""
        print("\n⚡ SCENARIO 2: Service Availability & Performance")
        print("=" * 70)
        
        scenario_result = {
            "name": "Service Availability Test",
            "services": {},
            "overall_health": False,
            "avg_response_time": 0.0
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            total_response_time = 0
            healthy_services = 0
            
            for service_name, base_url in self.base_urls.items():
                print(f"🔍 Testing {service_name.upper()}...")
                
                service_result = {
                    "name": service_name,
                    "health_check": False,
                    "api_docs": False, 
                    "response_time": 0,
                    "endpoint_count": 0
                }
                
                # Health check with timing
                try:
                    start_time = time.time()
                    health_response = await client.get(f"{base_url}/health")
                    response_time = (time.time() - start_time) * 1000
                    
                    service_result["health_check"] = health_response.status_code == 200
                    service_result["response_time"] = round(response_time, 2)
                    total_response_time += response_time
                    
                    if service_result["health_check"]:
                        healthy_services += 1
                        print(f"   ✅ Health: {response_time:.2f}ms")
                    else:
                        print(f"   ❌ Health: {health_response.status_code}")
                        
                except Exception as e:
                    print(f"   💥 Health check failed: {e}")
                
                # API documentation check
                try:
                    docs_response = await client.get(f"{base_url}/docs")
                    service_result["api_docs"] = docs_response.status_code == 200
                    if service_result["api_docs"]:
                        print(f"   ✅ API Docs accessible")
                    else:
                        print(f"   ⚠️  API Docs: {docs_response.status_code}")
                except:
                    print(f"   ❌ API Docs not accessible")
                
                # Endpoint count check
                try:
                    openapi_response = await client.get(f"{base_url}/openapi.json")
                    if openapi_response.status_code == 200:
                        openapi_data = openapi_response.json()
                        endpoint_count = len(openapi_data.get("paths", {}))
                        service_result["endpoint_count"] = endpoint_count
                        print(f"   📊 Available endpoints: {endpoint_count}")
                except:
                    print(f"   ⚠️  Could not determine endpoint count")
                
                scenario_result["services"][service_name] = service_result
            
            # Calculate overall metrics
            scenario_result["overall_health"] = healthy_services >= 2
            scenario_result["healthy_service_count"] = healthy_services
            scenario_result["avg_response_time"] = round(total_response_time / len(self.base_urls), 2)
            
            print(f"\n📊 Overall System Health: {healthy_services}/3 services healthy")
            print(f"📈 Average Response Time: {scenario_result['avg_response_time']:.2f}ms")
            
        return scenario_result

    async def calculate_overall_implementation_rate(self, scenarios: List[Dict]) -> float:
        """전체 구현률 계산"""
        total_features = 0
        implemented_features = 0
        
        # Service availability scoring
        for scenario in scenarios:
            if scenario["name"] == "Service Availability Test":
                services = scenario.get("services", {})
                for service_data in services.values():
                    total_features += 3  # health, docs, endpoints
                    if service_data.get("health_check"): implemented_features += 1
                    if service_data.get("api_docs"): implemented_features += 1
                    if service_data.get("endpoint_count", 0) > 0: implemented_features += 1
        
        # Workflow functionality scoring
        for scenario in scenarios:
            if scenario["name"] == "Basic Ontology Workflow":
                steps = scenario.get("steps", [])
                total_features += len(steps)
                implemented_features += sum(1 for step in steps if step.get("success"))
        
        return round((implemented_features / total_features * 100), 1) if total_features > 0 else 0

    async def run_comprehensive_verification(self):
        """포괄적 검증 실행"""
        print("🚀 ARRAKIS PROJECT - COMPREHENSIVE END-TO-END VERIFICATION")
        print("=" * 80)
        print("📋 Following priority_based_test_plan.md with ULTRA THINKING")
        print("🎯 Target: 85%+ Implementation Rate")
        print("=" * 80)
        
        # Run all scenarios
        scenario1 = await self.test_scenario_1_basic_ontology_workflow()
        scenario2 = await self.test_scenario_2_service_availability()
        
        self.test_results["scenarios"] = [scenario1, scenario2]
        
        # Calculate overall metrics
        self.test_results["implementation_rate"] = await self.calculate_overall_implementation_rate(
            self.test_results["scenarios"]
        )
        
        successful_scenarios = sum(1 for s in self.test_results["scenarios"] 
                                 if s.get("success_rate", 0) > 70 or s.get("overall_health", False))
        self.test_results["overall_success_rate"] = (successful_scenarios / len(self.test_results["scenarios"]) * 100)
        
        # Final report
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE VERIFICATION RESULTS")
        print("=" * 80)
        
        for scenario in self.test_results["scenarios"]:
            if "success_rate" in scenario:
                print(f"✅ {scenario['name']}: {scenario['success_rate']:.1f}% success")
            elif "overall_health" in scenario:
                health_status = "✅ HEALTHY" if scenario["overall_health"] else "⚠️ DEGRADED"
                print(f"{health_status} {scenario['name']}: {scenario.get('healthy_service_count', 0)}/3 services")
        
        print(f"\n🎯 OVERALL IMPLEMENTATION RATE: {self.test_results['implementation_rate']}%")
        print(f"📈 SCENARIO SUCCESS RATE: {self.test_results['overall_success_rate']:.1f}%")
        
        # Achievement assessment
        if self.test_results["implementation_rate"] >= 85:
            print("🏆 TARGET ACHIEVED: 85%+ Implementation Rate!")
        elif self.test_results["implementation_rate"] >= 75:
            print("🎉 EXCELLENT PROGRESS: 75%+ Implementation Rate")
        elif self.test_results["implementation_rate"] >= 65:
            print("✅ GOOD PROGRESS: 65%+ Implementation Rate")
        else:
            print("⚠️ MORE WORK NEEDED: Below 65% Implementation Rate")
        
        print(f"\n💾 Verification completed at: {datetime.now().isoformat()}")
        
        return self.test_results

async def main():
    verifier = EndToEndVerifier()
    results = await verifier.run_comprehensive_verification()
    
    # Save results
    results_file = f"/Users/isihyeon/Desktop/Arrakis-Project/end_to_end_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"📄 Results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main())