#!/bin/bash
# OMS 복원력 메커니즘 상태 확인 스크립트

echo "=========================================="
echo "OMS 복원력 메커니즘 상태 확인"
echo "=========================================="

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 환경 변수 확인
echo -e "\n1. 환경 변수 확인:"
if [ -f "ontology-management-service/.env" ]; then
    echo -e "${GREEN}✓${NC} .env 파일 존재"

    # 주요 설정 확인
    if grep -q "CIRCUIT_BREAKER_FAILURE_THRESHOLD" ontology-management-service/.env; then
        echo -e "${GREEN}✓${NC} 서킷 브레이커 설정 확인"
        grep "CIRCUIT_BREAKER_" ontology-management-service/.env | head -3
    else
        echo -e "${YELLOW}⚠${NC} 서킷 브레이커 설정 없음"
    fi

    if grep -q "ENABLE_ETAG_CACHING=true" ontology-management-service/.env; then
        echo -e "${GREEN}✓${NC} E-Tag 캐싱 활성화"
    else
        echo -e "${YELLOW}⚠${NC} E-Tag 캐싱 비활성화"
    fi
else
    echo -e "${RED}✗${NC} .env 파일이 없습니다"
    echo "  → .env.development 또는 .env.production을 복사하세요"
fi

# 2. Docker 컨테이너 상태
echo -e "\n2. Docker 컨테이너 상태:"
if docker ps | grep -q "oms-monolith"; then
    echo -e "${GREEN}✓${NC} OMS 컨테이너 실행 중"
else
    echo -e "${RED}✗${NC} OMS 컨테이너가 실행되지 않음"
fi

if docker ps | grep -q "redis"; then
    echo -e "${GREEN}✓${NC} Redis 컨테이너 실행 중"
else
    echo -e "${RED}✗${NC} Redis 컨테이너가 실행되지 않음"
fi

# 3. 서비스 헬스 체크
echo -e "\n3. 서비스 헬스 체크:"
if curl -s http://localhost:8091/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} OMS 서비스 응답"

    # E-Tag 테스트
    echo -e "\n4. E-Tag 테스트:"
    RESPONSE=$(curl -s -I http://localhost:8091/api/v1/schemas/main/object-types 2>/dev/null)
    if echo "$RESPONSE" | grep -q "etag:"; then
        echo -e "${GREEN}✓${NC} E-Tag 헤더 발견"
        echo "$RESPONSE" | grep -i "etag:"
    else
        echo -e "${YELLOW}⚠${NC} E-Tag 헤더 없음 (인증 필요할 수 있음)"
    fi
else
    echo -e "${RED}✗${NC} OMS 서비스 응답 없음"
fi

# 4. 파일 확인
echo -e "\n5. 설정 파일 확인:"
files=(
    "ontology-management-service/.env.development"
    "ontology-management-service/.env.production"
    "ontology-management-service/.env.resilience"
    "create_admin_test_user.py"
    "test_oms_resilience_activated.py"
    "OMS_RESILIENCE_ACTIVATION_SUMMARY.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (없음)"
    fi
done

echo -e "\n=========================================="
echo "권장 조치:"
echo "=========================================="

if [ ! -f "ontology-management-service/.env" ]; then
    echo "1. 환경 파일 설정:"
    echo "   cd ontology-management-service"
    echo "   cp .env.development .env"
fi

echo -e "\n2. 서비스 재시작:"
echo "   docker-compose down && docker-compose up -d"

echo -e "\n3. 관리자 계정 생성 및 테스트:"
echo "   python create_admin_test_user.py"
echo "   python test_oms_resilience_activated.py"

echo -e "\n4. 모니터링 확인:"
echo "   - Prometheus: http://localhost:8091/metrics"
echo "   - Grafana: http://localhost:3000"
echo "=========================================="
