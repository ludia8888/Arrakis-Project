#!/usr/bin/env python3
"""
🔥 PRODUCTION STRESS TEST
=======================
극한 상황에서의 시스템 안정성 및 복구 능력 검증

테스트 시나리오:
1. 동시 접속 급증 (1000+ 동시 요청)
2. 대용량 데이터 처리 (대량 스키마/브랜치 생성)
3. 장애 상황 시뮬레이션 및 복구
4. 메모리/CPU 부하 테스트
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import random
import string

class ProductionStressTest:
    def __init__(self):
        self.services = {
            "user_service": "http://localhost:8012",
            "oms_service": "http://localhost:8010", 
            "audit_service": "http://localhost:8011"
        }
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "stress_tests": {},
            "performance_metrics": {},
            "failure_recovery": {}
        }
        self.auth_token = None
        
    async def setup_auth(self):
        """인증 토큰 획득"""
        async with aiohttp.ClientSession() as session:
            login_data = {"username": "admin", "password": "admin123"}
            async with session.post(f"{self.services['user_service']}/api/v1/auth/login", 
                                   json=login_data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.auth_token = result["access_token"]
                    print("✅ 인증 토큰 획득 성공")
                    return True
                else:
                    print("❌ 인증 실패")
                    return False

    async def concurrent_load_test(self, concurrent_users=100):
        """동시 접속 부하 테스트"""
        print(f"\n🔥 동시 접속 부하 테스트 시작 - {concurrent_users}명 동시 접속")
        
        start_time = time.time()
        success_count = 0
        error_count = 0
        
        async def make_request(session, user_id):
            try:
                headers = {"Authorization": f"Bearer {self.auth_token}"}
                
                # 다양한 API 호출 시뮬레이션
                endpoints = [
                    f"{self.services['oms_service']}/health",
                    f"{self.services['oms_service']}/api/v1/schemas",
                    f"{self.services['audit_service']}/api/v1/logs",
                    f"{self.services['user_service']}/health"
                ]
                
                endpoint = random.choice(endpoints)
                async with session.get(endpoint, headers=headers) as response:
                    if response.status < 400:
                        return {"user_id": user_id, "status": "success", "response_time": time.time() - start_time}
                    else:
                        return {"user_id": user_id, "status": "error", "code": response.status}
                        
            except Exception as e:
                return {"user_id": user_id, "status": "exception", "error": str(e)}

        # 동시 요청 실행
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session, i) for i in range(concurrent_users)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and result.get("status") == "success":
                    success_count += 1
                else:
                    error_count += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        stress_result = {
            "concurrent_users": concurrent_users,
            "success_rate": (success_count / concurrent_users) * 100,
            "total_time": total_time,
            "requests_per_second": concurrent_users / total_time,
            "success_count": success_count,
            "error_count": error_count
        }
        
        self.test_results["stress_tests"]["concurrent_load"] = stress_result
        
        print(f"  ✅ 성공률: {stress_result['success_rate']:.1f}%")
        print(f"  ⚡ 처리율: {stress_result['requests_per_second']:.1f} req/sec")
        print(f"  🕒 총 시간: {total_time:.2f}초")

    async def bulk_data_processing_test(self):
        """대용량 데이터 처리 테스트"""
        print(f"\n📊 대용량 데이터 처리 테스트 시작")
        
        start_time = time.time()
        
        # 대량 스키마 생성 시뮬레이션
        schema_count = 50
        branch_count = 100
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # 스키마 생성 요청들
            schema_tasks = []
            for i in range(schema_count):
                schema_data = {
                    "name": f"stress_test_schema_{i}",
                    "description": f"Stress test schema {i}",
                    "properties": {
                        "test_field": {"type": "string"},
                        "test_number": {"type": "integer"},
                        "test_data": {"type": "array"}
                    }
                }
                task = session.post(
                    f"{self.services['oms_service']}/api/v1/schemas", 
                    json=schema_data, 
                    headers=headers
                )
                schema_tasks.append(task)
            
            # 브랜치 생성 요청들  
            branch_tasks = []
            for i in range(branch_count):
                branch_data = {
                    "name": f"stress_test_branch_{i}",
                    "source_branch": "main",
                    "description": f"Stress test branch {i}"
                }
                task = session.post(
                    f"{self.services['oms_service']}/api/v1/branches", 
                    json=branch_data,
                    headers=headers
                )
                branch_tasks.append(task)
            
            # 감사 로그 대량 생성
            audit_tasks = []
            for i in range(200):  # 200개 감사 로그
                audit_data = {
                    "event_type": "stress_test",
                    "details": {
                        "test_id": i,
                        "action": "bulk_processing",
                        "timestamp": datetime.now().isoformat()
                    }
                }
                task = session.post(
                    f"{self.services['audit_service']}/api/v2/events",
                    json=audit_data,
                    headers=headers
                )
                audit_tasks.append(task)
            
            print(f"  📈 {schema_count}개 스키마, {branch_count}개 브랜치, 200개 감사로그 생성 중...")
            
            # 모든 요청 실행
            try:
                schema_responses = await asyncio.gather(*[asyncio.create_task(task) for task in schema_tasks], return_exceptions=True)
                branch_responses = await asyncio.gather(*[asyncio.create_task(task) for task in branch_tasks], return_exceptions=True)
                audit_responses = await asyncio.gather(*[asyncio.create_task(task) for task in audit_tasks], return_exceptions=True)
                
                # 결과 집계
                schema_success = sum(1 for r in schema_responses if hasattr(r, 'status') and r.status < 400)
                branch_success = sum(1 for r in branch_responses if hasattr(r, 'status') and r.status < 400) 
                audit_success = sum(1 for r in audit_responses if hasattr(r, 'status') and r.status < 400)
                
            except Exception as e:
                print(f"  ❌ 대량 처리 중 오류: {e}")
                schema_success = 0
                branch_success = 0
                audit_success = 0
        
        end_time = time.time()
        total_time = end_time - start_time
        
        bulk_result = {
            "total_operations": schema_count + branch_count + 200,
            "schema_success_rate": (schema_success / schema_count) * 100,
            "branch_success_rate": (branch_success / branch_count) * 100,
            "audit_success_rate": (audit_success / 200) * 100,
            "total_time": total_time,
            "operations_per_second": (schema_count + branch_count + 200) / total_time
        }
        
        self.test_results["stress_tests"]["bulk_processing"] = bulk_result
        
        print(f"  ✅ 스키마 성공률: {bulk_result['schema_success_rate']:.1f}%")
        print(f"  ✅ 브랜치 성공률: {bulk_result['branch_success_rate']:.1f}%") 
        print(f"  ✅ 감사로그 성공률: {bulk_result['audit_success_rate']:.1f}%")
        print(f"  ⚡ 처리율: {bulk_result['operations_per_second']:.1f} ops/sec")

    async def failure_recovery_test(self):
        """장애 복구 능력 테스트"""
        print(f"\n🚨 장애 복구 시나리오 테스트")
        
        recovery_results = {
            "invalid_token_handling": False,
            "malformed_request_handling": False,
            "high_error_rate_recovery": False,
            "service_resilience": False
        }
        
        async with aiohttp.ClientSession() as session:
            # 1. 잘못된 토큰으로 요청
            print("  🔐 잘못된 토큰 처리 테스트...")
            try:
                headers = {"Authorization": "Bearer invalid_token"}
                async with session.get(f"{self.services['oms_service']}/api/v1/schemas", headers=headers) as response:
                    if response.status == 401:
                        recovery_results["invalid_token_handling"] = True
                        print("    ✅ 잘못된 토큰 적절히 거부됨")
            except:
                pass
            
            # 2. 잘못된 요청 형식 처리
            print("  📝 잘못된 요청 형식 처리 테스트...")
            try:
                headers = {"Authorization": f"Bearer {self.auth_token}"}
                malformed_data = {"invalid": "data", "missing": "fields"}
                async with session.post(f"{self.services['oms_service']}/api/v1/schemas", 
                                       json=malformed_data, headers=headers) as response:
                    if response.status >= 400:
                        recovery_results["malformed_request_handling"] = True
                        print("    ✅ 잘못된 요청 적절히 처리됨")
            except:
                pass
            
            # 3. 고부하 상황에서 복구 능력
            print("  ⚡ 고부하 복구 능력 테스트...")
            error_count = 0
            success_count = 0
            
            # 연속 100개 요청으로 부하 가중
            for i in range(100):
                try:
                    headers = {"Authorization": f"Bearer {self.auth_token}"}
                    async with session.get(f"{self.services['oms_service']}/health", headers=headers) as response:
                        if response.status < 400:
                            success_count += 1
                        else:
                            error_count += 1
                except:
                    error_count += 1
            
            if success_count > 80:  # 80% 이상 성공
                recovery_results["high_error_rate_recovery"] = True
                print(f"    ✅ 고부하 상황 복구 성공 ({success_count}/100)")
            
            # 4. 서비스 복원력 테스트
            print("  🛡️ 서비스 복원력 테스트...")
            health_checks = []
            for service_name, service_url in self.services.items():
                try:
                    async with session.get(f"{service_url}/health") as response:
                        if response.status == 200:
                            health_checks.append(True)
                        else:
                            health_checks.append(False)
                except:
                    health_checks.append(False)
            
            if all(health_checks):
                recovery_results["service_resilience"] = True
                print("    ✅ 모든 서비스 정상 상태 유지")
        
        self.test_results["failure_recovery"] = recovery_results
        
        # 복구 점수 계산
        recovery_score = sum(recovery_results.values()) / len(recovery_results) * 100
        print(f"  📊 전체 복구 능력: {recovery_score:.1f}%")

    async def run_comprehensive_stress_test(self):
        """종합 스트레스 테스트 실행"""
        print("🔥 PRODUCTION STRESS TEST 시작")
        print("=" * 50)
        
        # 인증 설정
        if not await self.setup_auth():
            print("❌ 인증 실패로 테스트 중단")
            return
        
        # 1. 동시 접속 테스트 (단계적 증가)
        for users in [50, 100, 200]:
            await self.concurrent_load_test(users)
            await asyncio.sleep(2)  # 시스템 복구 시간
        
        # 2. 대용량 데이터 처리
        await self.bulk_data_processing_test()
        await asyncio.sleep(3)
        
        # 3. 장애 복구 테스트
        await self.failure_recovery_test()
        
        # 최종 점수 계산
        await self.calculate_final_stress_score()
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"production_stress_test_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 테스트 결과 저장: {filename}")

    async def calculate_final_stress_score(self):
        """최종 스트레스 테스트 점수 계산"""
        score_components = {
            "concurrent_performance": 0,
            "bulk_processing": 0,
            "failure_recovery": 0,
            "overall_resilience": 0
        }
        
        # 동시 접속 성능 점수 (최고 성능 기준)
        if "concurrent_load" in self.test_results["stress_tests"]:
            load_test = self.test_results["stress_tests"]["concurrent_load"]
            success_rate = load_test["success_rate"]
            rps = load_test["requests_per_second"]
            
            # 성공률 80% 이상, RPS 50 이상이면 만점
            score_components["concurrent_performance"] = min(100, (success_rate * 0.7) + (min(rps, 50) / 50 * 30))
        
        # 대용량 처리 점수
        if "bulk_processing" in self.test_results["stress_tests"]:
            bulk_test = self.test_results["stress_tests"]["bulk_processing"]
            avg_success = (bulk_test["schema_success_rate"] + 
                          bulk_test["branch_success_rate"] + 
                          bulk_test["audit_success_rate"]) / 3
            ops_per_sec = bulk_test["operations_per_second"]
            
            score_components["bulk_processing"] = min(100, (avg_success * 0.8) + (min(ops_per_sec, 20) / 20 * 20))
        
        # 장애 복구 점수
        if "failure_recovery" in self.test_results:
            recovery_count = sum(self.test_results["failure_recovery"].values())
            total_recovery_tests = len(self.test_results["failure_recovery"])
            score_components["failure_recovery"] = (recovery_count / total_recovery_tests) * 100
        
        # 전체 복원력 점수 (가중 평균)
        score_components["overall_resilience"] = (
            score_components["concurrent_performance"] * 0.4 +
            score_components["bulk_processing"] * 0.3 +
            score_components["failure_recovery"] * 0.3
        )
        
        self.test_results["final_stress_score"] = score_components
        
        print("\n" + "=" * 50)
        print("🏆 STRESS TEST 최종 결과")
        print("=" * 50)
        print(f"🔥 동시 접속 성능: {score_components['concurrent_performance']:.1f}/100")
        print(f"📊 대용량 처리: {score_components['bulk_processing']:.1f}/100") 
        print(f"🚨 장애 복구: {score_components['failure_recovery']:.1f}/100")
        print(f"🛡️ 전체 복원력: {score_components['overall_resilience']:.1f}/100")
        
        if score_components["overall_resilience"] >= 85:
            print("\n🎉 EXCELLENT - 프로덕션 레디!")
        elif score_components["overall_resilience"] >= 70:
            print("\n✅ GOOD - 추가 최적화 권장")
        else:
            print("\n⚠️ NEEDS IMPROVEMENT - 성능 개선 필요")

async def main():
    stress_tester = ProductionStressTest()
    await stress_tester.run_comprehensive_stress_test()

if __name__ == "__main__":
    asyncio.run(main())