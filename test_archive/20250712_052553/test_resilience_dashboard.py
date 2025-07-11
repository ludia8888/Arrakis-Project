#!/usr/bin/env python3
"""
리질리언스 메트릭 대시보드 테스트
종합적인 리질리언스 모니터링 및 알림 시스템 검증
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

async def test_resilience_dashboard():
    """리질리언스 메트릭 대시보드 종합 테스트"""
    print("📊 리질리언스 메트릭 대시보드 테스트 시작")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_suites": [],
        "dashboard_analysis": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test Suite 1: 대시보드 기본 기능
        await test_suite_1_dashboard_basics(client, results)
        
        # Test Suite 2: 구성요소별 상세 메트릭
        await test_suite_2_component_metrics(client, results)
        
        # Test Suite 3: 리질리언스 건강도 체크
        await test_suite_3_health_check(client, results)
        
        # Test Suite 4: 알림 및 모니터링 시스템
        await test_suite_4_alerts_monitoring(client, results)
        
        # Test Suite 5: 대시보드 응답성 및 성능
        await test_suite_5_performance(client, results)
    
    # 결과 저장 및 분석
    filename = f"resilience_dashboard_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📊 테스트 결과가 {filename}에 저장되었습니다")
    analyze_dashboard_results(results)

async def test_suite_1_dashboard_basics(client: httpx.AsyncClient, results: Dict):
    """Test Suite 1: 대시보드 기본 기능"""
    print("\n📋 Test Suite 1: 대시보드 기본 기능")
    
    suite_results = {
        "suite": "dashboard_basics",
        "tests": [],
        "success": False
    }
    
    # Test 1.1: 메인 대시보드 접근
    print("   🔍 Test 1.1: 메인 대시보드 접근")
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/resilience/dashboard", headers=HEADERS)
        test_result = {
            "test": "main_dashboard_access",
            "status_code": resp.status_code,
            "response_time": resp.elapsed.total_seconds() if hasattr(resp, 'elapsed') else 0,
            "success": resp.status_code == 200,
            "has_data": False
        }
        
        if resp.status_code == 200:
            data = resp.json()
            test_result["has_data"] = "data" in data
            test_result["dashboard_sections"] = list(data.get("data", {}).keys()) if test_result["has_data"] else []
            print(f"     ✅ 대시보드 접근 성공 (응답시간: {test_result['response_time']:.2f}초)")
            if test_result["has_data"]:
                print(f"     📊 대시보드 섹션: {test_result['dashboard_sections']}")
        else:
            print(f"     ❌ 대시보드 접근 실패 ({resp.status_code})")
        
        suite_results["tests"].append(test_result)
    except Exception as e:
        print(f"     ❌ 테스트 오류: {e}")
        suite_results["tests"].append({
            "test": "main_dashboard_access",
            "error": str(e),
            "success": False
        })
    
    # Test 1.2: 시간 범위별 메트릭 조회
    print("   🔍 Test 1.2: 시간 범위별 메트릭 조회")
    time_ranges = ["1h", "24h", "7d"]
    
    for time_range in time_ranges:
        try:
            resp = await client.get(
                f"{OMS_URL}/api/v1/resilience/dashboard?time_range={time_range}", 
                headers=HEADERS
            )
            test_result = {
                "test": f"time_range_{time_range}",
                "time_range": time_range,
                "status_code": resp.status_code,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                data = resp.json()
                test_result["data_returned"] = "data" in data
                print(f"     ✅ {time_range} 범위 조회 성공")
            else:
                print(f"     ❌ {time_range} 범위 조회 실패 ({resp.status_code})")
            
            suite_results["tests"].append(test_result)
        except Exception as e:
            print(f"     ❌ {time_range} 범위 테스트 오류: {e}")
    
    # Test 1.3: 구성요소 필터링
    print("   🔍 Test 1.3: 구성요소 필터링")
    components = ["circuit_breaker", "etag_caching", "distributed_caching", "backpressure"]
    
    for component in components:
        try:
            resp = await client.get(
                f"{OMS_URL}/api/v1/resilience/dashboard?component={component}", 
                headers=HEADERS
            )
            test_result = {
                "test": f"component_filter_{component}",
                "component": component,
                "status_code": resp.status_code,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                print(f"     ✅ {component} 필터링 성공")
            else:
                print(f"     ❌ {component} 필터링 실패 ({resp.status_code})")
            
            suite_results["tests"].append(test_result)
        except Exception as e:
            print(f"     ❌ {component} 필터링 오류: {e}")
    
    # 성공 여부 판단
    successful_tests = len([t for t in suite_results["tests"] if t.get("success", False)])
    suite_results["success"] = successful_tests >= len(suite_results["tests"]) * 0.7
    suite_results["success_rate"] = successful_tests / len(suite_results["tests"]) if suite_results["tests"] else 0
    
    print(f"   📊 Test Suite 1 성공률: {suite_results['success_rate']:.1%} ({successful_tests}/{len(suite_results['tests'])})")
    
    results["test_suites"].append(suite_results)

async def test_suite_2_component_metrics(client: httpx.AsyncClient, results: Dict):
    """Test Suite 2: 구성요소별 상세 메트릭"""
    print("\n🔧 Test Suite 2: 구성요소별 상세 메트릭")
    
    suite_results = {
        "suite": "component_metrics",
        "tests": [],
        "success": False
    }
    
    components = ["circuit_breaker", "etag_caching", "distributed_caching", "backpressure"]
    
    for component in components:
        print(f"   🔍 {component} 상세 메트릭 조회")
        try:
            resp = await client.get(
                f"{OMS_URL}/api/v1/resilience/components/{component}/metrics", 
                headers=HEADERS
            )
            test_result = {
                "test": f"{component}_detailed_metrics",
                "component": component,
                "status_code": resp.status_code,
                "success": resp.status_code == 200,
                "has_metrics": False,
                "metric_categories": []
            }
            
            if resp.status_code == 200:
                data = resp.json()
                if "metrics" in data:
                    test_result["has_metrics"] = True
                    test_result["metric_categories"] = list(data["metrics"].keys())
                    print(f"     ✅ {component} 메트릭 조회 성공")
                    print(f"     📊 메트릭 카테고리: {test_result['metric_categories']}")
                else:
                    print(f"     ⚠️ {component} 메트릭 데이터 없음")
            else:
                print(f"     ❌ {component} 메트릭 조회 실패 ({resp.status_code})")
            
            suite_results["tests"].append(test_result)
        except Exception as e:
            print(f"     ❌ {component} 메트릭 테스트 오류: {e}")
            suite_results["tests"].append({
                "test": f"{component}_detailed_metrics",
                "component": component,
                "error": str(e),
                "success": False
            })
    
    # 성공 여부 판단
    successful_tests = len([t for t in suite_results["tests"] if t.get("success", False)])
    suite_results["success"] = successful_tests >= len(components) * 0.5
    suite_results["success_rate"] = successful_tests / len(suite_results["tests"]) if suite_results["tests"] else 0
    
    print(f"   📊 Test Suite 2 성공률: {suite_results['success_rate']:.1%} ({successful_tests}/{len(suite_results['tests'])})")
    
    results["test_suites"].append(suite_results)

async def test_suite_3_health_check(client: httpx.AsyncClient, results: Dict):
    """Test Suite 3: 리질리언스 건강도 체크"""
    print("\n🏥 Test Suite 3: 리질리언스 건강도 체크")
    
    suite_results = {
        "suite": "health_check",
        "tests": [],
        "success": False
    }
    
    # Test 3.1: 종합 건강도 체크
    print("   🔍 Test 3.1: 종합 건강도 체크")
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/resilience/health-check", headers=HEADERS)
        test_result = {
            "test": "overall_health_check",
            "status_code": resp.status_code,
            "success": resp.status_code == 200,
            "health_data": None
        }
        
        if resp.status_code == 200:
            data = resp.json()
            health_data = data.get("health", {})
            test_result["health_data"] = {
                "overall_status": health_data.get("overall_status"),
                "health_ratio": health_data.get("health_ratio"),
                "component_count": len(health_data.get("components", {})),
                "critical_issues": len(health_data.get("critical_issues", [])),
                "warnings": len(health_data.get("warnings", []))
            }
            
            print(f"     ✅ 건강도 체크 성공")
            print(f"     💊 전체 상태: {test_result['health_data']['overall_status']}")
            print(f"     📊 건강 비율: {test_result['health_data']['health_ratio']:.1%}")
            print(f"     🚨 중요 이슈: {test_result['health_data']['critical_issues']}개")
            print(f"     ⚠️ 경고: {test_result['health_data']['warnings']}개")
        else:
            print(f"     ❌ 건강도 체크 실패 ({resp.status_code})")
        
        suite_results["tests"].append(test_result)
    except Exception as e:
        print(f"     ❌ 건강도 체크 오류: {e}")
        suite_results["tests"].append({
            "test": "overall_health_check",
            "error": str(e),
            "success": False
        })
    
    # 성공 여부 판단
    successful_tests = len([t for t in suite_results["tests"] if t.get("success", False)])
    suite_results["success"] = successful_tests > 0
    suite_results["success_rate"] = successful_tests / len(suite_results["tests"]) if suite_results["tests"] else 0
    
    print(f"   📊 Test Suite 3 성공률: {suite_results['success_rate']:.1%} ({successful_tests}/{len(suite_results['tests'])})")
    
    results["test_suites"].append(suite_results)

async def test_suite_4_alerts_monitoring(client: httpx.AsyncClient, results: Dict):
    """Test Suite 4: 알림 및 모니터링 시스템"""
    print("\n🚨 Test Suite 4: 알림 및 모니터링 시스템")
    
    suite_results = {
        "suite": "alerts_monitoring",
        "tests": [],
        "success": False
    }
    
    # Test 4.1: 알림 목록 조회
    print("   🔍 Test 4.1: 알림 목록 조회")
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/resilience/alerts", headers=HEADERS)
        test_result = {
            "test": "alerts_list",
            "status_code": resp.status_code,
            "success": resp.status_code == 200,
            "alert_count": 0,
            "alert_severities": []
        }
        
        if resp.status_code == 200:
            data = resp.json()
            alerts = data.get("alerts", [])
            test_result["alert_count"] = len(alerts)
            test_result["alert_severities"] = list(set(alert.get("severity") for alert in alerts))
            
            print(f"     ✅ 알림 목록 조회 성공")
            print(f"     📊 총 알림 수: {test_result['alert_count']}")
            print(f"     🏷️ 심각도 종류: {test_result['alert_severities']}")
        else:
            print(f"     ❌ 알림 목록 조회 실패 ({resp.status_code})")
        
        suite_results["tests"].append(test_result)
    except Exception as e:
        print(f"     ❌ 알림 목록 테스트 오류: {e}")
        suite_results["tests"].append({
            "test": "alerts_list",
            "error": str(e),
            "success": False
        })
    
    # Test 4.2: 심각도별 알림 필터링
    print("   🔍 Test 4.2: 심각도별 알림 필터링")
    severities = ["critical", "warning", "info"]
    
    for severity in severities:
        try:
            resp = await client.get(
                f"{OMS_URL}/api/v1/resilience/alerts?severity={severity}", 
                headers=HEADERS
            )
            test_result = {
                "test": f"alerts_filter_{severity}",
                "severity": severity,
                "status_code": resp.status_code,
                "success": resp.status_code == 200
            }
            
            if resp.status_code == 200:
                data = resp.json()
                filtered_alerts = data.get("alerts", [])
                test_result["filtered_count"] = len(filtered_alerts)
                print(f"     ✅ {severity} 필터링 성공 ({test_result['filtered_count']}개)")
            else:
                print(f"     ❌ {severity} 필터링 실패 ({resp.status_code})")
            
            suite_results["tests"].append(test_result)
        except Exception as e:
            print(f"     ❌ {severity} 필터링 오류: {e}")
    
    # 성공 여부 판단
    successful_tests = len([t for t in suite_results["tests"] if t.get("success", False)])
    suite_results["success"] = successful_tests >= len(suite_results["tests"]) * 0.7
    suite_results["success_rate"] = successful_tests / len(suite_results["tests"]) if suite_results["tests"] else 0
    
    print(f"   📊 Test Suite 4 성공률: {suite_results['success_rate']:.1%} ({successful_tests}/{len(suite_results['tests'])})")
    
    results["test_suites"].append(suite_results)

async def test_suite_5_performance(client: httpx.AsyncClient, results: Dict):
    """Test Suite 5: 대시보드 응답성 및 성능"""
    print("\n⚡ Test Suite 5: 대시보드 응답성 및 성능")
    
    suite_results = {
        "suite": "performance",
        "tests": [],
        "success": False
    }
    
    # Test 5.1: 응답 시간 측정
    print("   🔍 Test 5.1: 대시보드 응답 시간 측정")
    response_times = []
    
    for i in range(5):
        try:
            start_time = time.time()
            resp = await client.get(f"{OMS_URL}/api/v1/resilience/dashboard", headers=HEADERS)
            response_time = time.time() - start_time
            response_times.append(response_time)
            
            print(f"     📏 요청 {i+1}: {response_time:.3f}초")
        except Exception as e:
            print(f"     ❌ 요청 {i+1} 실패: {e}")
    
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        test_result = {
            "test": "response_time_measurement",
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time,
            "total_requests": len(response_times),
            "success": avg_response_time < 5.0  # 5초 이내
        }
        
        print(f"     📊 평균 응답 시간: {avg_response_time:.3f}초")
        print(f"     📊 최대 응답 시간: {max_response_time:.3f}초")
        print(f"     📊 최소 응답 시간: {min_response_time:.3f}초")
        
        if test_result["success"]:
            print(f"     ✅ 응답 시간 기준 통과 (< 5초)")
        else:
            print(f"     ❌ 응답 시간 기준 미달 (>= 5초)")
        
        suite_results["tests"].append(test_result)
    else:
        suite_results["tests"].append({
            "test": "response_time_measurement",
            "error": "No successful requests",
            "success": False
        })
    
    # Test 5.2: 동시 요청 처리
    print("   🔍 Test 5.2: 동시 요청 처리 능력")
    try:
        concurrent_requests = 10
        start_time = time.time()
        
        tasks = []
        for i in range(concurrent_requests):
            task = client.get(f"{OMS_URL}/api/v1/resilience/dashboard", headers=HEADERS)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        successful_responses = len([r for r in responses if not isinstance(r, Exception) and hasattr(r, 'status_code') and r.status_code == 200])
        
        test_result = {
            "test": "concurrent_requests",
            "total_requests": concurrent_requests,
            "successful_responses": successful_responses,
            "total_time": total_time,
            "requests_per_second": concurrent_requests / total_time,
            "success": successful_responses >= concurrent_requests * 0.8
        }
        
        print(f"     📊 동시 요청: {concurrent_requests}개")
        print(f"     📊 성공한 응답: {successful_responses}개")
        print(f"     📊 전체 처리 시간: {total_time:.3f}초")
        print(f"     📊 초당 요청 처리: {test_result['requests_per_second']:.1f} req/s")
        
        if test_result["success"]:
            print(f"     ✅ 동시 요청 처리 기준 통과")
        else:
            print(f"     ❌ 동시 요청 처리 기준 미달")
        
        suite_results["tests"].append(test_result)
    except Exception as e:
        print(f"     ❌ 동시 요청 테스트 오류: {e}")
        suite_results["tests"].append({
            "test": "concurrent_requests",
            "error": str(e),
            "success": False
        })
    
    # 성공 여부 판단
    successful_tests = len([t for t in suite_results["tests"] if t.get("success", False)])
    suite_results["success"] = successful_tests >= len(suite_results["tests"]) * 0.5
    suite_results["success_rate"] = successful_tests / len(suite_results["tests"]) if suite_results["tests"] else 0
    
    print(f"   📊 Test Suite 5 성공률: {suite_results['success_rate']:.1%} ({successful_tests}/{len(suite_results['tests'])})")
    
    results["test_suites"].append(suite_results)

def analyze_dashboard_results(results: Dict):
    """대시보드 테스트 결과 분석"""
    print("\n🔬 리질리언스 대시보드 테스트 결과 분석")
    
    suites = results["test_suites"]
    total_suites = len(suites)
    successful_suites = len([s for s in suites if s.get("success", False)])
    
    print(f"📊 전체 테스트 스위트: {total_suites}")
    print(f"✅ 성공한 스위트: {successful_suites}")
    print(f"📈 성공률: {successful_suites/total_suites:.1%}")
    
    # 스위트별 상세 결과
    for suite in suites:
        suite_name = suite["suite"]
        success = suite.get("success", False)
        success_rate = suite.get("success_rate", 0)
        status = "✅ 성공" if success else "❌ 실패"
        print(f"   {suite_name}: {status} ({success_rate:.1%})")
    
    # 대시보드 기능 점수 계산
    total_score = 0
    max_score = 100
    
    for suite in suites:
        suite_name = suite["suite"]
        success_rate = suite.get("success_rate", 0)
        
        if suite_name == "dashboard_basics":
            score = int(30 * success_rate)
            total_score += score
            print(f"✅ 대시보드 기본 기능: {score}/30점")
        elif suite_name == "component_metrics":
            score = int(25 * success_rate)
            total_score += score
            print(f"✅ 구성요소 메트릭: {score}/25점")
        elif suite_name == "health_check":
            score = int(20 * success_rate)
            total_score += score
            print(f"✅ 건강도 체크: {score}/20점")
        elif suite_name == "alerts_monitoring":
            score = int(15 * success_rate)
            total_score += score
            print(f"✅ 알림 모니터링: {score}/15점")
        elif suite_name == "performance":
            score = int(10 * success_rate)
            total_score += score
            print(f"✅ 성능 테스트: {score}/10점")
    
    print(f"\n🏆 리질리언스 대시보드 점수: {total_score}/{max_score}")
    
    # 평가 결과
    if total_score >= 90:
        evaluation = "excellent"
        print("🌟 EXCELLENT - 리질리언스 대시보드가 완벽하게 구현되었습니다!")
    elif total_score >= 75:
        evaluation = "good"
        print("✅ GOOD - 대시보드가 잘 구현되었습니다!")
    elif total_score >= 60:
        evaluation = "fair"
        print("⚠️ FAIR - 부분적으로 대시보드 기능이 구현되었습니다.")
    else:
        evaluation = "poor"
        print("❌ POOR - 대시보드 구현에 문제가 있습니다.")
    
    # 권장사항
    recommendations = []
    if total_score < 90:
        recommendations.append("일부 대시보드 기능의 안정성을 개선하세요")
    if any(s.get("success_rate", 0) < 0.8 for s in suites if s["suite"] == "performance"):
        recommendations.append("대시보드 응답 성능을 최적화하세요")
    if any(s.get("success_rate", 0) < 0.5 for s in suites if s["suite"] == "alerts_monitoring"):
        recommendations.append("알림 시스템의 신뢰성을 향상시키세요")
    
    results["dashboard_analysis"] = {
        "total_score": total_score,
        "max_score": max_score,
        "success_rate": successful_suites/total_suites,
        "evaluation": evaluation,
        "recommendations": recommendations
    }

if __name__ == "__main__":
    asyncio.run(test_resilience_dashboard())