# TerminusDB Native Versioning 마이그레이션 가이드

## 개요
OMS에서 커스텀으로 구현된 버전 관리 기능들을 TerminusDB의 네이티브 기능으로 대체합니다.

## 마이그레이션 매핑

### 1. Version Management
```python
# Before: Custom version tracking
from core.validation.version_manager import VersionManager
vm = VersionManager()
version = vm.create_version("1.2.3", changes)

# After: TerminusDB commits
from database.clients.terminus_db import TerminusDBClient
client = TerminusDBClient()
commit_id = await client.commit(message="Version 1.2.3: changes")
```

### 2. History Tracking
```python
# Before: Custom history service
from core.history.service import HistoryService
history = HistoryService()
changes = history.get_changes(entity_id, start_date, end_date)

# After: TerminusDB history
changes = await client.log(path="schema/entity_id", 
                          since=start_date, 
                          until=end_date)
```

### 3. Diff Operations
```python
# Before: Custom diff generation
from core.versioning.version_service import VersioningService
vs = VersioningService()
diff = vs.generate_diff(old_version, new_version)

# After: TerminusDB diff
diff = await client.diff(commit1, commit2)
```

### 4. Branch Management
```python
# Before: Custom branch operations
from core.branch.models import Branch
branch = Branch.create("feature/new-schema")

# After: TerminusDB branches
await client.branch("feature/new-schema")
await client.checkout("feature/new-schema")
```

### 5. Merge Operations
```python
# Before: Custom merge strategies
from core.branch.merge_strategies import ThreeWayMerge
merger = ThreeWayMerge()
result = merger.merge(branch1, branch2)

# After: TerminusDB merge
await client.merge("feature/new-schema", 
                   message="Merge feature branch")
```

### 6. Time Travel
```python
# Before: Custom snapshot retrieval
from core.history.service import HistoryService
snapshot = history.get_snapshot_at_time(timestamp)

# After: TerminusDB time travel
await client.checkout(commit_id)
# or
data = await client.query_at_commit(query, commit_id)
```

## 제거할 파일들

### 즉시 제거 가능
- `core/validation/version_manager.py` - 완전히 TerminusDB commits로 대체
- `core/versioning/dag_compaction.py` - TerminusDB가 내부적으로 처리
- `core/event_publisher/change_detector.py` - TerminusDB hooks 사용

### 점진적 마이그레이션 필요
- `core/versioning/version_service.py` - 일부 비즈니스 로직 보존 필요
- `core/history/service.py` - UI 관련 기능 일부 유지
- `core/branch/` - 비즈니스 특화 merge 규칙만 유지

## 마이그레이션 단계

### Phase 1: 인터페이스 생성
```python
# shared/versioning/terminus_adapter.py
class TerminusVersioningAdapter:
    """기존 인터페이스를 유지하면서 TerminusDB 사용"""
    
    def create_version(self, version_string, changes):
        # Map to TerminusDB commit
        return self.client.commit(f"v{version_string}: {changes}")
    
    def get_history(self, entity_id):
        # Map to TerminusDB log
        return self.client.log(path=f"schema/{entity_id}")
```

### Phase 2: 서비스별 마이그레이션
1. 테스트 환경에서 adapter 적용
2. 기능 검증
3. 프로덕션 배포
4. 레거시 코드 제거

### Phase 3: 네이티브 API 직접 사용
1. Adapter 제거
2. TerminusDB API 직접 호출
3. 최종 정리

## 주의사항

### 1. 데이터 마이그레이션
- 기존 버전 히스토리를 TerminusDB commits로 변환 필요
- 마이그레이션 스크립트 작성 권장

### 2. API 호환성
- 기존 API 엔드포인트 유지
- 내부 구현만 TerminusDB로 변경

### 3. 비즈니스 로직 보존
- 버전 승인 워크플로우
- 특수한 merge 정책
- 감사 로그 요구사항

## 예상 효과
- **코드 감소**: ~3,900줄 제거
- **복잡도 감소**: 커스텀 DAG 관리 불필요
- **성능 향상**: TerminusDB 최적화 활용
- **신뢰성 향상**: 검증된 버전 관리 시스템 사용