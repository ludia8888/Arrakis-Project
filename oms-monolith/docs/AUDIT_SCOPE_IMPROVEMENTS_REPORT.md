# Audit & Scope 개선사항 구현 보고서

## 구현 일시
2025-06-26

## Executive Summary

추천 항목 1(Audit 로그 식별자 구조)과 추천 항목 2(Scope-Role 관계 정리)를 반영하여 OMS의 감사 및 권한 시스템을 대폭 개선했습니다.

---

## 추천 항목 1: Audit 로그 식별자 구조 개선

### 구현된 구조화된 ID 패턴
```
audit-{service}:{resource_type}:{resource_id}:{action}:{timestamp}:{uuid}
```

### 실제 예시
```
audit-oms:object_type:user:create:20250626T100000Z:550e8400-e29b-41d4-a716-446655440000
```

### 구성 요소별 설명

| 구성 요소 | 설명 | 예시 | 용도 |
|-----------|------|------|------|
| `audit` | 고정 접두사 | `audit` | 로그 타입 식별 |
| `service` | 서비스 이름 | `oms` | 멀티 서비스 환경에서 구분 |
| `resource_type` | 리소스 타입 | `object_type` | 리소스별 필터링 |
| `resource_id` | 리소스 ID | `user` (정리된 형태) | 특정 리소스 추적 |
| `action` | 수행된 액션 | `create` | 액션별 분석 |
| `timestamp` | 타임스탬프 | `20250626T100000Z` | 시간순 정렬, 시간대별 분석 |
| `uuid` | 고유 식별자 | `550e8400...` | 완전한 고유성 보장 |

### 검색 및 분석 활용

#### 1. 패턴 기반 검색
```python
# 모든 ObjectType 작업
pattern = "audit-oms:object_type:*:*:*:*"

# 모든 생성 작업
pattern = "audit-oms:*:*:create:*:*"

# 특정 날짜의 모든 작업
pattern = "audit-oms:*:*:*:20250626*:*"

# 고위험 작업 (삭제)
pattern = "audit-oms:*:*:delete:*:*"
```

#### 2. 이상 탐지 키 생성
각 audit ID는 다음과 같은 이상 탐지 키를 자동 생성합니다:
- `object_type:create` (리소스-액션 조합)
- `object_type:*` (리소스별 빈도)
- `*:create` (액션별 빈도)
- `object_type:create:20250626T10` (시간대별 패턴)
- `object_type:user:create` (특정 리소스 패턴)

#### 3. 시계열 분석
타임스탬프 형식(`YYYYMMDDTHHMMSSZ`)으로 다음 분석이 가능합니다:
- 시간대별 활동 패턴
- 일일/주별/월별 트렌드
- 피크 시간 식별
- 비정상적인 시간대 활동 탐지

### 구현된 주요 기능

#### AuditIDGenerator 클래스
- **구조화된 ID 생성**: 일관된 형식으로 ID 생성
- **특수 문자 처리**: 리소스 ID의 특수문자 정리
- **길이 제한**: 긴 ID를 50자로 제한하고 "..." 추가
- **ID 파싱**: 구조화된 ID를 다시 구성 요소로 분해
- **검색 패턴 생성**: 로그 시스템용 와일드카드 패턴

#### AuditIDPatterns 클래스
- **일반적인 패턴**: 자주 사용되는 검색 패턴 제공
- **고위험 작업 패턴**: 삭제, 복원, 승인 등
- **관리자 작업 패턴**: 시스템 수준 작업

---

## 추천 항목 2: Scope-Role 관계 정리

### 체계적인 Scope-Role 매핑 테이블

| Role | Scope Prefix | 필수 Scope | 선택 Scope | 접근 수준 |
|------|-------------|-------------|------------|----------|
| **admin** | `api:*:admin`, `api:system:*` | `api:system:admin` | 없음 | 전체 시스템 접근 |
| **developer** | `api:*:write` | `api:ontologies:read`, `api:schemas:read`, `api:branches:read` | `api:ontologies:write`, `api:schemas:write`, `api:branches:write` | 개발 작업 |
| **reviewer** | `api:*:read`, `api:proposals:approve` | `api:proposals:read`, `api:proposals:approve` | `api:ontologies:read`, `api:audit:read` | 검토 및 승인 |
| **viewer** | `api:*:read` | 없음 | 모든 `:read` scope | 읽기 전용 |
| **service_account** | `api:service:*`, `api:webhook:*` | `api:service:account` | `api:webhook:execute` | 서비스 통합 |

### Scope 계층 구조

```
api:system:admin (최상위)
├── api:ontologies:admin
│   ├── api:ontologies:write
│   │   └── api:ontologies:read
│   └── api:schemas:write
│       └── api:schemas:read
├── api:proposals:approve
│   └── api:proposals:read
└── api:audit:read

독립적 계층:
├── api:branches:write
│   └── api:branches:read
├── api:webhook:execute
└── api:service:account
```

### 실제 사용 예시

#### 1. Admin User JWT
```json
{
  "sub": "admin-001",
  "iss": "iam.company",
  "aud": "oms", 
  "scope": "api:system:admin",
  "roles": ["admin"],
  "exp": 1640995200
}
```

