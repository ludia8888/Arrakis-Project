#!/usr/bin/env python3
"""
엔터프라이즈 관찰성 통합 테스트
Prometheus + Grafana + Jaeger 통합 시스템 검증
"""
import asyncio
import sys
import time
import json
import httpx
from datetime import datetime
from typing import Dict, Any, List

# OMS 경로 추가
sys.path.append('/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service')

# 서비스 URL 설정
OMS_URL = "http://localhost:8091"
GRAFANA_URL = "http://localhost:3000"
PROMETHEUS_URL = "http://localhost:9091"
JAEGER_URL = "http://localhost:16686"

async def test_enterprise_observability_integration():
    """엔터프라이즈 관찰성 통합 테스트"""
    print("🎯 엔터프라이즈 관찰성 통합 테스트 시작")
    print("=" * 80)
    
    results = {
        "test_metadata": {
            "timestamp": datetime.now().isoformat(),
            "test_type": "enterprise_observability_integration",
            "version": "1.0.0"
        },
        "test_phases": [],
        "overall_status": "unknown"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: 엔터프라이즈 메트릭 시스템 테스트
        await test_phase_1_enterprise_metrics(client, results)
        
        # Phase 2: 관찰성 스택 가용성 테스트
        await test_phase_2_observability_stack(client, results)
        
        # Phase 3: 통합 모니터링 기능 테스트
        await test_phase_3_integrated_monitoring(client, results)
        
        # Phase 4: 대시보드 접근 테스트
        await test_phase_4_dashboard_access(client, results)
    
    # 최종 결과 저장
    filename = f"enterprise_observability_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📋 상세 결과가 {filename}에 저장되었습니다")
    generate_test_summary(results)

async def test_phase_1_enterprise_metrics(client: httpx.AsyncClient, results: Dict):
    """Phase 1: 엔터프라이즈 메트릭 시스템 테스트"""
    print("\n📊 Phase 1: 엔터프라이즈 메트릭 시스템 테스트")
    print("-" * 60)
    
    phase_results = {
        "phase": "enterprise_metrics",
        "start_time": datetime.now().isoformat(),
        "tests": [],
        "success": False
    }
    
    # 1.1 OMS 서비스 가용성 확인
    print("🔍 1.1 OMS 서비스 가용성 확인")
    try:
        resp = await client.get(f"{OMS_URL}/api/v1/health")
        oms_available = resp.status_code == 200
        print(f"   {'✅' if oms_available else '❌'} OMS 서비스: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "oms_service_health",
            "status_code": resp.status_code,
            "success": oms_available
        })
    except Exception as e:
        print(f"   ❌ OMS 연결 실패: {e}")
        phase_results["tests"].append({
            "test": "oms_service_health",
            "error": str(e),
            "success": False
        })
        oms_available = False
    
    # 1.2 Prometheus 메트릭 엔드포인트 테스트
    print("🔍 1.2 Prometheus 메트릭 엔드포인트 테스트")
    if oms_available:
        try:
            resp = await client.get(f"{OMS_URL}/metrics")
            metrics_available = resp.status_code == 200
            
            if metrics_available:
                metrics_content = resp.text
                metrics_count = len([line for line in metrics_content.split('\n') if line.startswith('# HELP')])
                print(f"   ✅ Prometheus 메트릭: {metrics_count}개 메트릭 발견")
                
                # 엔터프라이즈 메트릭 확인
                enterprise_metrics = [
                    "circuit_breaker_state",
                    "etag_cache_requests_total", 
                    "python_gc_collections_total",
                    "system_cpu_usage_percent",
                    "http_requests_total"
                ]
                
                found_metrics = []
                for metric in enterprise_metrics:
                    if metric in metrics_content:
                        found_metrics.append(metric)
                
                print(f"   📊 엔터프라이즈 메트릭: {len(found_metrics)}/{len(enterprise_metrics)}개 발견")
                for metric in found_metrics:
                    print(f"      ✅ {metric}")
                
                phase_results["tests"].append({
                    "test": "prometheus_metrics_endpoint",
                    "status_code": resp.status_code,
                    "total_metrics": metrics_count,
                    "enterprise_metrics_found": len(found_metrics),
                    "enterprise_metrics_expected": len(enterprise_metrics),
                    "found_metrics": found_metrics,
                    "success": len(found_metrics) >= 3  # 최소 3개 메트릭 필요
                })
            else:
                print(f"   ❌ Prometheus 메트릭 엔드포인트 실패: {resp.status_code}")
                phase_results["tests"].append({
                    "test": "prometheus_metrics_endpoint", 
                    "status_code": resp.status_code,
                    "success": False
                })
                
        except Exception as e:
            print(f"   ❌ 메트릭 엔드포인트 오류: {e}")
            phase_results["tests"].append({
                "test": "prometheus_metrics_endpoint",
                "error": str(e),
                "success": False
            })
    
    # 1.3 관찰성 건강도 엔드포인트 테스트
    print("🔍 1.3 관찰성 건강도 엔드포인트 테스트")
    if oms_available:
        try:
            resp = await client.get(f"{OMS_URL}/observability/health")
            health_available = resp.status_code == 200
            
            if health_available:
                health_data = resp.json()
                print(f"   ✅ 관찰성 건강도: {health_data.get('status', 'unknown')}")
                
                components = health_data.get('components', {})
                for component, status in components.items():
                    print(f"      📊 {component}: {status}")
                
                phase_results["tests"].append({
                    "test": "observability_health",
                    "status_code": resp.status_code,
                    "health_status": health_data.get('status'),
                    "components": components,
                    "success": health_data.get('status') == 'healthy'
                })
            else:
                print(f"   ❌ 관찰성 건강도 엔드포인트 실패: {resp.status_code}")
                phase_results["tests"].append({
                    "test": "observability_health",
                    "status_code": resp.status_code, 
                    "success": False
                })
                
        except Exception as e:
            print(f"   ❌ 관찰성 건강도 오류: {e}")
            phase_results["tests"].append({
                "test": "observability_health",
                "error": str(e),
                "success": False
            })
    
    # Phase 1 성공 여부 판단
    successful_tests = len([t for t in phase_results["tests"] if t.get("success", False)])
    phase_results["success"] = successful_tests >= 2  # 최소 2개 테스트 성공 필요
    phase_results["success_rate"] = successful_tests / len(phase_results["tests"]) if phase_results["tests"] else 0
    
    print(f"📊 Phase 1 결과: {'✅ 성공' if phase_results['success'] else '❌ 실패'} ({successful_tests}/{len(phase_results['tests'])})")
    
    results["test_phases"].append(phase_results)

