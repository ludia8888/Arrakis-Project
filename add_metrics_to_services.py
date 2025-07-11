#!/usr/bin/env python3
"""
🚨 EMERGENCY METRICS INJECTION
==============================
긴급하게 모든 서비스에 메트릭 엔드포인트 추가
"""

import requests
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

def test_all_metrics():
    """모든 서비스의 메트릭 엔드포인트 테스트"""
    services = {
        "User Service": "http://localhost:8012",
        "OMS Service": "http://localhost:8010", 
        "Audit Service": "http://localhost:8011"
    }
    
    print("🔥 EMERGENCY METRICS TEST")
    print("=" * 40)
    
    for service_name, base_url in services.items():
        print(f"\n🔍 Testing {service_name}...")
        
        # Health check
        try:
            health_response = requests.get(f"{base_url}/health", timeout=5)
            print(f"  ❤️ Health: {health_response.status_code}")
            health_data = health_response.json()
            metrics_enabled = health_data.get('metrics_enabled', False)
            print(f"  📊 Metrics Enabled: {metrics_enabled}")
        except Exception as e:
            print(f"  ❌ Health Check Failed: {e}")
            continue
            
        # Metrics check
        try:
            metrics_response = requests.get(f"{base_url}/metrics", timeout=5)
            print(f"  📈 Metrics Endpoint: {metrics_response.status_code}")
            
            if metrics_response.status_code == 200:
                metrics_text = metrics_response.text
                lines = metrics_text.split('\n')
                metric_count = len([line for line in lines if line.startswith('#')])
                print(f"  📊 Metrics Available: {metric_count} types")
                
                # 비즈니스 메트릭 확인
                business_metrics = [
                    'user_registrations_total',
                    'user_logins_total',
                    'schemas_created_total',
                    'audit_events_total',
                    'http_requests_total'
                ]
                
                for metric in business_metrics:
                    if metric in metrics_text:
                        print(f"    ✅ {metric}")
                    else:
                        print(f"    ❌ {metric} Missing")
                        
            elif metrics_response.status_code == 404:
                print(f"  🚨 CRITICAL: No metrics endpoint!")
                
        except Exception as e:
            print(f"  ❌ Metrics Check Failed: {e}")

def generate_some_traffic():
    """트래픽 생성으로 메트릭 데이터 만들기"""
    print("\n🚗 Generating traffic to create metrics...")
    
    # User Service 트래픽
    try:
        # 로그인 요청
        login_data = {"username": "admin", "password": "admin123"}
        response = requests.post("http://localhost:8012/api/v1/auth/login", json=login_data)
        print(f"  🔑 Login: {response.status_code}")
        
        if response.status_code == 200:
            token = response.json().get('access_token')
            
            # OMS Service 요청
            headers = {"Authorization": f"Bearer {token}"}
            oms_response = requests.get("http://localhost:8010/api/v1/schemas", headers=headers)
            print(f"  🗄️ OMS Schemas: {oms_response.status_code}")
            
            # Audit Service 요청
            audit_data = {"event_type": "metrics_test", "details": {"test": True}}
            audit_response = requests.post("http://localhost:8011/api/v2/events", json=audit_data, headers=headers)
            print(f"  📋 Audit Event: {audit_response.status_code}")
            
    except Exception as e:
        print(f"  ❌ Traffic Generation Failed: {e}")

def check_prometheus_targets():
    """Prometheus가 타겟들을 제대로 수집하고 있는지 확인"""
    print("\n🎯 Checking Prometheus Targets...")
    
    try:
        prometheus_url = "http://localhost:9091"
        response = requests.get(f"{prometheus_url}/api/v1/targets")
        
        if response.status_code == 200:
            data = response.json()
            targets = data.get('data', {}).get('activeTargets', [])
            
            print(f"  📊 Total Targets: {len(targets)}")
            
            for target in targets:
                job = target.get('labels', {}).get('job', 'unknown')
                health = target.get('health', 'unknown')
                last_error = target.get('lastError', '')
                
                if health == 'up':
                    print(f"    ✅ {job}: {health}")
                else:
                    print(f"    ❌ {job}: {health} - {last_error}")
                    
        else:
            print(f"  ❌ Prometheus not accessible: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ Prometheus check failed: {e}")

if __name__ == "__main__":
    print("🚨 EMERGENCY METRICS VALIDATION")
    print("🎯 프로덕션 레디를 위한 긴급 메트릭 검증")
    print("=" * 50)
    
    # 1. 모든 서비스 메트릭 테스트
    test_all_metrics()
    
    # 2. 트래픽 생성
    generate_some_traffic()
    
    # 3. 다시 메트릭 확인
    print("\n🔄 Re-checking metrics after traffic...")
    test_all_metrics()
    
    # 4. Prometheus 타겟 확인
    check_prometheus_targets()
    
    print("\n🏁 Emergency validation complete!")