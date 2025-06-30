# ADR-013: Ultimate Killer 모듈 폐지 및 다층 Sanitizer 도입

## Status
Accepted

## Context
`core.security.ultimate_killer.py` 모듈은 150개 이상의 복잡한 정규식 패턴을 사용하여 모든 보안 공격을 차단하려는 목적으로 만들어졌습니다. 그러나 다음과 같은 문제점들이 발견되었습니다:

1. **ReDoS (Regular Expression Denial of Service) 취약점**: 복잡한 정규식의 exponential backtracking으로 인한 CPU 과부하
2. **성능 저하**: 모든 입력에 대해 150개 이상의 정규식을 매칭하는 과도한 처리
3. **높은 오탐률**: 과도하게 엄격한 검증으로 정상적인 입력도 차단
4. **유지보수성 저하**: 단일 파일에 모든 패턴이 혼재되어 관리 어려움

## Decision
Ultimate Killer 모듈을 폐지하고 다음의 다층 보안 방어 체계로 대체합니다:

### 1. 3중 보안 레이어
1. **InputSanitizer (PARANOID level)**: 
   - UTF-8 유효성 검증
   - 길이 제한
   - 위험 패턴 검출 (12개 카테고리)
   - 성능 최적화된 정규식 사용

2. **Pydantic Model Validators**:
   - 타입 안전성
   - 필드별 검증 규칙
   - Cross-field validation

3. **UnifiedSecurityMiddleware**:
   - 인증/인가
   - Rate Limiting
   - Circuit Breaking

### 2. 마이그레이션 경로
```python
# Before (ultimate_killer.py)
from core.security.ultimate_killer import get_ultimate_killer
killer = get_ultimate_killer()
is_safe, attacks = killer.kill_all_attacks(input_value, "field_name")

# After (InputSanitizer)
from core.validation.input_sanitization import get_input_sanitizer, SanitizationLevel
sanitizer = get_input_sanitizer()
result = sanitizer.sanitize(input_value, SanitizationLevel.PARANOID)
if not result.is_safe:
    # Handle validation failure
```

### 3. 보안 커버리지 매핑
| Ultimate Killer Pattern | New Implementation |
|------------------------|-------------------|
| SQL Injection (18종) | InputSanitizer + Pydantic + TerminusDB parameterized queries |
| XSS (12종) | InputSanitizer + HTML sanitization |
| Command Injection | InputSanitizer + No subprocess in production |
| Path Traversal | InputSanitizer + Path validation |
| LDAP/JNDI Injection | InputSanitizer + No LDAP usage |
| ReDoS Protection | Performance-tested patterns only |

## Consequences

### Positive
- **성능 개선**: 100ms 이내 처리 보장 (기존 대비 10배 향상)
- **ReDoS 위험 제거**: 모든 패턴 성능 테스트 통과
- **유지보수성 향상**: 계층별 책임 분리
- **오탐률 감소**: 단계별 검증으로 정확도 향상
- **확장성**: 새로운 위협에 대한 규칙 추가 용이

### Negative
- 일부 edge case 공격 패턴이 누락될 가능성
- 기존 코드 마이그레이션 필요

### Mitigations
- 포괄적인 성능 테스트 추가 (`test_input_sanitization_performance.py`)
- CI/CD에 import 차단 규칙 추가
- WAF (Web Application Firewall) 추가 권장
- 정기적인 보안 패턴 업데이트 프로세스

## Implementation Details

### CI/CD Integration
1. **Import Linter**: `.importlinter` 설정에 ultimate_killer 금지 규칙 추가
2. **Pre-commit Hook**: `find_ultimate_killer_imports.py` 스크립트로 import 검출
3. **Performance Tests**: pytest benchmark로 ReDoS 취약점 자동 검증

### Monitoring
- Sanitizer 차단 로그 모니터링 (1분당 100건 초과 시 알람)
- Performance metrics 수집 (P99 < 100ms)
- Attack pattern 탐지율 추적

## References
- OWASP Defense in Depth: https://owasp.org/www-project-top-ten/
- ReDoS Prevention: https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS
- Performance Test Results: tests/security/test_input_sanitization_performance.py