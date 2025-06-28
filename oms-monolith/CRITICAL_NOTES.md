# 🚨 Ontology Management System - 중요 참고사항

**⚠️ 주의: 메인 문서(ONTOLOGY_MANAGEMENT_SYSTEM_GUIDE.md)와 실제 구현 사이에 중요한 차이점들이 있습니다.**

## 1. 실제 구현 상태

### API 엔드포인트
문서에 나온 대부분의 REST API는 **구현되지 않았습니다**. 실제로 작동하는 엔드포인트:

```bash
# Schema 관련 (main.py에 직접 구현)
GET  /api/v1/schemas/{branch}/object-types
POST /api/v1/schemas/{branch}/object-types

# 실제로 존재하는 라우터들
/api/v1/audit/*          # 감사 로그
/api/v1/batch/*          # 배치 작업
/api/v1/branch-lock/*    # 브랜치 잠금
/api/v1/issues/*         # 이슈 트래킹
/api/v1/shadow-index/*   # 섀도우 인덱싱
/api/v1/versions/*       # 버전 관리

# GraphQL (활성화된 경우)
/graphql                 # GraphQL 엔드포인트
/graphql-ws             # WebSocket 구독
```

### 미구현 서비스
`main.py`의 `Services` 클래스를 보면:
```python
self.validation_service = None  # TODO: 구현 필요
self.branch_service = None      # TODO: 구현 필요
self.history_service = None     # TODO: 구현 필요
```

## 2. Entry Points

### main.py (기본)
- 일반적인 용도
- 기본 인증 및 미들웨어

### main_secure.py (보안 강화)
- "생명을 위협하는 6개의 치명적 보안 취약점" 수정 버전
- Circuit Breaker 관리 API 포함
- 60초 시작 타임아웃 보호
- 추가 보안 검증

**프로덕션에서는 `main_secure.py` 사용을 권장합니다.**

## 3. 환경 설정

### 필수 환경 변수
```bash
# 기본 설정
ONTOLOGY_ENVIRONMENT=development
ONTOLOGY_DEBUG=true
ONTOLOGY_SECRET_KEY=your-secret-key  # 필수!
ONTOLOGY_DATABASE_PASSWORD=root      # 필수!

# 인증 모드 선택
USE_MSA_AUTH=false  # true로 설정하면 MSA 인증 사용

# 기능 토글
GRAPHQL_ENABLED=true
ENABLE_ISSUE_TRACKING=true
ENABLE_SHADOW_INDEXING=true
```

## 4. 미들웨어 순서 (중요!)

미들웨어는 **역순**으로 실행됩니다 (LIFO):

1. Authentication (먼저 실행)
2. RBAC
3. Scope-based RBAC
4. Schema Freeze
5. Audit
6. Issue Tracking
7. ETag
8. CORS (마지막 실행)

## 5. 데이터베이스 클라이언트

여러 구현체가 있습니다:
- `SimpleTerminusDBClient` - main.py에서 사용 (권장)
- `TerminusDBClient` - 레거시
- `terminus_db_simple.py` - 간소화 버전

## 6. 포트 사용

Docker Compose 실행 시:
- 8000: 메인 API
- 8090: API Gateway
- 8006: GraphQL HTTP
- 8004: GraphQL WebSocket
- 9090: Prometheus 메트릭

## 7. 실제 작동하는 기능들

### ✅ 구현 완료
- 기본 스키마 조회/생성
- 감사 로깅
- 이슈 트래킹
- 브랜치 잠금
- ETag 캐싱
- 헬스 체크
- 메트릭 수집
- GraphQL (기본 기능)

### ❌ 미구현/부분 구현
- 전체 CRUD API
- 검증 서비스
- 브랜치 머지
- 히스토리 추적
- 마이그레이션
- 일부 이벤트 처리

## 8. 개발 시 주의사항

1. **Mock 데이터 주의**: 일부 API는 실제 DB가 아닌 mock 데이터를 반환할 수 있음
2. **서비스 None 체크**: 서비스 사용 전 반드시 None 체크 필요
3. **DB 연결 문제**: "DB 연결 문제 해결 버전"이라는 주석이 있는 것으로 보아 불안정할 수 있음

## 9. 긴급 연락처

문제 발생 시:
- Slack: #ontology-emergency
- 긴급 전화: (문서화 필요)

## 10. 프로덕션 체크리스트

- [ ] `main_secure.py` 사용
- [ ] 모든 필수 환경 변수 설정
- [ ] 데이터베이스 백업 설정
- [ ] 모니터링 대시보드 확인
- [ ] Circuit Breaker 임계값 조정
- [ ] 로그 레벨 조정 (DEBUG → INFO)

---

**마지막 업데이트**: 2024년 1월
**작성자**: CTO Review
**상태**: 🟡 부분적으로 작동 (프로덕션 준비 안됨)