async def test_phase_2_observability_stack(client: httpx.AsyncClient, results: Dict):
    """Phase 2: 관찰성 스택 가용성 테스트"""
    print("\n🔍 Phase 2: 관찰성 스택 가용성 테스트")
    print("-" * 60)
    
    phase_results = {
        "phase": "observability_stack_availability",
        "start_time": datetime.now().isoformat(),
        "tests": [],
        "success": False
    }
    
    # 2.1 Prometheus 서버 테스트
    print("🔍 2.1 Prometheus 서버 테스트")
    try:
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": "up"})
        prometheus_available = resp.status_code == 200
        
        if prometheus_available:
            data = resp.json()
            targets = len(data.get('data', {}).get('result', []))
            print(f"   ✅ Prometheus 서버: {targets}개 타겟 모니터링 중")
        else:
            print(f"   ❌ Prometheus 서버 접근 실패: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "prometheus_server",
            "status_code": resp.status_code,
            "targets_count": targets if prometheus_available else 0,
            "success": prometheus_available
        })
        
    except Exception as e:
        print(f"   ❌ Prometheus 연결 오류: {e}")
        phase_results["tests"].append({
            "test": "prometheus_server",
            "error": str(e),
            "success": False
        })
    
    # 2.2 Grafana 서버 테스트
    print("🔍 2.2 Grafana 서버 테스트")
    try:
        resp = await client.get(f"{GRAFANA_URL}/api/health")
        grafana_available = resp.status_code == 200
        
        if grafana_available:
            print(f"   ✅ Grafana 서버: 정상 응답")
        else:
            print(f"   ❌ Grafana 서버 접근 실패: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "grafana_server",
            "status_code": resp.status_code,
            "success": grafana_available
        })
        
    except Exception as e:
        print(f"   ❌ Grafana 연결 오류: {e}")
        phase_results["tests"].append({
            "test": "grafana_server",
            "error": str(e),
            "success": False
        })
    
    # 2.3 Jaeger 서버 테스트
    print("🔍 2.3 Jaeger 서버 테스트")
    try:
        resp = await client.get(f"{JAEGER_URL}/api/services")
        jaeger_available = resp.status_code == 200
        
        if jaeger_available:
            services = resp.json()
            service_count = len(services.get('data', []))
            print(f"   ✅ Jaeger 서버: {service_count}개 서비스 추적 중")
        else:
            print(f"   ❌ Jaeger 서버 접근 실패: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "jaeger_server", 
            "status_code": resp.status_code,
            "services_count": service_count if jaeger_available else 0,
            "success": jaeger_available
        })
        
    except Exception as e:
        print(f"   ❌ Jaeger 연결 오류: {e}")
        phase_results["tests"].append({
            "test": "jaeger_server",
            "error": str(e),
            "success": False
        })
    
    # Phase 2 성공 여부 판단
    successful_tests = len([t for t in phase_results["tests"] if t.get("success", False)])
    phase_results["success"] = successful_tests >= 2  # 최소 2개 서버 사용 가능해야 함
    phase_results["success_rate"] = successful_tests / len(phase_results["tests"]) if phase_results["tests"] else 0
    
    print(f"📊 Phase 2 결과: {'✅ 성공' if phase_results['success'] else '❌ 실패'} ({successful_tests}/{len(phase_results['tests'])})")
    
    results["test_phases"].append(phase_results)

