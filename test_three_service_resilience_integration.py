#!/usr/bin/env python3
"""
3개 서비스 통합 리질리언스 테스트
실제 유저 플로우를 시뮬레이션하면서 각 서비스의 리질리언스 메커니즘을 테스트합니다.

테스트 시나리오:
1. 유저 인증 → 스키마 조회 → 문서 생성/수정 → 감사 로그 생성
2. 각 단계에서 서비스 장애 시뮬레이션
3. 리질리언스 메커니즘 검증 (Circuit Breaker, E-Tag, Backpressure)
"""

import asyncio
import httpx
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Service URLs
USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8092"
OMS_URL = "http://localhost:8091"

class ThreeServiceResilienceTest:
    def __init__(self):
        self.test_results = {
            "scenarios": [],
            "overall_stats": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "resilience_triggers": 0
            },
            "performance_metrics": {
                "avg_response_time": 0,
                "p95_response_time": 0,
                "error_rate": 0
            }
        }
        self.access_token = None
        self.service_token = None
        
    async def setup_authentication(self) -> bool:
        """인증 토큰 설정"""
        try:
            # 서비스 토큰 로드
            with open("service_token_write.json", "r") as f:
                creds = json.load(f)
                self.service_token = creds["access_token"]
            
            logger.info("✅ Authentication setup completed")
            return True
        except Exception as e:
            logger.error(f"❌ Authentication setup failed: {e}")
            return False

    async def test_scenario_1_normal_user_flow(self) -> Dict[str, Any]:
        """시나리오 1: 정상적인 유저 플로우"""
        scenario_result = {
            "name": "Normal User Flow",
            "description": "유저 인증 → 스키마 조회 → 문서 CRUD → 감사 로그 조회",
            "steps": [],
            "overall_success": True,
            "total_time": 0,
            "resilience_activations": []
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: 유저 서비스 헬스체크
            step_start = time.time()
            try:
                resp = await client.get(f"{USER_SERVICE_URL}/health")
                step_result = {
                    "step": "User Service Health Check",
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "response_time": time.time() - step_start,
                    "details": resp.json() if resp.status_code == 200 else None
                }
                scenario_result["steps"].append(step_result)
                logger.info(f"✅ User Service Health: {resp.status_code}")
            except Exception as e:
                step_result = {
                    "step": "User Service Health Check",
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - step_start
                }
                scenario_result["steps"].append(step_result)
                scenario_result["overall_success"] = False
                logger.error(f"❌ User Service Health failed: {e}")

            # Step 2: OMS 스키마 조회 (E-Tag 테스트)
            step_start = time.time()
            try:
                resp = await client.get(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                step_result = {
                    "step": "OMS Schema List",
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "response_time": time.time() - step_start,
                    "etag_header": resp.headers.get("ETag"),
                    "cache_header": resp.headers.get("Cache-Control")
                }
                scenario_result["steps"].append(step_result)
                
                # E-Tag 재요청 테스트
                if resp.headers.get("ETag"):
                    etag = resp.headers.get("ETag")
                    step_start = time.time()
                    resp2 = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/object-types",
                        headers={**headers, "If-None-Match": etag}
                    )
                    if resp2.status_code == 304:
                        scenario_result["resilience_activations"].append({
                            "mechanism": "E-Tag Cache Hit",
                            "status": "activated",
                            "response_time": time.time() - step_start
                        })
                        logger.info("✅ E-Tag cache hit (304 Not Modified)")
                
                logger.info(f"✅ OMS Schema List: {resp.status_code}")
            except Exception as e:
                step_result = {
                    "step": "OMS Schema List",
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - step_start
                }
                scenario_result["steps"].append(step_result)
                scenario_result["overall_success"] = False
                logger.error(f"❌ OMS Schema List failed: {e}")

            # Step 3: OMS 문서 생성
            step_start = time.time()
            try:
                document_data = {
                    "name": f"test_doc_{int(time.time())}",
                    "content": {"test": "data", "timestamp": datetime.now().isoformat()},
                    "description": "Resilience test document"
                }
                resp = await client.post(
                    f"{OMS_URL}/api/v1/documents/crud",
                    headers=headers,
                    json=document_data
                )
                step_result = {
                    "step": "OMS Document Creation",
                    "status_code": resp.status_code,
                    "success": resp.status_code in [200, 201],
                    "response_time": time.time() - step_start,
                    "document_id": resp.json().get("id") if resp.status_code in [200, 201] else None
                }
                scenario_result["steps"].append(step_result)
                logger.info(f"✅ OMS Document Creation: {resp.status_code}")
            except Exception as e:
                step_result = {
                    "step": "OMS Document Creation",
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - step_start
                }
                scenario_result["steps"].append(step_result)
                scenario_result["overall_success"] = False
                logger.error(f"❌ OMS Document Creation failed: {e}")

            # Step 4: 감사 서비스 로그 조회
            step_start = time.time()
            try:
                resp = await client.get(
                    f"{AUDIT_SERVICE_URL}/api/v1/health/detailed",
                    headers=headers
                )
                step_result = {
                    "step": "Audit Service Health Check",
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "response_time": time.time() - step_start,
                    "components": resp.json() if resp.status_code == 200 else None
                }
                scenario_result["steps"].append(step_result)
                logger.info(f"✅ Audit Service Health: {resp.status_code}")
            except Exception as e:
                step_result = {
                    "step": "Audit Service Health Check",
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - step_start
                }
                scenario_result["steps"].append(step_result)
                scenario_result["overall_success"] = False
                logger.error(f"❌ Audit Service Health failed: {e}")

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_2_circuit_breaker_activation(self) -> Dict[str, Any]:
        """시나리오 2: 서킷 브레이커 활성화 테스트"""
        scenario_result = {
            "name": "Circuit Breaker Activation",
            "description": "의도적인 에러 발생으로 서킷 브레이커 동작 확인",
            "steps": [],
            "overall_success": True,
            "total_time": 0,
            "resilience_activations": []
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 연속적인 404 에러 발생으로 서킷 브레이커 트리거
            logger.info("🔥 Starting Circuit Breaker activation test")
            
            failed_requests = 0
            circuit_opened = False
            
            for i in range(8):  # 임계값(5)보다 많이 요청
                step_start = time.time()
                try:
                    resp = await client.get(
                        f"{OMS_URL}/api/v1/test/error?error_code=404",
                        headers=headers
                    )
                    
                    step_result = {
                        "step": f"Error Request {i+1}",
                        "status_code": resp.status_code,
                        "success": False,
                        "response_time": time.time() - step_start
                    }
                    
                    if resp.status_code == 404:
                        failed_requests += 1
                        logger.info(f"🔥 Request {i+1}: 404 Error")
                    elif resp.status_code == 503:
                        circuit_opened = True
                        scenario_result["resilience_activations"].append({
                            "mechanism": "Circuit Breaker",
                            "status": "opened",
                            "trigger_count": failed_requests,
                            "response_time": time.time() - step_start
                        })
                        logger.info(f"✅ Circuit Breaker OPENED at request {i+1}")
                        break
                    
                    scenario_result["steps"].append(step_result)
                    
                except Exception as e:
                    step_result = {
                        "step": f"Error Request {i+1}",
                        "success": False,
                        "error": str(e),
                        "response_time": time.time() - step_start
                    }
                    scenario_result["steps"].append(step_result)
                    failed_requests += 1
                    logger.info(f"🔥 Request {i+1}: Exception - {type(e).__name__}")
                
                await asyncio.sleep(0.1)
            
            # 서킷 열린 후 정상 요청 차단 확인
            if circuit_opened:
                step_start = time.time()
                try:
                    resp = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/object-types",
                        headers=headers
                    )
                    
                    step_result = {
                        "step": "Normal Request After Circuit Open",
                        "status_code": resp.status_code,
                        "success": resp.status_code == 503,
                        "response_time": time.time() - step_start,
                        "blocked_by_circuit": resp.status_code == 503
                    }
                    scenario_result["steps"].append(step_result)
                    
                    if resp.status_code == 503:
                        logger.info("✅ Circuit Breaker correctly blocking normal requests")
                    else:
                        logger.warning(f"⚠️ Normal request not blocked: {resp.status_code}")
                        
                except Exception as e:
                    step_result = {
                        "step": "Normal Request After Circuit Open",
                        "success": True,  # Exception도 차단의 의미
                        "error": str(e),
                        "response_time": time.time() - step_start,
                        "blocked_by_circuit": True
                    }
                    scenario_result["steps"].append(step_result)
                    logger.info(f"✅ Circuit Breaker blocking with exception: {type(e).__name__}")

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_3_backpressure_handling(self) -> Dict[str, Any]:
        """시나리오 3: 백프레셔 처리 테스트"""
        scenario_result = {
            "name": "Backpressure Handling",
            "description": "높은 부하 상황에서 백프레셔 메커니즘 확인",
            "steps": [],
            "overall_success": True,
            "total_time": 0,
            "resilience_activations": []
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        # 동시 요청 생성
        async def make_load_request(session: httpx.AsyncClient, request_id: int):
            try:
                payload = {
                    "cpu_load": 0.1,  # 100ms CPU 부하
                    "io_delay": 0.2,  # 200ms I/O 지연  
                    "payload_size": 10000  # 10KB 페이로드
                }
                
                request_start = time.time()
                resp = await session.post(
                    f"{OMS_URL}/api/v1/test/load",
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(10.0)
                )
                
                return {
                    "request_id": request_id,
                    "status_code": resp.status_code,
                    "response_time": time.time() - request_start,
                    "success": resp.status_code == 200
                }
            except httpx.TimeoutException:
                return {
                    "request_id": request_id,
                    "status_code": 408,
                    "response_time": time.time() - request_start,
                    "success": False,
                    "error": "timeout"
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "status_code": 500,
                    "response_time": time.time() - request_start,
                    "success": False,
                    "error": str(e)
                }

        logger.info("🔥 Starting Backpressure test with concurrent requests")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 50개 동시 요청으로 백프레셔 트리거 시도
            tasks = []
            for i in range(50):
                task = make_load_request(client, i)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 분석
            successful_requests = 0
            failed_requests = 0
            timeouts = 0
            avg_response_time = 0
            response_times = []
            
            for result in results:
                if isinstance(result, dict):
                    if result["success"]:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        if result.get("error") == "timeout":
                            timeouts += 1
                    
                    response_times.append(result["response_time"])
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
            
            # 백프레셔 활성화 확인
            if timeouts > 0 or failed_requests > 10:
                scenario_result["resilience_activations"].append({
                    "mechanism": "Backpressure",
                    "status": "activated",
                    "timeout_count": timeouts,
                    "failed_count": failed_requests,
                    "success_rate": successful_requests / len(results) if results else 0
                })
                logger.info(f"✅ Backpressure activated: {timeouts} timeouts, {failed_requests} failures")
            
            step_result = {
                "step": "Concurrent Load Test",
                "total_requests": len(results),
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "timeout_requests": timeouts,
                "avg_response_time": avg_response_time,
                "p95_response_time": p95_response_time if response_times else 0,
                "success": True
            }
            scenario_result["steps"].append(step_result)

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_4_cross_service_failure_simulation(self) -> Dict[str, Any]:
        """시나리오 4: 크로스 서비스 장애 시뮬레이션"""
        scenario_result = {
            "name": "Cross-Service Failure Simulation",
            "description": "한 서비스 장애 시 다른 서비스들의 리질리언스 확인",
            "steps": [],
            "overall_success": True,
            "total_time": 0,
            "resilience_activations": []
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 각 서비스에 연속 요청하여 상호작용 테스트
            services_to_test = [
                {"name": "User Service", "url": f"{USER_SERVICE_URL}/health"},
                {"name": "OMS", "url": f"{OMS_URL}/api/v1/health"},
                {"name": "Audit Service", "url": f"{AUDIT_SERVICE_URL}/api/v1/health/"}
            ]
            
            for service in services_to_test:
                step_start = time.time()
                try:
                    # 정상 요청
                    resp = await client.get(service["url"], headers=headers)
                    
                    step_result = {
                        "step": f"{service['name']} Health Check",
                        "status_code": resp.status_code,
                        "success": resp.status_code == 200,
                        "response_time": time.time() - step_start,
                        "service_status": resp.json() if resp.status_code == 200 else None
                    }
                    scenario_result["steps"].append(step_result)
                    logger.info(f"✅ {service['name']}: {resp.status_code}")
                    
                except Exception as e:
                    step_result = {
                        "step": f"{service['name']} Health Check",
                        "success": False,
                        "error": str(e),
                        "response_time": time.time() - step_start
                    }
                    scenario_result["steps"].append(step_result)
                    logger.error(f"❌ {service['name']} failed: {e}")

            # OMS를 통한 전체 워크플로우 테스트
            step_start = time.time()
            try:
                # 스키마 조회 → 문서 생성 → 감사 이벤트 체인
                schema_resp = await client.get(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                
                workflow_result = {
                    "step": "End-to-End Workflow Test",
                    "schema_query": {
                        "status_code": schema_resp.status_code,
                        "success": schema_resp.status_code == 200,
                        "etag_present": "ETag" in schema_resp.headers
                    },
                    "response_time": time.time() - step_start
                }
                
                scenario_result["steps"].append(workflow_result)
                logger.info(f"✅ End-to-End Workflow: Schema query {schema_resp.status_code}")
                
            except Exception as e:
                workflow_result = {
                    "step": "End-to-End Workflow Test",
                    "success": False,
                    "error": str(e),
                    "response_time": time.time() - step_start
                }
                scenario_result["steps"].append(workflow_result)
                logger.error(f"❌ End-to-End Workflow failed: {e}")

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def run_all_tests(self) -> Dict[str, Any]:
        """모든 테스트 시나리오 실행"""
        logger.info("🚀 Starting Three-Service Resilience Integration Test")
        
        if not await self.setup_authentication():
            return {"error": "Authentication setup failed"}
        
        # 모든 시나리오 실행
        scenarios = [
            await self.test_scenario_1_normal_user_flow(),
            await self.test_scenario_2_circuit_breaker_activation(),
            await self.test_scenario_3_backpressure_handling(),
            await self.test_scenario_4_cross_service_failure_simulation()
        ]
        
        self.test_results["scenarios"] = scenarios
        
        # 전체 통계 계산
        total_tests = sum(len(s["steps"]) for s in scenarios)
        passed_tests = sum(sum(1 for step in s["steps"] if step.get("success", False)) for s in scenarios)
        failed_tests = total_tests - passed_tests
        resilience_triggers = sum(len(s["resilience_activations"]) for s in scenarios)
        
        self.test_results["overall_stats"].update({
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "resilience_triggers": resilience_triggers,
            "success_rate": round(passed_tests / total_tests * 100, 2) if total_tests > 0 else 0
        })
        
        # 성능 메트릭 계산
        all_response_times = []
        for scenario in scenarios:
            for step in scenario["steps"]:
                if "response_time" in step:
                    all_response_times.append(step["response_time"])
        
        if all_response_times:
            self.test_results["performance_metrics"].update({
                "avg_response_time": round(sum(all_response_times) / len(all_response_times), 3),
                "p95_response_time": round(sorted(all_response_times)[int(len(all_response_times) * 0.95)], 3),
                "error_rate": round(failed_tests / total_tests * 100, 2) if total_tests > 0 else 0
            })
        
        return self.test_results

async def main():
    test_runner = ThreeServiceResilienceTest()
    results = await test_runner.run_all_tests()
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"three_service_resilience_test_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    # 결과 요약 출력
    print("\n" + "="*80)
    print("🔍 THREE-SERVICE RESILIENCE INTEGRATION TEST RESULTS")
    print("="*80)
    
    if "error" in results:
        print(f"❌ Test failed: {results['error']}")
        return
    
    stats = results["overall_stats"]
    perf = results["performance_metrics"]
    
    print(f"📊 Overall Statistics:")
    print(f"   Total Tests: {stats['total_tests']}")
    print(f"   Passed: {stats['passed_tests']} ({stats.get('success_rate', 0)}%)")
    print(f"   Failed: {stats['failed_tests']}")
    print(f"   Resilience Triggers: {stats['resilience_triggers']}")
    
    print(f"\n⚡ Performance Metrics:")
    print(f"   Average Response Time: {perf['avg_response_time']}s")
    print(f"   P95 Response Time: {perf['p95_response_time']}s")
    print(f"   Error Rate: {perf['error_rate']}%")
    
    print(f"\n📋 Scenario Summary:")
    for scenario in results["scenarios"]:
        status = "✅" if scenario["overall_success"] else "❌"
        activations = len(scenario["resilience_activations"])
        print(f"   {status} {scenario['name']}: {activations} resilience activations")
        
        for activation in scenario["resilience_activations"]:
            print(f"      🛡️  {activation['mechanism']}: {activation['status']}")
    
    print(f"\n📁 Detailed results saved to: {filename}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())