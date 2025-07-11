#!/bin/bash
"""
🛑 ARRAKIS MSA PRODUCTION SERVICES STOPPER
==========================================

프로덕션 MSA 서비스 안전 종료 스크립트
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_header() {
    echo -e "${BLUE}=================================="
    echo -e "🛑 ARRAKIS MSA SERVICES SHUTDOWN"
    echo -e "==================================${NC}"
}

stop_service_by_port() {
    local port=$1
    local service_name=$2
    
    print_status "$service_name 종료 중..."
    
    # 포트로 프로세스 찾기
    local pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            print_status "프로세스 $pid 종료 중..."
            kill -TERM $pid 2>/dev/null
            
            # 5초 대기 후 강제 종료
            sleep 5
            if kill -0 $pid 2>/dev/null; then
                print_warning "프로세스 $pid 강제 종료"
                kill -KILL $pid 2>/dev/null
            fi
        done
        print_status "$service_name 종료 완료"
    else
        print_warning "$service_name가 포트 $port에서 실행되지 않고 있습니다."
    fi
}

stop_services_by_name() {
    print_status "서비스별 프로세스 종료 중..."
    
    # uvicorn 프로세스들 종료
    pkill -f "uvicorn.*main:app" 2>/dev/null
    
    # 추가적으로 특정 포트의 프로세스들 종료
    stop_service_by_port 3001 "User Service"
    stop_service_by_port 3002 "Ontology Service" 
    stop_service_by_port 3003 "Audit Service"
}

stop_redis() {
    print_status "Redis 종료 여부 확인..."
    
    echo "Redis도 함께 종료하시겠습니까? (y/n)"
    read -r response
    
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        if pgrep -x "redis-server" > /dev/null; then
            print_status "Redis 종료 중..."
            pkill -x redis-server
            print_status "Redis 종료 완료"
        else
            print_warning "Redis가 실행되지 않고 있습니다."
        fi
    else
        print_status "Redis는 계속 실행 상태로 유지됩니다."
    fi
}

cleanup_files() {
    print_status "임시 파일 정리 중..."
    
    # PID 파일 제거
    if [ -f ".production_services.pid" ]; then
        rm .production_services.pid
        print_status "PID 파일 제거"
    fi
    
    # 로그 파일 압축 (선택사항)
    if [ -d "logs" ] && [ "$(ls -A logs)" ]; then
        echo "로그 파일을 압축 보관하시겠습니까? (y/n)"
        read -r response
        
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            timestamp=$(date +"%Y%m%d_%H%M%S")
            tar -czf "logs_backup_$timestamp.tar.gz" logs/
            print_status "로그 파일 압축 완료: logs_backup_$timestamp.tar.gz"
            
            echo "기존 로그 파일을 삭제하시겠습니까? (y/n)"
            read -r response
            if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
                rm -rf logs/*
                print_status "로그 파일 삭제 완료"
            fi
        fi
    fi
}

verify_shutdown() {
    print_status "서비스 종료 상태 확인 중..."
    
    local ports=(3001 3002 3003)
    local services=("User Service" "Ontology Service" "Audit Service")
    
    all_stopped=true
    
    for i in "${!ports[@]}"; do
        local port=${ports[$i]}
        local service=${services[$i]}
        
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_error "$service (포트 $port)가 아직 실행 중입니다."
            all_stopped=false
        else
            print_status "$service: 종료 완료"
        fi
    done
    
    if $all_stopped; then
        print_status "모든 MSA 서비스가 정상적으로 종료되었습니다."
        return 0
    else
        print_error "일부 서비스가 아직 종료되지 않았습니다."
        return 1
    fi
}

main() {
    print_header
    
    echo "MSA 서비스를 종료하시겠습니까? (y/n)"
    read -r response
    
    if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_warning "서비스 종료가 취소되었습니다."
        exit 0
    fi
    
    # 서비스 종료
    stop_services_by_name
    
    # 종료 상태 확인
    sleep 2
    verify_shutdown
    
    # Redis 종료 여부 확인
    stop_redis
    
    # 파일 정리
    cleanup_files
    
    echo ""
    print_status "🎉 MSA 서비스 종료가 완료되었습니다!"
    echo ""
}

# Ctrl+C 시그널 처리
trap 'echo -e "\n${YELLOW}서비스 종료가 중단되었습니다.${NC}"; exit 1' INT

# 스크립트 실행
main "$@"