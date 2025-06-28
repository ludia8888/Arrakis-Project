# 레거시 검증 코드 마이그레이션 계획

## 🎯 목표
Boundary Definition 이전에 작성된 레거시 검증 코드를 안전하게 현대화

## 📊 발견된 레거시 코드 현황

### 1. HIGH RISK (즉시 조치)
- **array_element_rule.py** (586줄)
  - 문제: TerminusDB array constraints 미사용
  - 영향: 성능 저하, 중복 검증
  - 조치: Feature flag로 점진적 전환

- **foreign_ref_integrity_rule.py**
  - 문제: 참조 무결성 수동 구현
  - 영향: 데이터베이스 핵심 기능 중복
  - 조치: TerminusDB referential integrity 활용

### 2. MEDIUM RISK (단계적 개선)
- **oms_rules.py** - 타입 체커
- **enum_value_constraint_rule.py** - Enum 검증
- **unified_merge_engine.py** - 일부 중복

### 3. LOW RISK (모니터링)
- WOQL 직접 사용 패턴
- Schema service 이중 검증

## 🛡️ 안전한 마이그레이션 전략

### Phase 1: 탐지 및 로깅 (Week 1-2)
```python
# 레거시 코드에 deprecation 경고 추가
import warnings

class ArrayElementRule(BreakingChangeRule):
    def __init__(self):
        warnings.warn(
            "ArrayElementRule is legacy code. "
            "Consider using TerminusDB native array constraints. "
            "See: core/validation/terminus_boundary_definition.py",
            DeprecationWarning,
            stacklevel=2
        )
        # 사용 통계 수집
        logger.info("LEGACY_VALIDATION_USED", extra={
            "rule": "ArrayElementRule",
            "feature": "array_validation"
        })
```

### Phase 2: 이중 실행 (Week 3-4)
```python
# 새로운 wrapper 생성
class ModernArrayElementRule(BreakingChangeRule):
    def __init__(self, terminus_port, use_legacy=True):
        self.terminus_port = terminus_port
        self.legacy_rule = ArrayElementRule() if use_legacy else None
        
    async def check(self, entity_data, context):
        # 1. TerminusDB 네이티브 검증
        terminus_result = await self._terminus_native_check(entity_data)
        
        # 2. 레거시 검증 (비교용)
        if self.legacy_rule:
            legacy_result = await self.legacy_rule.check(entity_data, context)
            
            # 3. 결과 비교 및 로깅
            if terminus_result != legacy_result:
                logger.warning("VALIDATION_MISMATCH", extra={
                    "terminus": terminus_result,
                    "legacy": legacy_result
                })
        
        return terminus_result
```

### Phase 3: Feature Flag 전환 (Week 5-6)
```python
# ValidationConfig에 추가
class ValidationConfig:
    # 레거시 호환성 플래그
    use_legacy_array_validation: bool = field(
        default_factory=lambda: os.getenv("USE_LEGACY_ARRAY_VALIDATION", "true").lower() == "true"
    )
    use_legacy_ref_integrity: bool = field(
        default_factory=lambda: os.getenv("USE_LEGACY_REF_INTEGRITY", "true").lower() == "true"
    )
```

### Phase 4: 점진적 비활성화 (Week 7-8)
1. 특정 엔티티부터 레거시 비활성화
2. 성능/정확성 모니터링
3. 문제 없으면 확대 적용

### Phase 5: 레거시 제거 (Week 9-10)
1. 충분한 테스트 후 레거시 코드 제거
2. 문서화 및 팀 교육

## 📈 모니터링 메트릭

```python
# Prometheus 메트릭 추가
legacy_validation_usage = Counter(
    'legacy_validation_usage_total',
    'Legacy validation rule usage',
    ['rule_name', 'entity_type']
)

validation_mismatch_count = Counter(
    'validation_mismatch_total', 
    'Mismatches between legacy and modern validation',
    ['rule_name', 'mismatch_type']
)

validation_performance = Histogram(
    'validation_duration_seconds',
    'Validation execution time',
    ['validation_type', 'rule_name']
)
```

## ⚠️ 위험 관리

### 롤백 계획
- Feature flag로 즉시 레거시 모드 전환 가능
- 각 Phase마다 체크포인트 설정
- 데이터 무결성 검증 스크립트 준비

### 테스트 전략
1. 단위 테스트: 레거시/모던 결과 비교
2. 통합 테스트: 실제 TerminusDB 연동
3. 성능 테스트: 개선 효과 측정
4. A/B 테스트: 일부 사용자만 모던 버전

## 🎯 예상 효과

- **성능**: 30-50% 검증 시간 단축
- **유지보수**: 586줄 → 50줄 (90% 코드 감소)
- **정확성**: TerminusDB 네이티브 기능 활용
- **일관성**: Boundary Definition 준수

## 📅 타임라인

- Week 1-2: 탐지 및 로깅
- Week 3-4: 이중 실행
- Week 5-6: Feature Flag 전환
- Week 7-8: 점진적 비활성화
- Week 9-10: 레거시 제거
- Week 11-12: 문서화 및 완료

**총 소요 시간**: 12주 (3개월)
**리스크**: LOW (점진적 접근)