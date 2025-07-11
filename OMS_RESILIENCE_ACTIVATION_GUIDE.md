# OMS 복원력 메커니즘 활성화 가이드

## 1. E-Tag 캐싱 활성화

### 1.1 미들웨어 등록 확인

`bootstrap/app.py`에서 ETag 미들웨어가 등록되어 있는지 확인:

```python
from middleware.etag_middleware import ETagMiddleware

# 미들웨어 추가
app.add_middleware(ETagMiddleware)
```

### 1.2 라우트에 E-Tag 데코레이터 적용

`api/v1/schema_routes.py` 예시:

```python
from middleware.etag_middleware import enable_etag

@router.get("/{branch}/object-types")
@enable_etag(
    resource_type_func=lambda p: "object-types",
    resource_id_func=lambda p: f"{p.get('branch')}/all",
    branch_func=lambda p: p.get("branch", "main")
)
async def get_object_types(
    branch: str = Path(..., description="Branch name"),
    request: Request = None,
    user_context: UserContext = Depends(get_current_user)
):
    # 기존 로직...
```

### 1.3 특정 리소스에 대한 E-Tag 적용

```python
@router.get("/{branch}/object-types/{object_type_id}")
@enable_etag(
    resource_type_func=lambda p: "object-type",
    resource_id_func=lambda p: p.get("object_type_id"),
    branch_func=lambda p: p.get("branch", "main")
)
async def get_object_type(
    branch: str,
    object_type_id: str,
    request: Request = None,
    user_context: UserContext = Depends(get_current_user)
):
    # 기존 로직...
```

## 2. 서킷 브레이커 튜닝

### 2.1 환경변수 설정

`.env` 파일:

```bash
# 서킷 브레이커 설정
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5      # 실패 임계값 (기본: 5)
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3      # 복구 성공 임계값 (기본: 3)
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60       # 타임아웃 (기본: 60초)
CIRCUIT_BREAKER_ERROR_RATE_THRESHOLD=0.3 # 에러율 임계값 (기본: 0.5)
```

### 2.2 서킷 브레이커 설정 코드

`bootstrap/config.py`:

```python
class CircuitBreakerConfig:
    failure_threshold: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    success_threshold: int = int(os.getenv("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "3"))
    timeout_seconds: float = float(os.getenv("CIRCUIT_BREAKER_TIMEOUT_SECONDS", "60"))
    error_rate_threshold: float = float(os.getenv("CIRCUIT_BREAKER_ERROR_RATE_THRESHOLD", "0.3"))
```

### 2.3 특정 서비스에 서킷 브레이커 적용

```python
from middleware.circuit_breaker import circuit_breaker

@circuit_breaker(
    name="terminus_db",
    failure_threshold=3,  # TerminusDB는 더 민감하게
    error_rate_threshold=0.2
)
async def query_terminus_db(query: str):
    # TerminusDB 쿼리 로직
    pass
```

## 3. Redis 캐싱 최적화

### 3.1 캐시 키 전략

```python
# shared/cache/cache_keys.py
class CacheKeys:
    @staticmethod
    def schema_list(branch: str) -> str:
        return f"cache:schema:list:{branch}"
    
    @staticmethod
    def schema_detail(branch: str, schema_id: str) -> str:
        return f"cache:schema:detail:{branch}:{schema_id}"
    
    @staticmethod
    def user_permissions(user_id: str) -> str:
        return f"cache:permissions:{user_id}"
```

### 3.2 캐시 사용 예시

```python
from shared.cache.smart_cache import SmartCache

cache = SmartCache()

# 캐시 조회
cached_data = await cache.get(
    CacheKeys.schema_list(branch),
    tier="redis"  # 특정 계층 지정
)

if not cached_data:
    # 데이터 조회
    data = await fetch_schemas_from_db(branch)
    
    # 캐시 저장 (TTL: 5분)
    await cache.set(
        CacheKeys.schema_list(branch),
        data,
        ttl=300
    )
```

### 3.3 캐시 무효화

```python
# 스키마 업데이트 시 캐시 무효화
async def update_schema(branch: str, schema_id: str, data: dict):
    # 업데이트 로직
    result = await db.update_schema(branch, schema_id, data)
    
    # 관련 캐시 무효화
    await cache.delete(CacheKeys.schema_detail(branch, schema_id))
    await cache.delete(CacheKeys.schema_list(branch))
    
    return result
```

