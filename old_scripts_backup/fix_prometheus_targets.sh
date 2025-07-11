#!/bin/bash
echo "🔧 Prometheus 타겟 100점 달성 스크립트"

# Host에서 직접 접근 가능한 설정으로 변경
cat > /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/monitoring/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: arrakis-complete
    environment: production

alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - host.docker.internal:9093

rule_files:
- /etc/prometheus/rules/*.yml

scrape_configs:
# 핵심 MSA 서비스들 (현재 실행 중)
- job_name: arrakis-user-service
  static_configs:
  - targets:
    - host.docker.internal:8012
  metrics_path: /metrics
  scrape_interval: 5s
  
- job_name: arrakis-oms-service
  static_configs:
  - targets:
    - host.docker.internal:8010
  metrics_path: /metrics
  scrape_interval: 5s
  
- job_name: arrakis-audit-service
  static_configs:
  - targets:
    - host.docker.internal:8011
  metrics_path: /metrics
  scrape_interval: 5s

# Exporter들 (host.docker.internal 사용)
- job_name: node-exporter
  static_configs:
  - targets:
    - host.docker.internal:9100
  metrics_path: /metrics
  scrape_interval: 15s
  
- job_name: redis-exporter
  static_configs:
  - targets:
    - host.docker.internal:9121
  metrics_path: /metrics
  scrape_interval: 15s
  
- job_name: postgres-exporter
  static_configs:
  - targets:
    - host.docker.internal:9187
  metrics_path: /metrics
  scrape_interval: 15s

# Jaeger
- job_name: jaeger
  static_configs:
  - targets:
    - host.docker.internal:14269
  metrics_path: /metrics
  scrape_interval: 30s

# 알림 웹훅 서버
- job_name: alerting-webhook
  static_configs:
  - targets:
    - host.docker.internal:8080
  metrics_path: /health
  scrape_interval: 30s
EOF

echo "✅ Prometheus 설정 업데이트 완료"

# Prometheus 재시작
docker restart oms-prometheus-ultimate

echo "⏳ 30초 대기..."
sleep 30

# 타겟 상태 확인
echo "🎯 Prometheus 타겟 상태:"
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

echo "✅ 완료!"