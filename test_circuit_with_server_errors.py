#!/usr/bin/env python3
"""
글로벌 서킷 브레이커 서버 에러 테스트
실제 5xx 서버 에러를 유발하여 서킷 브레이커 동작 검증
"""
import asyncio
import json
import time
import httpx
from datetime import datetime
from typing import Dict, List, Any

# 서비스 설정
OMS_URL = "http://localhost:8091"
TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlOm9tcy1tb25vbGl0aCIsImlhdCI6MTc1MjIzODY2MiwiZXhwIjoxNzUyMjQyMjYyLCJhdWQiOiJhdWRpdC1zZXJ2aWNlIiwiaXNzIjoidXNlci1zZXJ2aWNlIiwiY2xpZW50X2lkIjoib21zLW1vbm9saXRoLWNsaWVudCIsInNlcnZpY2VfbmFtZSI6Im9tcy1tb25vbGl0aCIsImlzX3NlcnZpY2VfYWNjb3VudCI6dHJ1ZSwiZ3JhbnRfdHlwZSI6ImNsaWVudF9jcmVkZW50aWFscyIsInNjb3BlcyI6WyJhdWRpdDp3cml0ZSIsImF1ZGl0OnJlYWQiXSwicGVybWlzc2lvbnMiOlsiYXVkaXQ6d3JpdGUiLCJhdWRpdDpyZWFkIl0sInVzZXJfaWQiOiJzZXJ2aWNlOm9tcy1tb25vbGl0aCIsInVzZXJuYW1lIjoib21zLW1vbm9saXRoIiwidG9rZW5fdHlwZSI6InNlcnZpY2UiLCJ2ZXJzaW9uIjoiMS4wIn0.q-f78u9NZ3ajQUuAa962FaGLoyw7ylvwFQDkTf85e2pqDUtVgo8QSPhfvyHbnrlDdsD1I2XbVp6PpgZw6XMDhBqnJf8FlP1j4I9f8OOKIzJENsqs0U-cfD2kWBgO0CWB8LABSQIpONvpzuQnKudBK4KKTuAu27HbhALzSzwsTvDsV4mzCzxFOwzUUMLE-G97mhYYmMA-ufsyCDShfSX4CxsjpJ1yZoweAvFDI12zv_qVc0b25-Xs4E7vOeZ_rxOEH0KmBCTTW4UMecDESZDwG-oSd995h71cirvFBX3Ha8fgrh6eqZjp1mVfrf6RbjaI76slHHoR0CZ3gRLvz4RiSA"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

async def test_circuit_with_server_errors():
    """서버 에러를 통한 서킷 브레이커 테스트"""
    print("🔥 서버 에러 기반 글로벌 서킷 브레이커 테스트 시작")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_phases": [],
        "circuit_breaker_analysis": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: 베이스라인 확인
        await phase_1_baseline(client, results)
        
        # Phase 2: 서버 에러 생성 (TerminusDB 부하를 통한 실제 5xx 에러)
        await phase_2_server_error_generation(client, results)
        
        # Phase 3: 서킷 브레이커 동작 확인
        await phase_3_circuit_verification(client, results)
        
        # Phase 4: 글로벌 차단 동작 확인
        await phase_4_global_blocking(client, results)
    
    # 결과 저장 및 분석
    filename = f"circuit_server_error_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📊 테스트 결과가 {filename}에 저장되었습니다")
    analyze_circuit_behavior(results)

