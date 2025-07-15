#!/bin/bash
# Arrakis Project Initial Setup Script
# 처음 실행 시 필요한 모든 설정을 자동으로 수행

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_status "$BLUE" "🚀 Arrakis Project 초기 설정 시작..."

# 1. Python 가상환경 생성 및 활성화
print_status "$YELLOW" "📦 Python 가상환경 설정..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "$GREEN" "✅ 가상환경 생성 완료"
fi

# 2. 필요한 디렉토리 생성
print_status "$YELLOW" "📁 필요한 디렉토리 생성..."
mkdir -p logs
mkdir -p data
mkdir -p monitoring/prometheus/rules
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/alertmanager

# 3. 공통 패키지 심볼릭 링크 생성
print_status "$YELLOW" "🔗 공통 패키지 링크 생성..."
if [ ! -L "user-service/packages" ]; then
    ln -sf ../packages user-service/packages 2>/dev/null || true
fi
if [ ! -L "audit-service/packages" ]; then
    ln -sf ../packages audit-service/packages 2>/dev/null || true
fi
if [ ! -L "ontology-management-service/packages" ]; then
    ln -sf ../packages ontology-management-service/packages 2>/dev/null || true
fi

# 4. 환경 변수 파일 생성
print_status "$YELLOW" "⚙️  환경 변수 설정..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Arrakis Project Environment Variables
JWT_SECRET=$(openssl rand -hex 32)
POSTGRES_USER=arrakis_user
POSTGRES_PASSWORD=arrakis_password
POSTGRES_DB=arrakis_db
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://arrakis_user:arrakis_password@localhost:5432/arrakis_db
TERMINUSDB_ADMIN_PASS=admin123
LOG_LEVEL=INFO
USE_IAM_VALIDATION=true
ENABLE_TELEMETRY=true
ENABLE_METRICS=true
EOF
    print_status "$GREEN" "✅ .env 파일 생성 완료"
fi

# 5. requirements.txt 파일 수정/생성
print_status "$YELLOW" "📋 의존성 파일 준비..."

# OMS requirements.txt 수정
cat > ontology-management-service/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
redis==5.0.1
httpx==0.25.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.29.0
aiofiles==23.2.1
python-dotenv==1.0.0
prometheus-client==0.19.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation-fastapi==0.42b0
pyyaml==6.0.1
tenacity==8.2.3
boto3==1.29.7
nats-py==2.6.0
cloudevents==1.10.1
strawberry-graphql[fastapi]==0.215.1
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
EOF

# User Service requirements.txt
cat > user-service/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.29.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
redis==5.0.1
httpx==0.25.2
prometheus-client==0.19.0
python-dotenv==1.0.0
EOF

# Audit Service requirements.txt
cat > audit-service/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
asyncpg==0.29.0
redis==5.0.1
httpx==0.25.2
python-jose[cryptography]==3.3.0
nats-py==2.6.0
prometheus-client==0.19.0
python-dotenv==1.0.0
EOF

# 6. 모니터링 설정
print_status "$YELLOW" "📊 모니터링 설정..."
./monitoring/setup.sh

# 7. Docker 관련 파일 수정
print_status "$YELLOW" "🐳 Docker 설정 준비..."

# User Service Dockerfile
cat > user-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Audit Service Dockerfile
cat > audit-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# OMS Dockerfile
cat > ontology-management-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 8. 간단한 메인 파일 생성 (누락된 경우)
print_status "$YELLOW" "📝 메인 애플리케이션 파일 확인..."

# OMS main.py
if [ ! -f "ontology-management-service/api/main.py" ]; then
    mkdir -p ontology-management-service/api
    cat > ontology-management-service/api/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Ontology Management Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ontology-management-service",
        "version": "2.0.0"
    }

@app.get("/api/v1/schemas")
def list_schemas():
    return {"schemas": [], "total": 0}

@app.post("/api/v1/schemas")
def create_schema(schema: dict):
    return {"id": "schema_123", "name": schema.get("name"), "status": "created"}

# Import routes if available
try:
    from api.v1 import schema_routes, time_travel_routes, document_routes
    app.include_router(schema_routes.router, prefix="/api/v1")
    app.include_router(time_travel_routes.router, prefix="/api/v1")
    app.include_router(document_routes.router, prefix="/api/v1")
except ImportError:
    pass
EOF
fi

# User Service main.py
if [ ! -f "user-service/src/main.py" ]; then
    mkdir -p user-service/src
    cat > user-service/src/main.py << 'EOF'
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
import os

app = FastAPI(title="User Service", version="2.0.0")

SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class UserRegister(BaseModel):
    email: str
    password: str
    name: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Mock user storage
users_db = {}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "user-service",
        "version": "2.0.0"
    }

@app.post("/auth/register")
def register(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")

    users_db[user.email] = {
        "email": user.email,
        "password": user.password,  # In production, hash this!
        "name": user.name
    }
    return {"message": "User registered successfully"}

@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        {"sub": user["email"], "exp": datetime.utcnow() + access_token_expires},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {"access_token": access_token, "token_type": "bearer"}
EOF
fi

# Audit Service main.py
if [ ! -f "audit-service/src/main.py" ]; then
    mkdir -p audit-service/src
    cat > audit-service/src/main.py << 'EOF'
from fastapi import FastAPI
from datetime import datetime
from typing import List, Dict

app = FastAPI(title="Audit Service", version="2.0.0")

# Mock audit events storage
audit_events = []

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "audit-service",
        "version": "2.0.0"
    }

@app.post("/api/v1/audit/events")
def create_audit_event(event: Dict):
    event["timestamp"] = datetime.utcnow().isoformat()
    event["id"] = f"event_{len(audit_events) + 1}"
    audit_events.append(event)
    return event

@app.get("/api/v1/audit/events")
def list_audit_events(limit: int = 10) -> List[Dict]:
    return audit_events[-limit:]
EOF
fi

# 9. 데이터베이스 초기화 스크립트
print_status "$YELLOW" "🗄️  데이터베이스 설정..."
cat > init-db.sql << 'EOF'
-- Create databases
CREATE DATABASE IF NOT EXISTS user_service_db;
CREATE DATABASE IF NOT EXISTS audit_db;
CREATE DATABASE IF NOT EXISTS oms_db;
EOF

# 10. 실행 권한 부여
print_status "$YELLOW" "🔐 실행 권한 설정..."
chmod +x start.sh stop.sh test.sh status.sh monitoring/setup.sh

print_status "$GREEN" "✅ 초기 설정 완료!"
print_status "$BLUE" "📋 다음 단계:"
echo "   1. 서비스 시작: ./start.sh"
echo "   2. 상태 확인: ./status.sh"
echo "   3. 테스트 실행: ./test.sh"
echo ""
print_status "$GREEN" "🎉 Arrakis Project 사용 준비 완료!"
