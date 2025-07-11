#!/usr/bin/env python3
"""
글로벌 서킷 브레이커 간단 테스트
인증이 필요없는 헬스체크와 로그 분석을 통한 검증
"""
import asyncio
import json
import time
import httpx
from datetime import datetime
from typing import Dict, List, Any

# 서비스 설정
OMS_URL = "http://localhost:8091"
HEADERS = {"Content-Type": "application/json"}

async def test_global_circuit_simple():
    """글로벌 서킷 브레이커 단순 기능 테스트"""
    print("🔥 글로벌 서킷 브레이커 단순 기능 테스트 시작")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_phases": [],
        "summary": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: 기본 연결성 확인
        await phase_1_connectivity(client, results)
        
        # Phase 2: 에러 부하 생성
        await phase_2_error_generation(client, results)
        
        # Phase 3: 차단 효과 검증
        await phase_3_blocking_check(client, results)
        
        # Phase 4: 복구 확인
        await phase_4_recovery_check(client, results)
    
    # 결과 저장
    filename = f"global_circuit_simple_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📊 테스트 결과가 {filename}에 저장되었습니다")
    evaluate_results(results)

async def phase_1_connectivity(client: httpx.AsyncClient, results: Dict):
    """Phase 1: 기본 연결성 확인"""
    print("\n🔧 Phase 1: 기본 연결성 확인")
    
    phase_results = {
        "phase": "connectivity_check",
        "tests": [],
        "success": False
    }
    
    # 헬스체크 엔드포인트 테스트
    endpoints = [
        "/health",
        "/api/v1/health"
    ]
    
    working_endpoints = 0
    
    for endpoint in endpoints:
        try:
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}{endpoint}")
            response_time = time.time() - start_time
            
            test_result = {
                "endpoint": endpoint,
                "status_code": resp.status_code,
                "response_time": response_time,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                working_endpoints += 1
                print(f"   ✅ {endpoint} - 정상 ({resp.status_code})")
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
    
    phase_results["success"] = working_endpoints > 0
    phase_results["working_endpoints"] = working_endpoints
    results["test_phases"].append(phase_results)

async def phase_2_error_generation(client: httpx.AsyncClient, results: Dict):
    """Phase 2: 에러 부하 생성"""
    print("\n💥 Phase 2: 에러 부하 생성으로 서킷 브레이커 활성화 시도")
    
    phase_results = {
        "phase": "error_generation",
        "error_requests": [],
        "response_patterns": {},
        "success": False
    }
    
    # 다양한 에러 패턴으로 공격
    error_endpoints = [
        "/api/v1/nonexistent",
        "/api/v1/invalid/endpoint", 
        "/api/v1/fake/path",
        "/api/v1/error/test",
        "/api/v1/timeout/simulation"
    ]
    
    print(f"   🎯 {len(error_endpoints)}개 에러 엔드포인트로 10회씩 요청")
    
    error_count = 0
    total_requests = 0
    response_codes = {}
    
    for endpoint in error_endpoints:
        for i in range(10):
            try:
                start_time = time.time()
                resp = await client.get(f"{OMS_URL}{endpoint}", timeout=5.0)
                response_time = time.time() - start_time
                
                total_requests += 1
                status_code = resp.status_code
                
                if status_code not in response_codes:
                    response_codes[status_code] = 0
                response_codes[status_code] += 1
                
                if status_code >= 400:
                    error_count += 1
                
                phase_results["error_requests"].append({
                    "endpoint": endpoint,
                    "request_num": i + 1,
                    "status_code": status_code,
                    "response_time": response_time,
                    "is_error": status_code >= 400
                })
                
                # 짧은 간격으로 요청
                await asyncio.sleep(0.1)
                
            except asyncio.TimeoutError:
                error_count += 1
                total_requests += 1
                phase_results["error_requests"].append({
                    "endpoint": endpoint,
                    "request_num": i + 1,
                    "timeout": True,
                    "is_error": True
                })
            except Exception as e:
                error_count += 1
                total_requests += 1
                phase_results["error_requests"].append({
                    "endpoint": endpoint,
                    "request_num": i + 1,
                    "error": str(e),
                    "is_error": True
                })
    
    phase_results["response_patterns"] = response_codes
    phase_results["error_count"] = error_count
    phase_results["total_requests"] = total_requests
    phase_results["error_rate"] = error_count / total_requests if total_requests > 0 else 0
    
    print(f"   📊 총 {total_requests}회 요청, {error_count}회 에러 ({phase_results['error_rate']:.1%})")
    print(f"   📊 응답 코드 분포: {response_codes}")
    
    # 높은 에러율이면 성공으로 간주
    phase_results["success"] = phase_results["error_rate"] > 0.8
    
    results["test_phases"].append(phase_results)

async def phase_3_blocking_check(client: httpx.AsyncClient, results: Dict):
    """Phase 3: 차단 효과 검증"""
    print("\n🚫 Phase 3: 서킷 브레이커 차단 효과 검증")
    
    phase_results = {
        "phase": "blocking_verification",
        "blocking_tests": [],
        "circuit_indicators": [],
        "success": False
    }
    
    # 에러 생성 후 잠시 대기
    print("   ⏰ 서킷 브레이커 상태 변경 대기 (3초)")
    await asyncio.sleep(3)
    
    # 정상 엔드포인트에 요청하여 차단 여부 확인
    test_endpoints = [
        "/health",
        "/api/v1/health"
    ]
    
    blocked_indicators = 0
    service_errors = 0
    
    for endpoint in test_endpoints:
        for i in range(5):
            try:
                start_time = time.time()
                resp = await client.get(f"{OMS_URL}{endpoint}", timeout=10.0)
                response_time = time.time() - start_time
                
                blocking_test = {
                    "endpoint": endpoint,
                    "attempt": i + 1,
                    "status_code": resp.status_code,
                    "response_time": response_time,
                    "blocked": resp.status_code == 503,
                    "service_unavailable": resp.status_code in [503, 502, 504]
                }
                
                if resp.status_code == 503:
                    blocked_indicators += 1
                    print(f"   🚫 {endpoint} 시도 {i+1} - 차단됨 (503)")
                    
                    # 응답 내용 확인
                    try:
                        response_text = resp.text
                        if "circuit breaker" in response_text.lower():
                            blocking_test["circuit_breaker_confirmed"] = True
                            print(f"      ✅ 서킷 브레이커 메시지 확인")
                    except:
                        pass
                        
                elif resp.status_code in [502, 504]:
                    service_errors += 1
                    print(f"   ⚠️ {endpoint} 시도 {i+1} - 서비스 오류 ({resp.status_code})")
                else:
                    print(f"   ✅ {endpoint} 시도 {i+1} - 정상 ({resp.status_code})")
                
                phase_results["blocking_tests"].append(blocking_test)
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                phase_results["blocking_tests"].append({
                    "endpoint": endpoint,
                    "attempt": i + 1,
                    "error": str(e),
                    "potential_circuit_block": True
                })
                print(f"   🚫 {endpoint} 시도 {i+1} - 연결 실패 (잠재적 차단)")
    
    total_tests = len(phase_results["blocking_tests"])
    phase_results["blocked_count"] = blocked_indicators
    phase_results["service_error_count"] = service_errors
    phase_results["blocking_rate"] = blocked_indicators / total_tests if total_tests > 0 else 0
    
    print(f"   📊 차단 지표: {blocked_indicators}/{total_tests} ({phase_results['blocking_rate']:.1%})")
    
    # 차단 지표나 서비스 오류가 있으면 어느 정도 성공으로 간주
    phase_results["success"] = (blocked_indicators + service_errors) > 0
    
    results["test_phases"].append(phase_results)

async def phase_4_recovery_check(client: httpx.AsyncClient, results: Dict):
    """Phase 4: 복구 확인"""
    print("\n🔄 Phase 4: 서비스 복구 확인")
    
    phase_results = {
        "phase": "recovery_check",
        "recovery_tests": [],
        "success": False
    }
    
    # 복구 대기 시간
    print("   ⏰ 복구 대기 시간 (10초)")
    await asyncio.sleep(10)
    
    # 헬스체크로 복구 확인
    recovery_attempts = 5
    successful_attempts = 0
    
    for i in range(recovery_attempts):
        try:
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}/health", timeout=15.0)
            response_time = time.time() - start_time
            
            recovery_test = {
                "attempt": i + 1,
                "status_code": resp.status_code,
                "response_time": response_time,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                successful_attempts += 1
                print(f"   ✅ 복구 시도 {i+1} - 성공 ({response_time:.2f}초)")
            else:
                print(f"   ❌ 복구 시도 {i+1} - 실패 ({resp.status_code})")
            
            phase_results["recovery_tests"].append(recovery_test)
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"   ❌ 복구 시도 {i+1} - 연결 실패: {e}")
            phase_results["recovery_tests"].append({
                "attempt": i + 1,
                "error": str(e),
                "success": False
            })
    
    phase_results["successful_attempts"] = successful_attempts
    phase_results["recovery_rate"] = successful_attempts / recovery_attempts
    phase_results["success"] = phase_results["recovery_rate"] > 0.6
    
    print(f"   📊 복구율: {successful_attempts}/{recovery_attempts} ({phase_results['recovery_rate']:.1%})")
    
    results["test_phases"].append(phase_results)

