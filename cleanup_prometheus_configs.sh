#!/bin/bash
echo "🧹 Prometheus 설정 파일 정리 및 통합"
echo "====================================="

cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/monitoring/prometheus

# 1. 백업 디렉토리 생성
mkdir -p old_configs_backup
echo "📁 백업 디렉토리 생성 완료"

# 2. 중복 파일들 백업
echo "📦 중복 파일들 백업 중..."
mv prometheus-auth.yml old_configs_backup/ 2>/dev/null
mv prometheus-complete.yml old_configs_backup/ 2>/dev/null
mv prometheus-fixed.yml old_configs_backup/ 2>/dev/null
mv prometheus-ultimate.yml old_configs_backup/ 2>/dev/null
mv prometheus-original-backup.yml old_configs_backup/ 2>/dev/null

# 3. 최종 통합 설정 생성
echo "🔧 최종 통합 Prometheus 설정 생성..."
cat > prometheus.yml << 'EOF'
# ARRAKIS PROJECT - UNIFIED PROMETHEUS CONFIGURATION
# =================================================
# 모든 중복 설정을 통합한 최종 버전
# Last Updated: 2025-07-12

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'arrakis-production'
    environment: 'production'

# Alertmanager 설정
alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - host.docker.internal:9093  # Alertmanager

# 알람 규칙 파일
rule_files:
  - "/etc/prometheus/rules/*.yml"

# 스크랩 설정
scrape_configs:
  # ========== CORE MSA SERVICES (현재 실행 중) ==========
  - job_name: 'user-service'
    static_configs:
    - targets: ['host.docker.internal:8012']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'oms-service'
    static_configs:
    - targets: ['host.docker.internal:8010']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'audit-service'
    static_configs:
    - targets: ['host.docker.internal:8011']
    metrics_path: '/metrics'
    scrape_interval: 5s

  # ========== EXPORTERS ==========
  - job_name: 'node-exporter'
    static_configs:
    - targets: ['host.docker.internal:9100']
    metrics_path: '/metrics'
    scrape_interval: 15s

  - job_name: 'redis-exporter'
    static_configs:
    - targets: ['host.docker.internal:9121']
    metrics_path: '/metrics'
    scrape_interval: 15s

  - job_name: 'postgres-exporter'
    static_configs:
    - targets: ['host.docker.internal:9187']
    metrics_path: '/metrics'
    scrape_interval: 15s

  # ========== MONITORING INFRASTRUCTURE ==========
  - job_name: 'prometheus'
    static_configs:
    - targets: ['localhost:9090']

  - job_name: 'alertmanager'
    static_configs:
    - targets: ['host.docker.internal:9093']

  - job_name: 'grafana'
    static_configs:
    - targets: ['host.docker.internal:3000']

  # ========== TRACING & PROFILING ==========
  - job_name: 'jaeger'
    static_configs:
    - targets: ['host.docker.internal:14269']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # ========== CUSTOM SERVICES ==========
  - job_name: 'alerting-webhook'
    static_configs:
    - targets: ['host.docker.internal:8080']
    metrics_path: '/health'
    scrape_interval: 30s

  # ========== FUTURE SERVICES (준비됨) ==========
  # Real Services (활성화 시 주석 해제)
  #- job_name: 'user-service-real'
  #  static_configs:
  #  - targets: ['host.docker.internal:8080']
  #
  #- job_name: 'oms-monolith-real'
  #  static_configs:
  #  - targets: ['host.docker.internal:8091']
  #
  #- job_name: 'audit-service-real'
  #  static_configs:
  #  - targets: ['host.docker.internal:8092']
EOF

echo "✅ 통합 설정 파일 생성 완료"

# 4. 중복 스크립트 정리
echo "🧹 중복 스크립트 정리..."
cd /Users/isihyeon/Desktop/Arrakis-Project
if [ -f "fix_prometheus_targets.sh" ]; then
    mkdir -p old_scripts_backup
    mv fix_prometheus_targets.sh old_scripts_backup/
    echo "  ✅ fix_prometheus_targets.sh 백업 완료"
fi

# 5. 상위 디렉토리의 중복 파일 정리
if [ -f "../../../prometheus.yml" ]; then
    mv ../../../prometheus.yml old_configs_backup/prometheus-root.yml 2>/dev/null
    echo "  ✅ 루트의 prometheus.yml 백업 완료"
fi

# 6. 현재 상태 확인
echo ""
echo "📊 정리 결과:"
echo "============"
echo "✅ 활성 설정 파일:"
echo "  - prometheus.yml (통합 설정)"
echo ""
echo "📦 백업된 파일들:"
ls -la old_configs_backup/ 2>/dev/null | grep -v "^total" | grep -v "^d"
echo ""

# 7. Prometheus 재시작
echo "🔄 Prometheus 재시작..."
docker restart oms-prometheus-ultimate

echo ""
echo "✨ 정리 완료!"
echo "  - 모든 중복 설정이 백업되었습니다"
echo "  - 통합된 하나의 prometheus.yml만 사용합니다"
echo "  - 백업 파일들은 old_configs_backup/ 에 있습니다"
