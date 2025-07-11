# 🚀 Arrakis MSA Project - Enterprise Microservices Architecture

> **차세대 온톨로지 관리 플랫폼 - 모놀리스에서 마이크로서비스로**

## 📋 프로젝트 개요

Arrakis Project는 TerminusDB를 기반으로 한 엔터프라이즈급 온톨로지 관리 시스템(OMS)입니다. 모놀리스 아키텍처에서 마이크로서비스 아키텍처로의 점진적 전환을 지원하며, 복잡한 데이터 모델과 관계를 체계적으로 관리합니다.

## ✨ 핵심 기능

### 🎯 온톨로지 관리
- 객체 타입(ObjectType) 정의 및 관리
- 속성(Property) 시스템
- 링크 타입(LinkType) 관계 모델링
- 인터페이스 및 상속 지원

### 🚀 고급 기능 (2024.12 업데이트)
- **🧠 Vector Embeddings**: 7개 AI 프로바이더 지원
- **🔗 GraphQL Deep Linking**: 효율적인 그래프 탐색
- **💾 Redis SmartCache**: 3-tier 지능형 캐싱
- **🔍 Jaeger Tracing**: 분산 시스템 추적
- **⏰ Time Travel Queries**: 시간 기반 데이터 조회
- **📦 Delta Encoding**: 효율적인 버전 저장
- **📄 @unfoldable Documents**: 선택적 콘텐츠 로딩
- **📝 @metadata Frames**: 구조화된 문서 메타데이터

## 🏗️ 마이크로서비스 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Clients   │────▶│    Nginx    │────▶│   API Gateway    │
└─────────────┘     └─────────────┘     └──────────────────┘
                                                   │
                    ┌──────────────────────────────┴────────────────────────┐
                    │                                                        │
         ┌──────────▼──────────┐  ┌──────────────┐  ┌──────────────┐      │
         │    User Service     │  │ Audit Service│  │  OMS Service │      │
         └─────────────────────┘  └──────────────┘  └──────┬───────┘      │
                                                            │              │
         ┌──────────────────────────────────────────────────┴──────────────┘
         │                           Microservices
         │
    ┌────▼────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
    │  Data   │  │  Embedding  │  │  Scheduler  │  │Event Gateway │
    │ Kernel  │  │   Service   │  │   Service   │  │              │
    └────┬────┘  └─────────────┘  └─────────────┘  └──────────────┘
         │
    ┌────▼────────┐     ┌─────────────┐     ┌─────────────┐
    │ TerminusDB  │     │    Redis    │     │  PostgreSQL │
    └─────────────┘     └─────────────┘     └─────────────┘
```

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/ludia8888/Arrakis-Project.git
cd Arrakis-Project
```

### 2. 환경 설정
```bash
cp .env.example .env
# .env 파일에서 JWT_SECRET 등 필수 값 설정
```

### 3. 마이크로서비스 실행
```bash
./start-microservices.sh
```

### 4. 서비스 접속
- **OMS API**: http://localhost:8000
- **API 문서**: http://localhost:8000/api/v1/docs
- **User Service**: http://localhost:8010
- **Audit Service**: http://localhost:8011
- **Data Kernel**: http://localhost:8080
- **GraphQL**: http://localhost:8006/graphql
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686

## 📚 프로젝트 구조

```
Arrakis-Project/
├── user-service/                 # 사용자 인증 서비스
├── audit-service/                # 감사 로깅 서비스
├── data-kernel-service/          # TerminusDB 게이트웨이
├── embedding-service/            # 텍스트 임베딩 서비스
├── scheduler-service/            # 작업 스케줄링 서비스
├── event-gateway/                # 이벤트 라우팅 서비스
├── ontology-management-service/  # OMS 코어 (모놀리스→MSA 전환 중)
├── arrakis-common/               # 공통 라이브러리
├── monitoring/                   # 모니터링 설정
│   ├── prometheus/              # Prometheus 설정
│   ├── grafana/                 # Grafana 대시보드
│   └── alertmanager/            # 알림 설정
├── docker-compose.yml            # 통합 Docker 설정
├── start-microservices.sh        # 시작 스크립트
└── README.md                     # 이 문서
```

