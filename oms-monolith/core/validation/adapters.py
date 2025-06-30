"""
Port Adapters - 실제 구현체들을 Port 인터페이스에 맞게 연결
순환 참조 해결의 핵심: 인프라 레이어의 구현체를 Core 레이어의 인터페이스에 맞춤
"""
from typing import Any, Dict, List, Optional
import json
import logging

from core.validation.ports import CachePort, TerminusPort, EventPort, PolicyServerPort, RuleLoaderPort

logger = logging.getLogger(__name__)


class SmartCacheAdapter:
    """
    shared.cache.smart_cache.SmartCacheManager를 CachePort로 변환하는 어댑터
    실제 import는 생성자에서만 수행하여 순환 참조 방지
    """
    
    def __init__(self, cache_manager=None):
        if cache_manager is None:
            # 런타임에만 import하여 순환 참조 방지
            from shared.cache.smart_cache import SmartCacheManager
            from database.clients.terminus_db import TerminusDBClient
            tdb = TerminusDBClient()
            self.cache = SmartCacheManager(tdb)
        else:
            self.cache = cache_manager
    
    async def get(self, key: str) -> Any:
        """캐시에서 값 조회"""
        try:
            return await self.cache.get(key)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
        except KeyError as e:
            logger.error(f"Cache key error for {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값 저장"""
        try:
            await self.cache.set(key, value, ttl=ttl)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache set error for key {key}: {e}")
        except ValueError as e:
            logger.error(f"Cache value error for key {key}: {e}")
    
    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        try:
            await self.cache.delete(key)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache delete error for key {key}: {e}")
        except KeyError as e:
            logger.error(f"Cache key not found for delete {key}: {e}")
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        try:
            return await self.cache.exists(key)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False


class TerminusDBAdapter:
    """
    database.clients.terminus_db.TerminusDBClient를 TerminusPort로 변환하는 어댑터
    """
    
    def __init__(self, tdb_client=None):
        if tdb_client is None:
            # 런타임에만 import
            from database.clients.terminus_db import TerminusDBClient
            self.tdb = TerminusDBClient()
        else:
            self.tdb = tdb_client
    
    async def query(
        self, 
        sparql: str, 
        db: str = "oms", 
        branch: str = "main", 
        **opts
    ) -> List[Dict[str, Any]]:
        """SPARQL 쿼리 실행"""
        try:
            return await self.tdb.query(sparql, db=db, branch=branch)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"TerminusDB query error: {e}")
            return []
        except ValueError as e:
            logger.error(f"TerminusDB query parsing error: {e}")
            return []
    
    async def get_document(
        self, 
        doc_id: str, 
        db: str = "oms", 
        branch: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """문서 조회"""
        try:
            return await self.tdb.get_document(doc_id, db=db, branch=branch)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"TerminusDB get_document error: {e}")
            return None
        except KeyError as e:
            logger.error(f"TerminusDB document not found: {e}")
            return None
    
    async def insert_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """문서 삽입"""
        try:
            return await self.tdb.insert_document(
                document, 
                db=db, 
                branch=branch,
                author=author,
                message=message
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"TerminusDB insert_document error: {e}")
            raise
        except ValueError as e:
            logger.error(f"TerminusDB insert validation error: {e}")
            raise
    
    async def update_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> bool:
        """문서 업데이트"""
        try:
            return await self.tdb.update_document(
                document, 
                db=db, 
                branch=branch,
                author=author,
                message=message
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"TerminusDB update_document error: {e}")
            return False
        except KeyError as e:
            logger.error(f"TerminusDB document not found for update: {e}")
            return False
        except ValueError as e:
            logger.error(f"TerminusDB update validation error: {e}")
            return False
    
    async def health_check(self) -> bool:
        """헬스 체크"""
        try:
            return await self.tdb.health_check()
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"TerminusDB health_check error: {e}")
            return False


