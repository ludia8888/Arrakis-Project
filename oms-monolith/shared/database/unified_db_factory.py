"""
Unified Database Factory - 엔터프라이즈 레벨 통합 데이터베이스 관리
모든 데이터베이스 연결을 단일 진입점으로 관리
"""

import asyncio
import logging
from typing import Dict, Any, Optional, TypeVar, Type
from abc import ABC, abstractmethod
from functools import lru_cache
from contextlib import asynccontextmanager

from shared.clients.terminus_db import TerminusDBClient
from shared.clients.redis_ha_client import RedisHAClient
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.utils.logger import get_logger
from shared.exceptions import OntologyException
from shared.config.unified_env import unified_env

logger = get_logger(__name__)
metrics = get_metrics_collector()

T = TypeVar('T')


class DatabaseConnectionError(OntologyException):
    """데이터베이스 연결 오류"""
    pass


class IDatabase(ABC):
    """통합 데이터베이스 인터페이스"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """연결 수립"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """연결 종료"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """헬스 체크"""
        pass


class UnifiedDatabaseFactory:
    """
    통합 데이터베이스 팩토리
    
    모든 데이터베이스 클라이언트의 생성과 관리를 담당하는 단일 진입점
    - Singleton 패턴으로 인스턴스 관리
    - Connection pooling 지원
    - 자동 재연결 및 헬스 체크
    - 메트릭 수집 통합
    """
    
    _instances: Dict[str, Any] = {}
    _config: Dict[str, Any] = {}
    _lock = asyncio.Lock()
    
    @classmethod
    async def configure(cls, config: Dict[str, Any]) -> None:
        """팩토리 설정"""
        async with cls._lock:
            cls._config = config
            logger.info("Unified database factory configured")
            
            # 기존 인스턴스 정리
            for name, instance in cls._instances.items():
                try:
                    if hasattr(instance, 'disconnect'):
                        await instance.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting {name}: {e}")
            
            cls._instances.clear()
    
    @classmethod
    async def get_terminus_client(cls) -> TerminusDBClient:
        """TerminusDB 클라이언트 획득 (Singleton)"""
        return await cls._get_or_create_client(
            'terminus',
            TerminusDBClient,
            cls._create_terminus_client
        )
    
    @classmethod
    async def get_redis_client(cls) -> RedisHAClient:
        """Redis HA 클라이언트 획득 (Singleton)"""
        return await cls._get_or_create_client(
            'redis',
            RedisHAClient,
            cls._create_redis_client
        )
    
    @classmethod
    async def get_cache_client(cls) -> Any:
        """캐시 클라이언트 획득 (Redis 또는 In-Memory)"""
        cache_type = cls._config.get('cache_type', 'redis')
        
        if cache_type == 'redis':
            return await cls.get_redis_client()
        elif cache_type == 'memory':
            return await cls._get_or_create_client(
                'memory_cache',
                InMemoryCache,
                cls._create_memory_cache
            )
        else:
            raise DatabaseConnectionError(f"Unknown cache type: {cache_type}")
    
    @classmethod
    async def _get_or_create_client(
        cls,
        name: str,
        client_class: Type[T],
        create_func
    ) -> T:
        """클라이언트 인스턴스 획득 또는 생성"""
        async with cls._lock:
            if name not in cls._instances:
                logger.info(f"Creating new {name} client instance")
                instance = await create_func()
                
                # 연결 확인
                if hasattr(instance, 'connect'):
                    connected = await instance.connect()
                    if not connected:
                        raise DatabaseConnectionError(
                            f"Failed to connect to {name}"
                        )
                
                cls._instances[name] = instance
                
                # 메트릭 등록
                metrics.database_connections.labels(
                    database=name,
                    status='connected'
                ).inc()
            
            return cls._instances[name]
    
    @classmethod
    async def _create_terminus_client(cls) -> TerminusDBClient:
        """TerminusDB 클라이언트 생성"""
        config = cls._config.get('terminus', {})
        
        return TerminusDBClient(
            endpoint=config.get('endpoint'),
            username=config.get('username'),
            password=config.get('password'),
            service_name=config.get('service_name', 'oms'),
            use_connection_pool=config.get('use_connection_pool', True)
        )
    
    @classmethod
    async def _create_redis_client(cls) -> RedisHAClient:
        """Redis HA 클라이언트 생성"""
        config = cls._config.get('redis', {})
        
        return RedisHAClient(
            sentinels=config.get('sentinels'),
            master_name=config.get('master_name'),
            password=config.get('password'),
            db=config.get('db', 0),
            decode_responses=config.get('decode_responses', True),
            health_check_interval=config.get('health_check_interval', 30)
        )
    
    @classmethod
    async def _create_memory_cache(cls):
        """인메모리 캐시 생성"""
        from shared.cache.memory_cache import InMemoryCache
        
        config = cls._config.get('memory_cache', {})
        return InMemoryCache(
            max_size=config.get('max_size', 1000),
            ttl=config.get('ttl', 3600)
        )
    
    @classmethod
    async def health_check_all(cls) -> Dict[str, bool]:
        """모든 데이터베이스 헬스 체크"""
        results = {}
        
        async with cls._lock:
            for name, instance in cls._instances.items():
                try:
                    if hasattr(instance, 'health_check'):
                        results[name] = await instance.health_check()
                    elif hasattr(instance, 'ping'):
                        results[name] = await instance.ping()
                    else:
                        results[name] = True  # 헬스 체크 메서드가 없으면 성공으로 간주
                except Exception as e:
                    logger.error(f"Health check failed for {name}: {e}")
                    results[name] = False
                    
                    # 메트릭 업데이트
                    metrics.database_health_check_failures.labels(
                        database=name
                    ).inc()
        
        return results
    
    @classmethod
    async def shutdown(cls) -> None:
        """모든 데이터베이스 연결 종료"""
        logger.info("Shutting down all database connections")
        
        async with cls._lock:
            for name, instance in cls._instances.items():
                try:
                    if hasattr(instance, 'disconnect'):
                        await instance.disconnect()
                    elif hasattr(instance, 'close'):
                        await instance.close()
                    
                    logger.info(f"Disconnected {name}")
                    
                    # 메트릭 업데이트
                    metrics.database_connections.labels(
                        database=name,
                        status='disconnected'
                    ).inc()
                    
                except Exception as e:
                    logger.error(f"Error disconnecting {name}: {e}")
            
            cls._instances.clear()
    
    @classmethod
    @asynccontextmanager
    async def transaction(cls, db_name: str = 'terminus'):
        """트랜잭션 컨텍스트 매니저"""
        client = None
        
        try:
            if db_name == 'terminus':
                client = await cls.get_terminus_client()
            else:
                raise ValueError(f"Transaction not supported for {db_name}")
            
            # 트랜잭션 시작
            if hasattr(client, 'begin_transaction'):
                await client.begin_transaction()
            
            yield client
            
            # 트랜잭션 커밋
            if hasattr(client, 'commit_transaction'):
                await client.commit_transaction()
                
        except Exception as e:
            # 트랜잭션 롤백
            if client and hasattr(client, 'rollback_transaction'):
                await client.rollback_transaction()
            raise
    
    @classmethod
    def get_connection_stats(cls) -> Dict[str, Any]:
        """연결 통계 반환"""
        stats = {
            'total_connections': len(cls._instances),
            'connections': {}
        }
        
        for name, instance in cls._instances.items():
            conn_info = {
                'connected': True,
                'type': type(instance).__name__
            }
            
            # 추가 통계 수집
            if hasattr(instance, 'get_stats'):
                conn_info.update(instance.get_stats())
            
            stats['connections'][name] = conn_info
        
        return stats


# 편의 함수들
async def get_db() -> TerminusDBClient:
    """기본 데이터베이스 클라이언트 획득"""
    return await UnifiedDatabaseFactory.get_terminus_client()


async def get_cache() -> Any:
    """기본 캐시 클라이언트 획득"""
    return await UnifiedDatabaseFactory.get_cache_client()


async def get_redis() -> RedisHAClient:
    """Redis 클라이언트 획득"""
    return await UnifiedDatabaseFactory.get_redis_client()


# 초기화 함수
async def initialize_databases(config: Optional[Dict[str, Any]] = None) -> None:
    """데이터베이스 초기화"""
    if config is None:
        # 환경 변수에서 설정 로드
        config = {
            'terminus': {
                'endpoint': unified_env.get('TERMINUS_DB_ENDPOINT'),
                'username': unified_env.get('TERMINUS_DB_USER'),
                'password': unified_env.get('TERMINUS_DB_PASSWORD'),
                'service_name': 'oms',
                'use_connection_pool': True
            },
            'redis': {
                'sentinels': unified_env.get('REDIS_SENTINELS').split(',') if unified_env.get('REDIS_SENTINELS') else [],
                'master_name': unified_env.get('REDIS_MASTER_NAME'),
                'password': unified_env.get('REDIS_PASSWORD'),
                'db': unified_env.get('REDIS_DB'),
                'decode_responses': True
            },
            'cache_type': unified_env.get('CACHE_TYPE')
        }
    
    await UnifiedDatabaseFactory.configure(config)
    logger.info("Database connections initialized")


# 인메모리 캐시 구현 (간단한 버전)
class InMemoryCache:
    """간단한 인메모리 캐시 구현"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        if key in self._cache:
            self._access_times[key] = asyncio.get_event_loop().time()
            return self._cache[key]
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """값 설정"""
        # 크기 제한 확인
        if len(self._cache) >= self.max_size:
            # LRU 제거
            oldest_key = min(self._access_times, key=self._access_times.get)
            del self._cache[oldest_key]
            del self._access_times[oldest_key]
        
        self._cache[key] = value
        self._access_times[key] = asyncio.get_event_loop().time()
    
    async def delete(self, key: str) -> None:
        """값 삭제"""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
    
    async def health_check(self) -> bool:
        """헬스 체크"""
        return True
    
    async def disconnect(self) -> None:
        """연결 종료 (캐시 클리어)"""
        self._cache.clear()
        self._access_times.clear()