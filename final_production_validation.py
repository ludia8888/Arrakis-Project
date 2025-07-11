#!/opt/homebrew/bin/python3.12
"""
🔥 FINAL PRODUCTION VALIDATION
==============================
95점 이상을 위한 최종 프로덕션 검증

메트릭이 완전히 활성화된 상태에서 모든 영역을 재평가
"""

import asyncio
import aiohttp
import requests
import time
import json
from datetime import datetime

class FinalProductionValidator:
    def __init__(self):
        self.services = {
            "user_service": "http://localhost:8012",
            "oms_service": "http://localhost:8010",
            "audit_service": "http://localhost:8011"
        }
        self.results = {}
        self.total_score = 0
        
    async def validate_metrics_infrastructure(self):
        """메트릭 인프라 완전 검증"""
        print("📊 메트릭 인프라 완전 검증...")
        
        metrics_score = 0
        total_checks = 0
        
        for service_name, url in self.services.items():
            try:
                # 메트릭 엔드포인트 확인
                metrics_response = requests.get(f"{url}/metrics", timeout=5)
                if metrics_response.status_code == 200:
                    metrics_text = metrics_response.text
                    
                    # 핵심 메트릭 확인
                    required_metrics = [
                        'http_requests_total',
                        'service_health',
                        'python_gc_objects_collected_total',
                        'python_info'
                    ]
                    
                    metrics_found = sum(1 for metric in required_metrics if metric in metrics_text)
                    service_score = (metrics_found / len(required_metrics)) * 100
                    metrics_score += service_score
                    total_checks += 1
                    
                    print(f"  ✅ {service_name}: {service_score:.1f}점 ({metrics_found}/{len(required_metrics)} 메트릭)")
                else:
                    print(f"  ❌ {service_name}: 메트릭 엔드포인트 실패")
                    total_checks += 1
                    
            except Exception as e:
                print(f"  ❌ {service_name}: 연결 실패 - {e}")
                total_checks += 1
        
        avg_metrics_score = metrics_score / max(total_checks, 1)
        self.results['metrics_infrastructure'] = avg_metrics_score
        print(f"  📊 메트릭 인프라 점수: {avg_metrics_score:.1f}/100")
        return avg_metrics_score
        
    async def validate_service_performance(self):
        """서비스 성능 검증"""
        print("\n⚡ 서비스 성능 검증...")
        
        performance_scores = []
        
        # 동시 요청 테스트
        start_time = time.time()
        tasks = []
        
        async with aiohttp.ClientSession() as session:
            # 각 서비스에 10개씩 동시 요청
            for service_name, url in self.services.items():
                for i in range(10):
                    task = session.get(f"{url}/health")
                    tasks.append(task)
            
            try:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in responses if hasattr(r, 'status') and r.status == 200)
                success_rate = (successful / len(tasks)) * 100
                
                end_time = time.time()
                total_time = end_time - start_time
                rps = len(tasks) / total_time
                
                print(f"  ✅ 동시 요청: {success_rate:.1f}% 성공률")
                print(f"  ⚡ 처리율: {rps:.1f} req/sec")
                
                # 성능 점수 계산
                performance_score = min(100, success_rate * 0.8 + min(rps, 100) * 0.2)
                performance_scores.append(performance_score)
                
            except Exception as e:
                print(f"  ❌ 성능 테스트 실패: {e}")
                performance_scores.append(0)
        
        avg_performance = sum(performance_scores) / max(len(performance_scores), 1)
        self.results['service_performance'] = avg_performance
        print(f"  ⚡ 서비스 성능 점수: {avg_performance:.1f}/100")
        return avg_performance
        
    async def validate_business_functionality(self):
        """비즈니스 기능 검증"""
        print("\n🔧 비즈니스 기능 검증...")
        
        functionality_score = 0
        tests_passed = 0
        total_tests = 0
        
        try:
            # 1. 사용자 로그인
            login_data = {"username": "admin", "password": "admin123"}
            login_response = requests.post(f"{self.services['user_service']}/api/v1/auth/login", json=login_data)
            
            if login_response.status_code == 200:
                token = login_response.json().get('access_token')
                tests_passed += 1
                print("  ✅ 사용자 인증: 성공")
            else:
                print("  ❌ 사용자 인증: 실패")
            total_tests += 1
            
            # 2. OMS 스키마 조회 (인증된 요청)
            if 'token' in locals():
                headers = {"Authorization": f"Bearer {token}"}
                schema_response = requests.get(f"{self.services['oms_service']}/api/v1/schemas", headers=headers)
                
                if schema_response.status_code == 200:
                    tests_passed += 1
                    print("  ✅ OMS 스키마 조회: 성공")
                else:
                    print("  ❌ OMS 스키마 조회: 실패")
            else:
                print("  ⏭️ OMS 스키마 조회: 토큰 없음으로 스킵")
            total_tests += 1
            
            # 3. 감사 이벤트 생성
            audit_data = {"event_type": "final_validation", "details": {"test": "business_functionality"}}
            if 'headers' in locals():
                audit_response = requests.post(f"{self.services['audit_service']}/api/v2/events", json=audit_data, headers=headers)
            else:
                audit_response = requests.post(f"{self.services['audit_service']}/api/v2/events", json=audit_data)
                
            if audit_response.status_code == 200:
                tests_passed += 1
                print("  ✅ 감사 이벤트 생성: 성공")
            else:
                print("  ❌ 감사 이벤트 생성: 실패")
            total_tests += 1
            
        except Exception as e:
            print(f"  ❌ 비즈니스 기능 테스트 오류: {e}")
        
        functionality_score = (tests_passed / max(total_tests, 1)) * 100
        self.results['business_functionality'] = functionality_score
        print(f"  🔧 비즈니스 기능 점수: {functionality_score:.1f}/100 ({tests_passed}/{total_tests})")
        return functionality_score
        
    async def validate_monitoring_integration(self):
        """모니터링 통합 검증"""
        print("\n📈 모니터링 통합 검증...")
        
        monitoring_score = 0
        checks_passed = 0
        total_checks = 0
        
        # 1. Prometheus 연결 확인
        try:
            prometheus_response = requests.get("http://localhost:9091/api/v1/targets")
            if prometheus_response.status_code == 200:
                checks_passed += 1
                print("  ✅ Prometheus 연결: 성공")
            else:
                print("  ❌ Prometheus 연결: 실패")
        except:
            print("  ❌ Prometheus 연결: 실패")
        total_checks += 1
        
        # 2. Grafana 연결 확인
        try:
            grafana_response = requests.get("http://localhost:3000/api/health")
            if grafana_response.status_code == 200:
                checks_passed += 1
                print("  ✅ Grafana 연결: 성공")
            else:
                print("  ❌ Grafana 연결: 실패")
        except:
            print("  ❌ Grafana 연결: 실패")
        total_checks += 1
        
        # 3. Jaeger 연결 확인
        try:
            jaeger_response = requests.get("http://localhost:16686/api/services")
            if jaeger_response.status_code == 200:
                checks_passed += 1
                print("  ✅ Jaeger 연결: 성공")
            else:
                print("  ❌ Jaeger 연결: 실패")
        except:
            print("  ❌ Jaeger 연결: 실패")
        total_checks += 1
        
        # 4. TerminusDB 연결 확인
        try:
            terminusdb_response = requests.get("http://localhost:6363/api/info")
            if terminusdb_response.status_code == 200:
                checks_passed += 1
                print("  ✅ TerminusDB 연결: 성공")
            else:
                print("  ❌ TerminusDB 연결: 실패")
        except:
            print("  ❌ TerminusDB 연결: 실패")
        total_checks += 1
        
        monitoring_score = (checks_passed / max(total_checks, 1)) * 100
        self.results['monitoring_integration'] = monitoring_score
        print(f"  📈 모니터링 통합 점수: {monitoring_score:.1f}/100 ({checks_passed}/{total_checks})")
        return monitoring_score
        
    async def calculate_final_score(self):
        """최종 점수 계산"""
        print("\n🏆 최종 점수 계산...")
        
        # 가중치 적용
        weights = {
            'metrics_infrastructure': 0.25,  # 25%
            'service_performance': 0.25,     # 25%
            'business_functionality': 0.30,  # 30%
            'monitoring_integration': 0.20   # 20%
        }
        
        weighted_score = 0
        for component, score in self.results.items():
            weight = weights.get(component, 0)
            weighted_score += score * weight
            print(f"  {component}: {score:.1f}점 (가중치 {weight*100:.0f}%)")
        
        self.total_score = weighted_score
        
        # 추가 보너스 점수
        if all(score >= 90 for score in self.results.values()):
            bonus = 5  # 모든 영역 90점 이상시 보너스
            self.total_score += bonus
            print(f"  🎉 완벽 점수 보너스: +{bonus}점")
        
        self.total_score = min(100, self.total_score)  # 최대 100점
        
        return self.total_score
        
    async def run_final_validation(self):
        """최종 검증 실행"""
        print("🔥 FINAL PRODUCTION VALIDATION")
        print("=" * 50)
        print("🎯 목표: 95점 이상 달성하여 프로덕션 레디 완성")
        
        # 모든 검증 실행
        await self.validate_metrics_infrastructure()
        await self.validate_service_performance()
        await self.validate_business_functionality()
        await self.validate_monitoring_integration()
        
        # 최종 점수 계산
        final_score = await self.calculate_final_score()
        
        print("\n" + "=" * 50)
        print("🏆 FINAL PRODUCTION VALIDATION 결과")
        print("=" * 50)
        print(f"📊 최종 점수: {final_score:.1f}/100")
        
        if final_score >= 95:
            print("🎉 EXCELLENT! 프로덕션 레디 달성!")
            print("✅ 시스템이 완전히 프로덕션 레디 상태입니다!")
        elif final_score >= 90:
            print("🟢 VERY GOOD! 거의 프로덕션 레디!")
            print("⚡ 소폭 개선으로 완벽한 상태 달성 가능")
        elif final_score >= 80:
            print("🟡 GOOD! 주요 개선 필요")
            print("🔧 몇 가지 영역 개선 후 프로덕션 배포 가능")
        else:
            print("🔴 NEEDS IMPROVEMENT!")
            print("⚠️ 프로덕션 배포 전 상당한 개선 필요")
        
        # 결과 저장
        result_data = {
            "timestamp": datetime.now().isoformat(),
            "final_score": final_score,
            "component_scores": self.results,
            "status": "PRODUCTION_READY" if final_score >= 95 else "NEEDS_IMPROVEMENT"
        }
        
        filename = f"final_production_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 결과 저장: {filename}")
        return final_score

async def main():
    validator = FinalProductionValidator()
    return await validator.run_final_validation()

if __name__ == "__main__":
    final_score = asyncio.run(main())
    exit(0 if final_score >= 95 else 1)