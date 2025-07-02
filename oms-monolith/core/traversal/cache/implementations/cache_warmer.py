"""
Cache warming implementations
"""

import asyncio
import hashlib
import threading
import time
import logging
from typing import List, Optional, Callable, Any

from ..interfaces.contracts import CacheWarmerInterface, AsyncCacheWarmerInterface
from ..interfaces.models import CacheConfig
from .multi_level_cache import MultiLevelCache

logger = logging.getLogger(__name__)


class CacheWarmer(CacheWarmerInterface):
    """
    Cache warming service for preloading frequently used data.
    
    Strategies:
    - Predictive warming based on access patterns
    - Scheduled warming of common queries
    - Priority-based warming
    """
    
    def __init__(self, cache: MultiLevelCache, config: Optional[CacheConfig] = None):
        self.cache = cache
        self.config = config or CacheConfig()
        self._warming_queries: List[str] = self.config.cache_warming_queries.copy()
        self._warming_active = False
        self._warming_thread: Optional[threading.Thread] = None
        
    def start_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start cache warming process"""
        if self._warming_active or not self.config.enable_cache_warming:
            return
            
        self._warming_active = True
        self._warming_thread = threading.Thread(
            target=self._warming_worker,
            args=(query_executor,),
            daemon=True
        )
        self._warming_thread.start()
    
    def stop_warming(self) -> None:
        """Stop cache warming process"""
        self._warming_active = False
        if self._warming_thread:
            self._warming_thread.join(timeout=5.0)
    
    def add_warming_query(self, query: str) -> None:
        """Add query to warming list"""
        if query not in self._warming_queries:
            self._warming_queries.append(query)
    
    def _warming_worker(self, query_executor: Callable[[str], Any]) -> None:
        """Background worker for cache warming"""
        while self._warming_active:
            try:
                for query in self._warming_queries:
                    if not self._warming_active:
                        break
                        
                    # Check if query result is already cached
                    cache_key = self._generate_cache_key(query)
                    if self.cache.get(cache_key) is None:
                        # Execute query and cache result
                        try:
                            result = query_executor(query)
                            if result is not None:
                                self.cache.put(cache_key, result, "query_results")
                        except (ConnectionError, TimeoutError) as e:
                            # Log network error but continue warming
                            logger.warning(f"Cache warming network error: {e}")
                            continue
                        except Exception as e:
                            # Log error but continue warming
                            logger.error(f"Cache warming error: {e}")
                            continue
                
                # Sleep between warming cycles
                time.sleep(self.config.cache_warming_interval_seconds)
                
            except Exception as e:
                # Log error and continue
                logger.error(f"Warming worker error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _generate_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return f"warming:{hashlib.md5(query.encode()).hexdigest()}"


class AsyncCacheWarmer(AsyncCacheWarmerInterface):
    """
    Async cache warming service for preloading frequently used data.
    
    Uses asyncio tasks instead of threads for better integration
    with async environments.
    """
    
    def __init__(self, cache: MultiLevelCache, config: Optional[CacheConfig] = None):
        if not cache.async_mode:
            raise ValueError("AsyncCacheWarmer requires MultiLevelCache in async_mode")
        
        self.cache = cache
        self.config = config or CacheConfig()
        self._warming_queries: List[str] = self.config.cache_warming_queries.copy()
        self._warming_active = False
        self._warming_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start async cache warming process"""
        if self._warming_active or not self.config.enable_cache_warming:
            return
            
        self._warming_active = True
        self._stop_event.clear()
        
        # Create warming task
        self._warming_task = asyncio.create_task(
            self._warming_worker(query_executor)
        )
    
    async def stop_warming(self) -> None:
        """Stop async cache warming process"""
        self._warming_active = False
        self._stop_event.set()
        
        if self._warming_task and not self._warming_task.done():
            self._warming_task.cancel()
            try:
                await asyncio.wait_for(self._warming_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
    
    def add_warming_query(self, query: str) -> None:
        """Add query to warming list"""
        if query not in self._warming_queries:
            self._warming_queries.append(query)
    
    async def _warming_worker(self, query_executor: Callable[[str], Any]) -> None:
        """Async background worker for cache warming"""
        while self._warming_active:
            try:
                for query in self._warming_queries:
                    if not self._warming_active or self._stop_event.is_set():
                        break
                        
                    # Check if query result is already cached
                    cache_key = self._generate_cache_key(query)
                    
                    # Use async cache methods
                    if await self.cache.aget(cache_key) is None:
                        # Execute query and cache result
                        try:
                            # If query_executor is async
                            if asyncio.iscoroutinefunction(query_executor):
                                result = await query_executor(query)
                            else:
                                # Run sync function in executor
                                result = await asyncio.get_event_loop().run_in_executor(
                                    None, query_executor, query
                                )
                            
                            if result is not None:
                                await self.cache.aput(cache_key, result, "query_results")
                                
                        except (ConnectionError, TimeoutError) as e:
                            # Log network error but continue warming
                            logger.warning(f"Cache warming network error: {e}")
                            continue
                        except Exception as e:
                            # Log error but continue warming
                            logger.error(f"Cache warming error: {e}")
                            continue
                
                # Async sleep between warming cycles
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), 
                        timeout=float(self.config.cache_warming_interval_seconds)
                    )
                except asyncio.TimeoutError:
                    # Timeout means we continue warming
                    pass
                    
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                break
            except Exception as e:
                # Log error and wait longer
                logger.error(f"Warming worker error: {e}")
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=60.0  # Wait longer on error
                    )
                except asyncio.TimeoutError:
                    pass
    
    def _generate_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return f"warming:{hashlib.md5(query.encode()).hexdigest()}"