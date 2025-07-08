# OMS (Ontology Management Service) 리팩토링 계획

## 현재 문제점

### 1. 순환 Import 문제
- `core.time_travel.service` ↔ `core.branch.foundry_branch_service`
- 두 서비스가 서로를 직접 참조하여 순환 의존성 발생

### 2. 기타 Import 오류
- `infra.siem.adapter`의 `SIEMAdapter` 누락
- Python 3.9에서 `typing.ParamSpec` 사용 (3.10+ 기능)

### 3. 구조적 문제
- 서비스 간 강한 결합도
- 명확하지 않은 책임 분리

## 리팩토링 방안

### Phase 1: 순환 Import 해결 (긴급)

#### 1.1 인터페이스 분리
```python
# core/interfaces/branch_interface.py
class IBranchService(Protocol):
    async def get_branch_state(self, branch_name: str) -> BranchState: ...
    
# core/interfaces/time_travel_interface.py  
class ITimeTravelService(Protocol):
    async def query_at_time(self, query: TemporalQuery) -> TemporalQueryResult: ...
```

#### 1.2 의존성 주입 패턴 적용
- 생성자에서 직접 import 대신 인터페이스 타입 사용
- 런타임에 실제 구현체 주입

### Phase 2: 모듈 재구성

#### 2.1 공통 모델 분리
```
core/
  models/          # 공통 모델
  interfaces/      # 서비스 인터페이스
  services/        # 구체적 서비스 구현
    branch/
    time_travel/
    versioning/
```

#### 2.2 서비스 레지스트리 도입
- 중앙에서 서비스 인스턴스 관리
- 순환 참조 없이 서비스 간 통신

### Phase 3: Import 오류 수정

#### 3.1 누락된 모듈 처리
- `SIEMAdapter` 구현 또는 제거
- 사용하지 않는 import 정리

#### 3.2 Python 버전 호환성
- `typing_extensions` 사용으로 하위 호환성 확보

## 실행 계획

### 즉시 실행 (Phase 1)
1. 인터페이스 파일 생성
2. 서비스 클래스를 인터페이스 사용하도록 수정
3. 앱 초기화 시 의존성 주입

### 단기 계획 (Phase 2)
1. 모델 클래스 재배치
2. 서비스 레지스트리 구현
3. 각 서비스 리팩토링

### 장기 계획 (Phase 3)
1. 전체 코드베이스 import 정리
2. 타입 힌트 개선
3. 테스트 케이스 추가

## 예상 효과
- 서비스 즉시 실행 가능
- 유지보수성 향상
- 테스트 용이성 증가
- 확장성 개선