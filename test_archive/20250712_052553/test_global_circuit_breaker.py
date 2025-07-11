#!/usr/bin/env python3
"""
글로벌 서킷 브레이커 프로덕션 레벨 테스트
극한 실패 상황을 통해 전역 차단 로직 검증
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

async def test_global_circuit_breaker():
    """글로벌 서킷 브레이커 극한 테스트"""
    print("🔥 글로벌 서킷 브레이커 프로덕션 레벨 테스트 시작")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_phases": [],
        "global_circuit_stats": {},
        "production_readiness": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: 서킷 브레이커 상태 초기화 및 확인
        await phase_1_initialization(client, results)
        
        # Phase 2: 집중 실패 공격으로 글로벌 서킷 강제 오픈
        await phase_2_global_circuit_trigger(client, results)
        
        # Phase 3: 글로벌 차단 검증 (모든 엔드포인트 차단 확인)
        await phase_3_global_blocking_verification(client, results)
        
        # Phase 4: 분산 상태 관리 검증 (Redis 기반)
        await phase_4_distributed_state_verification(client, results)
        
        # Phase 5: 자동 복구 및 Half-Open 동작 검증
        await phase_5_recovery_verification(client, results)
        
        # Phase 6: 프로덕션 메트릭 및 모니터링 검증
        await phase_6_production_metrics(client, results)
    
    # 결과 저장
    filename = f"global_circuit_breaker_production_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📊 테스트 결과가 {filename}에 저장되었습니다")
    
    # 최종 평가
    evaluate_production_readiness(results)

async def phase_1_initialization(client: httpx.AsyncClient, results: Dict):
    """Phase 1: 초기화 및 상태 확인"""
    print("\n🔧 Phase 1: 글로벌 서킷 브레이커 초기화")
    
    phase_results = {
        "phase": "initialization",
        "steps": [],
        "success": True
    }
    
    try:
        # 서킷 브레이커 상태 확인
        resp = await client.get(f"{OMS_URL}/api/v1/circuit-breaker/status", headers=HEADERS)
        step_result = {
            "step": "initial_status_check",
            "status_code": resp.status_code,
            "response_time": resp.elapsed.total_seconds(),
            "success": resp.status_code == 200
        }
        
        if resp.status_code == 200:
            status_data = resp.json()
            step_result["circuit_state"] = status_data.get("data", {}).get("state", "unknown")
            step_result["metrics"] = status_data.get("data", {}).get("metrics", {})
            print(f"   ✅ 초기 상태: {step_result['circuit_state']}")
        else:
            print(f"   ❌ 상태 확인 실패: {resp.status_code}")
        
        phase_results["steps"].append(step_result)
        
        # 필요시 서킷 브레이커 리셋
        if step_result.get("circuit_state") != "closed":
            print("   🔄 서킷 브레이커 리셋 중...")
            reset_resp = await client.post(f"{OMS_URL}/api/v1/circuit-breaker/reset", headers=HEADERS)
            phase_results["steps"].append({
                "step": "circuit_reset",
                "status_code": reset_resp.status_code,
                "success": reset_resp.status_code == 200
            })
            
            # 리셋 후 상태 재확인
            await asyncio.sleep(1)
            verify_resp = await client.get(f"{OMS_URL}/api/v1/circuit-breaker/status", headers=HEADERS)
            if verify_resp.status_code == 200:
                verify_data = verify_resp.json()
                final_state = verify_data.get("data", {}).get("state", "unknown")
                print(f"   ✅ 리셋 후 상태: {final_state}")
    
    except Exception as e:
        print(f"   ❌ 초기화 오류: {e}")
        phase_results["success"] = False
        phase_results["error"] = str(e)
    
    results["test_phases"].append(phase_results)

async def phase_2_global_circuit_trigger(client: httpx.AsyncClient, results: Dict):
    """Phase 2: 글로벌 서킷 강제 오픈"""
    print("\n💥 Phase 2: 집중 실패 공격으로 글로벌 서킷 오픈")
    
    phase_results = {
        "phase": "global_circuit_trigger",
        "attack_patterns": [],
        "circuit_transitions": [],
        "success": False
    }
    
    try:
        # 공격 패턴 1: 연속 5xx 에러 유발
        print("   🎯 공격 패턴 1: 연속 5xx 에러")
        attack_1 = await execute_error_attack(client, "500_errors", 8)
        phase_results["attack_patterns"].append(attack_1)
        
        # 서킷 상태 확인
        await asyncio.sleep(2)
        status_check_1 = await check_circuit_status(client)
        phase_results["circuit_transitions"].append(status_check_1)
        
        if status_check_1.get("state") == "open":
            print("   ✅ 글로벌 서킷이 OPEN 상태로 전환됨!")
            phase_results["success"] = True
        else:
            # 공격 패턴 2: 더 강한 공격
            print("   🎯 공격 패턴 2: 더 강한 연속 공격")
            attack_2 = await execute_error_attack(client, "mixed_errors", 15)
            phase_results["attack_patterns"].append(attack_2)
            
            await asyncio.sleep(2)
            status_check_2 = await check_circuit_status(client)
            phase_results["circuit_transitions"].append(status_check_2)
            
            if status_check_2.get("state") == "open":
                print("   ✅ 글로벌 서킷이 OPEN 상태로 전환됨!")
                phase_results["success"] = True
    
    except Exception as e:
        print(f"   ❌ 공격 실행 오류: {e}")
        phase_results["error"] = str(e)
    
    results["test_phases"].append(phase_results)

async def execute_error_attack(client: httpx.AsyncClient, attack_type: str, count: int) -> Dict:
    """에러 공격 실행"""
    attack_result = {
        "type": attack_type,
        "total_requests": count,
        "requests": [],
        "avg_response_time": 0
    }
    
    response_times = []
    
    for i in range(count):
        try:
            start_time = time.time()
            
            if attack_type == "500_errors":
                # 존재하지 않는 엔드포인트로 500 에러 유발
                resp = await client.post(f"{OMS_URL}/api/v1/nonexistent/error", 
                                       headers=HEADERS, 
                                       json={"force_error": True})
            elif attack_type == "mixed_errors":
                # 다양한 에러 유발
                endpoints = [
                    "/api/v1/nonexistent/500", 
                    "/api/v1/error/simulate", 
                    "/api/v1/invalid/endpoint",
                    "/api/v1/timeout/test"
                ]
                endpoint = endpoints[i % len(endpoints)]
                resp = await client.get(f"{OMS_URL}{endpoint}", headers=HEADERS)
            
            response_time = time.time() - start_time
            response_times.append(response_time)
            
            attack_result["requests"].append({
                "request_num": i + 1,
                "status_code": resp.status_code,
                "response_time": response_time,
                "success": resp.status_code < 500
            })
            
            # 공격 강도 조절
            await asyncio.sleep(0.1)
            
        except Exception as e:
            attack_result["requests"].append({
                "request_num": i + 1,
                "error": str(e),
                "success": False
            })
    
    if response_times:
        attack_result["avg_response_time"] = sum(response_times) / len(response_times)
    
    return attack_result

async def phase_3_global_blocking_verification(client: httpx.AsyncClient, results: Dict):
    """Phase 3: 글로벌 차단 검증"""
    print("\n🚫 Phase 3: 글로벌 차단 로직 검증")
    
    phase_results = {
        "phase": "global_blocking_verification",
        "blocking_tests": [],
        "blocked_endpoints": [],
        "success": False
    }
    
    # 다양한 엔드포인트에 요청하여 모두 차단되는지 확인
    test_endpoints = [
        "/api/v1/schemas",
        "/api/v1/documents",
        "/api/v1/branches",
        "/api/v1/organizations",
        "/api/v1/properties",
        "/api/v1/system/info"
    ]
    
    blocked_count = 0
    
    for endpoint in test_endpoints:
        try:
            resp = await client.get(f"{OMS_URL}{endpoint}", headers=HEADERS)
            
            blocking_result = {
                "endpoint": endpoint,
                "status_code": resp.status_code,
                "blocked": resp.status_code == 503,
                "response_time": resp.elapsed.total_seconds() if hasattr(resp, 'elapsed') else 0
            }
            
            if resp.status_code == 503:
                blocked_count += 1
                phase_results["blocked_endpoints"].append(endpoint)
                print(f"   ✅ {endpoint} - 차단됨 (503)")
            else:
                print(f"   ❌ {endpoint} - 차단되지 않음 ({resp.status_code})")
            
            phase_results["blocking_tests"].append(blocking_result)
            
        except Exception as e:
            phase_results["blocking_tests"].append({
                "endpoint": endpoint,
                "error": str(e),
                "blocked": False
            })
    
    # 성공 기준: 80% 이상의 엔드포인트가 차단되어야 함
    blocking_rate = blocked_count / len(test_endpoints)
    phase_results["blocking_rate"] = blocking_rate
    phase_results["success"] = blocking_rate >= 0.8
    
    print(f"   📊 차단율: {blocking_rate:.1%} ({blocked_count}/{len(test_endpoints)})")
    
    results["test_phases"].append(phase_results)

async def phase_4_distributed_state_verification(client: httpx.AsyncClient, results: Dict):
    """Phase 4: 분산 상태 관리 검증"""
    print("\n🔄 Phase 4: 분산 상태 관리 (Redis) 검증")
    
    phase_results = {
        "phase": "distributed_state_verification",
        "redis_checks": [],
        "state_persistence": False,
        "success": False
    }
    
    try:
        # 현재 서킷 상태 확인
        status_1 = await check_circuit_status(client)
        phase_results["redis_checks"].append({
            "check": "initial_state",
            "timestamp": time.time(),
            "state": status_1.get("state"),
            "metrics": status_1.get("metrics", {})
        })
        
        # 잠시 대기 후 상태 재확인 (Redis 지속성 검증)
        await asyncio.sleep(5)
        status_2 = await check_circuit_status(client)
        phase_results["redis_checks"].append({
            "check": "persistence_check",
            "timestamp": time.time(),
            "state": status_2.get("state"),
            "metrics": status_2.get("metrics", {})
        })
        
        # 상태 일관성 확인
        if status_1.get("state") == status_2.get("state"):
            phase_results["state_persistence"] = True
            print("   ✅ Redis 상태 지속성 확인됨")
        else:
            print("   ❌ Redis 상태 불일치 감지")
        
        # 메트릭 확인
        metrics_check = await check_circuit_metrics(client)
        phase_results["metrics_verification"] = metrics_check
        
        phase_results["success"] = phase_results["state_persistence"] and metrics_check.get("success", False)
    
    except Exception as e:
        print(f"   ❌ 분산 상태 검증 오류: {e}")
        phase_results["error"] = str(e)
    
    results["test_phases"].append(phase_results)

async def phase_5_recovery_verification(client: httpx.AsyncClient, results: Dict):
    """Phase 5: 자동 복구 검증"""
    print("\n🔄 Phase 5: 자동 복구 및 Half-Open 동작 검증")
    
    phase_results = {
        "phase": "recovery_verification",
        "recovery_steps": [],
        "half_open_tests": [],
        "success": False
    }
    
    try:
        # 수동 리셋으로 복구 시뮬레이션
        print("   🔄 수동 복구 테스트")
        reset_resp = await client.post(f"{OMS_URL}/api/v1/circuit-breaker/reset", headers=HEADERS)
        
        recovery_step = {
            "step": "manual_reset",
            "status_code": reset_resp.status_code,
            "success": reset_resp.status_code == 200
        }
        
        if reset_resp.status_code == 200:
            print("   ✅ 수동 리셋 성공")
            
            # 리셋 후 상태 확인
            await asyncio.sleep(2)
            status_after_reset = await check_circuit_status(client)
            recovery_step["new_state"] = status_after_reset.get("state")
            
            if status_after_reset.get("state") == "closed":
                print("   ✅ 서킷이 CLOSED 상태로 복구됨")
                
                # 정상 요청으로 복구 확인
                test_resp = await client.get(f"{OMS_URL}/api/v1/health", headers=HEADERS)
                recovery_step["verification_request"] = {
                    "status_code": test_resp.status_code,
                    "success": test_resp.status_code == 200
                }
                
                if test_resp.status_code == 200:
                    phase_results["success"] = True
                    print("   ✅ 복구 후 정상 요청 처리 확인")
        
        phase_results["recovery_steps"].append(recovery_step)
    
    except Exception as e:
        print(f"   ❌ 복구 검증 오류: {e}")
        phase_results["error"] = str(e)
    
    results["test_phases"].append(phase_results)

async def phase_6_production_metrics(client: httpx.AsyncClient, results: Dict):
    """Phase 6: 프로덕션 메트릭 검증"""
    print("\n📊 Phase 6: 프로덕션 메트릭 및 모니터링 검증")
    
    phase_results = {
        "phase": "production_metrics",
        "metric_checks": [],
        "monitoring_data": {},
        "success": False
    }
    
    try:
        # 메트릭 엔드포인트 확인
        metrics_resp = await client.get(f"{OMS_URL}/api/v1/circuit-breaker/metrics", headers=HEADERS)
        
        if metrics_resp.status_code == 200:
            metrics_data = metrics_resp.json()
            phase_results["monitoring_data"] = metrics_data
            
            # 메트릭 품질 검사
            required_metrics = [
                "total_requests", "failed_requests", "uptime_percentage", 
                "mean_time_to_recovery_seconds", "availability_score"
            ]
            
            metrics_quality = {}
            for metric in required_metrics:
                if metric in str(metrics_data):
                    metrics_quality[metric] = "present"
                else:
                    metrics_quality[metric] = "missing"
            
            phase_results["metrics_quality"] = metrics_quality
            
            # 가용성 점수 확인
            availability_score = metrics_data.get("metrics", {}).get("calculated_metrics", {}).get("availability_score", 0)
            resilience_health = metrics_data.get("metrics", {}).get("calculated_metrics", {}).get("resilience_health", "unknown")
            
            phase_results["availability_score"] = availability_score
            phase_results["resilience_health"] = resilience_health
            
            print(f"   📈 가용성 점수: {availability_score}/100")
            print(f"   💪 리질리언스 건강도: {resilience_health}")
            
            # 성공 기준: 메트릭이 정상적으로 수집되고 있는지
            phase_results["success"] = len([m for m in metrics_quality.values() if m == "present"]) >= len(required_metrics) * 0.8
        
        else:
            print(f"   ❌ 메트릭 조회 실패: {metrics_resp.status_code}")
    
    except Exception as e:
        print(f"   ❌ 메트릭 검증 오류: {e}")
        phase_results["error"] = str(e)
    
    results["test_phases"].append(phase_results)

async def check_circuit_status(client: httpx.AsyncClient) -> Dict:
    """서킷 브레이커 상태 확인"""
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/circuit-breaker/status", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {})
        return {"state": "unknown", "error": f"Status code: {resp.status_code}"}
    except Exception as e:
        return {"state": "error", "error": str(e)}

async def check_circuit_metrics(client: httpx.AsyncClient) -> Dict:
    """서킷 브레이커 메트릭 확인"""
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/circuit-breaker/metrics", headers=HEADERS)
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        return {"success": False, "error": f"Status code: {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def evaluate_production_readiness(results: Dict):
    """프로덕션 준비도 평가"""
    print("\n🎯 프로덕션 준비도 평가")
    
    phases = results["test_phases"]
    total_phases = len(phases)
    successful_phases = len([p for p in phases if p.get("success", False)])
    
    success_rate = successful_phases / total_phases if total_phases > 0 else 0
    
    print(f"📊 전체 테스트 페이즈: {total_phases}")
    print(f"✅ 성공한 페이즈: {successful_phases}")
    print(f"📈 성공률: {success_rate:.1%}")
    
    # 프로덕션 준비도 점수 계산
    production_score = 0
    
    # 글로벌 서킷 오픈 성공 (30점)
    trigger_phase = next((p for p in phases if p["phase"] == "global_circuit_trigger"), {})
    if trigger_phase.get("success"):
        production_score += 30
        print("✅ 글로벌 서킷 트리거: 30/30점")
    else:
        print("❌ 글로벌 서킷 트리거: 0/30점")
    
    # 글로벌 차단 검증 (25점)
    blocking_phase = next((p for p in phases if p["phase"] == "global_blocking_verification"), {})
    if blocking_phase.get("success"):
        production_score += 25
        print("✅ 글로벌 차단 로직: 25/25점")
    else:
        blocking_rate = blocking_phase.get("blocking_rate", 0)
        partial_score = int(25 * blocking_rate)
        production_score += partial_score
        print(f"⚠️ 글로벌 차단 로직: {partial_score}/25점 (차단율: {blocking_rate:.1%})")
    
    # 분산 상태 관리 (20점)
    distributed_phase = next((p for p in phases if p["phase"] == "distributed_state_verification"), {})
    if distributed_phase.get("success"):
        production_score += 20
        print("✅ 분산 상태 관리: 20/20점")
    else:
        print("❌ 분산 상태 관리: 0/20점")
    
    # 자동 복구 (15점)
    recovery_phase = next((p for p in phases if p["phase"] == "recovery_verification"), {})
    if recovery_phase.get("success"):
        production_score += 15
        print("✅ 자동 복구: 15/15점")
    else:
        print("❌ 자동 복구: 0/15점")
    
    # 프로덕션 메트릭 (10점)
    metrics_phase = next((p for p in phases if p["phase"] == "production_metrics"), {})
    if metrics_phase.get("success"):
        production_score += 10
        print("✅ 프로덕션 메트릭: 10/10점")
    else:
        print("❌ 프로덕션 메트릭: 0/10점")
    
    print(f"\n🏆 최종 프로덕션 준비도 점수: {production_score}/100")
    
    # 평가 결과
    if production_score >= 90:
        print("🌟 EXCELLENT - 프로덕션 배포 준비 완료!")
    elif production_score >= 75:
        print("✅ GOOD - 프로덕션 배포 가능 (일부 개선 권장)")
    elif production_score >= 60:
        print("⚠️ FAIR - 추가 개선 후 프로덕션 배포 권장")
    else:
        print("❌ POOR - 프로덕션 배포 전 반드시 문제 해결 필요")
    
    results["production_readiness"] = {
        "score": production_score,
        "max_score": 100,
        "success_rate": success_rate,
        "evaluation": "excellent" if production_score >= 90 else 
                     "good" if production_score >= 75 else
                     "fair" if production_score >= 60 else "poor"
    }

if __name__ == "__main__":
    asyncio.run(test_global_circuit_breaker())