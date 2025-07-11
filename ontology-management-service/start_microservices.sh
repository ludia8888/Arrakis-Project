#!/bin/bash

# 점진적 마이그레이션: 모놀리스에서 마이크로서비스로 전환
# Start Microservices Migration Script

set -e

echo "🚀 Arrakis MSA - 마이크로서비스 모드 시작"
echo "================================================"

# 환경 변수 파일 복사
if [ ! -f .env ]; then
    echo "📋 환경 설정 파일 생성 중..."
    cp .env.microservices .env
    echo "✅ .env 파일이 생성되었습니다."
else
    echo "⚠️  .env 파일이 이미 존재합니다. 기존 설정을 유지합니다."
fi

# Docker 네트워크 생성
echo ""
echo "🌐 Docker 네트워크 확인 중..."
docker network create oms-network 2>/dev/null || echo "✅ oms-network가 이미 존재합니다."

# 기존 컨테이너 정리 (옵션)
if [ "$1" == "--clean" ]; then
    echo ""
    echo "🧹 기존 컨테이너 정리 중..."
    docker-compose -f docker-compose.yml -f docker-compose.microservices.yml down
fi

# 필수 서비스 먼저 시작 (TerminusDB, Redis, NATS, PostgreSQL)
echo ""
echo "🔧 인프라 서비스 시작 중..."
docker-compose -f docker-compose.yml up -d terminusdb redis nats postgres

# 잠시 대기 (인프라 서비스 준비)
echo "⏳ 인프라 서비스 준비 대기 중 (10초)..."
sleep 10

# Data Kernel 시작 (첫 번째 마이크로서비스)
echo ""
echo "🎯 Data Kernel Gateway 시작 중..."
docker-compose -f docker-compose.yml up -d data-kernel

# User Service 시작
echo ""
echo "👤 User Service 시작 중..."
docker-compose -f docker-compose.yml up -d user-service

# 잠시 대기
echo "⏳ 기본 서비스 준비 대기 중 (5초)..."
sleep 5

# 마이크로서비스들 시작
echo ""
echo "🚀 마이크로서비스 시작 중..."
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml up -d embedding-service scheduler-service scheduler-worker event-gateway

# OMS Monolith 시작 (마이크로서비스 모드)
echo ""
echo "🏛️  OMS Monolith 시작 중 (마이크로서비스 모드)..."
docker-compose -f docker-compose.yml up -d oms-monolith

# 모니터링 서비스 시작 (옵션)
if [ "$2" == "--monitoring" ]; then
    echo ""
    echo "📊 모니터링 서비스 시작 중..."
    docker-compose -f docker-compose.yml up -d prometheus grafana jaeger
fi

# 상태 확인
echo ""
echo "📋 서비스 상태 확인 중..."
sleep 5

echo ""
echo "🎉 마이크로서비스 모드 시작 완료!"
echo ""
echo "📌 서비스 엔드포인트:"
echo "  - OMS API: http://localhost:8083"
echo "  - Data Kernel API: http://localhost:8082"
echo "  - Data Kernel gRPC: localhost:50051"
echo "  - Embedding Service: http://localhost:8001"
echo "  - Scheduler Service: http://localhost:8002"
echo "  - Event Gateway: http://localhost:8003"
echo "  - User Service: http://localhost:8081"
echo "  - TerminusDB: http://localhost:6363"
echo "  - Redis: localhost:6381"
echo "  - NATS: localhost:4222"
echo ""
echo "📊 모니터링 (--monitoring 옵션 사용 시):"
echo "  - Prometheus: http://localhost:9091"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Jaeger: http://localhost:16686"
echo ""
echo "🔍 로그 확인:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.microservices.yml logs -f [service-name]"
echo ""
echo "🛑 종료하려면:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.microservices.yml down"
echo ""

# 서비스 상태 표시
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml ps