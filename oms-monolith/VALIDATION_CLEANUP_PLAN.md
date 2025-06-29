# Validation 정리 계획

## 현황
- 총 37개의 validation 관련 파일
- TerminusDB가 대체 가능한 구조적 validation과 유지해야 할 비즈니스 룰 validation이 혼재

## 정리 방향

### 1. TerminusDB로 대체 가능한 것들 (제거 대상)
- `core/validation/schema_validator.py` - JSON Schema validation
- `scripts/check_schema_completeness.py` - Schema 완전성 검증
- `scripts/check_enum_compatibility.py` - Enum 호환성 검증
- `core/validation/rules/terminus_redundant_check.py` - 중복 검증

### 2. 반드시 유지해야 할 비즈니스 룰 (통합 대상)
```
core/validation/
├── business_rules/
│   ├── merge_validation.py (from merge_validation_service.py)
│   ├── semantic_validation.py (from semantic_validator.py)
│   └── enterprise_rules.py (from enterprise_validation.py)
├── auth/
│   └── permission_validator.py (from resource_permission_checker.py)
└── system/
    ├── health_checks.py (from health_checker.py)
    └── production_readiness.py (from production_readiness_check.py)
```

### 3. 제거할 유틸리티 스크립트
- 모든 migration/cleanup 스크립트 (10개)
- 테스트 스크립트들은 별도 정리

## 구현 계획

### Step 1: 비즈니스 룰 백업
```bash
mkdir -p validation_backup
cp -r core/validation validation_backup/
cp -r core/traversal validation_backup/
cp middleware/enterprise_validation.py validation_backup/
```

### Step 2: 새로운 구조 생성
```bash
mkdir -p core/validation/business_rules
mkdir -p core/validation/auth
mkdir -p core/validation/system
```

### Step 3: 비즈니스 룰 통합
1. Merge validation 로직 추출 및 통합
2. Semantic validation 로직 추출 및 통합
3. Enterprise validation 로직 추출 및 통합
4. Permission validation 로직 추출 및 통합

### Step 4: TerminusDB 스키마로 구조적 validation 이전
- Type validation → TerminusDB @type
- Required fields → TerminusDB min_cardinality
- Enum validation → TerminusDB @oneOf
- Foreign key → TerminusDB @link

## 예상 결과
- 37개 파일 → 6-8개 핵심 비즈니스 룰 파일로 축소
- 구조적 validation은 모두 TerminusDB 스키마에 위임
- 비즈니스 룰만 Python 코드로 유지