class EventPublisherAdapter:
    """
    shared.events.EventPublisher를 EventPort로 변환하는 어댑터
    """
    
    def __init__(self, event_publisher=None):
        if event_publisher is None:
            # 런타임에만 import
            from shared.events import EventPublisher
            self.publisher = EventPublisher()
        else:
            self.publisher = event_publisher
    
    async def publish(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        correlation_id: Optional[str] = None
    ) -> None:
        """이벤트 발행"""
        try:
            # EventPublisher의 실제 메서드에 맞게 호출
            if hasattr(self.publisher, 'publish_event'):
                await self.publisher.publish_event(
                    event_type=event_type,
                    data=data,
                    correlation_id=correlation_id
                )
            elif hasattr(self.publisher, 'publish'):
                await self.publisher.publish(
                    event_type,
                    data,
                    correlation_id=correlation_id
                )
            else:
                logger.warning(f"EventPublisher does not have publish method")
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Event publish error: {e}")
        except ValueError as e:
            logger.error(f"Event data validation error: {e}")
    
    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        """배치 이벤트 발행"""
        try:
            if hasattr(self.publisher, 'publish_batch'):
                await self.publisher.publish_batch(events)
            else:
                # 배치 메서드가 없으면 개별 발행
                for event in events:
                    await self.publish(
                        event.get('event_type', 'unknown'),
                        event.get('data', {}),
                        event.get('correlation_id')
                    )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Event publish_batch error: {e}")
        except ValueError as e:
            logger.error(f"Event batch validation error: {e}")


