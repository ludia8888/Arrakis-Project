# 🚀 OMS 레거시 코드 정리 액션 플랜

## 🎯 우선순위별 정리 계획

### 🔴 Priority 1: 즉시 정리 (가장 심각한 중복)

#### 1. Validation 통합 (37개 → 1개)
현재 상태:
- 88개 파일에 `validate` 관련 코드 산재
- 37개 파일에 독립적인 validation 구현

액션:
```bash
# 모든 validation을 core/validation/으로 통합
1. core/validation/enterprise_service.py를 메인 진입점으로
2. 각 모듈의 custom validation → core/validation/rules/로 이동
3. 중복 제거 후 import만 변경
```

#### 2. Database Client 통합 (23개 → 1개)
현재 상태:
- 104개 파일이 TerminusDB 사용
- 23개의 독립적인 DB 클라이언트 구현

액션:
```bash
# database/clients/terminus_db.py를 싱글톤으로
1. 모든 DB 연결을 database/clients/terminus_db.py로 통합
2. 각 모듈의 자체 DB 코드 제거
3. get_terminus_client() 함수로 통일
```

### 🟡 Priority 2: 거대 파일 분할

#### 1. api/graphql/resolvers.py (1,800줄)
```bash
api/graphql/
├── resolvers/
│   ├── __init__.py
│   ├── object_type_resolver.py
│   ├── property_resolver.py
│   ├── link_type_resolver.py
│   └── query_resolver.py
```

#### 2. core/api/schema_generator.py (1,025줄)
```bash
core/api/schema_generator/
├── __init__.py
├── base_generator.py
├── object_generator.py
├── property_generator.py
└── relationship_generator.py
```

### 🟢 Priority 3: 구조 개선

#### 1. Auth 클라이언트 정리 (12개 → 2-3개)
⚠️ **중요**: User Service가 실제 IAM 역할을 담당하므로, OMS는 클라이언트만 유지

현재 상태:
- `core/integrations/user_service_client.py` - JWT 검증
- `core/integrations/iam_service_client.py` - IAM 통합
- `middleware/auth_msa.py` - MSA 인증 미들웨어
- 기타 중복된 auth 구현들

액션:
```bash
# User Service 클라이언트만 유지하고 나머지는 제거
core/integrations/
├── user_service_client.py  # User Service와 통신 (유지)
└── iam_service_client.py   # IAM 통합 (유지)

middleware/
├── auth_msa.py            # MSA 인증 미들웨어 (유지)
└── (나머지 auth 관련 파일들 제거)
```

❌ 제거 대상:
- `api/auth_examples.py`
- `api/gateway/auth.py`
- `api/graphql/auth.py`
- `core/auth.py` (UserContext만 유지)
- 기타 로컬 인증 구현들

#### 2. Cache 통합 (6개 → 1개)
```bash
shared/cache/
├── __init__.py
├── cache_manager.py   # 통합 캐시 매니저
├── redis_adapter.py   # Redis 어댑터
└── memory_cache.py    # 메모리 캐시
```

## 📋 단계별 실행 계획

### Week 1: 백업 및 분석
- [ ] 전체 코드베이스 백업
- [ ] 의존성 그래프 생성
- [ ] 사용/미사용 코드 구분

### Week 2: Validation 통합
- [ ] core/validation/rules/ 폴더 구조 생성
- [ ] 각 모듈의 validation 코드 추출
- [ ] 통합 테스트 작성
- [ ] 단계적 마이그레이션

### Week 3: Database Client 통합
- [ ] 싱글톤 패턴 구현
- [ ] Connection pool 설정
- [ ] 각 모듈 마이그레이션
- [ ] 성능 테스트

### Week 4: 거대 파일 분할
- [ ] GraphQL resolvers 분할
- [ ] Schema generator 모듈화
- [ ] Import 경로 업데이트
- [ ] 통합 테스트

## 🛡️ 안전 장치

1. **Feature Flag 사용**
```python
USE_LEGACY_VALIDATION = os.getenv("USE_LEGACY_VALIDATION", "false") == "true"

if USE_LEGACY_VALIDATION:
    # 기존 코드
else:
    # 새 통합 코드
```

2. **단계적 마이그레이션**
- 한 번에 하나의 모듈만 변경
- 각 변경 후 full test suite 실행
- 롤백 계획 준비

3. **모니터링**
- 성능 메트릭 추적
- 에러율 모니터링
- 사용자 피드백 수집

## 📊 예상 결과

### 코드 감소
- Validation: -70% (37개 → 10개 파일)
- DB Clients: -90% (23개 → 3개 파일)
- 전체: -40% 예상

### 성능 개선
- DB 연결 풀 사용으로 50% 빠른 쿼리
- 캐시 통합으로 중복 제거
- 메모리 사용량 30% 감소

### 유지보수성
- 버그 수정 시간 70% 단축
- 새 기능 추가 시간 50% 단축
- 테스트 커버리지 향상

## ⚠️ 리스크 관리

1. **Breaking Changes**
- 모든 API 엔드포인트 문서화
- Deprecation warnings 추가
- 마이그레이션 가이드 제공

2. **Performance Regression**
- 각 단계별 벤치마크
- 부하 테스트 실행
- 롤백 준비

3. **Data Integrity**
- 백업 검증
- 트랜잭션 로그 유지
- 감사 추적

## 🚀 시작하기

1. **팀 합의**
- 우선순위 검토
- 일정 조정
- 역할 분담

2. **환경 준비**
- 테스트 환경 구축
- CI/CD 파이프라인 업데이트
- 모니터링 도구 설정

3. **첫 번째 타겟: Validation 통합**
- 가장 영향이 크고
- 비교적 독립적이며
- 테스트하기 쉬움

이 계획을 따르면 4주 내에 코드베이스가 훨씬 깨끗해질 것입니다!