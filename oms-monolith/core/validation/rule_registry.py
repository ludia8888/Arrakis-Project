"""
Dynamic Rule Loading System
플러그인 방식의 동적 규칙 로딩으로 순환 참조 해결
"""
import importlib
import pkgutil
import logging
import functools
from typing import List, Type, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

from core.validation.ports import CachePort, TerminusPort, EventPort, RuleLoaderPort
from core.validation.interfaces import BreakingChangeRule
from core.validation.config import get_validation_config

logger = logging.getLogger(__name__)

# 규칙 로딩 캐시 (통합 설정 사용)
_rule_cache: Dict[str, List[BreakingChangeRule]] = {}
_cache_timestamp: Dict[str, datetime] = {}
# CACHE_TTL은 이제 ValidationConfig에서 가져옴

class RuleRegistry:
    """규칙 레지스트리 - 동적으로 규칙을 로드하고 관리"""
    
    def __init__(
        self,
        cache: Optional[CachePort] = None,
        tdb: Optional[TerminusPort] = None,
        event: Optional[EventPort] = None,
        rule_loader: Optional[RuleLoaderPort] = None
    ):
        self.cache = cache
        self.tdb = tdb
        self.event = event
        self.rule_loader = rule_loader
        self._rules: Dict[str, BreakingChangeRule] = {}
        self._rule_classes: Dict[str, Type[BreakingChangeRule]] = {}
        
        # 동적 규칙 로더가 있으면 Entry-point 방식 사용
        self._use_entry_points = rule_loader is not None
    
    async def load_rules_from_package(self, package_name: str = "core.validation.rules") -> List[BreakingChangeRule]:
        """
        패키지에서 모든 규칙을 동적으로 로드
        Entry-point 플러그인 시스템 지원으로 확장성 강화
        """
        # 캐시 확인 (통합 설정 사용)
        config = get_validation_config()
        cache_ttl = timedelta(seconds=config.rule_cache_ttl_seconds)
        
        cache_key = f"{package_name}:{self.cache}:{self.tdb}:{self.event}:{self._use_entry_points}"
        if cache_key in _rule_cache:
            timestamp = _cache_timestamp.get(cache_key)
            if timestamp and datetime.now() - timestamp < cache_ttl:
                logger.debug(f"Returning cached rules for {package_name}")
                return _rule_cache[cache_key]
        
        rules = []
        
        # Entry-point 방식 우선 시도
        if self._use_entry_points and self.rule_loader:
            try:
                logger.info("Loading rules via Entry-point system")
                entry_point_rules = await self.rule_loader.load_rules(
                    rule_type='validation_rules',
                    entity_type=None
                )
                
                # Entry-point에서 로드된 규칙들을 BreakingChangeRule로 변환
                for rule_info in entry_point_rules:
                    rule_instance = rule_info.get('instance')
                    if rule_instance and isinstance(rule_instance, BreakingChangeRule):
                        rule_id = getattr(rule_instance, 'rule_id', rule_info.get('name', 'unknown'))
                        self._rules[rule_id] = rule_instance
                        rules.append(rule_instance)
                        logger.info(f"Loaded rule via entry-point: {rule_id}")
                
                logger.info(f"Loaded {len(rules)} rules via Entry-point system")
                
            except (ImportError, AttributeError, RuntimeError) as e:
                logger.error(f"Failed to load rules via Entry-point: {e}")
                # Entry-point 실패시 폴백으로 패키지 스캔 방식 사용
                rules = await self._load_rules_fallback(package_name)
        else:
            # 기본 패키지 스캔 방식
            rules = await self._load_rules_fallback(package_name)
        
        # 캐시에 저장
        _rule_cache[cache_key] = rules
        _cache_timestamp[cache_key] = datetime.now()
        
        return rules
    
    async def _load_rules_fallback(self, package_name: str) -> List[BreakingChangeRule]:
        """
        폴백 규칙 로딩 - 기존 패키지 스캔 방식
        """
        rules = []
        
        try:
            # 패키지 import
            pkg = importlib.import_module(package_name)
            pkg_path = Path(pkg.__file__).parent
            
            # 패키지 내 모든 모듈 순회
            for mod_info in pkgutil.iter_modules([str(pkg_path)]):
                if mod_info.name.startswith('_'):
                    continue
                    
                try:
                    # 모듈 동적 import
                    module_name = f"{package_name}.{mod_info.name}"
                    module = importlib.import_module(module_name)
                    
                    # 모듈 내 클래스 검사
                    for attr_name in dir(module):
                        if attr_name.startswith('_'):
                            continue
                            
                        attr = getattr(module, attr_name)
                        
                        # BreakingChangeRule을 구현한 클래스인지 확인
                        if (isinstance(attr, type) and 
                            issubclass(attr, BreakingChangeRule) and 
                            attr is not BreakingChangeRule and
                            hasattr(attr, 'rule_id') and
                            hasattr(attr, 'check')):
                            
                            try:
                                # 규칙 인스턴스 생성 (의존성 주입)
                                rule_instance = self._create_rule_instance(attr)
                                if rule_instance:
                                    rule_id = rule_instance.rule_id
                                    self._rules[rule_id] = rule_instance
                                    self._rule_classes[rule_id] = attr
                                    rules.append(rule_instance)
                                    logger.info(f"Loaded rule: {rule_id} from {module_name}")
                                    
                            except (TypeError, ValueError, RuntimeError) as e:
                                logger.error(f"Failed to instantiate rule {attr_name}: {e}")
                                
                except (ImportError, AttributeError, RuntimeError) as e:
                    logger.error(f"Failed to load module {module_name}: {e}")
                    
        except (ImportError, OSError, RuntimeError) as e:
            logger.error(f"Failed to load rules package {package_name}: {e}")
            
        logger.info(f"Loaded {len(rules)} validation rules via fallback")
        return rules
    
    def _create_rule_instance(self, rule_class: Type[BreakingChangeRule]) -> Optional[BreakingChangeRule]:
        """
        규칙 인스턴스 생성 - 생성자 시그니처에 따라 적절한 의존성 주입
        """
        try:
            # 생성자 파라미터 확인
            import inspect
            sig = inspect.signature(rule_class.__init__)
            params = list(sig.parameters.keys())
            
            # self를 제외한 파라미터 확인
            # TerminusDB native rules require terminus_port parameter
            if 'terminus_port' in params:
                return rule_class(terminus_port=self.tdb)
            elif len(params) == 1:  # only self
                return rule_class()
            elif 'cache' in params and 'tdb' in params:
                return rule_class(cache=self.cache, tdb=self.tdb)
            elif 'cache' in params:
                return rule_class(cache=self.cache)
            elif 'tdb' in params:
                return rule_class(tdb=self.tdb)
            else:
                # 기본 생성자 시도
                return rule_class()
                
        except (TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create instance of {rule_class.__name__}: {e}")
            return None
    
    def get_rule(self, rule_id: str) -> Optional[BreakingChangeRule]:
        """특정 규칙 가져오기"""
        return self._rules.get(rule_id)
    
    def get_all_rules(self) -> List[BreakingChangeRule]:
        """모든 로드된 규칙 가져오기"""
        return list(self._rules.values())
    
    def register_rule(self, rule: BreakingChangeRule) -> None:
        """규칙 수동 등록"""
        self._rules[rule.rule_id] = rule
        logger.info(f"Manually registered rule: {rule.rule_id}")
    
    def unregister_rule(self, rule_id: str) -> None:
        """규칙 등록 해제"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"Unregistered rule: {rule_id}")
    
    async def reload_rules(self) -> List[BreakingChangeRule]:
        """모든 규칙 재로드 (캐시 무효화)"""
        self._rules.clear()
        self._rule_classes.clear()
        
        # 캐시 무효화
        _rule_cache.clear()
        _cache_timestamp.clear()
        
        # Entry-point 방식을 사용하는 경우 rule_loader에도 재로드 요청
        if self._use_entry_points and self.rule_loader:
            try:
                await self.rule_loader.reload_rules()
                logger.info("Rule loader reloaded successfully")
            except (RuntimeError, AttributeError) as e:
                logger.error(f"Failed to reload rule loader: {e}")
        
        return await self.load_rules_from_package()
    
    def get_rule_info(self) -> Dict[str, Dict[str, Any]]:
        """로드된 규칙 정보 반환"""
        info = {}
        for rule_id, rule in self._rules.items():
            info[rule_id] = {
                "description": getattr(rule, 'description', 'No description'),
                "severity": getattr(rule, 'severity', 'UNKNOWN'),
                "class": rule.__class__.__name__,
                "module": rule.__class__.__module__
            }
        return info

# 싱글톤 패턴의 전역 레지스트리 (선택적)
_global_registry: Optional[RuleRegistry] = None

def get_global_registry(
    cache: Optional[CachePort] = None,
    tdb: Optional[TerminusPort] = None,
    event: Optional[EventPort] = None,
    rule_loader: Optional[RuleLoaderPort] = None
) -> RuleRegistry:
    """전역 레지스트리 가져오기 또는 생성"""
    global _global_registry
    if _global_registry is None:
        _global_registry = RuleRegistry(
            cache=cache, 
            tdb=tdb, 
            event=event,
            rule_loader=rule_loader
        )
        # 비동기 메서드이므로 여기서는 호출하지 않음
        # 사용하는 곳에서 load_rules_from_package()를 호출해야 함
    return _global_registry

async def load_rules(
    cache: Optional[CachePort] = None,
    tdb: Optional[TerminusPort] = None,
    event: Optional[EventPort] = None,
    rule_loader: Optional[RuleLoaderPort] = None,
    package_name: str = "core.validation.rules"
) -> List[BreakingChangeRule]:
    """
    간편한 규칙 로드 함수
    서비스에서 이 함수만 호출하면 모든 규칙이 로드됨
    """
    registry = RuleRegistry(
        cache=cache, 
        tdb=tdb, 
        event=event,
        rule_loader=rule_loader
    )
    return await registry.load_rules_from_package(package_name)