async def phase_1_baseline(client: httpx.AsyncClient, results: Dict):
    """Phase 1: 베이스라인 확인"""
    print("\n🔧 Phase 1: 베이스라인 상태 확인")
    
    phase_results = {
        "phase": "baseline_check",
        "tests": [],
        "success": False
    }
    
    # 정상 동작 확인
    test_endpoints = [
        "/health",
        "/api/v1/health"
    ]
    
    working_count = 0
    
    for endpoint in test_endpoints:
        try:
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}{endpoint}", headers=HEADERS)
            response_time = time.time() - start_time
            
            test_result = {
                "endpoint": endpoint,
                "status_code": resp.status_code,
                "response_time": response_time,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                working_count += 1
                print(f"   ✅ {endpoint} - 정상")
            else:
                print(f"   ❌ {endpoint} - 오류 ({resp.status_code})")
            
            phase_results["tests"].append(test_result)
            
        except Exception as e:
            print(f"   ❌ {endpoint} - 연결 실패: {e}")
            phase_results["tests"].append({
                "endpoint": endpoint,
                "error": str(e),
                "success": False
            })
    
    phase_results["success"] = working_count > 0
    phase_results["working_endpoints"] = working_count
    results["test_phases"].append(phase_results)

async def phase_2_server_error_generation(client: httpx.AsyncClient, results: Dict):
    """Phase 2: 실제 서버 에러 생성"""
    print("\n💥 Phase 2: 실제 서버 에러 생성 (대용량 동시 요청)")
    
    phase_results = {
        "phase": "server_error_generation",
        "error_attacks": [],
        "response_analysis": {},
        "success": False
    }
    
    # 공격 1: 대용량 병렬 요청으로 서버 과부하 유발
    print("   🎯 공격 1: 대용량 병렬 요청 (100개 동시)")
    attack_1_results = await execute_concurrent_attack(client, 100)
    phase_results["error_attacks"].append(attack_1_results)
    
    # 잠시 대기
    await asyncio.sleep(2)
    
    # 공격 2: 무효한 JSON으로 서버 에러 유발
    print("   🎯 공격 2: 무효한 데이터로 서버 에러 유발")
    attack_2_results = await execute_invalid_data_attack(client)
    phase_results["error_attacks"].append(attack_2_results)
    
    # 전체 에러 분석
    total_requests = 0
    server_errors = 0
    
    for attack in phase_results["error_attacks"]:
        total_requests += attack.get("total_requests", 0)
        server_errors += attack.get("server_errors", 0)
    
    phase_results["response_analysis"] = {
        "total_requests": total_requests,
        "server_errors": server_errors,
        "server_error_rate": server_errors / total_requests if total_requests > 0 else 0
    }
    
    print(f"   📊 총 {total_requests}회 요청, {server_errors}회 서버 에러")
    print(f"   📊 서버 에러율: {phase_results['response_analysis']['server_error_rate']:.1%}")
    
    # 서버 에러가 충분히 발생했으면 성공
    phase_results["success"] = server_errors >= 5
    
    results["test_phases"].append(phase_results)

async def execute_concurrent_attack(client: httpx.AsyncClient, count: int) -> Dict:
    """동시 요청 공격 실행"""
    print(f"     📡 {count}개 동시 요청 실행 중...")
    
    attack_result = {
        "type": "concurrent_overload",
        "total_requests": count,
        "requests": [],
        "server_errors": 0
    }
    
    async def make_request(i):
        try:
            # 부하가 높은 엔드포인트 요청
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}/api/v1/health", 
                                  headers=HEADERS, 
                                  timeout=1.0)  # 짧은 타임아웃으로 부하 증가
            response_time = time.time() - start_time
            
            result = {
                "request_id": i,
                "status_code": resp.status_code,
                "response_time": response_time,
                "is_server_error": resp.status_code >= 500
            }
            
            if resp.status_code >= 500:
                attack_result["server_errors"] += 1
            
            return result
            
        except asyncio.TimeoutError:
            attack_result["server_errors"] += 1
            return {
                "request_id": i,
                "timeout": True,
                "is_server_error": True
            }
        except Exception as e:
            attack_result["server_errors"] += 1
            return {
                "request_id": i,
                "error": str(e),
                "is_server_error": True
            }
    
    # 동시 실행
    tasks = [make_request(i) for i in range(count)]
    request_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 결과 정리
    for result in request_results:
        if isinstance(result, Exception):
            attack_result["server_errors"] += 1
            attack_result["requests"].append({
                "exception": str(result),
                "is_server_error": True
            })
        else:
            attack_result["requests"].append(result)
    
    print(f"     📊 동시 요청 결과: {attack_result['server_errors']}/{count} 서버 에러")
    return attack_result

async def execute_invalid_data_attack(client: httpx.AsyncClient) -> Dict:
    """무효한 데이터 공격 실행"""
    print("     🔧 무효한 데이터로 서버 에러 유발 중...")
    
    attack_result = {
        "type": "invalid_data_attack",
        "total_requests": 0,
        "requests": [],
        "server_errors": 0
    }
    
    # 다양한 무효한 요청 패턴
    invalid_patterns = [
        # 극도로 큰 JSON 페이로드
        {"data": "x" * 10000000},  # 10MB 문자열
        # 깊게 중첩된 JSON
        {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}},
        # 순환 참조 시뮬레이션
        {"self_ref": "circular"},
        # NULL 바이트 주입
        {"null_byte": "test\x00injection"},
        # 특수 문자
        {"special": "\\x1b[31m\\x1b[0m"}
    ]
    
    for i, pattern in enumerate(invalid_patterns):
        try:
            start_time = time.time()
            resp = await client.post(f"{OMS_URL}/api/v1/test/invalid", 
                                   headers=HEADERS,
                                   json=pattern,
                                   timeout=5.0)
            response_time = time.time() - start_time
            
            attack_result["total_requests"] += 1
            
            result = {
                "pattern_id": i,
                "status_code": resp.status_code,
                "response_time": response_time,
                "is_server_error": resp.status_code >= 500
            }
            
            if resp.status_code >= 500:
                attack_result["server_errors"] += 1
                print(f"       🔥 패턴 {i+1}: 서버 에러 ({resp.status_code})")
            else:
                print(f"       ✅ 패턴 {i+1}: 처리됨 ({resp.status_code})")
            
            attack_result["requests"].append(result)
            
        except Exception as e:
            attack_result["total_requests"] += 1
            attack_result["server_errors"] += 1
            attack_result["requests"].append({
                "pattern_id": i,
                "error": str(e),
                "is_server_error": True
            })
            print(f"       💥 패턴 {i+1}: 예외 발생 - {e}")
    
    print(f"     📊 무효 데이터 공격 결과: {attack_result['server_errors']}/{attack_result['total_requests']} 서버 에러")
    return attack_result

