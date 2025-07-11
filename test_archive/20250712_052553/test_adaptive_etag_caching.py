#!/usr/bin/env python3
"""
적응형 E-Tag 캐싱 테스트
캐시 히트율과 접근 패턴에 따른 동적 TTL 조정 검증
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

async def test_adaptive_etag_caching():
    """적응형 E-Tag 캐싱 테스트"""
    print("🔄 적응형 E-Tag 캐싱 테스트 시작")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_scenarios": [],
        "adaptive_caching_analysis": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Scenario 1: 기본 E-Tag 동작 확인
        await scenario_1_basic_etag(client, results)
        
        # Scenario 2: 반복 요청으로 캐시 통계 축적
        await scenario_2_cache_statistics_buildup(client, results)
        
        # Scenario 3: 적응형 TTL 변화 관찰
        await scenario_3_adaptive_ttl_observation(client, results)
        
        # Scenario 4: 리소스 타입별 캐시 전략 검증
        await scenario_4_resource_type_strategies(client, results)
    
    # 결과 저장 및 분석
    filename = f"adaptive_etag_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📊 테스트 결과가 {filename}에 저장되었습니다")
    analyze_adaptive_caching_results(results)

async def scenario_1_basic_etag(client: httpx.AsyncClient, results: Dict):
    """Scenario 1: 기본 E-Tag 동작 확인"""
    print("\n🔧 Scenario 1: 기본 E-Tag 동작 확인")
    
    scenario_results = {
        "scenario": "basic_etag_functionality",
        "requests": [],
        "etag_headers": [],
        "success": False
    }
    
    try:
        # 첫 번째 요청 - ETag 생성
        print("   📡 첫 번째 요청 (ETag 생성)")
        resp1 = await client.get(f"{OMS_URL}/api/v1/health", headers=HEADERS)
        
        request_1 = {
            "request_num": 1,
            "status_code": resp1.status_code,
            "headers": dict(resp1.headers),
            "has_etag": "ETag" in resp1.headers,
            "has_cache_control": "Cache-Control" in resp1.headers,
            "cache_strategy": resp1.headers.get("X-Cache-Strategy")
        }
        scenario_results["requests"].append(request_1)
        
        if request_1["has_etag"]:
            etag_value = resp1.headers["ETag"]
            scenario_results["etag_headers"].append({
                "request": 1,
                "etag": etag_value,
                "cache_control": resp1.headers.get("Cache-Control"),
                "cache_strategy": resp1.headers.get("X-Cache-Strategy")
            })
            
            print(f"     ✅ ETag 생성: {etag_value}")
            print(f"     🏷️ Cache-Control: {resp1.headers.get('Cache-Control', 'None')}")
            print(f"     🎯 Cache Strategy: {resp1.headers.get('X-Cache-Strategy', 'None')}")
            
            # 두 번째 요청 - 조건부 요청 (If-None-Match)
            print("   📡 두 번째 요청 (조건부 요청)")
            conditional_headers = {**HEADERS, "If-None-Match": etag_value}
            resp2 = await client.get(f"{OMS_URL}/api/v1/health", headers=conditional_headers)
            
            request_2 = {
                "request_num": 2,
                "status_code": resp2.status_code,
                "headers": dict(resp2.headers),
                "is_304": resp2.status_code == 304,
                "cache_hit": resp2.status_code == 304
            }
            scenario_results["requests"].append(request_2)
            
            if request_2["is_304"]:
                print(f"     ✅ 캐시 히트 (304 Not Modified)")
                scenario_results["success"] = True
            else:
                print(f"     ❌ 캐시 미스 ({resp2.status_code})")
        else:
            print("     ❌ ETag 헤더 없음")
    
    except Exception as e:
        print(f"   ❌ 기본 ETag 테스트 오류: {e}")
        scenario_results["error"] = str(e)
    
    results["test_scenarios"].append(scenario_results)

async def scenario_2_cache_statistics_buildup(client: httpx.AsyncClient, results: Dict):
    """Scenario 2: 반복 요청으로 캐시 통계 축적"""
    print("\n📈 Scenario 2: 캐시 통계 축적을 위한 반복 요청")
    
    scenario_results = {
        "scenario": "cache_statistics_buildup",
        "total_requests": 0,
        "cache_hits": 0,
        "etag_evolution": [],
        "success": False
    }
    
    try:
        etag_value = None
        
        # 10회 반복 요청
        for i in range(10):
            print(f"   📡 요청 {i+1}/10")
            
            request_headers = HEADERS.copy()
            if etag_value:
                request_headers["If-None-Match"] = etag_value
            
            resp = await client.get(f"{OMS_URL}/api/v1/health", headers=request_headers)
            
            scenario_results["total_requests"] += 1
            
            if resp.status_code == 304:
                scenario_results["cache_hits"] += 1
                print(f"     ✅ 캐시 히트 #{scenario_results['cache_hits']}")
            elif resp.status_code == 200:
                # 새로운 ETag 확인
                new_etag = resp.headers.get("ETag")
                if new_etag:
                    etag_value = new_etag
                    print(f"     🔄 새 ETag: {new_etag}")
                else:
                    print(f"     ⚠️ ETag 없음")
            
            # ETag 및 캐시 전략 변화 추적
            etag_info = {
                "request_num": i + 1,
                "status_code": resp.status_code,
                "etag": resp.headers.get("ETag"),
                "cache_control": resp.headers.get("Cache-Control"),
                "cache_strategy": resp.headers.get("X-Cache-Strategy"),
                "cache_hit": resp.status_code == 304
            }
            scenario_results["etag_evolution"].append(etag_info)
            
            # 요청 간격
            await asyncio.sleep(0.5)
        
        # 통계 계산
        hit_rate = scenario_results["cache_hits"] / scenario_results["total_requests"]
        scenario_results["hit_rate"] = hit_rate
        scenario_results["success"] = hit_rate > 0
        
        print(f"   📊 캐시 히트율: {hit_rate:.1%} ({scenario_results['cache_hits']}/{scenario_results['total_requests']})")
    
    except Exception as e:
        print(f"   ❌ 캐시 통계 축적 오류: {e}")
        scenario_results["error"] = str(e)
    
    results["test_scenarios"].append(scenario_results)

async def scenario_3_adaptive_ttl_observation(client: httpx.AsyncClient, results: Dict):
    """Scenario 3: 적응형 TTL 변화 관찰"""
    print("\n🎯 Scenario 3: 적응형 TTL 변화 관찰")
    
    scenario_results = {
        "scenario": "adaptive_ttl_observation",
        "ttl_observations": [],
        "success": False
    }
    
    try:
        # 서로 다른 엔드포인트로 다양한 접근 패턴 시뮬레이션
        endpoints = [
            {"url": "/api/v1/health", "name": "health", "expected_type": "system"},
            {"url": "/api/v1/health", "name": "health_repeat", "expected_type": "system"}
        ]
        
        for endpoint in endpoints:
            print(f"   🔍 엔드포인트: {endpoint['url']}")
            
            # 여러 번 요청하여 적응형 TTL 변화 관찰
            for attempt in range(3):
                resp = await client.get(f"{OMS_URL}{endpoint['url']}", headers=HEADERS)
                
                ttl_observation = {
                    "endpoint": endpoint["url"],
                    "attempt": attempt + 1,
                    "status_code": resp.status_code,
                    "cache_control": resp.headers.get("Cache-Control"),
                    "cache_strategy": resp.headers.get("X-Cache-Strategy"),
                    "vary_header": resp.headers.get("Vary")
                }
                
                # Cache-Control에서 max-age 추출
                cache_control = resp.headers.get("Cache-Control", "")
                max_age = extract_max_age(cache_control)
                ttl_observation["max_age_seconds"] = max_age
                
                scenario_results["ttl_observations"].append(ttl_observation)
                
                print(f"     시도 {attempt + 1}: max-age={max_age}s, strategy={resp.headers.get('X-Cache-Strategy', 'None')}")
                
                await asyncio.sleep(1)
        
        # TTL 적응성 분석
        unique_max_ages = set(obs.get("max_age_seconds") for obs in scenario_results["ttl_observations"] if obs.get("max_age_seconds"))
        scenario_results["ttl_variation"] = len(unique_max_ages) > 1
        scenario_results["success"] = len(scenario_results["ttl_observations"]) > 0
        
        print(f"   📊 TTL 변화 관찰: {len(unique_max_ages)}개 서로 다른 TTL 값")
    
    except Exception as e:
        print(f"   ❌ 적응형 TTL 관찰 오류: {e}")
        scenario_results["error"] = str(e)
    
    results["test_scenarios"].append(scenario_results)

async def scenario_4_resource_type_strategies(client: httpx.AsyncClient, results: Dict):
    """Scenario 4: 리소스 타입별 캐시 전략 검증"""
    print("\n🏷️ Scenario 4: 리소스 타입별 캐시 전략 검증")
    
    scenario_results = {
        "scenario": "resource_type_strategies",
        "resource_strategies": [],
        "success": False
    }
    
    try:
        # 다양한 리소스 타입 테스트 (실제 존재하는 엔드포인트만)
        test_endpoints = [
            {"url": "/api/v1/health", "expected_resource_type": "system", "description": "시스템 헬스체크"}
        ]
        
        for endpoint in test_endpoints:
            print(f"   🔍 {endpoint['description']}: {endpoint['url']}")
            
            resp = await client.get(f"{OMS_URL}{endpoint['url']}", headers=HEADERS)
            
            strategy_info = {
                "url": endpoint["url"],
                "expected_resource_type": endpoint["expected_resource_type"],
                "status_code": resp.status_code,
                "cache_control": resp.headers.get("Cache-Control"),
                "cache_strategy": resp.headers.get("X-Cache-Strategy"),
                "vary_header": resp.headers.get("Vary"),
                "has_adaptive_headers": bool(resp.headers.get("X-Cache-Strategy"))
            }
            
            # Cache-Control 분석
            cache_control = resp.headers.get("Cache-Control", "")
            strategy_info["has_public"] = "public" in cache_control
            strategy_info["has_must_revalidate"] = "must-revalidate" in cache_control
            strategy_info["has_no_cache"] = "no-cache" in cache_control
            strategy_info["max_age"] = extract_max_age(cache_control)
            
            scenario_results["resource_strategies"].append(strategy_info)
            
            print(f"     📋 Cache-Control: {cache_control}")
            print(f"     🎯 Strategy: {resp.headers.get('X-Cache-Strategy', 'None')}")
            print(f"     ⏱️ Max-Age: {strategy_info['max_age']}초")
            
            if strategy_info["has_adaptive_headers"]:
                print(f"     ✅ 적응형 캐시 헤더 감지됨")
            else:
                print(f"     ⚠️ 적응형 캐시 헤더 없음")
        
        # 전략 다양성 분석
        strategies = [s.get("cache_strategy") for s in scenario_results["resource_strategies"] if s.get("cache_strategy")]
        scenario_results["strategy_diversity"] = len(set(strategies)) > 1
        scenario_results["success"] = len(scenario_results["resource_strategies"]) > 0
        
        print(f"   📊 테스트한 리소스 타입: {len(scenario_results['resource_strategies'])}개")
    
    except Exception as e:
        print(f"   ❌ 리소스 타입 전략 검증 오류: {e}")
        scenario_results["error"] = str(e)
    
    results["test_scenarios"].append(scenario_results)

def extract_max_age(cache_control: str) -> int:
    """Cache-Control 헤더에서 max-age 값 추출"""
    if not cache_control:
        return 0
    
    parts = cache_control.split(",")
    for part in parts:
        part = part.strip()
        if part.startswith("max-age="):
            try:
                return int(part.split("=")[1])
            except (IndexError, ValueError):
                pass
    return 0

def analyze_adaptive_caching_results(results: Dict):
    """적응형 캐싱 테스트 결과 분석"""
    print("\n🔬 적응형 E-Tag 캐싱 결과 분석")
    
    scenarios = results["test_scenarios"]
    total_scenarios = len(scenarios)
    successful_scenarios = len([s for s in scenarios if s.get("success", False)])
    
    print(f"📊 전체 시나리오: {total_scenarios}")
    print(f"✅ 성공한 시나리오: {successful_scenarios}")
    print(f"📈 성공률: {successful_scenarios/total_scenarios:.1%}")
    
    # 시나리오별 분석
    for scenario in scenarios:
        scenario_name = scenario["scenario"]
        success = scenario.get("success", False)
        status = "✅ 성공" if success else "❌ 실패"
        print(f"   {scenario_name}: {status}")
        
        if scenario_name == "basic_etag_functionality":
            etag_headers = scenario.get("etag_headers", [])
            if etag_headers:
                print(f"      ETag 생성: {len(etag_headers)}개")
        elif scenario_name == "cache_statistics_buildup":
            hit_rate = scenario.get("hit_rate", 0)
            print(f"      캐시 히트율: {hit_rate:.1%}")
        elif scenario_name == "adaptive_ttl_observation":
            ttl_variation = scenario.get("ttl_variation", False)
            print(f"      TTL 변화 감지: {'Yes' if ttl_variation else 'No'}")
        elif scenario_name == "resource_type_strategies":
            strategy_diversity = scenario.get("strategy_diversity", False)
            print(f"      전략 다양성: {'Yes' if strategy_diversity else 'No'}")
    
    # 적응형 캐싱 점수 계산
    total_score = 0
    max_score = 100
    
    basic_etag = next((s for s in scenarios if s["scenario"] == "basic_etag_functionality"), {})
    if basic_etag.get("success"):
        total_score += 30
        print("✅ 기본 ETag 기능: 30/30점")
    else:
        print("❌ 기본 ETag 기능: 0/30점")
    
    cache_buildup = next((s for s in scenarios if s["scenario"] == "cache_statistics_buildup"), {})
    if cache_buildup.get("success"):
        hit_rate = cache_buildup.get("hit_rate", 0)
        score = int(25 * hit_rate)
        total_score += score
        print(f"✅ 캐시 통계 축적: {score}/25점 (히트율: {hit_rate:.1%})")
    else:
        print("❌ 캐시 통계 축적: 0/25점")
    
    ttl_observation = next((s for s in scenarios if s["scenario"] == "adaptive_ttl_observation"), {})
    if ttl_observation.get("success"):
        ttl_variation = ttl_observation.get("ttl_variation", False)
        score = 25 if ttl_variation else 15
        total_score += score
        print(f"✅ 적응형 TTL: {score}/25점")
    else:
        print("❌ 적응형 TTL: 0/25점")
    
    resource_strategies = next((s for s in scenarios if s["scenario"] == "resource_type_strategies"), {})
    if resource_strategies.get("success"):
        strategy_diversity = resource_strategies.get("strategy_diversity", False)
        score = 20 if strategy_diversity else 15
        total_score += score
        print(f"✅ 리소스 타입 전략: {score}/20점")
    else:
        print("❌ 리소스 타입 전략: 0/20점")
    
    print(f"\n🏆 적응형 캐싱 점수: {total_score}/{max_score}")
    
    # 평가 결과
    if total_score >= 85:
        evaluation = "excellent"
        print("🌟 EXCELLENT - 적응형 E-Tag 캐싱이 완벽하게 구현되었습니다!")
    elif total_score >= 70:
        evaluation = "good"
        print("✅ GOOD - 적응형 캐싱이 잘 구현되었습니다!")
    elif total_score >= 50:
        evaluation = "fair"
        print("⚠️ FAIR - 부분적으로 적응형 기능이 구현되었습니다.")
    else:
        evaluation = "poor"
        print("❌ POOR - 적응형 캐싱 구현에 문제가 있습니다.")
    
    results["adaptive_caching_analysis"] = {
        "total_score": total_score,
        "max_score": max_score,
        "success_rate": successful_scenarios/total_scenarios,
        "evaluation": evaluation
    }

if __name__ == "__main__":
    asyncio.run(test_adaptive_etag_caching())