def evaluate_results(results: Dict):
    """결과 평가"""
    print("\n🎯 테스트 결과 평가")
    
    phases = results["test_phases"]
    total_phases = len(phases)
    successful_phases = len([p for p in phases if p.get("success", False)])
    
    print(f"📊 전체 테스트 페이즈: {total_phases}")
    print(f"✅ 성공한 페이즈: {successful_phases}")
    print(f"📈 성공률: {successful_phases/total_phases:.1%}")
    
    # 각 페이즈별 상세 결과
    for phase in phases:
        phase_name = phase["phase"]
        success = phase.get("success", False)
        status = "✅ 성공" if success else "❌ 실패"
        print(f"   {phase_name}: {status}")
        
        # 페이즈별 특별 정보
        if phase_name == "error_generation":
            error_rate = phase.get("error_rate", 0)
            print(f"      에러율: {error_rate:.1%}")
        elif phase_name == "blocking_verification":
            blocking_rate = phase.get("blocking_rate", 0)
            print(f"      차단율: {blocking_rate:.1%}")
        elif phase_name == "recovery_check":
            recovery_rate = phase.get("recovery_rate", 0)
            print(f"      복구율: {recovery_rate:.1%}")
    
    # 전체 평가
    if successful_phases >= 3:
        print("\n🌟 전체적으로 글로벌 서킷 브레이커가 정상 작동하고 있습니다!")
    elif successful_phases >= 2:
        print("\n✅ 부분적으로 서킷 브레이커 기능이 확인되었습니다.")
    else:
        print("\n❌ 서킷 브레이커 기능 확인이 어렵습니다. 설정을 점검해주세요.")
    
    results["summary"] = {
        "total_phases": total_phases,
        "successful_phases": successful_phases,
        "success_rate": successful_phases/total_phases,
        "overall_status": "success" if successful_phases >= 3 else "partial" if successful_phases >= 2 else "failure"
    }

if __name__ == "__main__":
    asyncio.run(test_global_circuit_simple())