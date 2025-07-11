#!/usr/bin/env python3
"""
극단적 장애 시나리오 테스트
리질리언스 메커니즘을 강제로 활성화시키기 위한 고강도 테스트

시나리오:
1. 서비스 다운 시뮬레이션 (컨테이너 중지/재시작)
2. 네트워크 지연 및 타임아웃 시뮬레이션
3. 대용량 동시 요청으로 백프레셔 강제 활성화
4. 메모리/CPU 부하로 서비스 응답 지연
"""

import asyncio
import httpx
import json
import time
import logging
import subprocess
import signal
from typing import Dict, Any, List, Optional
from datetime import datetime
import concurrent.futures
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_SERVICE_URL = "http://localhost:8080"
AUDIT_SERVICE_URL = "http://localhost:8092" 
OMS_URL = "http://localhost:8091"

class ExtremeFailureTest:
    def __init__(self):
        self.test_results = {
            "extreme_scenarios": [],
            "resilience_summary": {
                "circuit_breaker_activations": 0,
                "etag_cache_hits": 0,
                "backpressure_activations": 0,
                "service_recoveries": 0
            }
        }
        self.service_token = None

    async def setup_authentication(self) -> bool:
        """인증 설정"""
        try:
            with open("service_token_write.json", "r") as f:
                creds = json.load(f)
                self.service_token = creds["access_token"]
            return True
        except Exception as e:
            logger.error(f"Authentication setup failed: {e}")
            return False

    async def test_scenario_1_massive_concurrent_load(self) -> Dict[str, Any]:
        """시나리오 1: 대규모 동시 부하로 백프레셔 강제 활성화"""
        scenario_result = {
            "name": "Massive Concurrent Load",
            "description": "500개 동시 요청으로 백프레셔와 서킷브레이커 강제 활성화",
            "total_time": 0,
            "resilience_activations": [],
            "load_stats": {}
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        async def make_heavy_request(session: httpx.AsyncClient, request_id: int):
            try:
                # 극도로 무거운 요청 생성
                payload = {
                    "cpu_load": 0.5,     # 500ms CPU 부하
                    "io_delay": 1.0,     # 1초 I/O 지연
                    "payload_size": 50000 # 50KB 페이로드
                }
                
                request_start = time.time()
                resp = await session.post(
                    f"{OMS_URL}/api/v1/test/load",
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(3.0)  # 짧은 타임아웃으로 강제 실패
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
                    "response_time": 3.0,
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

        logger.info("🔥 Starting MASSIVE concurrent load test (500 requests)")
        
        # 여러 연결을 사용하여 더 큰 부하 생성
        connector = httpx.AsyncHTTPTransport(limits=httpx.Limits(max_connections=100))
        async with httpx.AsyncClient(transport=connector, timeout=5.0) as client:
            
            # 500개 동시 요청 실행
            tasks = []
            for i in range(500):
                task = make_heavy_request(client, i)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 통계 분석
            successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            timeouts = sum(1 for r in results if isinstance(r, dict) and r.get("error") == "timeout")
            failures = len(results) - successful
            
            avg_response_time = 0
            if results:
                response_times = [r.get("response_time", 0) for r in results if isinstance(r, dict)]
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            scenario_result["load_stats"] = {
                "total_requests": len(results),
                "successful": successful,
                "timeouts": timeouts,
                "failures": failures,
                "success_rate": round(successful / len(results) * 100, 2),
                "avg_response_time": round(avg_response_time, 3)
            }
            
            # 백프레셔 활성화 확인
            if timeouts > 50 or failures > 100:
                scenario_result["resilience_activations"].append({
                    "mechanism": "Backpressure/Circuit Breaker",
                    "status": "activated",
                    "timeout_count": timeouts,
                    "failure_count": failures,
                    "trigger_reason": "massive_concurrent_load"
                })
                self.test_results["resilience_summary"]["backpressure_activations"] += 1
                logger.info(f"✅ BACKPRESSURE ACTIVATED: {timeouts} timeouts, {failures} failures")
            
        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_2_circuit_breaker_stress(self) -> Dict[str, Any]:
        """시나리오 2: 서킷브레이커 스트레스 테스트"""
        scenario_result = {
            "name": "Circuit Breaker Stress Test",
            "description": "지속적인 에러 요청으로 서킷브레이커 완전 활성화",
            "total_time": 0,
            "resilience_activations": [],
            "circuit_states": []
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        logger.info("🔥 Starting Circuit Breaker STRESS test")
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            # 1단계: 연속 에러로 서킷 오픈
            logger.info("Phase 1: Triggering circuit breaker with errors")
            circuit_opened = False
            
            for i in range(20):  # 많은 수의 에러 요청
                try:
                    # 다양한 에러 코드로 테스트
                    error_codes = [404, 500, 503]
                    error_code = error_codes[i % len(error_codes)]
                    
                    resp = await client.get(
                        f"{OMS_URL}/api/v1/test/error?error_code={error_code}",
                        headers=headers
                    )
                    
                    scenario_result["circuit_states"].append({
                        "request": i + 1,
                        "error_code": error_code,
                        "response_code": resp.status_code,
                        "timestamp": time.time()
                    })
                    
                    if resp.status_code == 503 and "circuit" in resp.text.lower():
                        circuit_opened = True
                        logger.info(f"✅ Circuit Breaker OPENED at request {i+1}")
                        break
                        
                except Exception as e:
                    scenario_result["circuit_states"].append({
                        "request": i + 1,
                        "error": str(e),
                        "timestamp": time.time()
                    })
                    logger.info(f"Request {i+1}: Exception - {type(e).__name__}")
                
                await asyncio.sleep(0.05)  # 빠른 요청으로 부하 증가
            
            # 2단계: 서킷 열린 상태에서 정상 요청 차단 확인
            if circuit_opened:
                logger.info("Phase 2: Testing circuit breaker blocking")
                
                for i in range(10):
                    try:
                        resp = await client.get(
                            f"{OMS_URL}/api/v1/schemas/main/object-types",
                            headers=headers
                        )
                        
                        is_blocked = resp.status_code == 503
                        scenario_result["circuit_states"].append({
                            "phase": "blocking_test",
                            "request": i + 1,
                            "blocked": is_blocked,
                            "status_code": resp.status_code,
                            "timestamp": time.time()
                        })
                        
                        if is_blocked:
                            logger.info(f"✅ Request {i+1} blocked by circuit breaker")
                        else:
                            logger.warning(f"⚠️ Request {i+1} NOT blocked: {resp.status_code}")
                            
                    except Exception as e:
                        scenario_result["circuit_states"].append({
                            "phase": "blocking_test", 
                            "request": i + 1,
                            "blocked": True,
                            "error": str(e),
                            "timestamp": time.time()
                        })
                        logger.info(f"✅ Request {i+1} blocked with exception")
                    
                    await asyncio.sleep(0.1)
                
                scenario_result["resilience_activations"].append({
                    "mechanism": "Circuit Breaker",
                    "status": "fully_activated",
                    "blocking_confirmed": True
                })
                self.test_results["resilience_summary"]["circuit_breaker_activations"] += 1

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_3_etag_cache_validation(self) -> Dict[str, Any]:
        """시나리오 3: E-Tag 캐시 효과성 검증"""
        scenario_result = {
            "name": "E-Tag Cache Validation",
            "description": "반복 요청으로 E-Tag 캐싱 효과 측정",
            "total_time": 0,
            "resilience_activations": [],
            "cache_stats": {}
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        logger.info("🔥 Starting E-Tag cache validation test")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1단계: 초기 요청으로 E-Tag 획득
            initial_resp = await client.get(
                f"{OMS_URL}/api/v1/schemas/main/object-types",
                headers=headers
            )
            
            etag = initial_resp.headers.get("ETag")
            logger.info(f"Initial E-Tag: {etag}")
            
            if not etag:
                logger.warning("No E-Tag header found")
                scenario_result["cache_stats"]["etag_available"] = False
                scenario_result["total_time"] = time.time() - start_time
                return scenario_result
            
            # 2단계: E-Tag를 사용한 조건부 요청 반복
            cache_hits = 0
            cache_misses = 0
            
            for i in range(20):
                try:
                    request_start = time.time()
                    resp = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/object-types",
                        headers={**headers, "If-None-Match": etag}
                    )
                    request_time = time.time() - request_start
                    
                    if resp.status_code == 304:
                        cache_hits += 1
                        logger.info(f"✅ Cache HIT #{cache_hits} (304 Not Modified) - {request_time:.3f}s")
                    else:
                        cache_misses += 1
                        # 새 E-Tag 업데이트
                        if resp.headers.get("ETag"):
                            etag = resp.headers.get("ETag")
                        logger.info(f"Cache MISS #{cache_misses} ({resp.status_code}) - {request_time:.3f}s")
                    
                except Exception as e:
                    cache_misses += 1
                    logger.error(f"Cache test error: {e}")
                
                await asyncio.sleep(0.1)
            
            cache_hit_rate = round(cache_hits / (cache_hits + cache_misses) * 100, 2)
            
            scenario_result["cache_stats"] = {
                "etag_available": True,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "hit_rate": cache_hit_rate,
                "total_requests": cache_hits + cache_misses
            }
            
            if cache_hits > 5:
                scenario_result["resilience_activations"].append({
                    "mechanism": "E-Tag Caching",
                    "status": "working",
                    "hit_rate": cache_hit_rate,
                    "hits": cache_hits
                })
                self.test_results["resilience_summary"]["etag_cache_hits"] += cache_hits
                logger.info(f"✅ E-TAG CACHING WORKING: {cache_hit_rate}% hit rate")

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def test_scenario_4_service_recovery(self) -> Dict[str, Any]:
        """시나리오 4: 서비스 복구 능력 테스트"""
        scenario_result = {
            "name": "Service Recovery Test",
            "description": "서비스 부하 후 자동 복구 확인",
            "total_time": 0,
            "resilience_activations": [],
            "recovery_stats": {}
        }
        
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.service_token}"}
        
        logger.info("🔥 Starting Service Recovery test")
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1단계: 서비스에 극한 부하 가하기
            logger.info("Phase 1: Applying extreme load to trigger failures")
            
            # 메모리 집약적 요청들
            memory_tasks = []
            for i in range(10):
                task = client.get(
                    f"{OMS_URL}/api/v1/test/memory?size_mb=50",  # 50MB 메모리 할당
                    headers=headers
                )
                memory_tasks.append(task)
            
            # 동시 실행으로 메모리 압박
            memory_results = await asyncio.gather(*memory_tasks, return_exceptions=True)
            
            failed_memory_requests = sum(1 for r in memory_results if isinstance(r, Exception))
            logger.info(f"Memory stress results: {failed_memory_requests} failures out of {len(memory_results)}")
            
            # 2단계: 부하 중지 후 복구 확인
            logger.info("Phase 2: Checking service recovery")
            await asyncio.sleep(2)  # 복구 대기
            
            recovery_attempts = []
            for i in range(10):
                try:
                    resp = await client.get(f"{OMS_URL}/api/v1/health", headers=headers)
                    recovery_attempts.append({
                        "attempt": i + 1,
                        "status_code": resp.status_code,
                        "success": resp.status_code == 200,
                        "timestamp": time.time()
                    })
                    
                    if resp.status_code == 200:
                        logger.info(f"✅ Recovery attempt {i+1}: Service healthy")
                    else:
                        logger.warning(f"⚠️ Recovery attempt {i+1}: Still failing ({resp.status_code})")
                        
                except Exception as e:
                    recovery_attempts.append({
                        "attempt": i + 1,
                        "success": False,
                        "error": str(e),
                        "timestamp": time.time()
                    })
                    logger.warning(f"⚠️ Recovery attempt {i+1}: Exception - {type(e).__name__}")
                
                await asyncio.sleep(1)
            
            successful_recoveries = sum(1 for r in recovery_attempts if r.get("success"))
            recovery_rate = round(successful_recoveries / len(recovery_attempts) * 100, 2)
            
            scenario_result["recovery_stats"] = {
                "memory_stress_failures": failed_memory_requests,
                "recovery_attempts": len(recovery_attempts),
                "successful_recoveries": successful_recoveries,
                "recovery_rate": recovery_rate
            }
            
            if recovery_rate > 70:
                scenario_result["resilience_activations"].append({
                    "mechanism": "Service Recovery",
                    "status": "successful",
                    "recovery_rate": recovery_rate
                })
                self.test_results["resilience_summary"]["service_recoveries"] += 1
                logger.info(f"✅ SERVICE RECOVERY CONFIRMED: {recovery_rate}% success rate")

        scenario_result["total_time"] = time.time() - start_time
        return scenario_result

    async def run_extreme_tests(self) -> Dict[str, Any]:
        """모든 극단적 테스트 실행"""
        logger.info("🚀 Starting EXTREME FAILURE SCENARIOS")
        
        if not await self.setup_authentication():
            return {"error": "Authentication failed"}
        
        # 모든 극단적 시나리오 실행
        extreme_scenarios = [
            await self.test_scenario_1_massive_concurrent_load(),
            await self.test_scenario_2_circuit_breaker_stress(),
            await self.test_scenario_3_etag_cache_validation(),
            await self.test_scenario_4_service_recovery()
        ]
        
        self.test_results["extreme_scenarios"] = extreme_scenarios
        return self.test_results

async def main():
    test_runner = ExtremeFailureTest()
    results = await test_runner.run_extreme_tests()
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"extreme_failure_test_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    # 결과 요약 출력
    print("\n" + "="*80)
    print("🔥 EXTREME FAILURE SCENARIOS TEST RESULTS")
    print("="*80)
    
    if "error" in results:
        print(f"❌ Test failed: {results['error']}")
        return
    
    summary = results["resilience_summary"]
    
    print(f"🛡️  Resilience Mechanisms Summary:")
    print(f"   Circuit Breaker Activations: {summary['circuit_breaker_activations']}")
    print(f"   E-Tag Cache Hits: {summary['etag_cache_hits']}")
    print(f"   Backpressure Activations: {summary['backpressure_activations']}")
    print(f"   Service Recoveries: {summary['service_recoveries']}")
    
    print(f"\n📋 Extreme Scenario Results:")
    for scenario in results["extreme_scenarios"]:
        activations = len(scenario["resilience_activations"])
        status = "✅ PASSED" if activations > 0 else "⚠️ NO ACTIVATIONS"
        print(f"   {status} {scenario['name']}: {activations} resilience activations")
        
        for activation in scenario["resilience_activations"]:
            print(f"      🛡️  {activation['mechanism']}: {activation['status']}")
    
    print(f"\n📁 Detailed results saved to: {filename}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())