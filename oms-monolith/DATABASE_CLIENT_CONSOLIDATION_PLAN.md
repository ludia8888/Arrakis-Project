# Database Client 통합 계획

## 현재 상황 분석

### 1. Primary Database Clients (database/clients/)
- `terminus_db.py` - 메인 TerminusDB 클라이언트 (mTLS 지원)
- `redis_ha_client.py` - Redis HA 클라이언트 (Sentinel 지원)
- `http_client.py` - HTTP 기반 클라이언트
- `service_client_base.py` - 서비스 클라이언트 베이스
- `registry.py` - 클라이언트 레지스트리

### 2. Service-Specific Clients
- `core/audit/audit_database.py` - Audit Service 통합
- `core/integrations/iam_service_client.py` - User Service 통합
- `core/integrations/user_service_client.py` - User Service 통합 (중복)
- `shared/issue_tracking/database.py` - SQLite 기반 이슈 트래킹
- `shared/feature_flags/database.py` - Feature flag 저장소

### 3. Cache Implementations
- `shared/cache/cache_manager.py` - TerminusDB 캐시 매니저
- `shared/infrastructure/cache_client.py` - 인프라 캐시 클라이언트

### 4. SDK Duplicates
- `core/sdk/sdk_client.py` - SDK 클라이언트 (중복)
- `sdk/clients/oms_client.py` - SDK 클라이언트 (중복)

## 통합 아키텍처

```
┌─────────────────────────────────────────────┐
│          Database Client Factory            │
├─────────────────────────────────────────────┤
│  Internal Clients        External Clients   │
│  ├─ TerminusDB          ├─ User Service    │
│  ├─ Redis HA            └─ Audit Service   │
│  └─ SQLite                                  │
└─────────────────────────────────────────────┘
```

## 구현 계획

### Phase 1: 통합 인터페이스 정의
```python
# shared/database/interfaces.py
class IDocumentDatabase:
    """Document 기반 데이터베이스 인터페이스"""
    async def create(self, collection: str, document: Dict) -> str
    async def read(self, collection: str, id: str) -> Dict
    async def update(self, collection: str, id: str, document: Dict) -> bool
    async def delete(self, collection: str, id: str) -> bool
    async def query(self, woql: str) -> List[Dict]

class ICacheDatabase:
    """캐시 데이터베이스 인터페이스"""
    async def get(self, key: str) -> Optional[Any]
    async def set(self, key: str, value: Any, ttl: int = None) -> bool
    async def delete(self, key: str) -> bool
    async def exists(self, key: str) -> bool

class IMessageQueue:
    """메시지 큐 인터페이스"""
    async def publish(self, topic: str, message: Dict) -> bool
    async def subscribe(self, topic: str, handler: Callable) -> bool
```

### Phase 2: 통합 클라이언트 팩토리
```python
# shared/database/client_factory.py
class DatabaseClientFactory:
    """모든 데이터베이스 클라이언트의 단일 진입점"""
    
    _instances = {}
    
    @classmethod
    def get_terminus_client(cls) -> IDocumentDatabase:
        """TerminusDB 클라이언트 (싱글톤)"""
        if 'terminus' not in cls._instances:
            cls._instances['terminus'] = TerminusDBClient(
                url=config.TERMINUS_URL,
                key=config.TERMINUS_KEY,
                cert_path=config.TERMINUS_CERT_PATH
            )
        return cls._instances['terminus']
    
    @classmethod
    def get_redis_client(cls) -> ICacheDatabase:
        """Redis HA 클라이언트 (싱글톤)"""
        if 'redis' not in cls._instances:
            cls._instances['redis'] = RedisHAClient(
                sentinels=config.REDIS_SENTINELS,
                master_name=config.REDIS_MASTER
            )
        return cls._instances['redis']
    
    @classmethod
    def get_user_service_client(cls) -> IExternalService:
        """User Service 클라이언트 (MSA 경계 유지)"""
        if 'user_service' not in cls._instances:
            cls._instances['user_service'] = UserServiceClient(
                base_url=config.USER_SERVICE_URL,
                timeout=30
            )
        return cls._instances['user_service']
```

### Phase 3: 제거할 중복 클라이언트들

#### 즉시 제거 가능
1. `core/sdk/sdk_client.py` - `sdk/clients/oms_client.py`와 중복
2. `core/integrations/iam_service_client.py` - `user_service_client.py`와 중복
3. `shared/infrastructure/cache_client.py` - `cache_manager.py`와 중복

#### 통합 후 제거
1. 각 서비스의 자체 DB 연결 코드
2. 중복된 connection pool 구현
3. 개별 retry/error handling 로직

### Phase 4: 마이그레이션 전략

#### Step 1: 새로운 클라이언트 팩토리 생성
```bash
mkdir -p shared/database
touch shared/database/__init__.py
touch shared/database/interfaces.py
touch shared/database/client_factory.py
```

#### Step 2: 서비스별 점진적 마이그레이션
```python
# Before
from database.clients.terminus_db import TerminusDBClient
client = TerminusDBClient()

# After
from shared.database.client_factory import DatabaseClientFactory
client = DatabaseClientFactory.get_terminus_client()
```

#### Step 3: 레거시 클라이언트 제거
- 모든 서비스가 새 팩토리 사용 확인
- 레거시 클라이언트 파일 제거
- import 정리

## TerminusDB 활용 최적화

### 1. 네이티브 기능 활용
- **Branch/Merge**: 버전 관리는 TerminusDB에 위임
- **WOQL**: 복잡한 쿼리는 WOQL 직접 사용
- **Schema Validation**: 구조적 검증은 TerminusDB 스키마로

### 2. 제거할 커스텀 구현
- Custom versioning in database clients
- Manual schema validation in clients
- Custom transaction management

### 3. 유지할 비즈니스 로직
- MSA 간 통신 로직
- 비즈니스 특화 retry 전략
- 서비스별 인증/인가

## 예상 효과

### 코드 감소
- 23개 파일 → 5-6개 핵심 클라이언트
- 중복 코드 40% 감소
- 유지보수 포인트 대폭 감소

### 성능 개선
- Connection pooling 통합으로 리소스 효율화
- 캐시 전략 일원화
- TerminusDB 네이티브 최적화 활용

### 아키텍처 개선
- MSA 경계 명확화
- 의존성 주입 패턴 적용
- 테스트 용이성 향상

## 위험 관리

### 1. 하위 호환성
- 기존 인터페이스 유지
- Deprecation warning 제공
- 점진적 마이그레이션

### 2. 서비스 중단 방지
- Feature flag로 점진적 롤아웃
- 롤백 계획 수립
- 충분한 테스트 커버리지

### 3. 성능 모니터링
- 마이그레이션 전후 성능 비교
- Connection pool 메트릭 모니터링
- Error rate 추적