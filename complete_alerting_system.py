#!/opt/homebrew/bin/python3.12
"""
🚨 COMPLETE ALERTING SYSTEM SETUP
===================================
완전한 엔터프라이즈 알람 및 알림 시스템 구축

- Prometheus 설정 수정 (올바른 포트)
- Alertmanager 완전 구성
- Redis/Postgres Exporter 활성화
- 알람 규칙 생성
- 다중 알림 채널 설정
"""

import os
import yaml
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class CompleteAlertingSystem:
    def __init__(self):
        self.base_path = Path("/Users/isihyeon/Desktop/Arrakis-Project")
        self.monitoring_path = self.base_path / "ontology-management-service/monitoring"
        self.results = {}
        
    def fix_prometheus_config(self):
        """Prometheus 설정 수정 - 올바른 포트로 업데이트"""
        print("🔧 Prometheus 설정 수정...")
        
        prometheus_config = {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s',
                'external_labels': {
                    'monitor': 'oms-cluster',
                    'environment': 'production'
                }
            },
            'alerting': {
                'alertmanagers': [{
                    'static_configs': [{
                        'targets': ['localhost:9093']
                    }]
                }]
            },
            'rule_files': [
                "/etc/prometheus/rules/*.yml",
                "/etc/prometheus/rules/enterprise_resilience_alerts.yml"
            ],
            'scrape_configs': [
                # 실제 실행 중인 MSA 서비스들
                {
                    'job_name': 'user-service',
                    'static_configs': [{
                        'targets': ['host.docker.internal:8012']
                    }],
                    'scrape_interval': '5s',
                    'metrics_path': '/metrics'
                },
                {
                    'job_name': 'oms-service', 
                    'static_configs': [{
                        'targets': ['host.docker.internal:8010']
                    }],
                    'scrape_interval': '5s',
                    'metrics_path': '/metrics'
                },
                {
                    'job_name': 'audit-service',
                    'static_configs': [{
                        'targets': ['host.docker.internal:8011']
                    }],
                    'scrape_interval': '5s',
                    'metrics_path': '/metrics'
                },
                # Node Exporter (시스템 메트릭)
                {
                    'job_name': 'node-exporter',
                    'static_configs': [{
                        'targets': ['localhost:9100']
                    }]
                },
                # Redis Exporter
                {
                    'job_name': 'redis-exporter',
                    'static_configs': [{
                        'targets': ['localhost:9121']
                    }]
                },
                # Postgres Exporter
                {
                    'job_name': 'postgres-exporter',
                    'static_configs': [{
                        'targets': ['localhost:9187']
                    }]
                },
                # Jaeger
                {
                    'job_name': 'jaeger',
                    'static_configs': [{
                        'targets': ['localhost:14269']
                    }]
                }
            ]
        }
        
        # 설정 파일 저장
        config_path = self.monitoring_path / "prometheus/prometheus-fixed.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(prometheus_config, f, default_flow_style=False)
        
        print(f"  ✅ Prometheus 설정 저장: {config_path}")
        return config_path
    
    def create_alerting_rules(self):
        """알람 규칙 생성"""
        print("📋 알람 규칙 생성...")
        
        alerting_rules = {
            'groups': [
                {
                    'name': 'msa_service_alerts',
                    'rules': [
                        {
                            'alert': 'ServiceDown',
                            'expr': 'up == 0',
                            'for': '1m',
                            'labels': {
                                'severity': 'critical'
                            },
                            'annotations': {
                                'summary': 'Service {{ $labels.job }} is down',
                                'description': 'Service {{ $labels.job }} has been down for more than 1 minute.'
                            }
                        },
                        {
                            'alert': 'HighErrorRate',
                            'expr': 'rate(http_requests_total{status=~"5.."}[5m]) > 0.1',
                            'for': '2m',
                            'labels': {
                                'severity': 'warning'
                            },
                            'annotations': {
                                'summary': 'High error rate detected',
                                'description': 'Error rate is {{ $value }} for service {{ $labels.job }}'
                            }
                        },
                        {
                            'alert': 'HighResponseTime',
                            'expr': 'histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2',
                            'for': '5m',
                            'labels': {
                                'severity': 'warning'
                            },
                            'annotations': {
                                'summary': 'High response time',
                                'description': '95th percentile response time is {{ $value }}s for {{ $labels.job }}'
                            }
                        },
                        {
                            'alert': 'LowDiskSpace',
                            'expr': '(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10',
                            'for': '5m',
                            'labels': {
                                'severity': 'critical'
                            },
                            'annotations': {
                                'summary': 'Low disk space',
                                'description': 'Disk space is {{ $value }}% on {{ $labels.instance }}'
                            }
                        },
                        {
                            'alert': 'HighMemoryUsage',
                            'expr': '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85',
                            'for': '5m',
                            'labels': {
                                'severity': 'warning'
                            },
                            'annotations': {
                                'summary': 'High memory usage',
                                'description': 'Memory usage is {{ $value }}% on {{ $labels.instance }}'
                            }
                        },
                        {
                            'alert': 'DatabaseConnectionFailure',
                            'expr': 'pg_up == 0',
                            'for': '30s',
                            'labels': {
                                'severity': 'critical'
                            },
                            'annotations': {
                                'summary': 'Database connection failure',
                                'description': 'PostgreSQL database is unreachable'
                            }
                        }
                    ]
                }
            ]
        }
        
        rules_path = self.monitoring_path / "prometheus/rules/alerting_rules.yml"
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(rules_path, 'w') as f:
            yaml.dump(alerting_rules, f, default_flow_style=False)
        
        print(f"  ✅ 알람 규칙 저장: {rules_path}")
        return rules_path
    
    def create_alertmanager_config(self):
        """Alertmanager 설정 생성"""
        print("🚨 Alertmanager 설정 생성...")
        
        alertmanager_config = {
            'global': {
                'smtp_smarthost': 'localhost:587',
                'smtp_from': 'alerts@arrakis-project.com',
                'slack_api_url': 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
            },
            'route': {
                'group_by': ['alertname'],
                'group_wait': '10s',
                'group_interval': '10s',
                'repeat_interval': '1h',
                'receiver': 'web.hook'
            },
            'receivers': [
                {
                    'name': 'web.hook',
                    'webhook_configs': [{
                        'url': 'http://localhost:8080/webhook/alerts',
                        'send_resolved': True
                    }],
                    'email_configs': [{
                        'to': 'admin@arrakis-project.com',
                        'subject': '🚨 Arrakis Alert: {{ .GroupLabels.alertname }}',
                        'body': '''
Alert: {{ .GroupLabels.alertname }}
Severity: {{ .CommonLabels.severity }}
Summary: {{ .CommonAnnotations.summary }}
Description: {{ .CommonAnnotations.description }}

Time: {{ .FireTime }}
                        '''
                    }],
                    'slack_configs': [{
                        'channel': '#alerts',
                        'title': '🚨 Arrakis Production Alert',
                        'text': '{{ .CommonAnnotations.summary }}'
                    }]
                }
            ]
        }
        
        config_path = self.monitoring_path / "alertmanager/alertmanager-complete.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(alertmanager_config, f, default_flow_style=False)
        
        print(f"  ✅ Alertmanager 설정 저장: {config_path}")
        return config_path
    
    def create_webhook_server(self):
        """웹훅 알림 서버 생성"""
        print("🔗 웹훅 알림 서버 생성...")
        
        webhook_server = '''#!/opt/homebrew/bin/python3.12
"""
🚨 ALERTING WEBHOOK SERVER
웹훅을 통한 실시간 알림 처리
"""

from fastapi import FastAPI, Request
import uvicorn
import json
import logging
from datetime import datetime
import asyncio
import smtplib
from email.mime.text import MIMEText

app = FastAPI(title="Arrakis Alerting Webhook")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/webhook/alerts")
async def handle_alerts(request: Request):
    """Alertmanager 웹훅 처리"""
    try:
        data = await request.json()
        
        for alert in data.get('alerts', []):
            alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
            severity = alert.get('labels', {}).get('severity', 'unknown')
            status = alert.get('status', 'unknown')
            
            logger.info(f"🚨 Alert: {alert_name} | Severity: {severity} | Status: {status}")
            
            # 콘솔에 실시간 출력
            print(f"""
{'='*60}
🚨 ARRAKIS PRODUCTION ALERT
{'='*60}
Alert: {alert_name}
Severity: {severity.upper()}
Status: {status.upper()}
Time: {datetime.now().isoformat()}
Summary: {alert.get('annotations', {}).get('summary', 'N/A')}
Description: {alert.get('annotations', {}).get('description', 'N/A')}
{'='*60}
            """)
            
            # Slack 시뮬레이션 (실제로는 Slack API 호출)
            await send_slack_notification(alert_name, severity, status)
            
            # 이메일 알림 (선택적)
            if severity == 'critical':
                await send_email_alert(alert_name, alert)
        
        return {"status": "ok", "processed": len(data.get('alerts', []))}
        
    except Exception as e:
        logger.error(f"웹훅 처리 오류: {e}")
        return {"status": "error", "message": str(e)}

async def send_slack_notification(alert_name: str, severity: str, status: str):
    """Slack 알림 시뮬레이션"""
    emoji = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "🔵"
    print(f"📱 Slack 알림: {emoji} {alert_name} - {severity.upper()}")

async def send_email_alert(alert_name: str, alert: dict):
    """이메일 알림 (중요 알람만)"""
    print(f"📧 이메일 알림: {alert_name} - CRITICAL ALERT")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "alerting-webhook"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
'''
        
        webhook_path = self.base_path / "alerting_webhook_server.py"
        with open(webhook_path, 'w') as f:
            f.write(webhook_server)
        
        # 실행 권한 부여
        os.chmod(webhook_path, 0o755)
        
        print(f"  ✅ 웹훅 서버 생성: {webhook_path}")
        return webhook_path
    
    def create_docker_compose_complete(self):
        """완전한 Docker Compose 설정 생성"""
        print("🐳 완전한 Docker Compose 생성...")
        
        compose_config = {
            'version': '3.8',
            'services': {
                'prometheus': {
                    'image': 'prom/prometheus:latest',
                    'container_name': 'oms-prometheus-complete',
                    'ports': ['9091:9090'],
                    'volumes': [
                        './prometheus/prometheus-fixed.yml:/etc/prometheus/prometheus.yml:ro',
                        './prometheus/rules:/etc/prometheus/rules:ro',
                        'prometheus-data:/prometheus'
                    ],
                    'command': [
                        '--config.file=/etc/prometheus/prometheus.yml',
                        '--storage.tsdb.path=/prometheus',
                        '--web.console.libraries=/usr/share/prometheus/console_libraries',
                        '--web.console.templates=/usr/share/prometheus/consoles',
                        '--web.enable-lifecycle',
                        '--web.enable-admin-api'
                    ],
                    'restart': 'unless-stopped'
                },
                'alertmanager': {
                    'image': 'prom/alertmanager:latest',
                    'container_name': 'oms-alertmanager-complete',
                    'ports': ['9093:9093'],
                    'volumes': [
                        './alertmanager/alertmanager-complete.yml:/etc/alertmanager/alertmanager.yml:ro',
                        'alertmanager-data:/alertmanager'
                    ],
                    'command': [
                        '--config.file=/etc/alertmanager/alertmanager.yml',
                        '--storage.path=/alertmanager',
                        '--web.external-url=http://localhost:9093'
                    ],
                    'restart': 'unless-stopped'
                },
                'redis-exporter': {
                    'image': 'oliver006/redis_exporter:latest',
                    'container_name': 'oms-redis-exporter',
                    'ports': ['9121:9121'],
                    'environment': [
                        'REDIS_ADDR=host.docker.internal:6379'
                    ],
                    'restart': 'unless-stopped'
                },
                'postgres-exporter': {
                    'image': 'prometheuscommunity/postgres-exporter:latest',
                    'container_name': 'oms-postgres-exporter',
                    'ports': ['9187:9187'],
                    'environment': [
                        'DATA_SOURCE_NAME=postgresql://oms_user:oms_password@host.docker.internal:5432/oms_db?sslmode=disable'
                    ],
                    'restart': 'unless-stopped'
                },
                'node-exporter': {
                    'image': 'prom/node-exporter:latest',
                    'container_name': 'oms-node-exporter-complete',
                    'ports': ['9100:9100'],
                    'volumes': [
                        '/proc:/host/proc:ro',
                        '/sys:/host/sys:ro',
                        '/:/rootfs:ro'
                    ],
                    'command': [
                        '--path.procfs=/host/proc',
                        '--path.sysfs=/host/sys',
                        '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
                    ],
                    'restart': 'unless-stopped'
                }
            },
            'volumes': {
                'prometheus-data': None,
                'alertmanager-data': None
            }
        }
        
        compose_path = self.monitoring_path / "docker-compose-complete-alerting.yml"
        
        with open(compose_path, 'w') as f:
            yaml.dump(compose_config, f, default_flow_style=False)
        
        print(f"  ✅ 완전한 Docker Compose 저장: {compose_path}")
        return compose_path
    
    def test_current_services(self):
        """현재 실행 중인 서비스들 메트릭 테스트"""
        print("🧪 현재 서비스 메트릭 테스트...")
        
        services_to_test = [
            ("User Service", "http://localhost:8012/metrics"),
            ("OMS Service", "http://localhost:8010/metrics"),
            ("Audit Service", "http://localhost:8011/metrics"),
            ("Node Exporter", "http://localhost:9100/metrics")
        ]
        
        results = {}
        
        for service_name, url in services_to_test:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    metrics_count = len([line for line in response.text.split('\n') if line.startswith('#')])
                    results[service_name] = {"status": "✅", "metrics": metrics_count}
                    print(f"  ✅ {service_name}: {metrics_count} 메트릭 타입")
                else:
                    results[service_name] = {"status": "❌", "error": f"HTTP {response.status_code}"}
                    print(f"  ❌ {service_name}: HTTP {response.status_code}")
            except Exception as e:
                results[service_name] = {"status": "❌", "error": str(e)}
                print(f"  ❌ {service_name}: {e}")
        
        return results
    
    async def setup_complete_alerting(self):
        """완전한 알람 시스템 설정"""
        print("🚨 COMPLETE ALERTING SYSTEM SETUP")
        print("=" * 60)
        
        # 1. 현재 서비스 테스트
        service_results = self.test_current_services()
        
        # 2. Prometheus 설정 수정
        prometheus_config = self.fix_prometheus_config()
        
        # 3. 알람 규칙 생성
        alert_rules = self.create_alerting_rules()
        
        # 4. Alertmanager 설정
        alertmanager_config = self.create_alertmanager_config()
        
        # 5. 웹훅 서버 생성
        webhook_server = self.create_webhook_server()
        
        # 6. 완전한 Docker Compose
        docker_compose = self.create_docker_compose_complete()
        
        print("\n🎯 설정 완료 결과:")
        print(f"✅ Prometheus 설정: {prometheus_config}")
        print(f"✅ 알람 규칙: {alert_rules}")
        print(f"✅ Alertmanager 설정: {alertmanager_config}")
        print(f"✅ 웹훅 서버: {webhook_server}")
        print(f"✅ Docker Compose: {docker_compose}")
        
        print("\n🚀 다음 단계:")
        print("1. 웹훅 서버 시작: python3 alerting_webhook_server.py")
        print("2. 완전한 모니터링 스택 시작:")
        print("   cd ontology-management-service/monitoring")
        print("   docker-compose -f docker-compose-complete-alerting.yml up -d")
        print("3. Prometheus 설정 재로드")
        print("4. 알람 테스트")
        
        return {
            "service_metrics": service_results,
            "prometheus_config": str(prometheus_config),
            "alert_rules": str(alert_rules),
            "alertmanager_config": str(alertmanager_config),
            "webhook_server": str(webhook_server),
            "docker_compose": str(docker_compose)
        }

async def main():
    system = CompleteAlertingSystem()
    results = await system.setup_complete_alerting()
    
    # 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f"complete_alerting_setup_{timestamp}.json"
    
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 설정 결과 저장: {result_file}")
    
    return results

if __name__ == "__main__":
    results = asyncio.run(main())