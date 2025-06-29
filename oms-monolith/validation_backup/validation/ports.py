"""
Validation Service Ports (Interfaces)
의존성 역전을 위한 Port 인터페이스 정의
순환 참조 해결을 위한 핵심 추상화 계층
"""
from typing import Protocol, Any, Dict, List, Optional, runtime_checkable

@runtime_checkable
class CachePort(Protocol):
    """캐시 인터페이스 - 외부 캐시 시스템과의 계약"""
    
    async def get(self, key: str) -> Any:
        """캐시에서 값 조회"""
        ...
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값 저장"""
        ...
    
    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        ...
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        ...

@runtime_checkable
class TerminusPort(Protocol):
    """TerminusDB 인터페이스 - 데이터베이스와의 계약"""
    
    async def query(
        self, 
        sparql: str, 
        db: str = "oms", 
        branch: str = "main", 
        **opts
    ) -> List[Dict[str, Any]]:
        """SPARQL 쿼리 실행"""
        ...
    
    async def get_document(
        self, 
        doc_id: str, 
        db: str = "oms", 
        branch: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """문서 조회"""
        ...
    
    async def insert_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """문서 삽입"""
        ...
    
    async def update_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> bool:
        """문서 업데이트"""
        ...
    
    async def health_check(self) -> bool:
        """헬스 체크"""
        ...
    
    async def get_branch_diff(
        self,
        branch: str,
        base_branch: str,
        db: str = "oms"
    ) -> Dict[str, Any]:
        """브랜치 간 차이점 조회"""
        ...
    
    async def get_branch_entities(
        self,
        branch: str,
        db: str = "oms"
    ) -> List[str]:
        """브랜치의 모든 엔티티 조회"""
        ...
    
    async def traverse_graph(
        self,
        start_nodes: List[str],
        relations: List[str],
        max_depth: int = 5,
        branch: str = "main",
        db: str = "oms"
    ) -> Dict[str, Any]:
        """그래프 탐색 수행"""
        ...
    
    # Native TerminusDB validation methods - reduce duplication
    async def validate_schema_changes(
        self,
        schema_changes: Dict[str, Any],
        db: str = "oms",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """TerminusDB 내장 스키마 검증 사용"""
        ...
    
    async def detect_circular_dependencies(
        self,
        db: str = "oms",
        branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """TerminusDB path() 쿼리로 순환 의존성 탐지"""
        ...
    
    async def detect_merge_conflicts(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: str = "main",
        db: str = "oms"
    ) -> List[Dict[str, Any]]:
        """TerminusDB 내장 머지 충돌 탐지"""
        ...

@runtime_checkable
class EventPort(Protocol):
    """이벤트 발행 인터페이스 - 이벤트 시스템과의 계약"""
    
    async def publish(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        correlation_id: Optional[str] = None
    ) -> None:
        """이벤트 발행"""
        ...
    
    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        """배치 이벤트 발행"""
        ...

@runtime_checkable  
class PolicyServerPort(Protocol):
    """외부 정책 서버 인터페이스 - 기업 정책 검증과의 계약"""
    
    async def validate_policy(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """정책 검증 요청"""
        ...
    
    async def get_policies(
        self,
        entity_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """정책 목록 조회"""
        ...
    
    async def health_check(self) -> bool:
        """정책 서버 헬스 체크"""
        ...

@runtime_checkable
class RuleLoaderPort(Protocol):
    """동적 규칙 로더 인터페이스 - 플러그인 시스템과의 계약"""
    
    async def load_rules(
        self,
        rule_type: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Any]:
        """규칙 동적 로딩"""
        ...
    
    async def reload_rules(self) -> None:
        """규칙 재로딩"""
        ...
    
    def get_available_rules(self) -> List[Dict[str, Any]]:
        """사용 가능한 규칙 정보 조회"""
        ...

class ValidationContext:
    """
    검증 컨텍스트 - 규칙 실행에 필요한 모든 정보를 담는 컨테이너
    의존성 주입을 통해 Port 구현체들을 전달받음
    """
    
    def __init__(
        self,
        source_branch: str,
        target_branch: str,
        user_id: Optional[str] = None,
        cache: Optional[CachePort] = None,
        terminus_client: Optional[TerminusPort] = None,
        event_publisher: Optional[EventPort] = None,
        policy_server: Optional[PolicyServerPort] = None,
        rule_loader: Optional[RuleLoaderPort] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.user_id = user_id
        self.cache = cache
        self.terminus_client = terminus_client
        self.event_publisher = event_publisher
        self.policy_server = policy_server
        self.rule_loader = rule_loader
        self.metadata = metadata or {}
        
    def with_metadata(self, **kwargs) -> 'ValidationContext':
        """메타데이터를 추가한 새 컨텍스트 생성"""
        new_metadata = {**self.metadata, **kwargs}
        return ValidationContext(
            source_branch=self.source_branch,
            target_branch=self.target_branch,
            user_id=self.user_id,
            cache=self.cache,
            terminus_client=self.terminus_client,
            event_publisher=self.event_publisher,
            policy_server=self.policy_server,
            rule_loader=self.rule_loader,
            metadata=new_metadata
        )

# Adapter implementations for testing
class InMemoryCacheAdapter:
    """테스트용 인메모리 캐시 어댑터"""
    
    def __init__(self):
        self._storage: Dict[str, Any] = {}
    
    async def get(self, key: str) -> Any:
        return self._storage.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._storage[key] = value
    
    async def delete(self, key: str) -> None:
        self._storage.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        return key in self._storage

class NoOpEventAdapter:
    """테스트용 이벤트 어댑터 (아무것도 하지 않음)"""
    
    async def publish(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        correlation_id: Optional[str] = None
    ) -> None:
        pass
    
    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        pass