# 미들웨어 개선 권장사항

## 의존성 분석 결과 요약

### 1. 발견된 문제점

#### 순서 위반
1. **AuditLogMiddleware ← RequestIdMiddleware**
   - `AuditLogMiddleware`가 `request_id`를 필요로 하지만 `RequestIdMiddleware`가 나중에 실행됨
   - **해결책**: `RequestIdMiddleware`를 `AuditLogMiddleware` 앞으로 이동

2. **ScopeRBACMiddleware ← AuthMiddleware**
   - `ScopeRBACMiddleware`가 `user`를 필요로 하지만 `AuthMiddleware`가 나중에 실행됨
   - **해결책**: `AuthMiddleware`를 `ScopeRBACMiddleware` 앞으로 이동

#### user_context 제공자 부재
- 다음 미들웨어들이 `user_context`를 필요로 함:
  - `RateLimitingMiddleware`
  - `EventStateStoreMiddleware`
  - `AuditLogMiddleware`
- 현재 `user_context`를 제공하는 미들웨어가 없음
- **해결책**: `AuthMiddleware`에서 `user_context` 제공하도록 수정

### 2. 권장 미들웨어 실행 순서

```python
# bootstrap/app.py에서 권장하는 순서 (역순으로 추가)
app.add_middleware(GlobalCircuitBreakerMiddleware)  # 1. 최상위 보호
app.add_middleware(ErrorHandlerMiddleware)          # 2. 에러 처리
app.add_middleware(CORSMiddleware)                  # 3. CORS 처리
app.add_middleware(ETagMiddleware)                  # 4. 캐싱
app.add_middleware(RequestIdMiddleware)             # 5. 요청 ID 생성 (먼저 실행)
app.add_middleware(AuthMiddleware)                  # 6. 인증 (user_context 제공)
app.add_middleware(TerminusContextMiddleware)       # 7. DB 컨텍스트
app.add_middleware(CoreDatabaseContextMiddleware)   # 8. PostgreSQL 컨텍스트
app.add_middleware(ScopeRBACMiddleware)            # 9. 권한 확인 (user 필요)
app.add_middleware(AuditLogMiddleware)             # 10. 감사 로깅 (request_id, user_context 필요)
app.add_middleware(RateLimitingMiddleware)         # 11. 요청 제한 (user_context 필요)
app.add_middleware(SchemaFreezeMiddleware)         # 12. 스키마 잠금
app.add_middleware(ThreeWayMergeMiddleware)        # 13. 병합 처리
app.add_middleware(EventStateStoreMiddleware)      # 14. 이벤트 저장 (user_context 필요)
app.add_middleware(IssueTrackingMiddleware)        # 15. 이슈 추적
app.add_middleware(ComponentMiddleware)            # 16. 컴포넌트 관리
```

### 3. 코드 수정 사항

#### AuthMiddleware 수정
```python
# middleware/auth_middleware.py
async def dispatch(self, request: Request, call_next):
    # ... 기존 코드 ...
    
    # user_context 제공 추가
    if user:
        request.state.user_context = UserContext(
            user_id=user.id,
            username=user.username,
            roles=user.roles,
            permissions=user.permissions
        )
    
    # ... 나머지 코드 ...
```

#### ScopeRBACMiddleware 순환 의존성 제거
```python
# core/iam/scope_rbac_middleware.py
# permissions를 requires와 provides 모두에서 사용하는 문제 해결
# provides에서만 permissions 설정하도록 수정
```

### 4. 의존성 자동 테스트 통합

```python
# tests/test_middleware_dependencies.py
import pytest
from test_middleware_dependency_simple import SimpleMiddlewareDependencyAnalyzer

def test_middleware_order_is_valid():
    """미들웨어 순서가 의존성을 만족하는지 테스트"""
    analyzer = SimpleMiddlewareDependencyAnalyzer()
    # ... 분석 실행 ...
    validation = analyzer.validate_current_order(current_order)
    
    assert validation["valid"], f"미들웨어 순서 위반: {validation['violations']}"
    assert len(validation["cycles"]) == 0, f"순환 의존성 발견: {validation['cycles']}"
```

### 5. CI/CD 통합

```yaml
# .github/workflows/middleware-check.yml
name: Middleware Dependency Check

on: [push, pull_request]

jobs:
  check-middleware:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
    - name: Run middleware dependency check
      run: |
        python test_middleware_dependency_simple.py
        if [ $? -ne 0 ]; then
          echo "미들웨어 의존성 문제 발견!"
          exit 1
        fi
```

### 6. 문서화 개선

각 미들웨어 파일 상단에 의존성 명시:
```python
"""
RequestIdMiddleware
===================

제공: request.state.request_id
필요: 없음
헤더: X-Request-Id (읽기/쓰기)

설명: 모든 요청에 고유 ID를 할당하여 추적 가능하게 함
"""
```

### 7. 미들웨어 등록 헬퍼 함수

```python
# bootstrap/middleware_registry.py
from typing import List, Tuple

def get_middleware_order() -> List[Tuple[type, dict]]:
    """
    의존성 순서가 검증된 미들웨어 목록 반환
    Returns: [(MiddlewareClass, kwargs), ...]
    """
    return [
        (GlobalCircuitBreakerMiddleware, {"config": circuit_config}),
        (ErrorHandlerMiddleware, {}),
        # ... 순서대로 나열 ...
    ]

# bootstrap/app.py에서 사용
for middleware_class, kwargs in reversed(get_middleware_order()):
    app.add_middleware(middleware_class, **kwargs)
```

## 결론

이러한 개선사항을 적용하면:
1. **미들웨어 의존성 충돌 방지**
2. **자동화된 순서 검증**
3. **명확한 문서화로 협업 개선**
4. **CI/CD 통합으로 품질 보증**

모든 개발자가 미들웨어를 추가하거나 수정할 때 의존성을 쉽게 이해하고 검증할 수 있게 됩니다.