class PolicyServerAdapter:
    """
    외부 정책 서버 연동 어댑터
    HTTP/REST API를 통한 기업 정책 검증 시스템 연동
    """
    
    def __init__(self, config=None):
        if config is None:
            # 설정에서 정책 서버 URL 가져오기
            from core.validation.config import get_validation_config
            config = get_validation_config()
        
        self.config = config
        # Use property that handles environment config
        self.base_url = config.policy_server_url
        self.timeout = getattr(config, 'policy_server_timeout', 10.0)
        self.api_key = getattr(config, 'policy_server_api_key', None)
        
        # HTTP 클라이언트 설정
        from shared.clients.unified_http_client import UnifiedHTTPClient
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        self.http_client = UnifiedHTTPClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout
        )
    
    
    async def validate_policy(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """정책 검증 요청"""
        try:
            payload = {
                'entity_type': entity_type,
                'entity_data': entity_data,
                'operation': operation,
                'context': context or {}
            }
            
            response = await self.http_client.post("/validate", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'valid': result.get('valid', True),
                    'violations': result.get('violations', []),
                    'warnings': result.get('warnings', []),
                    'policy_version': result.get('policy_version'),
                    'response_time_ms': result.get('response_time_ms', 0)
                }
            else:
                logger.error(f"Policy server error: {response.status_code} - {response.text}")
                return {
                    'valid': True,  # Fail-open: 정책 서버 장애시 통과
                    'violations': [],
                    'warnings': [f"Policy server unavailable (HTTP {response.status_code})"],
                    'fallback': True
                }
                    
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Policy server connection error: {e}")
            return {
                'valid': True,  # Fail-open: 연결 오류시 통과
                'violations': [],
                'warnings': [f"Policy server unavailable: {str(e)}"],
                'fallback': True
            }
        except json.JSONDecodeError as e:
            logger.error(f"Policy response parsing error: {e}")
            return {
                'valid': True,  # Fail-open: 파싱 오류시 통과
                'violations': [],
                'warnings': [f"Invalid policy response format: {str(e)}"],
                'fallback': True
            }
        except ValueError as e:
            logger.error(f"Policy validation error: {e}")
            return {
                'valid': True,  # Fail-open: 검증 오류시 통과
                'violations': [],
                'warnings': [f"Policy validation failed: {str(e)}"],
                'fallback': True
            }
    
    async def get_policies(
        self,
        entity_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """정책 목록 조회"""
        try:
            params = {}
            if entity_type:
                params['entity_type'] = entity_type
            if active_only:
                params['active_only'] = 'true'
            
            response = await self.http_client.get("/list", params=params)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('policies', [])
            else:
                logger.error(f"Policy list error: {response.status_code}")
                return []
                    
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Policy server connection error: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Policy list response parsing error: {e}")
            return []
    
    async def health_check(self) -> bool:
        """정책 서버 헬스 체크"""
        try:
            response = await self.http_client.get("/health")
            return response.status_code == 200
                
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Policy server health check error: {e}")
            return False
    
    async def close(self):
        """클라이언트 정리"""
        # UnifiedHTTPClient는 자체적으로 커넥션 풀을 관리함
        pass


class DynamicRuleLoaderAdapter:
    """
    동적 규칙 로더 어댑터
    Entry-point 기반 플러그인 시스템으로 규칙 동적 로딩
    """
    
    def __init__(self, config=None):
        if config is None:
            from core.validation.config import get_validation_config
            config = get_validation_config()
        
        self.config = config
        self.rule_cache = {}
        self.last_reload = None
        self.reload_interval = config.rule_reload_interval  # Use ValidationConfig value
        
        # Entry-point 네임스페이스 설정
        self.namespaces = {
            'validation_rules': 'oms.validation.rules',
            'naming_rules': 'oms.validation.naming',
            'schema_rules': 'oms.validation.schema',
            'business_rules': 'oms.validation.business'
        }
        
        # 통합 설정으로 임계값 관리
        self.config = config
    
    async def load_rules(
        self,
        rule_type: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Any]:
        """규칙 동적 로딩"""
        try:
            # 캐시된 규칙이 있고 아직 유효하면 반환
            cache_key = f"{rule_type}:{entity_type}"
            if cache_key in self.rule_cache:
                cached_rules, cached_time = self.rule_cache[cache_key]
                if self._is_cache_valid(cached_time):
                    return cached_rules
            
            # Entry-point에서 규칙 로딩
            rules = []
            
            # setuptools entry_points 사용
            try:
                import pkg_resources
                
                # 특정 타입의 규칙만 로딩하거나 모든 규칙 로딩
                namespaces_to_check = []
                if rule_type and rule_type in self.namespaces:
                    namespaces_to_check = [self.namespaces[rule_type]]
                else:
                    namespaces_to_check = list(self.namespaces.values())
                
                for namespace in namespaces_to_check:
                    for entry_point in pkg_resources.iter_entry_points(namespace):
                        try:
                            rule_class = entry_point.load()
                            
                            # 엔티티 타입 필터링
                            if entity_type:
                                if hasattr(rule_class, 'entity_types'):
                                    if entity_type not in rule_class.entity_types:
                                        continue
                            
                            # 규칙 인스턴스 생성
                            rule_instance = rule_class()
                            rules.append({
                                'instance': rule_instance,
                                'name': entry_point.name,
                                'module': entry_point.module_name,
                                'rule_type': rule_type or 'general',
                                'entity_type': entity_type,
                                'priority': getattr(rule_class, 'priority', 100),
                                'enabled': getattr(rule_class, 'enabled', True)
                            })
                            
                        except ImportError as e:
                            logger.error(f"Failed to import rule {entry_point.name}: {e}")
                            continue
                        except AttributeError as e:
                            logger.error(f"Invalid rule class {entry_point.name}: {e}")
                            continue
                        except RuntimeError as e:
                            logger.error(f"Failed to load rule {entry_point.name}: {e}")
                            continue
                            
            except ImportError:
                # pkg_resources가 없으면 폴백 메커니즘
                logger.warning("pkg_resources not available, using fallback rule loading")
                rules = await self._load_fallback_rules(rule_type, entity_type)
            
            # 우선순위에 따라 정렬
            rules.sort(key=lambda r: r.get('priority', 100), reverse=True)
            
            # 캐시에 저장
            import time
            self.rule_cache[cache_key] = (rules, time.time())
            
            logger.info(f"Loaded {len(rules)} rules for {rule_type}:{entity_type}")
            return rules
            
        except ImportError as e:
            logger.error(f"Rule import error: {e}")
            return []
        except RuntimeError as e:
            logger.error(f"Rule loading runtime error: {e}")
            return []
    
    async def reload_rules(self) -> None:
        """규칙 재로딩"""
        try:
            # 캐시 클리어
            self.rule_cache.clear()
            
            # 마지막 재로딩 시간 업데이트
            import time
            self.last_reload = time.time()
            
            logger.info("Rules reloaded successfully")
            
        except RuntimeError as e:
            logger.error(f"Rule reload error: {e}")
    
    def get_available_rules(self) -> List[Dict[str, Any]]:
        """사용 가능한 규칙 정보 조회"""
        try:
            rules_info = []
            
            import pkg_resources
            for namespace in self.namespaces.values():
                for entry_point in pkg_resources.iter_entry_points(namespace):
                    try:
                        rule_class = entry_point.load()
                        rules_info.append({
                            'name': entry_point.name,
                            'module': entry_point.module_name,
                            'namespace': namespace,
                            'description': getattr(rule_class, '__doc__', ''),
                            'priority': getattr(rule_class, 'priority', 100),
                            'enabled': getattr(rule_class, 'enabled', True),
                            'entity_types': getattr(rule_class, 'entity_types', []),
                            'version': getattr(rule_class, '__version__', '1.0.0')
                        })
                    except ImportError as e:
                        logger.error(f"Failed to import rule for inspection {entry_point.name}: {e}")
                        continue
                    except AttributeError as e:
                        logger.error(f"Failed to inspect rule attributes {entry_point.name}: {e}")
                        continue
            
            return rules_info
            
        except ImportError as e:
            logger.error(f"Failed to import rules registry: {e}")
            return []
        except RuntimeError as e:
            logger.error(f"Failed to get available rules: {e}")
            return []
    
    def _is_cache_valid(self, cached_time: float) -> bool:
        """캐시 유효성 검사"""
        import time
        return (time.time() - cached_time) < self.reload_interval
    
    async def _load_fallback_rules(self, rule_type: Optional[str], entity_type: Optional[str]) -> List[Any]:
        """폴백 규칙 로딩 (pkg_resources 없을 때)"""
        # 하드코딩된 기본 규칙들
        fallback_rules = []
        
        # 기본 규칙 클래스들 (예시)
        if rule_type == 'validation_rules' or rule_type is None:
            fallback_rules.extend([
                {
                    'instance': self._create_basic_validation_rule(),
                    'name': 'basic_validation',
                    'module': 'core.validation.adapters',
                    'rule_type': 'validation_rules',
                    'priority': 50,
                    'enabled': True
                }
            ])
        
        return fallback_rules
    
    def _create_basic_validation_rule(self):
        """기본 검증 규칙 생성"""
        class BasicValidationRule:
            def __init__(self):
                self.name = "basic_validation"
                self.priority = 50
                
            async def validate(self, data, context):
                # 기본적인 검증 로직
                return {'valid': True, 'errors': []}
        
        return BasicValidationRule()


# Factory functions for easy adapter creation
def create_cache_adapter(cache_manager=None) -> CachePort:
    """캐시 어댑터 생성"""
    return SmartCacheAdapter(cache_manager)


def create_terminus_adapter(tdb_client=None) -> TerminusPort:
    """TerminusDB 어댑터 생성"""
    return TerminusDBAdapter(tdb_client)


def create_event_adapter(event_publisher=None) -> EventPort:
    """이벤트 어댑터 생성"""
    return EventPublisherAdapter(event_publisher)


def create_policy_server_adapter(config=None) -> PolicyServerPort:
    """정책 서버 어댑터 생성"""
    return PolicyServerAdapter(config)


def create_rule_loader_adapter(config=None) -> RuleLoaderPort:
    """동적 규칙 로더 어댑터 생성"""
    return DynamicRuleLoaderAdapter(config)


# Test adapters for unit testing
class MockCacheAdapter:
    """테스트용 Mock 캐시 어댑터"""
    
    def __init__(self):
        self.storage = {}
        self.call_count = {
            'get': 0,
            'set': 0,
            'delete': 0,
            'exists': 0
        }
    
    async def get(self, key: str) -> Any:
        self.call_count['get'] += 1
        return self.storage.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.call_count['set'] += 1
        self.storage[key] = value
    
    async def delete(self, key: str) -> None:
        self.call_count['delete'] += 1
        self.storage.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        self.call_count['exists'] += 1
        return key in self.storage


class MockTerminusAdapter:
    """테스트용 Mock TerminusDB 어댑터"""
    
    def __init__(self):
        self.documents = {}
        self.query_results = []
        self.call_count = {
            'query': 0,
            'get_document': 0,
            'insert_document': 0,
            'update_document': 0
        }
    
    async def query(
        self, 
        sparql: str, 
        db: str = "oms", 
        branch: str = "main", 
        **opts
    ) -> List[Dict[str, Any]]:
        self.call_count['query'] += 1
        return self.query_results
    
    async def get_document(
        self, 
        doc_id: str, 
        db: str = "oms", 
        branch: str = "main"
    ) -> Optional[Dict[str, Any]]:
        self.call_count['get_document'] += 1
        return self.documents.get(doc_id)
    
    async def insert_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        self.call_count['insert_document'] += 1
        doc_id = document.get('@id', f'doc_{len(self.documents)}')
        self.documents[doc_id] = document
        return doc_id
    
    async def update_document(
        self, 
        document: Dict[str, Any], 
        db: str = "oms", 
        branch: str = "main",
        author: Optional[str] = None,
        message: Optional[str] = None
    ) -> bool:
        self.call_count['update_document'] += 1
        doc_id = document.get('@id')
        if doc_id and doc_id in self.documents:
            self.documents[doc_id] = document
            return True
        return False
    
    async def health_check(self) -> bool:
        return True


class MockEventAdapter:
    """테스트용 Mock 이벤트 어댑터"""
    
    def __init__(self):
        self.published_events = []
        self.call_count = {
            'publish': 0,
            'publish_batch': 0
        }
    
    async def publish(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        correlation_id: Optional[str] = None
    ) -> None:
        self.call_count['publish'] += 1
        self.published_events.append({
            'event_type': event_type,
            'data': data,
            'correlation_id': correlation_id
        })
    
    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        self.call_count['publish_batch'] += 1
        self.published_events.extend(events)


class MockPolicyServerAdapter:
    """테스트용 Mock 정책 서버 어댑터"""
    
    def __init__(self):
        self.policies = []
        self.validation_results = {}
        self.health_status = True
        self.call_count = {
            'validate_policy': 0,
            'get_policies': 0,
            'health_check': 0
        }
    
    async def validate_policy(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.call_count['validate_policy'] += 1
        
        # 테스트용 기본 결과
        key = f"{entity_type}:{operation}"
        if key in self.validation_results:
            return self.validation_results[key]
        
        return {
            'valid': True,
            'violations': [],
            'warnings': [],
            'policy_version': '1.0.0',
            'response_time_ms': 10
        }
    
    async def get_policies(
        self,
        entity_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        self.call_count['get_policies'] += 1
        return self.policies
    
    async def health_check(self) -> bool:
        self.call_count['health_check'] += 1
        return self.health_status
    
    def set_validation_result(self, entity_type: str, operation: str, result: Dict[str, Any]):
        """테스트용 검증 결과 설정"""
        key = f"{entity_type}:{operation}"
        self.validation_results[key] = result
    
    def add_policy(self, policy: Dict[str, Any]):
        """테스트용 정책 추가"""
        self.policies.append(policy)


class MockRuleLoaderAdapter:
    """테스트용 Mock 동적 규칙 로더 어댑터"""
    
    def __init__(self):
        self.rules = {}
        self.available_rules = []
        self.call_count = {
            'load_rules': 0,
            'reload_rules': 0,
            'get_available_rules': 0
        }
    
    async def load_rules(
        self,
        rule_type: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Any]:
        self.call_count['load_rules'] += 1
        
        key = f"{rule_type}:{entity_type}"
        return self.rules.get(key, [])
    
    async def reload_rules(self) -> None:
        self.call_count['reload_rules'] += 1
        # Mock에서는 아무것도 하지 않음
        pass
    
    def get_available_rules(self) -> List[Dict[str, Any]]:
        self.call_count['get_available_rules'] += 1
        return self.available_rules
    
    def set_rules(self, rule_type: str, entity_type: str, rules: List[Any]):
        """테스트용 규칙 설정"""
        key = f"{rule_type}:{entity_type}"
        self.rules[key] = rules
    
    def add_available_rule(self, rule_info: Dict[str, Any]):
        """테스트용 사용 가능한 규칙 추가"""
        self.available_rules.append(rule_info)