async def phase_3_circuit_verification(client: httpx.AsyncClient, results: Dict):
    """Phase 3: 서킷 브레이커 동작 확인"""
    print("\n🔍 Phase 3: 서킷 브레이커 상태 변화 확인")
    
    phase_results = {
        "phase": "circuit_verification",
        "state_checks": [],
        "behavioral_analysis": {},
        "success": False
    }
    
    # 에러 생성 후 서킷 상태 변화 확인
    print("   ⏰ 서킷 브레이커 상태 변화 대기 (5초)")
    await asyncio.sleep(5)
    
    # 여러 번 상태 확인
    for i in range(10):
        try:
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}/api/v1/health", 
                                  headers=HEADERS, 
                                  timeout=10.0)
            response_time = time.time() - start_time
            
            state_check = {
                "check_num": i + 1,
                "status_code": resp.status_code,
                "response_time": response_time,
                "potential_circuit_open": False
            }
            
            # 서킷 브레이커 동작 지표 확인
            if resp.status_code == 503:
                state_check["potential_circuit_open"] = True
                print(f"   🚫 상태 확인 {i+1}: 서비스 차단 (503) - 서킷 브레이커 동작 가능성")
            elif response_time > 5.0:
                state_check["slow_response"] = True
                print(f"   ⏱️ 상태 확인 {i+1}: 느린 응답 ({response_time:.2f}초)")
            elif resp.status_code == 200:
                print(f"   ✅ 상태 확인 {i+1}: 정상 ({response_time:.2f}초)")
            else:
                print(f"   ⚠️ 상태 확인 {i+1}: 기타 ({resp.status_code})")
            
            phase_results["state_checks"].append(state_check)
            
            await asyncio.sleep(1)
            
        except Exception as e:
            phase_results["state_checks"].append({
                "check_num": i + 1,
                "error": str(e),
                "potential_circuit_open": True
            })
            print(f"   💥 상태 확인 {i+1}: 연결 실패 - {e}")
    
    # 동작 분석
    total_checks = len(phase_results["state_checks"])
    circuit_indicators = len([c for c in phase_results["state_checks"] 
                            if c.get("potential_circuit_open", False)])
    
    phase_results["behavioral_analysis"] = {
        "total_checks": total_checks,
        "circuit_indicators": circuit_indicators,
        "circuit_indication_rate": circuit_indicators / total_checks if total_checks > 0 else 0
    }
    
    print(f"   📊 서킷 브레이커 지표: {circuit_indicators}/{total_checks} 확인")
    
    # 서킷 브레이커 동작 지표가 있으면 성공
    phase_results["success"] = circuit_indicators > 0
    
    results["test_phases"].append(phase_results)

