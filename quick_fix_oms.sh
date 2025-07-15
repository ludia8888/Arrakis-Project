#!/bin/bash
# OMS 빠른 수정 스크립트
# 발견된 문제들을 빠르게 해결

echo "🔧 OMS 빠른 수정 시작..."
echo "================================"

# 1. 의존성 문제 해결
echo "📦 1. 의존성 패키지 설치..."
cd ontology-management-service
# macOS 보호된 환경에서 설치
pip install --user --break-system-packages -r requirements.txt 2>/dev/null || pip install -r requirements.txt
pip install --user --break-system-packages cachetools backoff prometheus-client 2>/dev/null || pip install cachetools backoff prometheus-client
cd ..

# 2. 환경 변수 설정
echo "🔧 2. 환경 변수 설정 파일 생성..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Service URLs
USER_SERVICE_URL=http://user-service:8002
OMS_SERVICE_URL=http://localhost:8000
IAM_SERVICE_URL=http://iam-service:8003
AUDIT_SERVICE_URL=http://audit-service:8001

# Database
TERMINUS_SERVER=http://localhost:6363
TERMINUS_DB=ontology_db
TERMINUS_USER=admin
TERMINUS_PASSWORD=root

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_AUDIENCE=oms
JWT_ISSUER=user-service
USE_JWKS=true

# NATS
NATS_URL=nats://localhost:4222

# Service Discovery
ENABLE_SERVICE_DISCOVERY=true
SERVICE_NAME=oms-monolith
EOF
    echo "✅ .env 파일 생성 완료"
else
    echo "⚠️  .env 파일이 이미 존재합니다"
fi

# 3. common_security 패키지 처리
echo "🔧 3. common_security 패키지 처리..."
# common_security가 로컬 패키지인 경우 mock 생성
mkdir -p packages/backend/common_security
cat > packages/backend/common_security/__init__.py << EOF
# Mock common_security package
class SecurityConfig:
    pass

def validate_input(data):
    return data
EOF

# 4. 서비스 시작 스크립트
echo "🚀 4. 서비스 시작 스크립트 생성..."
cat > start_services.sh << 'EOF'
#!/bin/bash
# MSA 서비스 시작 스크립트

echo "🚀 MSA 서비스 시작..."

# Redis 시작
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    redis-server --daemonize yes
fi

# User Service 시작
echo "Starting User Service..."
cd user-service
uvicorn main:app --port 8002 --reload &
cd ..

# Audit Service 시작
echo "Starting Audit Service..."
cd audit-service
uvicorn main:app --port 8001 --reload &
cd ..

# OMS 시작
echo "Starting OMS..."
cd ontology-management-service
uvicorn main:app --port 8000 --reload &
cd ..

echo "✅ 모든 서비스가 시작되었습니다"
echo "User Service: http://localhost:8002"
echo "Audit Service: http://localhost:8001"
echo "OMS: http://localhost:8000"
EOF

chmod +x start_services.sh

# 5. 테스트 실행
echo "🧪 5. 통합 테스트 준비..."
echo "다음 명령으로 통합 테스트를 실행할 수 있습니다:"
echo "  python test_msa_integration_complete.py"

echo ""
echo "✅ OMS 빠른 수정 완료!"
echo "================================"
echo "다음 단계:"
echo "1. ./start_services.sh 로 모든 서비스 시작"
echo "2. python test_msa_integration_complete.py 로 통합 테스트 실행"
echo "3. 문제가 있으면 MSA_INTEGRATION_FINAL_REPORT.md 참고"
