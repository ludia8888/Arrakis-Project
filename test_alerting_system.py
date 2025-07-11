#!/opt/homebrew/bin/python3.12
"""
🚨 ALERTING SYSTEM TEST
========================
완전한 알람 시스템 테스트 및 시뮬레이션
"""

import requests
import time
import json
import asyncio
from datetime import datetime

class AlertingSystemTester:
    def __init__(self):
        self.prometheus_url = "http://localhost:9091"
        self.alertmanager_url = "http://localhost:9093"
        self.webhook_url = "http://localhost:8080"
        
    def test_prometheus_targets(self):
        """Prometheus 타겟 상태 확인"""
        print("📊 Prometheus 타겟 상태 확인...")
        
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/targets")
            if response.status_code == 200:
                data = response.json()
                targets = data.get('data', {}).get('activeTargets', [])
                
                print(f"  총 {len(targets)}개 타겟 발견:")
                for target in targets:
                    job = target.get('labels', {}).get('job', 'unknown')
                    health = target.get('health', 'unknown')
                    last_error = target.get('lastError', '')
                    
                    status_icon = "✅" if health == "up" else "❌"
                    print(f"    {status_icon} {job}: {health}")
                    if last_error:
                        print(f"        Error: {last_error}")
                        
                return targets
            else:
                print(f"  ❌ Prometheus API 호출 실패: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            return []
    
    def test_alertmanager_status(self):
        """Alertmanager 상태 확인"""
        print("\n🚨 Alertmanager 상태 확인...")
        
        try:
            # 기본 헬스체크
            health_response = requests.get(f"{self.alertmanager_url}/-/healthy")
            print(f"  헬스체크: {health_response.status_code}")
            
            # 설정 상태 확인
            config_response = requests.get(f"{self.alertmanager_url}/api/v1/status")
            if config_response.status_code == 200:
                config_data = config_response.json()
                print(f"  설정 상태: ✅ 정상")
                print(f"  클러스터 상태: {config_data.get('data', {}).get('clusterStatus', {}).get('status', 'unknown')}")
            
            return True
        except Exception as e:
            print(f"  ❌ Alertmanager 연결 실패: {e}")
            return False
    
    def test_webhook_server(self):
        """웹훅 서버 연결 테스트"""
        print("\n🔗 웹훅 서버 테스트...")
        
        try:
            # 헬스체크
            health_response = requests.get(f"{self.webhook_url}/health")
            if health_response.status_code == 200:
                print("  ✅ 웹훅 서버 정상 동작")
                
                # 테스트 알람 전송
                test_alert = {
                    "alerts": [{
                        "labels": {
                            "alertname": "TestAlert",
                            "severity": "warning"
                        },
                        "annotations": {
                            "summary": "알람 시스템 테스트",
                            "description": "이것은 알람 시스템 테스트입니다."
                        },
                        "status": "firing"
                    }]
                }
                
                webhook_response = requests.post(f"{self.webhook_url}/webhook/alerts", json=test_alert)
                if webhook_response.status_code == 200:
                    print("  ✅ 테스트 알람 전송 성공")
                    return True
                else:
                    print(f"  ❌ 테스트 알람 전송 실패: {webhook_response.status_code}")
                    return False
            else:
                print(f"  ❌ 웹훅 서버 헬스체크 실패: {health_response.status_code}")
                return False
        except Exception as e:
            print(f"  ❌ 웹훅 서버 연결 실패: {e}")
            return False
    
    def test_exporters(self):
        """Exporter 상태 테스트"""
        print("\n📈 Exporter 상태 테스트...")
        
        exporters = [
            ("Node Exporter", "http://localhost:9100/metrics"),
            ("Redis Exporter", "http://localhost:9121/metrics"),
            ("Postgres Exporter", "http://localhost:9187/metrics")
        ]
        
        results = {}
        for name, url in exporters:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    metrics_count = len([line for line in response.text.split('\n') if line.startswith('#')])
                    results[name] = {"status": "✅", "metrics": metrics_count}
                    print(f"  ✅ {name}: {metrics_count} 메트릭 타입")
                else:
                    results[name] = {"status": "❌", "error": f"HTTP {response.status_code}"}
                    print(f"  ❌ {name}: HTTP {response.status_code}")
            except Exception as e:
                results[name] = {"status": "❌", "error": str(e)}
                print(f"  ❌ {name}: {e}")
        
        return results
    
    def check_alert_rules(self):
        """알람 규칙 확인"""
        print("\n📋 알람 규칙 확인...")
        
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/rules")
            if response.status_code == 200:
                data = response.json()
                groups = data.get('data', {}).get('groups', [])
                
                total_rules = 0
                for group in groups:
                    rules = group.get('rules', [])
                    group_name = group.get('name', 'unknown')
                    print(f"  그룹 '{group_name}': {len(rules)}개 규칙")
                    
                    for rule in rules:
                        if rule.get('type') == 'alerting':
                            rule_name = rule.get('name', 'unknown')
                            state = rule.get('state', 'unknown')
                            print(f"    📌 {rule_name}: {state}")
                            total_rules += 1
                
                print(f"  총 {total_rules}개 알람 규칙 로드됨")
                return total_rules
            else:
                print(f"  ❌ 알람 규칙 조회 실패: {response.status_code}")
                return 0
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            return 0
    
    def simulate_service_failure(self):
        """서비스 장애 시뮬레이션"""
        print("\n🔥 서비스 장애 시뮬레이션...")
        
        print("  테스트용 알람 트리거를 위해 일부 서비스 중지...")
        print("  (실제로는 중지하지 않고, 알람 조건만 확인)")
        
        # 현재 알람 상태 확인
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/alerts")
            if response.status_code == 200:
                data = response.json()
                alerts = data.get('data', {}).get('alerts', [])
                
                if alerts:
                    print(f"  현재 {len(alerts)}개 활성 알람:")
                    for alert in alerts[:5]:  # 최대 5개만 표시
                        alert_name = alert.get('labels', {}).get('alertname', 'unknown')
                        state = alert.get('state', 'unknown')
                        print(f"    🚨 {alert_name}: {state}")
                else:
                    print("  ✅ 현재 활성 알람 없음 (정상 상태)")
                    
                return len(alerts)
            else:
                print(f"  ❌ 알람 상태 조회 실패: {response.status_code}")
                return 0
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            return 0
    
    def generate_comprehensive_report(self):
        """종합 보고서 생성"""
        print("\n" + "="*60)
        print("🚨 ALERTING SYSTEM COMPREHENSIVE TEST")
        print("="*60)
        
        # 1. Prometheus 타겟 테스트
        targets = self.test_prometheus_targets()
        
        # 2. Alertmanager 테스트
        alertmanager_ok = self.test_alertmanager_status()
        
        # 3. 웹훅 서버 테스트
        webhook_ok = self.test_webhook_server()
        
        # 4. Exporter 테스트
        exporter_results = self.test_exporters()
        
        # 5. 알람 규칙 확인
        rules_count = self.check_alert_rules()
        
        # 6. 현재 알람 상태
        active_alerts = self.simulate_service_failure()
        
        # 결과 요약
        print("\n" + "="*60)
        print("📊 ALERTING SYSTEM STATUS SUMMARY")
        print("="*60)
        
        healthy_targets = len([t for t in targets if t.get('health') == 'up'])
        total_targets = len(targets)
        
        print(f"🎯 Prometheus 타겟: {healthy_targets}/{total_targets} 정상")
        print(f"🚨 Alertmanager: {'✅ 정상' if alertmanager_ok else '❌ 문제'}")
        print(f"🔗 웹훅 서버: {'✅ 정상' if webhook_ok else '❌ 문제'}")
        
        working_exporters = len([r for r in exporter_results.values() if r['status'] == '✅'])
        total_exporters = len(exporter_results)
        print(f"📈 Exporters: {working_exporters}/{total_exporters} 정상")
        
        print(f"📋 알람 규칙: {rules_count}개 로드됨")
        print(f"🔥 현재 활성 알람: {active_alerts}개")
        
        # 종합 점수 계산
        score = 0
        if healthy_targets > 0:
            score += 30 * (healthy_targets / max(total_targets, 1))
        if alertmanager_ok:
            score += 20
        if webhook_ok:
            score += 20
        if working_exporters > 0:
            score += 20 * (working_exporters / max(total_exporters, 1))
        if rules_count > 0:
            score += 10
        
        print(f"\n🏆 종합 알람 시스템 점수: {score:.1f}/100")
        
        if score >= 90:
            print("🎉 EXCELLENT! 알람 시스템이 완벽하게 구축되었습니다!")
        elif score >= 75:
            print("🟢 VERY GOOD! 알람 시스템이 잘 구축되었습니다!")
        elif score >= 60:
            print("🟡 GOOD! 몇 가지 개선이 필요합니다.")
        else:
            print("🔴 NEEDS IMPROVEMENT! 알람 시스템에 문제가 있습니다.")
        
        # 결과 저장
        results = {
            "timestamp": datetime.now().isoformat(),
            "prometheus_targets": targets,
            "alertmanager_healthy": alertmanager_ok,
            "webhook_healthy": webhook_ok,
            "exporter_results": exporter_results,
            "alert_rules_count": rules_count,
            "active_alerts_count": active_alerts,
            "overall_score": score
        }
        
        result_file = f"alerting_system_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 테스트 결과 저장: {result_file}")
        
        return results

def main():
    tester = AlertingSystemTester()
    results = tester.generate_comprehensive_report()
    return results

if __name__ == "__main__":
    results = main()