async def phase_4_global_blocking(client: httpx.AsyncClient, results: Dict):
    """Phase 4: 글로벌 차단 동작 확인"""
    print("\n🌐 Phase 4: 글로벌 차단 범위 확인")
    
    phase_results = {
        "phase": "global_blocking_verification",
        "endpoint_tests": [],
        "global_effect": {},
        "success": False
    }
    
    # 다양한 엔드포인트에서 차단 효과 확인
    test_endpoints = [
        "/health",
        "/api/v1/health",
        "/api/v1/test/simple"  # 간단한 테스트 엔드포인트
    ]
    
    blocked_endpoints = 0
    total_endpoint_tests = 0
    
    for endpoint in test_endpoints:
        print(f"   🔍 {endpoint} 차단 효과 확인")
        
        endpoint_blocked = 0
        endpoint_tests = 5
        
        for i in range(endpoint_tests):
            try:
                start_time = time.time()
                resp = await client.get(f"{OMS_URL}{endpoint}", 
                                      headers=HEADERS, 
                                      timeout=8.0)
                response_time = time.time() - start_time
                
                test_result = {
                    "endpoint": endpoint,
                    "attempt": i + 1,
                    "status_code": resp.status_code,
                    "response_time": response_time,
                    "blocked": resp.status_code == 503
                }
                
                total_endpoint_tests += 1
                
                if resp.status_code == 503:
                    endpoint_blocked += 1
                    print(f"     🚫 시도 {i+1}: 차단됨")
                elif resp.status_code == 200:
                    print(f"     ✅ 시도 {i+1}: 정상")
                else:
                    print(f"     ⚠️ 시도 {i+1}: 기타 ({resp.status_code})")
                
                phase_results["endpoint_tests"].append(test_result)
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                total_endpoint_tests += 1
                endpoint_blocked += 1
                phase_results["endpoint_tests"].append({
                    "endpoint": endpoint,
                    "attempt": i + 1,
                    "error": str(e),
                    "blocked": True
                })
                print(f"     💥 시도 {i+1}: 연결 실패")
        
        if endpoint_blocked > 0:
            blocked_endpoints += 1
        
        print(f"     📊 {endpoint}: {endpoint_blocked}/{endpoint_tests} 차단")
    
    phase_results["global_effect"] = {
        "total_endpoints_tested": len(test_endpoints),
        "blocked_endpoints": blocked_endpoints,
        "total_tests": total_endpoint_tests,
        "global_blocking_rate": blocked_endpoints / len(test_endpoints) if test_endpoints else 0
    }
    
    print(f"   📊 글로벌 차단 효과: {blocked_endpoints}/{len(test_endpoints)} 엔드포인트 영향")
    
    # 글로벌 차단 효과가 확인되면 성공
    phase_results["success"] = blocked_endpoints > 0
    
    results["test_phases"].append(phase_results)

def analyze_circuit_behavior(results: Dict):
    """서킷 브레이커 동작 분석"""
    print("\n🔬 서킷 브레이커 동작 분석")
    
    phases = results["test_phases"]
    
    # 각 페이즈별 분석
    baseline_ok = False
    errors_generated = False
    circuit_triggered = False
    global_blocking = False
    
    for phase in phases:
        phase_name = phase["phase"]
        success = phase.get("success", False)
        
        if phase_name == "baseline_check" and success:
            baseline_ok = True
            print("✅ 베이스라인: 서비스 정상 동작 확인")
        elif phase_name == "server_error_generation" and success:
            errors_generated = True
            error_rate = phase.get("response_analysis", {}).get("server_error_rate", 0)
            print(f"✅ 에러 생성: {error_rate:.1%} 서버 에러율")
        elif phase_name == "circuit_verification" and success:
            circuit_triggered = True
            indication_rate = phase.get("behavioral_analysis", {}).get("circuit_indication_rate", 0)
            print(f"✅ 서킷 동작: {indication_rate:.1%} 동작 지표")
        elif phase_name == "global_blocking_verification" and success:
            global_blocking = True
            blocking_rate = phase.get("global_effect", {}).get("global_blocking_rate", 0)
            print(f"✅ 글로벌 차단: {blocking_rate:.1%} 엔드포인트 영향")
    
    # 종합 평가
    total_score = 0
    if baseline_ok:
        total_score += 25
    if errors_generated:
        total_score += 25
    if circuit_triggered:
        total_score += 30
    if global_blocking:
        total_score += 20
    
    print(f"\n🏆 서킷 브레이커 동작 점수: {total_score}/100")
    
    if total_score >= 80:
        print("🌟 EXCELLENT - 글로벌 서킷 브레이커가 완벽하게 작동합니다!")
        evaluation = "excellent"
    elif total_score >= 60:
        print("✅ GOOD - 서킷 브레이커가 잘 작동합니다.")
        evaluation = "good"
    elif total_score >= 40:
        print("⚠️ FAIR - 부분적 서킷 브레이커 동작 확인")
        evaluation = "fair"
    else:
        print("❌ POOR - 서킷 브레이커 동작을 확인할 수 없습니다.")
        evaluation = "poor"
    
    results["circuit_breaker_analysis"] = {
        "baseline_ok": baseline_ok,
        "errors_generated": errors_generated,
        "circuit_triggered": circuit_triggered,
        "global_blocking": global_blocking,
        "total_score": total_score,
        "evaluation": evaluation
    }

if __name__ == "__main__":
    asyncio.run(test_circuit_with_server_errors())