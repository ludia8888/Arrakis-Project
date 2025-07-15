#!/bin/bash
# Arrakis Project - 통합 테스트 환경 설정 스크립트
# 가상환경 설정 문제 해결

echo "🔧 Arrakis Project - Testing Environment Setup"
echo "============================================="

# 현재 작업 디렉토리 확인
echo "📍 Current directory: $(pwd)"

# 가상환경 활성화
echo "🐍 Activating virtual environment..."
if [ -f "venv_ultimate/bin/activate" ]; then
    source venv_ultimate/bin/activate
    echo "✅ Virtual environment activated: venv_ultimate"
else
    echo "❌ Virtual environment not found, creating new one..."
    python3 -m venv venv_ultimate
    source venv_ultimate/bin/activate
    pip install --upgrade pip
    echo "✅ New virtual environment created and activated"
fi

# Python 경로 확인
echo "🔍 Python path verification:"
echo "   Python executable: $(which python)"
echo "   Python version: $(python --version)"

# 핵심 의존성 설치 확인
echo "📦 Checking core dependencies..."
python -c "
import fastapi, uvicorn, pydantic, httpx
print('✅ Core dependencies verified')
" 2>/dev/null || {
    echo "❌ Installing missing core dependencies..."
    pip install fastapi uvicorn pydantic httpx
}

# 서비스별 Python 경로 설정
echo "🛠️  Setting up service-specific environments..."

# OMS 서비스 설정
cd ontology-management-service
export PYTHONPATH="${PWD}:${PYTHONPATH}"
echo "✅ OMS PYTHONPATH set: $PWD"

# 간단한 import 테스트
python -c "
import sys
sys.path.append('.')
try:
    from api.simple_schema_routes import router
    print('✅ OMS schema routes import successful')
except Exception as e:
    print(f'❌ OMS import failed: {e}')
"

cd ..

# User Service 설정
cd user-service
export PYTHONPATH="${PWD}:${PYTHONPATH}"
echo "✅ User Service PYTHONPATH set: $PWD"

python -c "
import sys
sys.path.append('.')
try:
    import src.main
    print('✅ User Service import successful')
except Exception as e:
    print(f'❌ User Service import failed: {e}')
"

cd ..

# 테스트 실행 함수
test_all_services() {
    echo "🧪 Testing all services..."

    # 서비스 상태 확인
    echo "1. OMS Health Check:"
    curl -s http://localhost:8000/health && echo " ✅" || echo " ❌"

    echo "2. User Service Health Check:"
    curl -s http://localhost:8010/health && echo " ✅" || echo " ❌"

    echo "3. Schema CRUD Test:"
    curl -s http://localhost:8000/api/v1/schemas/ && echo " ✅" || echo " ❌"

    echo "4. User Registration Test:"
    curl -X POST http://localhost:8010/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email":"test@test.com","password":"test123","name":"Test User"}' \
      -s > /dev/null && echo "✅ Registration works" || echo "❌ Registration failed"
}

echo ""
echo "🎯 Environment setup complete!"
echo "📋 Available commands:"
echo "   test_all_services  - Test all service endpoints"
echo "   source venv_ultimate/bin/activate  - Activate virtual environment"
echo ""
echo "🚀 Run 'test_all_services' to verify everything is working"

# 함수를 사용 가능하게 만들기
export -f test_all_services
