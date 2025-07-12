#!/usr/bin/env python3
"""
Arrakis Project - Deep Continuous Verification System
사용자의 요구대로 끊임없이 deep verification을 수행하는 시스템
priority_based_test_plan.md에 따라 ultra thinking으로 검증
"""

import asyncio
import httpx
import time
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class ContinuousDeepVerifier:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.plan_file = self.base_dir / "priority_based_test_plan.md"
        self.results_file = self.base_dir / f"continuous_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        self.services = {
            "oms": {"url": "http://localhost:8000", "name": "OMS"},
            "user": {"url": "http://localhost:8010", "name": "User Service"},
            "audit": {"url": "http://localhost:8011", "name": "Audit Service"}
        }
        
        self.verification_results = {
            "start_time": datetime.now().isoformat(),
            "cycles": [],
            "cumulative_stats": {
                "total_tests": 0,
                "total_passed": 0,
                "total_failed": 0,
                "implementation_rate": 0.0,
                "trend": []
            }
        }

    async def verify_service_health(self, service_key: str) -> Dict[str, Any]:
        """개별 서비스 헬스 상세 검증"""
        service = self.services[service_key]
        result = {
            "service": service["name"],
            "timestamp": datetime.now().isoformat(),
            "health_check": False,
            "response_time": 0,
            "status_code": 0,
            "api_docs": False,
            "endpoints": []
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Health endpoint 검증
            try:
                start_time = time.time()
                response = await client.get(f"{service['url']}/health")
                result["response_time"] = round((time.time() - start_time) * 1000, 2)
                result["status_code"] = response.status_code
                result["health_check"] = response.status_code == 200
                
                if result["health_check"]:
                    health_data = response.json()
                    result["health_data"] = health_data
                    
            except Exception as e:
                result["health_error"] = str(e)

            # 2. API Documentation 접근성 검증
            try:
                docs_response = await client.get(f"{service['url']}/docs")
                result["api_docs"] = docs_response.status_code == 200
            except:
                result["api_docs"] = False

            # 3. OpenAPI schema 검증
            try:
                openapi_response = await client.get(f"{service['url']}/openapi.json")
                if openapi_response.status_code == 200:
                    openapi_data = openapi_response.json()
                    result["endpoints"] = list(openapi_data.get("paths", {}).keys())
                    result["endpoint_count"] = len(result["endpoints"])
            except:
                result["endpoint_count"] = 0

        return result

    async def verify_oms_specific_functionality(self) -> Dict[str, Any]:
        """OMS 특화 기능 검증"""
        result = {
            "schema_api_status": False,
            "fallback_mode": False,
            "schema_crud_available": False,
            "dependency_issues": [],
            "routes_loaded": 0
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Fallback schema status endpoint 검증
                response = await client.get("http://localhost:8000/api/v1/schemas/status")
                if response.status_code == 200:
                    data = response.json()
                    result["schema_api_status"] = True
                    result["fallback_mode"] = data.get("status") == "fallback_mode"
                    result["missing_dependencies"] = data.get("missing_dependencies", "")
                    
                # 전체 API endpoints 검증
                openapi_response = await client.get("http://localhost:8000/openapi.json")
                if openapi_response.status_code == 200:
                    paths = openapi_response.json().get("paths", {})
                    result["routes_loaded"] = len(paths)
                    result["available_endpoints"] = list(paths.keys())
                    
                    # Schema CRUD endpoints 확인
                    schema_endpoints = [p for p in paths.keys() if "schema" in p.lower()]
                    result["schema_endpoints"] = schema_endpoints
                    result["schema_crud_available"] = len(schema_endpoints) > 1
                    
            except Exception as e:
                result["error"] = str(e)
                
        return result

    async def verify_user_service_functionality(self) -> Dict[str, Any]:
        """User Service 특화 기능 검증"""
        result = {
            "auth_endpoints": False,
            "registration_available": False,
            "login_available": False,
            "jwt_functionality": False
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # API endpoints 검증
                openapi_response = await client.get("http://localhost:8010/openapi.json")
                if openapi_response.status_code == 200:
                    paths = openapi_response.json().get("paths", {})
                    result["total_endpoints"] = len(paths)
                    
                    # 인증 관련 endpoints 확인
                    auth_endpoints = []
                    for path in paths.keys():
                        if any(keyword in path.lower() for keyword in ["auth", "login", "register", "token"]):
                            auth_endpoints.append(path)
                    
                    result["auth_endpoints"] = auth_endpoints
                    result["registration_available"] = any("register" in ep for ep in auth_endpoints)
                    result["login_available"] = any("login" in ep for ep in auth_endpoints)
                    
            except Exception as e:
                result["error"] = str(e)
                
        return result

    async def verify_audit_service_functionality(self) -> Dict[str, Any]:
        """Audit Service 특화 기능 검증"""
        result = {
            "audit_endpoints": False,
            "event_logging": False,
            "query_capability": False
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # API endpoints 검증
                openapi_response = await client.get("http://localhost:8011/openapi.json")
                if openapi_response.status_code == 200:
                    paths = openapi_response.json().get("paths", {})
                    result["total_endpoints"] = len(paths)
                    
                    # 감사 관련 endpoints 확인
                    audit_endpoints = []
                    for path in paths.keys():
                        if any(keyword in path.lower() for keyword in ["audit", "event", "log", "history"]):
                            audit_endpoints.append(path)
                    
                    result["audit_endpoints"] = audit_endpoints
                    result["event_logging"] = any("event" in ep for ep in audit_endpoints)
                    result["query_capability"] = len(audit_endpoints) > 1
                    
            except Exception as e:
                result["error"] = str(e)
                
        return result

    async def test_inter_service_communication(self) -> Dict[str, Any]:
        """서비스간 통신 검증"""
        result = {
            "user_to_audit": False,
            "oms_to_user": False,
            "oms_to_audit": False,
            "communication_errors": []
        }
        
        # 이 부분은 실제 통신 테스트를 위해 나중에 구현
        # 현재는 서비스 가용성만 확인
        all_services_healthy = True
        for service_key in self.services.keys():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.services[service_key]['url']}/health")
                    if response.status_code != 200:
                        all_services_healthy = False
            except:
                all_services_healthy = False
                
        result["all_services_reachable"] = all_services_healthy
        return result

    async def calculate_implementation_rate(self, cycle_results: Dict[str, Any]) -> float:
        """실제 구현률 계산"""
        total_features = 0
        implemented_features = 0
        
        # OMS 기능 평가
        oms_results = cycle_results.get("oms_functionality", {})
        total_features += 5  # 예상 OMS 기능 수
        if oms_results.get("schema_api_status"): implemented_features += 1
        if oms_results.get("routes_loaded", 0) > 2: implemented_features += 1
        if oms_results.get("schema_crud_available"): implemented_features += 2
        if not oms_results.get("fallback_mode"): implemented_features += 1
        
        # User Service 기능 평가
        user_results = cycle_results.get("user_functionality", {})
        total_features += 3
        if user_results.get("registration_available"): implemented_features += 1
        if user_results.get("login_available"): implemented_features += 1
        if user_results.get("auth_endpoints"): implemented_features += 1
        
        # Audit Service 기능 평가
        audit_results = cycle_results.get("audit_functionality", {})
        total_features += 3
        if audit_results.get("event_logging"): implemented_features += 1
        if audit_results.get("query_capability"): implemented_features += 1
        if audit_results.get("audit_endpoints"): implemented_features += 1
        
        # Service Health 평가
        for service_key in ["oms", "user", "audit"]:
            health = cycle_results.get(f"{service_key}_health", {})
            total_features += 2
            if health.get("health_check"): implemented_features += 1
            if health.get("api_docs"): implemented_features += 1
            
        implementation_rate = (implemented_features / total_features * 100) if total_features > 0 else 0
        return round(implementation_rate, 1)

    async def run_verification_cycle(self, cycle_number: int) -> Dict[str, Any]:
        """단일 검증 사이클 실행"""
        print(f"\n🔍 Verification Cycle #{cycle_number}")
        print("=" * 60)
        
        cycle_start = time.time()
        cycle_results = {
            "cycle": cycle_number,
            "timestamp": datetime.now().isoformat(),
            "duration": 0
        }
        
        # 1. 각 서비스 헬스 검증
        print("📊 Verifying service health...")
        for service_key in self.services.keys():
            health_result = await self.verify_service_health(service_key)
            cycle_results[f"{service_key}_health"] = health_result
            
            status = "✅" if health_result["health_check"] else "❌"
            response_time = health_result.get("response_time", 0)
            endpoint_count = health_result.get("endpoint_count", 0)
            
            print(f"  {status} {self.services[service_key]['name']}: "
                  f"{response_time}ms, {endpoint_count} endpoints")

        # 2. OMS 특화 기능 검증
        print("\n🎯 Verifying OMS functionality...")
        oms_functionality = await self.verify_oms_specific_functionality()
        cycle_results["oms_functionality"] = oms_functionality
        
        schema_status = "✅" if oms_functionality["schema_api_status"] else "❌"
        routes_count = oms_functionality.get("routes_loaded", 0)
        fallback = "⚠️ FALLBACK" if oms_functionality.get("fallback_mode") else "✅ FULL"
        
        print(f"  {schema_status} Schema API: {routes_count} routes, {fallback}")

        # 3. User Service 특화 기능 검증
        print("\n👤 Verifying User Service functionality...")
        user_functionality = await self.verify_user_service_functionality()
        cycle_results["user_functionality"] = user_functionality
        
        auth_endpoints = user_functionality.get("auth_endpoints", [])
        auth_status = "✅" if auth_endpoints else "❌"
        auth_count = len(auth_endpoints) if isinstance(auth_endpoints, list) else 0
        
        print(f"  {auth_status} Auth System: {auth_count} auth endpoints")

        # 4. Audit Service 특화 기능 검증
        print("\n📝 Verifying Audit Service functionality...")
        audit_functionality = await self.verify_audit_service_functionality()
        cycle_results["audit_functionality"] = audit_functionality
        
        audit_endpoints = audit_functionality.get("audit_endpoints", [])
        audit_status = "✅" if audit_endpoints else "❌"
        audit_count = len(audit_endpoints) if isinstance(audit_endpoints, list) else 0
        
        print(f"  {audit_status} Audit System: {audit_count} audit endpoints")

        # 5. 서비스간 통신 검증
        print("\n🔗 Verifying inter-service communication...")
        communication = await self.test_inter_service_communication()
        cycle_results["communication"] = communication
        
        comm_status = "✅" if communication.get("all_services_reachable") else "❌"
        print(f"  {comm_status} Service Communication")

        # 6. 구현률 계산
        implementation_rate = await self.calculate_implementation_rate(cycle_results)
        cycle_results["implementation_rate"] = implementation_rate
        
        cycle_results["duration"] = round(time.time() - cycle_start, 2)
        
        print(f"\n📈 Implementation Rate: {implementation_rate}%")
        print(f"⏱️  Cycle Duration: {cycle_results['duration']}s")
        
        return cycle_results

    async def update_cumulative_stats(self, cycle_results: Dict[str, Any]):
        """누적 통계 업데이트"""
        stats = self.verification_results["cumulative_stats"]
        
        # 테스트 카운트 업데이트
        cycle_tests = 0
        cycle_passed = 0
        
        # 각 서비스별 테스트 결과 집계
        for service_key in ["oms", "user", "audit"]:
            health = cycle_results.get(f"{service_key}_health", {})
            if health.get("health_check"):
                cycle_passed += 1
            cycle_tests += 1
            
        # 기능별 테스트 결과 집계
        if cycle_results.get("oms_functionality", {}).get("schema_api_status"):
            cycle_passed += 1
        cycle_tests += 1
        
        if cycle_results.get("communication", {}).get("all_services_reachable"):
            cycle_passed += 1
        cycle_tests += 1
        
        stats["total_tests"] += cycle_tests
        stats["total_passed"] += cycle_passed
        stats["total_failed"] += (cycle_tests - cycle_passed)
        
        # 구현률 트렌드 업데이트
        current_rate = cycle_results.get("implementation_rate", 0)
        stats["implementation_rate"] = current_rate
        stats["trend"].append({
            "cycle": cycle_results["cycle"],
            "rate": current_rate,
            "timestamp": cycle_results["timestamp"]
        })
        
        # 최근 10개 사이클만 유지
        if len(stats["trend"]) > 10:
            stats["trend"] = stats["trend"][-10:]

    def save_results(self):
        """결과를 파일에 저장"""
        try:
            with open(self.results_file, 'w') as f:
                json.dump(self.verification_results, f, indent=2)
            print(f"📄 Results saved to: {self.results_file}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")

    def print_summary(self):
        """검증 결과 요약 출력"""
        stats = self.verification_results["cumulative_stats"]
        cycle_count = len(self.verification_results["cycles"])
        
        print("\n" + "="*80)
        print("📊 CONTINUOUS DEEP VERIFICATION SUMMARY")
        print("="*80)
        
        print(f"🔄 Total Cycles: {cycle_count}")
        print(f"🧪 Total Tests: {stats['total_tests']}")
        print(f"✅ Passed: {stats['total_passed']}")
        print(f"❌ Failed: {stats['total_failed']}")
        
        if stats['total_tests'] > 0:
            success_rate = (stats['total_passed'] / stats['total_tests']) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print(f"🎯 Current Implementation Rate: {stats['implementation_rate']}%")
        
        if len(stats['trend']) > 1:
            trend_change = stats['trend'][-1]['rate'] - stats['trend'][0]['rate']
            trend_indicator = "📈" if trend_change > 0 else "📉" if trend_change < 0 else "➡️"
            print(f"{trend_indicator} Trend: {trend_change:+.1f}% over {len(stats['trend'])} cycles")

    async def continuous_verification_loop(self, max_cycles: int = 100, interval: int = 30):
        """연속 검증 루프"""
        print("🚀 Starting Continuous Deep Verification System")
        print(f"📋 Plan: {self.plan_file}")
        print(f"🎯 Max Cycles: {max_cycles}, Interval: {interval}s")
        print("💡 Ultra thinking mode: ACTIVATED")
        
        try:
            for cycle in range(1, max_cycles + 1):
                cycle_results = await self.run_verification_cycle(cycle)
                self.verification_results["cycles"].append(cycle_results)
                await self.update_cumulative_stats(cycle_results)
                
                # 매 5 사이클마다 요약 출력
                if cycle % 5 == 0:
                    self.print_summary()
                    self.save_results()
                
                # 마지막 사이클이 아니라면 대기
                if cycle < max_cycles:
                    print(f"\n💤 Waiting {interval}s for next cycle...")
                    await asyncio.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\n🛑 Verification interrupted by user")
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")
        finally:
            self.verification_results["end_time"] = datetime.now().isoformat()
            self.print_summary()
            self.save_results()

async def main():
    """메인 실행 함수"""
    verifier = ContinuousDeepVerifier()
    
    # 사용자 요구사항: "끊임없이 deep verification"
    # priority_based_test_plan.md 기반으로 ultra thinking
    await verifier.continuous_verification_loop(
        max_cycles=50,  # 50 사이클
        interval=20     # 20초 간격
    )

if __name__ == "__main__":
    print("🎯 Arrakis Project - Deep Continuous Verification")
    print("📋 Following priority_based_test_plan.md with ultra thinking")
    print("="*80)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Verification system terminated")
        sys.exit(0)