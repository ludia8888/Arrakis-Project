# 🚨 OMS 레거시 코드 분석 보고서

## 📊 주요 발견사항

### 1. 🗂️ 거대 파일들 (>500 lines)
- **73개 파일**이 500줄 이상
- 최대: `api/graphql/resolvers.py` (1,800줄!)
- 많은 파일이 1,000줄 이상으로 유지보수 어려움

### 2. 🔄 중복 기능 (가장 심각)

#### Validation 중복 (37개 파일!)
```
- analyze_validation_issue.py
- api/v1/validation_routes.py
- core/auth/resource_permission_checker.py
- core/health/health_checker.py
- core/traversal/merge_validator.py
... 32개 더
```
**문제**: 검증 로직이 곳곳에 흩어져 있음

#### Database 클라이언트 중복 (23개 파일!)
```
- database/clients/redis_ha_client.py
- database/clients/terminus_db.py
- core/audit/audit_database.py
- core/integrations/iam_service_client.py
... 19개 더
```
**문제**: 각 모듈이 자체 DB 연결 구현

#### Auth 중복 (12개 파일!)
```
- api/auth_examples.py
- api/gateway/auth.py
- api/graphql/auth.py
- core/auth.py
... 8개 더
```
**문제**: 인증 로직이 여러 곳에 중복

### 3. 🕰️ 레거시 패턴
- **Commented code**: 주석 처리된 코드 방치
- **Old string formatting**: `.format()` 사용 (f-string 대신)
- **Deprecated methods**: 오래된 메서드 사용
- **TODO/FIXME**: 37개의 미해결 주석

### 4. 📁 특히 문제가 되는 폴더들

#### `/shared/models/` vs `/models/`
- `data_types.py`가 **두 곳에 동일하게 존재** (878줄씩!)
- 어느 것이 진짜인지 불명확

#### `/core/` 폴더
- 너무 많은 하위 모듈 (30개+)
- 각 모듈이 독립적으로 DB 연결, 캐시, 검증 구현

## 🎯 즉시 정리가 필요한 것들

### 1. 중복 파일 제거
```bash
# 동일한 파일들
- shared/models/data_types.py vs models/data_types.py
- 여러 validation 구현들
- 중복 DB 클라이언트들
```

### 2. 거대 파일 분할
```bash
# 1000줄 이상 파일들
- api/graphql/resolvers.py (1800줄) → 기능별 분리
- core/api/schema_generator.py (1025줄) → 모듈화
- api/graphql/schema.py (973줄) → 타입별 분리
```

### 3. 통합이 필요한 기능들
```bash
# Validation → core/validation/ 으로 통합
# Database clients → database/clients/ 로 통합  
# Auth → middleware/auth 로 통합
# Cache → shared/cache/ 로 통합
```

## 🛠️ 권장 정리 순서

### Phase 1: 즉시 제거 가능
1. **Commented code** 제거
2. **중복 파일** 제거 (data_types.py 등)
3. **사용하지 않는 test 파일들** 정리

### Phase 2: 통합 작업
1. **Validation** 로직을 core/validation으로 통합
2. **Database clients**를 하나로 통합
3. **Auth** 로직을 middleware로 통합

### Phase 3: 리팩토링
1. **거대 파일들** 분할
2. **Old string formatting**을 f-string으로 변경
3. **TODO/FIXME** 해결

## 📈 예상 효과

- **코드 30-40% 감소** 예상
- **유지보수성 대폭 향상**
- **성능 개선** (중복 연결/캐시 제거)
- **버그 감소** (일관된 검증 로직)

## 🚨 위험 요소

1. **data_types.py 중복**: 어느 것이 실제 사용되는지 확인 필요
2. **DB 클라이언트 통합**: 각각 다른 설정을 사용할 수 있음
3. **거대 파일 분할**: 의존성 문제 발생 가능

## 💡 다음 단계

1. **백업 생성** (이미 validation 백업은 있음)
2. **우선순위 설정**: 가장 영향이 큰 중복부터 제거
3. **단계별 진행**: 한 번에 너무 많이 변경하지 않기
4. **테스트 강화**: 각 변경 후 철저한 테스트

가장 시급한 것은 **validation 중복 (37개 파일)**과 **data_types.py 중복**입니다!