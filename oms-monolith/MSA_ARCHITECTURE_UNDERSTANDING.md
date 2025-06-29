# OMS MSA 아키텍처 이해

## 🏗️ 현재 MSA 구조

```
┌─────────────────┐         ┌─────────────────┐
│  User Service   │         │  Audit Service  │
│   (IAM 담당)    │         │  (감사 로그)    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ JWT Token                 │ Events
         │                           │
    ┌────▼────────────────────────────▼────┐
    │          OMS Monolith                │
    │  (Ontology Management System)        │
    └──────────────────────────────────────┘
```

## 🔑 User Service (IAM)

User Service가 모든 인증/인가를 담당:
- **JWT 토큰 발급**
- **사용자 인증**
- **권한 관리**
- **역할 기반 접근 제어 (RBAC)**

### OMS에서 유지해야 할 것:
```bash
core/integrations/
├── user_service_client.py    # User Service와 통신
└── iam_service_client.py     # IAM 기능 통합

middleware/
└── auth_msa.py              # JWT 검증 미들웨어
```

### OMS에서 제거해야 할 것:
- 로컬 인증 구현
- 자체 JWT 생성/검증 (User Service에 위임)
- 중복된 권한 관리 코드

## 📊 Audit Service

감사 로그를 담당하는 별도 MSA:
- **모든 API 호출 기록**
- **데이터 변경 이력**
- **보안 이벤트 추적**

## ⚠️ 레거시 정리 시 주의사항

### 1. Auth 관련 코드
```python
# ❌ 제거 대상 (로컬 인증)
def generate_jwt_token(user_id):
    # OMS가 직접 JWT 생성하면 안됨
    pass

# ✅ 유지 대상 (User Service 호출)
async def validate_token(token):
    return await user_service_client.validate_jwt_token(token)
```

### 2. 중복 제거 시 MSA 경계 유지
- OMS는 **Ontology 관리에만 집중**
- 인증은 **User Service에 완전 위임**
- 감사는 **Audit Service에 위임**

### 3. 통합 시 고려사항
```bash
# Before: 각 모듈이 독립적으로 인증
api/graphql/auth.py      → 제거
api/gateway/auth.py      → 제거
core/auth.py            → UserContext만 유지

# After: 중앙화된 MSA 클라이언트
core/integrations/user_service_client.py  # 모든 인증은 여기로
```

## 🎯 정리 우선순위 수정

1. **Validation 통합** (OMS 핵심 기능)
2. **Database Client 통합** (OMS 내부)
3. **Auth 클라이언트 정리** (MSA 경계 명확화)
   - User Service 클라이언트로 통합
   - 로컬 인증 코드 제거
4. **Cache 통합** (OMS 내부)
5. **거대 파일 분할**

## 💡 Best Practices

1. **MSA 경계 존중**
   - 각 서비스의 책임 영역 명확화
   - Cross-service 호출은 클라이언트를 통해서만

2. **중복 제거 시 서비스 경계 확인**
   - OMS 내부 중복만 제거
   - MSA 클라이언트는 유지

3. **환경 변수로 MSA 설정**
   ```env
   USER_SERVICE_URL=https://user-service:8443
   AUDIT_SERVICE_URL=https://audit-service:8444
   JWT_SECRET=shared-secret-with-user-service
   ```

이렇게 MSA 아키텍처를 이해하고 정리하면 더 깔끔한 구조가 될 것입니다!