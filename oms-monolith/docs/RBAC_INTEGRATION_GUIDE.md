# RBAC Integration Guide

## 🔐 TerminusDB Native RBAC와 Application RBAC 통합 가이드

### 개요

OMS는 두 가지 레벨의 RBAC를 사용합니다:
1. **TerminusDB Native RBAC** - 데이터베이스 레벨 보안
2. **Application RBAC** - API/비즈니스 로직 레벨 보안

두 시스템은 서로 다른 목적을 가지며 상호보완적으로 작동합니다.

## 1. TerminusDB Native RBAC

### 기능
- 데이터베이스 접근 제어
- Branch 생성/삭제 권한
- 데이터 읽기/쓰기 권한
- 스키마 변경 권한

### 구현 예시
```python
# core/advanced/terminus_advanced.py
async def setup_role_based_access(self, role_config: Dict) -> Dict:
    """역할 기반 접근 제어 설정"""
    
    # 역할 생성
    self.client.create_role("ontology_reader", "Can read ontology data")
    
    # 권한 부여
    self.client.grant_capability(
        "ontology_reader",
        "db:oms/*",  # 리소스
        ["branch", "meta_read", "instance_read"]  # 액션
    )
```

### 사용 가능한 액션
- `branch` - 브랜치 작업
- `meta_read` - 스키마 읽기
- `meta_write` - 스키마 쓰기
- `instance_read` - 데이터 읽기
- `instance_write` - 데이터 쓰기
- `*` - 모든 권한

## 2. Application RBAC

### 기능
- API 엔드포인트 접근 제어
- 비즈니스 로직 권한 확인
- 세밀한 리소스별 권한

### 구현
```python
# middleware/rbac_middleware.py
self.route_permissions = {
    "GET:/api/v1/schemas": (ResourceType.SCHEMA, Action.READ),
    "POST:/api/v1/schemas": (ResourceType.SCHEMA, Action.CREATE),
    # ...
}
```

## 3. 통합 전략

### 현재 상태
- 두 RBAC 시스템이 독립적으로 작동
- Application RBAC가 주요 보안 게이트키퍼 역할
- TerminusDB RBAC는 추가 보안 레이어

### 권장 통합 방법

#### 1단계: 역할 정렬
```python
# 동일한 역할 이름 사용
UNIFIED_ROLES = {
    "ontology_reader": {
        "description": "Read-only access to ontology",
        "terminus_capabilities": ["meta_read", "instance_read"],
        "app_permissions": [
            (ResourceType.SCHEMA, Action.READ),
            (ResourceType.OBJECT_TYPE, Action.READ)
        ]
    },
    "ontology_editor": {
        "description": "Edit ontology structure and data",
        "terminus_capabilities": ["meta_read", "meta_write", "instance_read", "instance_write"],
        "app_permissions": [
            (ResourceType.SCHEMA, Action.ALL),
            (ResourceType.OBJECT_TYPE, Action.ALL)
        ]
    }
}
```

#### 2단계: 통합 미들웨어 생성
```python
class IntegratedRBACMiddleware:
    """TerminusDB와 Application RBAC를 통합"""
    
    async def check_permission(self, user, resource, action):
        # 1. Application 레벨 권한 확인
        if not self.app_checker.check(user, resource, action):
            return False
            
        # 2. TerminusDB 레벨 권한 확인
        db_actions = self.map_to_terminus_actions(action)
        try:
            # 실제 DB 작업 시도 (권한 없으면 예외 발생)
            await self.terminus_client.check_capability(
                user.username,
                f"db:{self.db_name}/*",
                db_actions
            )
            return True
        except PermissionError:
            return False
```

#### 3단계: 역할 동기화
```python
async def sync_roles():
    """Application 역할을 TerminusDB에 동기화"""
    
    for role_name, config in UNIFIED_ROLES.items():
        # TerminusDB에 역할 생성
        await terminus_client.create_role(
            role_name,
            config["description"]
        )
        
        # 권한 부여
        await terminus_client.grant_capability(
            role_name,
            f"db:oms/*",
            config["terminus_capabilities"]
        )
```

## 4. 마이그레이션 계획

### Phase 1: 현재 상태 유지 ✅
- Application RBAC 계속 사용
- TerminusDB RBAC는 보조 역할

### Phase 2: 역할 동기화
- 동일한 역할 이름 사용
- 권한 매핑 테이블 생성

### Phase 3: 통합 테스트
- 두 시스템이 함께 작동하는지 확인
- 권한 불일치 해결

### Phase 4: 점진적 전환
- 중요 작업부터 TerminusDB RBAC 활용
- Application RBAC는 API 레벨에서만 사용

## 5. 장점

### 보안 강화
- 다층 방어 (Defense in Depth)
- DB 직접 접근 시에도 보호

### 감사 추적
- TerminusDB가 모든 접근 기록
- 누가 언제 무엇을 했는지 추적

### 중앙 집중식 관리
- 역할과 권한을 한 곳에서 관리
- 일관성 있는 권한 정책

## 6. 주의사항

1. **역할 이름 일치**: Application과 TerminusDB에서 동일한 역할 이름 사용
2. **권한 매핑**: Application 권한을 TerminusDB 권한으로 정확히 매핑
3. **에러 처리**: TerminusDB 권한 오류를 적절히 처리
4. **성능**: 이중 권한 확인으로 인한 오버헤드 최소화

## 7. 예제: 통합된 권한 확인

```python
@router.post("/api/v1/schemas/{branch}/object-types")
async def create_object_type(
    branch: str,
    user: UserContext = Depends(get_current_user)
):
    # 1. Application RBAC (자동으로 미들웨어에서 확인됨)
    
    # 2. TerminusDB RBAC (실제 작업 시)
    try:
        # TerminusDB가 권한 확인하며 작업 수행
        result = await terminus_client.insert_document(
            {"@type": "ObjectType", ...}
        )
    except PermissionError:
        raise HTTPException(403, "Database permission denied")
        
    return result
```

## 결론

TerminusDB Native RBAC는 강력한 데이터베이스 레벨 보안을 제공합니다. 
기존 Application RBAC와 함께 사용하면 더욱 안전하고 감사 가능한 시스템을 구축할 수 있습니다.