async def test_phase_3_integrated_monitoring(client: httpx.AsyncClient, results: Dict):
    """Phase 3: 통합 모니터링 기능 테스트"""
    print("\n🔄 Phase 3: 통합 모니터링 기능 테스트")
    print("-" * 60)
    
    phase_results = {
        "phase": "integrated_monitoring",
        "start_time": datetime.now().isoformat(),
        "tests": [],
        "success": False
    }
    
    # 3.1 메트릭 데이터 흐름 테스트
    print("🔍 3.1 메트릭 데이터 흐름 테스트")
    try:
        # OMS에서 몇 번의 요청 생성
        for i in range(5):
            await client.get(f"{OMS_URL}/api/v1/health")
        
        # 잠시 대기 (메트릭 수집 시간)
        await asyncio.sleep(2)
        
        # Prometheus에서 메트릭 조회
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", 
                               params={"query": "http_requests_total"})
        
        if resp.status_code == 200:
            data = resp.json()
            metric_results = data.get('data', {}).get('result', [])
            
            if metric_results:
                print(f"   ✅ HTTP 요청 메트릭: {len(metric_results)}개 시계열 발견")
                
                # 값 확인
                for result in metric_results[:3]:  # 처음 3개만 표시
                    metric_name = result.get('metric', {})
                    value = result.get('value', [None, '0'])[1]
                    print(f"      📊 {metric_name.get('__name__', 'unknown')}: {value}")
                
                phase_results["tests"].append({
                    "test": "metrics_data_flow",
                    "status_code": resp.status_code,
                    "metrics_found": len(metric_results),
                    "success": len(metric_results) > 0
                })
            else:
                print(f"   ⚠️ HTTP 요청 메트릭 데이터 없음")
                phase_results["tests"].append({
                    "test": "metrics_data_flow",
                    "status_code": resp.status_code,
                    "metrics_found": 0,
                    "success": False
                })
        else:
            print(f"   ❌ Prometheus 쿼리 실패: {resp.status_code}")
            phase_results["tests"].append({
                "test": "metrics_data_flow",
                "status_code": resp.status_code,
                "success": False
            })
            
    except Exception as e:
        print(f"   ❌ 메트릭 데이터 흐름 테스트 오류: {e}")
        phase_results["tests"].append({
            "test": "metrics_data_flow",
            "error": str(e),
            "success": False
        })
    
    # 3.2 엔터프라이즈 메트릭 확인
    print("🔍 3.2 엔터프라이즈 메트릭 확인")
    enterprise_metrics_queries = [
        ("circuit_breaker_state", "서킷 브레이커 상태"),
        ("python_gc_collections_total", "가비지 컬렉션"),
        ("system_memory_usage_percent", "메모리 사용률"),
        ("process_cpu_seconds_total", "CPU 사용량")
    ]
    
    found_enterprise_metrics = 0
    
    for metric_query, description in enterprise_metrics_queries:
        try:
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query",
                                   params={"query": metric_query})
            
            if resp.status_code == 200:
                data = resp.json()
                results_count = len(data.get('data', {}).get('result', []))
                
                if results_count > 0:
                    found_enterprise_metrics += 1
                    print(f"      ✅ {description}: {results_count}개 시계열")
                else:
                    print(f"      ⚠️ {description}: 데이터 없음")
            else:
                print(f"      ❌ {description}: 쿼리 실패 ({resp.status_code})")
                
        except Exception as e:
            print(f"      ❌ {description}: 오류 ({e})")
    
    phase_results["tests"].append({
        "test": "enterprise_metrics_verification",
        "total_metrics_checked": len(enterprise_metrics_queries),
        "found_metrics": found_enterprise_metrics,
        "success": found_enterprise_metrics >= 2  # 최소 2개 메트릭 필요
    })
    
    print(f"   📊 엔터프라이즈 메트릭: {found_enterprise_metrics}/{len(enterprise_metrics_queries)}개 활성")
    
    # Phase 3 성공 여부 판단
    successful_tests = len([t for t in phase_results["tests"] if t.get("success", False)])
    phase_results["success"] = successful_tests >= 1  # 최소 1개 테스트 성공
    phase_results["success_rate"] = successful_tests / len(phase_results["tests"]) if phase_results["tests"] else 0
    
    print(f"📊 Phase 3 결과: {'✅ 성공' if phase_results['success'] else '❌ 실패'} ({successful_tests}/{len(phase_results['tests'])})")
    
    results["test_phases"].append(phase_results)

