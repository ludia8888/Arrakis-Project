#!/bin/bash
"""
🚀 ARRAKIS MSA PRODUCTION SERVICES LAUNCHER
===========================================

프로덕션 레디 검증을 위한 MSA 서비스 통합 실행 스크립트
- 실제 사용자 환경과 동일한 포트 구성
- 프로덕션급 설정 적용
- 서비스 간 연동 검증
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=================================="
    echo -e "🚀 ARRAKIS MSA PRODUCTION SERVICES"
    echo -e "==================================${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

check_port() {
    local port=$1
    local service_name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null; then
        print_warning "$service_name이 이미 포트 $port에서 실행 중입니다."
        echo "기존 프로세스를 종료하고 재시작하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            pkill -f "uvicorn.*--port $port" 2>/dev/null
            sleep 2
            return 0
        else
            return 1
        fi
    fi
    return 0
}

start_redis() {
    print_status "Redis 상태 확인 중..."
    if ! pgrep -x "redis-server" > /dev/null; then
        print_status "Redis 시작 중..."
        redis-server --daemonize yes --port 6379
        sleep 2
        if pgrep -x "redis-server" > /dev/null; then
            print_status "Redis 시작 완료 (포트 6379)"
        else
            print_error "Redis 시작 실패"
            return 1
        fi
    else
        print_status "Redis 이미 실행 중"
    fi
    return 0
}

start_user_service() {
    print_status "User Service 시작 중..."
    
    if ! check_port 3001 "User Service"; then
        return 1
    fi
    
    cd user-service || {
        print_error "user-service 디렉토리를 찾을 수 없습니다."
        return 1
    }
    
    # 가상환경 활성화 (있는 경우)
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # 프로덕션 모드로 시작
    export ENVIRONMENT="production"
    export PORT="3001"
    export HOST="0.0.0.0"
    
    nohup uvicorn main:app --host 0.0.0.0 --port 3001 --workers 2 > ../logs/user-service.log 2>&1 &
    USER_SERVICE_PID=$!
    
    cd ..
    
    # 서비스 시작 대기
    sleep 3
    
    # 헬스체크
    for i in {1..10}; do
        if curl -s http://localhost:3001/health > /dev/null 2>&1; then
            print_status "User Service 시작 완료 (PID: $USER_SERVICE_PID, 포트: 3001)"
            return 0
        fi
        sleep 1
    done
    
    print_error "User Service 헬스체크 실패"
    return 1
}

start_ontology_service() {
    print_status "Ontology Management Service 시작 중..."
    
    if ! check_port 3002 "Ontology Service"; then
        return 1
    fi
    
    cd ontology-management-service || {
        print_error "ontology-management-service 디렉토리를 찾을 수 없습니다."
        return 1
    }
    
    # 가상환경 활성화 (있는 경우)
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # 프로덕션 모드로 시작
    export ENVIRONMENT="production"
    export PORT="3002"
    export HOST="0.0.0.0"
    export DATABASE_URL="sqlite:///./data/versions.db"
    
    nohup uvicorn main:app --host 0.0.0.0 --port 3002 --workers 2 > ../logs/ontology-service.log 2>&1 &
    ONTOLOGY_SERVICE_PID=$!
    
    cd ..
    
    # 서비스 시작 대기
    sleep 3
    
    # 헬스체크
    for i in {1..10}; do
        if curl -s http://localhost:3002/health > /dev/null 2>&1; then
            print_status "Ontology Service 시작 완료 (PID: $ONTOLOGY_SERVICE_PID, 포트: 3002)"
            return 0
        fi
        sleep 1
    done
    
    print_error "Ontology Service 헬스체크 실패"
    return 1
}

start_audit_service() {
    print_status "Audit Service 시작 중..."
    
    if ! check_port 3003 "Audit Service"; then
        return 1
    fi
    
    cd audit-service || {
        print_error "audit-service 디렉토리를 찾을 수 없습니다."
        return 1
    }
    
    # 가상환경 활성화 (있는 경우)
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # 프로덕션 모드로 시작
    export ENVIRONMENT="production"
    export PORT="3003"
    export HOST="0.0.0.0"
    
    nohup uvicorn main:app --host 0.0.0.0 --port 3003 --workers 2 > ../logs/audit-service.log 2>&1 &
    AUDIT_SERVICE_PID=$!
    
    cd ..
    
    # 서비스 시작 대기
    sleep 3
    
    # 헬스체크
    for i in {1..10}; do
        if curl -s http://localhost:3003/health > /dev/null 2>&1; then
            print_status "Audit Service 시작 완료 (PID: $AUDIT_SERVICE_PID, 포트: 3003)"
            return 0
        fi
        sleep 1
    done
    
    print_error "Audit Service 헬스체크 실패"
    return 1
}

verify_service_integration() {
    print_status "MSA 서비스 간 연동 검증 중..."
    
    # 각 서비스의 health 엔드포인트 확인
    services=(
        "http://localhost:3001/health:User Service"
        "http://localhost:3002/health:Ontology Service" 
        "http://localhost:3003/health:Audit Service"
    )
    
    all_services_ok=true
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r url name <<< "$service_info"
        
        if curl -s -f "$url" > /dev/null 2>&1; then
            print_status "$name: 정상"
        else
            print_error "$name: 응답 없음 ($url)"
            all_services_ok=false
        fi
    done
    
    if $all_services_ok; then
        print_status "모든 MSA 서비스 정상 동작 확인"
        return 0
    else
        print_error "일부 서비스가 정상적으로 응답하지 않습니다"
        return 1
    fi
}

create_logs_directory() {
    if [ ! -d "logs" ]; then
        mkdir -p logs
        print_status "로그 디렉토리 생성: ./logs"
    fi
}

save_service_pids() {
    cat > .production_services.pid << EOF
USER_SERVICE_PID=$USER_SERVICE_PID
ONTOLOGY_SERVICE_PID=$ONTOLOGY_SERVICE_PID
AUDIT_SERVICE_PID=$AUDIT_SERVICE_PID
TIMESTAMP=$(date)
EOF
    print_status "서비스 PID 정보 저장: .production_services.pid"
}

main() {
    print_header
    
    # 로그 디렉토리 생성
    create_logs_directory
    
    # Redis 시작
    if ! start_redis; then
        print_error "Redis 시작 실패. 스크립트를 종료합니다."
        exit 1
    fi
    
    # User Service 시작
    if ! start_user_service; then
        print_error "User Service 시작 실패. 스크립트를 종료합니다."
        exit 1
    fi
    
    # Ontology Service 시작
    if ! start_ontology_service; then
        print_error "Ontology Service 시작 실패. 스크립트를 종료합니다."
        exit 1
    fi
    
    # Audit Service 시작
    if ! start_audit_service; then
        print_error "Audit Service 시작 실패. 스크립트를 종료합니다."
        exit 1
    fi
    
    # 서비스 간 연동 검증
    if ! verify_service_integration; then
        print_error "서비스 간 연동 검증 실패"
        exit 1
    fi
    
    # PID 정보 저장
    save_service_pids
    
    echo ""
    print_status "🎉 모든 MSA 서비스가 성공적으로 시작되었습니다!"
    echo ""
    echo -e "${BLUE}서비스 엔드포인트:${NC}"
    echo "  • User Service:      http://localhost:3001"
    echo "  • Ontology Service:  http://localhost:3002"
    echo "  • Audit Service:     http://localhost:3003"
    echo ""
    echo -e "${BLUE}로그 파일:${NC}"
    echo "  • User Service:      ./logs/user-service.log"
    echo "  • Ontology Service:  ./logs/ontology-service.log"
    echo "  • Audit Service:     ./logs/audit-service.log"
    echo ""
    echo -e "${YELLOW}서비스 종료:${NC} ./stop_production_services.sh"
    echo -e "${YELLOW}프로덕션 검증:${NC} python3 production_ready_comprehensive_validation.py"
}

# Ctrl+C 시그널 처리
trap 'echo -e "\n${YELLOW}서비스 시작이 중단되었습니다.${NC}"; exit 1' INT

# 스크립트 실행
main "$@"