## 📖 문서

- **[마이크로서비스 마이그레이션 가이드](MICROSERVICES_MIGRATION_GUIDE.md)**: MSA 전환 가이드
- **[아키텍처 재편 보고서](MICROSERVICES_RESTRUCTURE_REPORT.md)**: 구조 재편 상세
- **[OMS README](ontology-management-service/README.md)**: OMS 상세 구현
- **[확장 아키텍처](ARCHITECTURE_EXTENDED.md)**: 시스템 설계 상세
- **[기능 가이드](FEATURES.md)**: 확장 기능 사용법

## 🛠️ 기술 스택

### 마이크로서비스
- **Python 3.11+**: 메인 언어
- **FastAPI**: REST API 프레임워크
- **gRPC**: 서비스 간 통신
- **Docker & Docker Compose**: 컨테이너화

### 데이터베이스
- **TerminusDB**: 그래프 데이터베이스
- **PostgreSQL**: 관계형 데이터베이스
- **Redis**: 캐시 및 메시지 브로커

### 메시징 & 이벤트
- **NATS**: 이벤트 스트리밍
- **Event Gateway**: 이벤트 라우팅

### 모니터링 & 추적
- **Prometheus**: 메트릭 수집
- **Grafana**: 시각화 대시보드
- **Jaeger**: 분산 추적
- **AlertManager**: 알림 관리

### 보안
- **JWT**: 토큰 기반 인증
- **RBAC**: 역할 기반 접근 제어
- **mTLS**: 상호 TLS 인증

## 🔧 개발 환경 설정

### 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# 주요 환경 변수
JWT_SECRET=your-secure-secret-key
USE_DATA_KERNEL_GATEWAY=true  # 마이크로서비스 모드
USE_EMBEDDING_MS=true
USE_SCHEDULER_MS=true
USE_EVENT_GATEWAY=true
```

### 개발 모드 실행
```bash
# 전체 서비스 실행
docker-compose up -d

# 특정 서비스만 실행
docker-compose up -d oms user-service

# 로그 확인
docker-compose logs -f [service-name]
```

## 🧪 테스트

```bash
# 마이크로서비스 상태 검증
cd ontology-management-service
python verify_microservices.py

# API 테스트
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/config/migration-progress

# 단위 테스트
pytest tests/unit/

# 통합 테스트
pytest tests/integration/
```

## 🤝 기여 방법

1. Fork 저장소
2. Feature 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

## 👥 팀

- **아키텍처 설계**: Claude AI Assistant
- **시스템 구현**: 이시현 (isihyeon)
- **TerminusDB 확장**: Claude & 이시현

## 🔗 관련 링크

- **GitHub**: https://github.com/ludia8888/Arrakis-Project
- **이슈 트래커**: https://github.com/ludia8888/Arrakis-Project/issues
- **위키**: https://github.com/ludia8888/Arrakis-Project/wiki

## 🚀 마이크로서비스 전환 현황

### 완료된 작업
- ✅ 모든 마이크로서비스를 프로젝트 루트로 이동
- ✅ 통합 Docker Compose 구성 완료
- ✅ Prometheus/Grafana 모니터링 통합
- ✅ 점진적 마이그레이션 메커니즘 구현

### 진행 중인 작업
- 🔄 공통 코드를 arrakis-common으로 추출
- 🔄 Kubernetes 배포 준비
- 🔄 API Gateway 통합

---

**Arrakis MSA Project** - *"복잡한 데이터의 사막을 항해하는 나침반"* 🧭

> 이 프로젝트는 Frank Herbert의 Dune 시리즈에서 영감을 받아, 데이터의 광대한 사막(Arrakis)을 효과적으로 관리하고 탐색할 수 있는 도구를 제공합니다. 이제 마이크로서비스 아키텍처로 진화하여 더욱 확장 가능하고 유연한 시스템을 제공합니다.