async def test_phase_4_dashboard_access(client: httpx.AsyncClient, results: Dict):
    """Phase 4: 대시보드 접근 테스트"""
    print("\n📈 Phase 4: 대시보드 접근 테스트")
    print("-" * 60)
    
    phase_results = {
        "phase": "dashboard_access",
        "start_time": datetime.now().isoformat(),
        "tests": [],
        "success": False
    }
    
    # 4.1 Grafana 대시보드 API 테스트
    print("🔍 4.1 Grafana 대시보드 목록 확인")
    try:
        # Grafana API 기본 접근 (인증 없이)
        resp = await client.get(f"{GRAFANA_URL}/api/search", params={"type": "dash-db"})
        
        if resp.status_code == 200:
            dashboards = resp.json()
            dashboard_count = len(dashboards)
            print(f"   ✅ Grafana 대시보드: {dashboard_count}개 발견")
            
            # 엔터프라이즈 리질리언스 대시보드 찾기
            enterprise_dashboard = None
            for dashboard in dashboards:
                if "resilience" in dashboard.get("title", "").lower() or "enterprise" in dashboard.get("title", "").lower():
                    enterprise_dashboard = dashboard
                    break
            
            if enterprise_dashboard:
                print(f"      ✅ 엔터프라이즈 대시보드 발견: {enterprise_dashboard.get('title')}")
            else:
                print(f"      ⚠️ 엔터프라이즈 리질리언스 대시보드를 찾을 수 없음")
            
            phase_results["tests"].append({
                "test": "grafana_dashboards",
                "status_code": resp.status_code,
                "dashboard_count": dashboard_count,
                "enterprise_dashboard_found": enterprise_dashboard is not None,
                "success": dashboard_count > 0
            })
            
        else:
            print(f"   ❌ Grafana 대시보드 API 실패: {resp.status_code}")
            phase_results["tests"].append({
                "test": "grafana_dashboards",
                "status_code": resp.status_code,
                "success": False
            })
            
    except Exception as e:
        print(f"   ❌ Grafana 대시보드 접근 오류: {e}")
        phase_results["tests"].append({
            "test": "grafana_dashboards",
            "error": str(e),
            "success": False
        })
    
    # 4.2 Prometheus Web UI 테스트
    print("🔍 4.2 Prometheus Web UI 접근 확인")
    try:
        resp = await client.get(f"{PROMETHEUS_URL}/graph")
        prometheus_ui_available = resp.status_code == 200
        
        if prometheus_ui_available:
            print(f"   ✅ Prometheus Web UI: 접근 가능")
        else:
            print(f"   ❌ Prometheus Web UI 접근 실패: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "prometheus_web_ui",
            "status_code": resp.status_code,
            "success": prometheus_ui_available
        })
        
    except Exception as e:
        print(f"   ❌ Prometheus Web UI 오류: {e}")
        phase_results["tests"].append({
            "test": "prometheus_web_ui",
            "error": str(e),
            "success": False
        })
    
    # 4.3 Jaeger UI 테스트
    print("🔍 4.3 Jaeger UI 접근 확인")
    try:
        resp = await client.get(f"{JAEGER_URL}/search")
        jaeger_ui_available = resp.status_code == 200
        
        if jaeger_ui_available:
            print(f"   ✅ Jaeger UI: 접근 가능")
        else:
            print(f"   ❌ Jaeger UI 접근 실패: {resp.status_code}")
        
        phase_results["tests"].append({
            "test": "jaeger_web_ui",
            "status_code": resp.status_code,
            "success": jaeger_ui_available
        })
        
    except Exception as e:
        print(f"   ❌ Jaeger UI 오류: {e}")
        phase_results["tests"].append({
            "test": "jaeger_web_ui",
            "error": str(e),
            "success": False
        })
    
    # Phase 4 성공 여부 판단
    successful_tests = len([t for t in phase_results["tests"] if t.get("success", False)])
    phase_results["success"] = successful_tests >= 2  # 최소 2개 UI 접근 가능해야 함
    phase_results["success_rate"] = successful_tests / len(phase_results["tests"]) if phase_results["tests"] else 0
    
    print(f"📊 Phase 4 결과: {'✅ 성공' if phase_results['success'] else '❌ 실패'} ({successful_tests}/{len(phase_results['tests'])})")
    
    results["test_phases"].append(phase_results)