#### 2. Developer User JWT
```json
{
  "sub": "dev-001",
  "iss": "iam.company", 
  "aud": "oms",
  "scope": "api:ontologies:write api:schemas:read api:branches:write api:proposals:write",
  "roles": ["developer"],
  "exp": 1640995200
}
```

#### 3. Reviewer User JWT
```json
{
  "sub": "reviewer-001",
  "iss": "iam.company",
  "aud": "oms", 
  "scope": "api:ontologies:read api:proposals:approve api:audit:read",
  "roles": ["reviewer"],
  "exp": 1640995200
}
```

### 구현된 검증 로직

#### ScopeRoleMatrix 클래스
- **역할 자동 할당**: Scope 조합에 따른 자동 역할 결정
- **역할 검증**: 할당된 역할이 보유 scope와 일치하는지 확인
- **계층 구조 지원**: 상위 scope가 하위 scope를 포함하는 로직
- **패턴 매칭**: 정규식 기반 동적 scope 매칭

#### 검증 예시
```python
# 올바른 역할 할당
is_valid, issues = ScopeRoleMatrix.validate_role_scope_assignment(
    Role.REVIEWER,
    ["api:proposals:read", "api:proposals:approve"]
)
# is_valid = True, issues = []

# 잘못된 역할 할당
is_valid, issues = ScopeRoleMatrix.validate_role_scope_assignment(
    Role.REVIEWER,
    ["api:ontologies:read"]  # 필수 scope 누락
)
# is_valid = False, issues = ["Missing required scopes..."]
```

---

## 3. 통합 효과

### 감사 추적 개선
1. **정확한 로그 식별**: 구조화된 ID로 빠른 검색
2. **패턴 분석**: 사용자별, 리소스별, 시간별 패턴 분석
3. **이상 탐지**: 자동화된 이상 행동 탐지

### 권한 관리 개선
1. **명확한 매핑**: Scope와 Role 간 명확한 관계
2. **자동 검증**: 권한 할당의 일관성 자동 확인
3. **계층적 권한**: 상속 관계를 통한 효율적 권한 관리

### 운영 효율성
1. **빠른 문제 해결**: 구조화된 ID로 신속한 로그 검색
2. **컴플라이언스**: 체계적인 감사 추적
3. **확장성**: 새로운 리소스/액션 쉽게 추가 가능

---

## 4. 실제 사용 시나리오

### 시나리오 1: 보안 사고 조사
```bash
# 특정 사용자의 삭제 작업 조회
search_pattern = "audit-oms:*:*:delete:*:*"
grep "user-123" audit_logs | grep "delete"

# 특정 시간대 의심 활동 조회
search_pattern = "audit-oms:*:*:*:20250626T02*:*"  # 새벽 2시대
```

### 시나리오 2: 권한 검토
```python
# 사용자의 실제 권한과 할당된 역할 검증
user_scopes = ["api:ontologies:write", "api:schemas:read"]
assigned_role = Role.DEVELOPER

is_valid, issues = ScopeRoleMatrix.validate_role_scope_assignment(
    assigned_role, user_scopes
)
```

### 시나리오 3: 이상 탐지
```python
# 특정 리소스에 대한 비정상적인 접근 패턴
audit_id = "audit-oms:object_type:sensitive_data:read:20250626T030000Z:uuid"
anomaly_keys = AuditIDGenerator.get_anomaly_detection_keys(audit_id)
# 새벽 3시에 민감한 데이터 접근 - 이상 패턴으로 플래그
```

---

## 5. 향후 확장 계획

### 단기 (1-2주)
1. **로그 집계 대시보드**: Grafana 대시보드 구축
2. **알림 시스템**: 고위험 패턴 자동 알림
3. **성능 최적화**: 인덱싱 전략 수립

### 중기 (1-2개월)
1. **ML 기반 이상 탐지**: 사용자 행동 패턴 학습
2. **자동 권한 추천**: 사용 패턴 기반 권한 최적화
3. **컴플라이언스 리포트**: 자동화된 감사 보고서

### 장기 (3-6개월)
1. **예측 분석**: 보안 위험 예측 모델
2. **동적 권한 조정**: 실시간 권한 조정
3. **연합 감사**: 다중 서비스 통합 감사

---

## 6. 결론

구조화된 Audit ID와 체계적인 Scope-Role 매핑을 통해 OMS의 감사 및 권한 시스템이 엔터프라이즈급으로 업그레이드되었습니다.

**주요 이점:**
- 🔍 **빠른 검색**: 구조화된 ID로 즉시 로그 검색
- 📊 **패턴 분석**: 자동화된 이상 탐지 및 트렌드 분석  
- 🔐 **명확한 권한**: Scope-Role 매핑으로 권한 투명성
- 📈 **확장성**: 새로운 리소스/권한 쉽게 추가
- ✅ **컴플라이언스**: 감사 요구사항 완벽 충족

이제 OMS는 대규모 엔터프라이즈 환경에서도 안전하고 효율적으로 운영할 수 있는 기반을 갖추었습니다.

---

*구현 완료: 2025-06-26*  
*검토자: Claude Code*