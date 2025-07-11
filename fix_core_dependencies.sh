#!/bin/bash
# Core 모듈 의존성 문제 해결 스크립트

echo "🔧 OMS Core 모듈 의존성 문제 해결 시작..."

# 1. 누락된 패키지 설치
echo "📦 누락된 패키지 설치 중..."
pip install cachetools

# 2. requirements.txt의 모든 패키지 재설치 (prometheus_client 등)
echo "📦 requirements.txt 패키지 재설치 중..."
cd ontology-management-service
pip install -r requirements.txt --force-reinstall prometheus-client backoff terminusdb-client

# 3. common_security 로컬 패키지 처리
echo "📦 common_security 로컬 패키지 처리..."
# common_security가 로컬 패키지인 경우 경로 수정 필요
# 일단 스킵하거나 mock으로 대체 가능

# 4. 환경 변수 설정 예시
echo "🔧 환경 변수 설정 예시 생성..."
cat > .env.example << EOF
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
EOF

echo "✅ 의존성 문제 해결 완료!"
echo "⚠️  주의사항:"
echo "  1. .env.example을 참고하여 실제 .env 파일을 생성하세요"
echo "  2. common_security 패키지는 별도 처리가 필요할 수 있습니다"
echo "  3. 서비스 URL들을 실제 환경에 맞게 수정하세요"