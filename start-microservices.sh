#!/bin/bash

# Arrakis MSA - 통합 마이크로서비스 시작 스크립트

set -e

echo "🚀 Arrakis MSA - 마이크로서비스 모드 시작"
echo "================================================"

# 환경 변수 설정
export USE_DATA_KERNEL_GATEWAY=true
export USE_EMBEDDING_MS=true
export USE_SCHEDULER_MS=true
export USE_EVENT_GATEWAY=true

# Docker 네트워크 생성
echo ""
echo "🌐 Docker 네트워크 확인 중..."
docker network create arrakis-net 2>/dev/null || echo "✅ arrakis-net이 이미 존재합니다."

# 기존 컨테이너 정리 (옵션)
if [ "$1" == "--clean" ]; then
    echo ""
    echo "🧹 기존 컨테이너 정리 중..."
    docker-compose down
fi

# 서비스 시작
echo ""
echo "🔧 서비스 시작 중..."
docker-compose up -d

# 상태 확인
echo ""
echo "📋 서비스 상태 확인 중..."
sleep 10

echo ""
echo "🎉 마이크로서비스 모드 시작 완료!"
echo ""
echo "📌 서비스 엔드포인트:"
echo "  - OMS API: http://localhost:8000"
echo "  - User Service: http://localhost:8010"
echo "  - Audit Service: http://localhost:8011"
echo "  - Data Kernel API: http://localhost:8080"
echo "  - Embedding Service: http://localhost:8001"
echo "  - Scheduler Service: http://localhost:8002"
echo "  - Event Gateway: http://localhost:8003"
echo ""
echo "📊 모니터링:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Jaeger: http://localhost:16686"
echo ""
echo "🔍 로그 확인:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "🛑 종료하려면:"
echo "  docker-compose down"
echo ""

# 서비스 상태 표시
docker-compose ps