def generate_test_summary(results: Dict):
    """테스트 결과 요약 생성"""
    print("\n" + "=" * 80)
    print("🎯 엔터프라이즈 관찰성 통합 테스트 결과 요약")
    print("=" * 80)
    
    phases = results["test_phases"]
    total_phases = len(phases)
    successful_phases = len([p for p in phases if p.get("success", False)])
    
    print(f"📊 전체 테스트 페이즈: {total_phases}")
    print(f"✅ 성공한 페이즈: {successful_phases}")
    print(f"📈 전체 성공률: {successful_phases/total_phases:.1%}")
    
    print("\n📋 페이즈별 상세 결과:")
    for phase in phases:
        phase_name = phase["phase"]
        success = phase.get("success", False)
        success_rate = phase.get("success_rate", 0)
        status = "✅ 성공" if success else "❌ 실패"
        print(f"   {phase_name}: {status} ({success_rate:.1%})")
    
    # 대시보드 접근 정보
    print("\n🌐 대시보드 접근 정보:")
    print(f"   📊 Prometheus: {PROMETHEUS_URL}")
    print(f"   📈 Grafana: {GRAFANA_URL}")
    print(f"   🔍 Jaeger: {JAEGER_URL}")
    print(f"   📋 OMS 메트릭: {OMS_URL}/metrics")
    print(f"   🔧 관찰성 건강도: {OMS_URL}/observability/health")
    
    # 전체 상태 판정
    if successful_phases >= 3:
        overall_status = "🎉 EXCELLENT - 엔터프라이즈 관찰성 스택이 완벽하게 통합되었습니다!"
        results["overall_status"] = "excellent"
    elif successful_phases >= 2:
        overall_status = "✅ GOOD - 관찰성 스택이 잘 동작하고 있습니다!"
        results["overall_status"] = "good"
    elif successful_phases >= 1:
        overall_status = "⚠️ PARTIAL - 일부 기능이 동작하지 않습니다."
        results["overall_status"] = "partial"
    else:
        overall_status = "❌ FAILED - 관찰성 스택에 문제가 있습니다."
        results["overall_status"] = "failed"
    
    print(f"\n🏆 최종 평가: {overall_status}")
    
    # 권장사항
    if successful_phases < total_phases:
        print("\n💡 권장사항:")
        if any(p["phase"] == "observability_stack_availability" and not p.get("success") for p in phases):
            print("   - Prometheus, Grafana, Jaeger 서버가 실행 중인지 확인하세요")
            print("   - Docker Compose 모니터링 스택을 시작하세요: docker-compose -f monitoring/docker-compose.monitoring.yml up -d")
        if any(p["phase"] == "enterprise_metrics" and not p.get("success") for p in phases):
            print("   - OMS 서비스가 실행 중인지 확인하세요")
            print("   - 엔터프라이즈 관찰성 모듈이 올바르게 로드되었는지 확인하세요")

if __name__ == "__main__":
    asyncio.run(test_enterprise_observability_integration())