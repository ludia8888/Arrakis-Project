#!/bin/bash
# Unified Monitoring Setup Script
# Sets up Prometheus, Grafana, and Jaeger configurations

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_status "$BLUE" "📊 Setting up monitoring configuration..."

# Create directories
mkdir -p monitoring/prometheus/rules
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/alertmanager

# Prometheus configuration
cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'oms'
    static_configs:
      - targets: ['oms:8090']
        labels:
          service: 'ontology-management-service'

  - job_name: 'user-service'
    static_configs:
      - targets: ['user-service:8000']
        labels:
          service: 'user-service'

  - job_name: 'audit-service'
    static_configs:
      - targets: ['audit-service:8000']
        labels:
          service: 'audit-service'

  - job_name: 'event-gateway'
    static_configs:
      - targets: ['event-gateway:8003']
        labels:
          service: 'event-gateway'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
        labels:
          service: 'redis'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
        labels:
          service: 'postgres'
EOF

# Prometheus alert rules
cat > monitoring/prometheus/rules/alerts.yml << 'EOF'
groups:
  - name: service_alerts
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "{{ $labels.job }} has been down for more than 5 minutes."

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          description: "Error rate is above 5% for {{ $labels.job }}."

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage for {{ $labels.container_name }}"
          description: "Memory usage is above 90% for {{ $labels.container_name }}."
EOF

# Grafana datasources
cat > monitoring/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    editable: true
EOF

# Grafana dashboard provisioning
cat > monitoring/grafana/provisioning/dashboards/dashboards.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'Arrakis Dashboards'
    orgId: 1
    folder: ''
    folderUid: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

# Create a sample Grafana dashboard
cat > monitoring/grafana/dashboards/arrakis-overview.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Arrakis Project Overview",
    "tags": ["arrakis"],
    "timezone": "browser",
    "panels": [
      {
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "id": 1,
        "title": "Service Status",
        "type": "stat",
        "targets": [
          {
            "expr": "up",
            "refId": "A"
          }
        ]
      },
      {
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "id": 2,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "refId": "A"
          }
        ]
      },
      {
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "id": 3,
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])",
            "refId": "A"
          }
        ]
      },
      {
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        "id": 4,
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "refId": "A"
          }
        ]
      }
    ],
    "schemaVersion": 22,
    "version": 0
  },
  "overwrite": true
}
EOF

# Alertmanager configuration
cat > monitoring/alertmanager/alertmanager.yml << 'EOF'
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'critical-receiver'

receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://event-gateway:8003/webhooks/alerts'
        send_resolved: true

  - name: 'critical-receiver'
    webhook_configs:
      - url: 'http://event-gateway:8003/webhooks/critical-alerts'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
EOF

print_status "$GREEN" "✅ Monitoring configuration created!"
print_status "$BLUE" "📋 Next steps:"
echo "   1. Start services: ./start.sh"
echo "   2. Access Grafana: http://localhost:3000 (admin/admin)"
echo "   3. Access Prometheus: http://localhost:9090"
echo "   4. Access Jaeger: http://localhost:16686"