## 4. 백프레셔 설정

### 4.1 환경변수

```bash
# 백프레셔 설정
BACKPRESSURE_ENABLED=true
BACKPRESSURE_MAX_QUEUE_SIZE=1000
BACKPRESSURE_MAX_CONCURRENT=100
```

### 4.2 API 레벨 백프레셔

```python
from middleware.circuit_breaker import BackpressureHandler

backpressure = BackpressureHandler(max_queue_size=1000)

@router.post("/heavy-operation")
async def heavy_operation(
    request: Request,
    user_context: UserContext = Depends(get_current_user)
):
    # 백프레셔 체크
    if not backpressure.can_accept_request("heavy_operation", threshold=50):
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable due to high load"
        )
    
    request_id = str(uuid.uuid4())
    backpressure.enqueue_request("heavy_operation", request_id)
    
    try:
        backpressure.start_processing("heavy_operation", request_id)
        # 무거운 작업 수행
        result = await perform_heavy_operation()
        return result
    finally:
        backpressure.finish_processing("heavy_operation")
```

## 5. 모니터링 설정

### 5.1 Prometheus 메트릭 엔드포인트

`api/monitoring/metrics.py`:

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@router.get("/metrics")
async def get_metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 5.2 Grafana 대시보드 쿼리 예시

```promql
# 서킷 브레이커 상태
circuit_breaker_state{service="oms"} 

# 캐시 히트율
rate(cache_hits_total[5m]) / rate(cache_requests_total[5m])

# E-Tag 효율성
etag_cache_effectiveness_ratio{resource_type="schema"}

# 백프레셔 큐 크기
backpressure_queue_size{circuit_name="heavy_operation"}
```

## 6. 테스트 방법

### 6.1 E-Tag 테스트

```bash
# 첫 요청 (E-Tag 생성)
curl -i -H "Authorization: Bearer $TOKEN" \
  http://localhost:8091/api/v1/schemas/main/object-types

# 응답에서 ETag 헤더 확인
# ETag: "686897696a7c876b7e"

# 조건부 요청 (캐시 히트 예상)
curl -i -H "Authorization: Bearer $TOKEN" \
  -H "If-None-Match: \"686897696a7c876b7e\"" \
  http://localhost:8091/api/v1/schemas/main/object-types

# 304 Not Modified 응답 확인
```

### 6.2 서킷 브레이커 테스트

```python
# 부하 테스트 스크립트
import asyncio
import httpx

async def load_test():
    async with httpx.AsyncClient() as client:
        # 의도적으로 실패하는 요청 생성
        tasks = []
        for i in range(20):
            task = client.get(
                "http://localhost:8091/api/v1/invalid-endpoint",
                timeout=1.0  # 짧은 타임아웃
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 서킷이 열렸는지 확인
        errors = sum(1 for r in results if isinstance(r, Exception))
        print(f"Errors: {errors}/20")
        
        # 서킷이 열린 후 빠른 실패 확인
        resp = await client.get("http://localhost:8091/api/v1/schemas/main/object-types")
        print(f"Circuit state response: {resp.status_code}")

asyncio.run(load_test())
```

## 7. 프로덕션 체크리스트

- [ ] E-Tag 미들웨어 활성화 및 주요 읽기 엔드포인트에 적용
- [ ] 서킷 브레이커 임계값을 환경별로 조정
- [ ] Redis 연결 풀 크기 최적화
- [ ] 백프레셔 임계값 설정
- [ ] Prometheus 메트릭 수집 확인
- [ ] Grafana 대시보드 구성
- [ ] 알림 규칙 설정 (서킷 열림, 캐시 히트율 저하 등)
- [ ] 부하 테스트 수행
- [ ] 장애 복구 시나리오 테스트

## 8. 모범 사례

1. **점진적 활성화**
   - 한 번에 모든 기능을 켜지 말고 단계적으로 활성화
   - 각 단계에서 메트릭 모니터링

2. **환경별 설정**
   - 개발: 느슨한 임계값
   - 스테이징: 프로덕션과 유사
   - 프로덕션: 보수적인 임계값

3. **정기적인 검토**
   - 월간 메트릭 리뷰
   - 분기별 임계값 조정
   - 연간 전체 아키텍처 검토