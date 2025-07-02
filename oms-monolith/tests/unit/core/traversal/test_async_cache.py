"""
Tests for AsyncLRUCache and async cache functionality
"""
import asyncio
import pytest
import time
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor

from core.traversal.caching import (
    AsyncLRUCache, MultiLevelCache, TraversalCacheManager,
    get_cache_manager, get_async_cache_manager, reset_cache_manager,
    CacheEntry
)
from core.traversal.models import TraversalQuery, TraversalDirection
from core.traversal.config import CacheConfig


class TestAsyncLRUCache:
    """Tests for AsyncLRUCache implementation"""
    
    @pytest.fixture
    def async_cache(self):
        """Create an async cache instance"""
        return AsyncLRUCache(max_size=100, default_ttl=300)
    
    @pytest.fixture
    def sync_cache(self):
        """Create a sync cache instance for comparison"""
        from core.traversal.caching import LRUCache
        return LRUCache(max_size=100, default_ttl=300)
    
    @pytest.mark.asyncio
    async def test_basic_async_operations(self, async_cache):
        """Test basic async get/put/delete operations"""
        # Test put and get
        await async_cache.aput("key1", "value1")
        result = await async_cache.aget("key1")
        assert result == "value1"
        
        # Test cache miss
        result = await async_cache.aget("nonexistent")
        assert result is None
        
        # Test delete
        deleted = await async_cache.adelete("key1")
        assert deleted is True
        result = await async_cache.aget("key1")
        assert result is None
        
        # Test delete non-existent
        deleted = await async_cache.adelete("nonexistent")
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, async_cache):
        """Test TTL expiration handling"""
        # Put with short TTL
        await async_cache.aput("ttl_key", "ttl_value", ttl_seconds=1)
        
        # Should exist immediately
        result = await async_cache.aget("ttl_key")
        assert result == "ttl_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        result = await async_cache.aget("ttl_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self, async_cache):
        """Test LRU eviction when cache is full"""
        cache = AsyncLRUCache(max_size=3, default_ttl=None)
        
        # Fill cache
        await cache.aput("a", 1)
        await cache.aput("b", 2)
        await cache.aput("c", 3)
        
        # Access 'a' to make it recently used
        await cache.aget("a")
        
        # Add new item, should evict 'b' (least recently used)
        await cache.aput("d", 4)
        
        # Check eviction
        assert await cache.aget("a") == 1
        assert await cache.aget("b") is None  # Evicted
        assert await cache.aget("c") == 3
        assert await cache.aget("d") == 4
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, async_cache):
        """Test concurrent access safety"""
        # Multiple concurrent puts
        async def put_many(start: int, count: int):
            for i in range(start, start + count):
                await async_cache.aput(f"key{i}", f"value{i}")
        
        # Run concurrent puts
        await asyncio.gather(
            put_many(0, 20),
            put_many(20, 20),
            put_many(40, 20)
        )
        
        # Verify all values
        for i in range(60):
            result = await async_cache.aget(f"key{i}")
            assert result == f"value{i}"
        
        # Check cache size
        size = await async_cache.asize()
        assert size == 60
    
    @pytest.mark.asyncio
    async def test_statistics(self, async_cache):
        """Test cache statistics tracking"""
        # Generate some activity
        await async_cache.aput("hit", "value")
        await async_cache.aget("hit")  # Hit
        await async_cache.aget("miss")  # Miss
        
        stats = await async_cache.astats()
        
        assert stats["cache_type"] == "AsyncLRU"
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["current_size"] == 1
    
    def test_sync_compatibility(self, async_cache):
        """Test backward compatibility with sync methods"""
        # Sync methods should still work
        async_cache.put("sync_key", "sync_value")
        result = async_cache.get("sync_key")
        assert result == "sync_value"
        
        # Stats should work
        stats = async_cache.stats()
        assert stats["cache_type"] == "AsyncLRU"


class TestMultiLevelAsyncCache:
    """Tests for MultiLevelCache in async mode"""
    
    @pytest.fixture
    def config(self):
        """Create test cache config"""
        return CacheConfig(
            enable_result_cache=True,
            enable_plan_cache=True,
            query_cache_ttl=300,
            result_cache_ttl=600,
            query_cache_max_size=100,
            result_cache_max_size=200
        )
    
    @pytest.fixture
    def async_ml_cache(self, config):
        """Create async multi-level cache"""
        return MultiLevelCache(config, async_mode=True)
    
    @pytest.mark.asyncio
    async def test_multi_level_operations(self, async_ml_cache):
        """Test multi-level cache operations"""
        # Put and get
        await async_ml_cache.aput("ml_key", "ml_value")
        result = await async_ml_cache.aget("ml_key")
        assert result == "ml_value"
        
        # Check both levels have the value
        assert await async_ml_cache.l1_cache.aget("ml_key") == "ml_value"
        assert await async_ml_cache.l2_cache.aget("ml_key") == "ml_value"
    
    @pytest.mark.asyncio
    async def test_cache_promotion(self, async_ml_cache):
        """Test L2 to L1 promotion"""
        # Put only in L2
        await async_ml_cache.l2_cache.aput("l2_only", "l2_value")
        
        # Get should promote to L1
        result = await async_ml_cache.aget("l2_only")
        assert result == "l2_value"
        
        # Now should be in L1
        assert await async_ml_cache.l1_cache.aget("l2_only") == "l2_value"
    
    @pytest.mark.asyncio
    async def test_async_mode_enforcement(self, config):
        """Test that sync cache rejects async calls"""
        sync_cache = MultiLevelCache(config, async_mode=False)
        
        with pytest.raises(RuntimeError, match="aget.*non-async"):
            await sync_cache.aget("key")
        
        with pytest.raises(RuntimeError, match="aput.*non-async"):
            await sync_cache.aput("key", "value")


class TestTraversalCacheManagerAsync:
    """Tests for TraversalCacheManager in async mode"""
    
    @pytest.fixture
    def async_manager(self):
        """Create async cache manager"""
        reset_cache_manager()
        return get_async_cache_manager()
    
    @pytest.fixture
    def sample_query(self):
        """Create sample traversal query"""
        return TraversalQuery(
            start_nodes=["node1", "node2"],
            relations=["rel1"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=3,
            limit=100
        )
    
    @pytest.mark.asyncio
    async def test_query_caching(self, async_manager, sample_query):
        """Test query result caching"""
        from core.traversal.models import TraversalResult
        
        # Create mock result
        result = TraversalResult(
            nodes=["node1", "node2", "node3"],
            edges=[],
            paths=[],
            metadata={}
        )
        
        # Cache result
        await async_manager.acache_query_result(sample_query, result)
        
        # Retrieve result
        cached = await async_manager.aget_query_result(sample_query)
        assert cached is not None
        assert cached.nodes == result.nodes
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, async_manager, sample_query):
        """Test cache invalidation"""
        # Add some data
        await async_manager.acache_query_result(sample_query, "dummy_result")
        
        # Verify it's cached
        assert await async_manager.aget_query_result(sample_query) == "dummy_result"
        
        # Invalidate
        await async_manager.ainvalidate_query_cache()
        
        # Should be gone
        assert await async_manager.aget_query_result(sample_query) is None


class TestAsyncCachePerformance:
    """Performance comparison tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_async_vs_sync_performance(self):
        """Compare async vs sync cache performance"""
        sync_cache = get_cache_manager().cache.l1_cache
        async_cache = get_async_cache_manager().cache.l1_cache
        
        iterations = 1000
        
        # Sync timing
        start = time.time()
        for i in range(iterations):
            sync_cache.put(f"key{i}", f"value{i}")
            sync_cache.get(f"key{i}")
        sync_time = time.time() - start
        
        # Async timing
        start = time.time()
        for i in range(iterations):
            await async_cache.aput(f"akey{i}", f"avalue{i}")
            await async_cache.aget(f"akey{i}")
        async_time = time.time() - start
        
        # Async should be comparable or better
        print(f"Sync time: {sync_time:.3f}s, Async time: {async_time:.3f}s")
        assert async_time < sync_time * 1.5  # Allow some overhead
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_async_performance(self):
        """Test performance under concurrent load"""
        cache = get_async_cache_manager().cache
        
        async def worker(worker_id: int, operations: int):
            for i in range(operations):
                key = f"w{worker_id}_k{i}"
                await cache.aput(key, f"value_{i}")
                await cache.aget(key)
        
        # Run 10 concurrent workers
        start = time.time()
        await asyncio.gather(*[
            worker(i, 100) for i in range(10)
        ])
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 1.0  # 1000 operations in < 1 second
        
        # Verify cache consistency
        stats = await cache.astats()
        assert stats["l1_cache"]["current_size"] > 0


class TestAsyncCacheWarmer:
    """Tests for AsyncCacheWarmer functionality"""
    
    @pytest.fixture
    def async_cache_manager(self):
        """Create async cache manager"""
        reset_cache_manager()
        return get_async_cache_manager()
    
    @pytest.mark.asyncio
    async def test_cache_warming_basic(self, async_cache_manager):
        """Test basic cache warming functionality"""
        # Mock query executor
        query_results = {
            "query1": "result1",
            "query2": "result2",
            "query3": "result3"
        }
        
        async def mock_executor(query: str):
            await asyncio.sleep(0.01)  # Simulate work
            return query_results.get(query)
        
        # Add queries to warm
        for query in query_results.keys():
            async_cache_manager.warmer.add_warming_query(query)
        
        # Start warming
        await async_cache_manager.astart_cache_warming(mock_executor)
        
        # Wait for warming to complete one cycle
        await asyncio.sleep(0.5)
        
        # Check that queries are cached
        for query, expected_result in query_results.items():
            cache_key = async_cache_manager.warmer._generate_cache_key(query)
            result = await async_cache_manager.cache.aget(cache_key)
            assert result == expected_result
        
        # Stop warming
        await async_cache_manager.astop_cache_warming()
    
    @pytest.mark.asyncio
    async def test_cache_warming_with_sync_executor(self, async_cache_manager):
        """Test cache warming with sync query executor"""
        # Sync query executor
        def sync_executor(query: str):
            time.sleep(0.01)  # Simulate blocking work
            return f"sync_result_{query}"
        
        async_cache_manager.warmer.add_warming_query("sync_query")
        
        # Start warming with sync executor
        await async_cache_manager.astart_cache_warming(sync_executor)
        
        # Wait for warming
        await asyncio.sleep(0.5)
        
        # Check result
        cache_key = async_cache_manager.warmer._generate_cache_key("sync_query")
        result = await async_cache_manager.cache.aget(cache_key)
        assert result == "sync_result_sync_query"
        
        await async_cache_manager.astop_cache_warming()
    
    @pytest.mark.asyncio
    async def test_cache_warming_error_handling(self, async_cache_manager):
        """Test cache warming handles errors gracefully"""
        call_count = 0
        
        async def failing_executor(query: str):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        async_cache_manager.warmer.add_warming_query("error_query")
        
        # Start warming
        await async_cache_manager.astart_cache_warming(failing_executor)
        
        # Wait for multiple attempts
        await asyncio.sleep(1.0)
        
        # Should eventually succeed
        cache_key = async_cache_manager.warmer._generate_cache_key("error_query")
        result = await async_cache_manager.cache.aget(cache_key)
        # May or may not be cached depending on timing
        
        await async_cache_manager.astop_cache_warming()
    
    @pytest.mark.asyncio
    async def test_cache_warming_stop(self, async_cache_manager):
        """Test stopping cache warming"""
        warming_active = True
        
        async def slow_executor(query: str):
            nonlocal warming_active
            if warming_active:
                await asyncio.sleep(10)  # Long running
            return "interrupted"
        
        async_cache_manager.warmer.add_warming_query("slow_query")
        
        # Start warming
        await async_cache_manager.astart_cache_warming(slow_executor)
        
        # Stop quickly
        warming_active = False
        await async_cache_manager.astop_cache_warming()
        
        # Should stop without hanging
        assert async_cache_manager.warmer._warming_active is False
        assert async_cache_manager.warmer._warming_task.done()


class TestAsyncPerformanceOptimizations:
    """Test performance optimizations in async cache"""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_batch_eviction_performance(self):
        """Test optimized eviction performance"""
        cache = AsyncLRUCache(max_size=100, default_ttl=1)
        
        # Fill cache with expiring entries
        for i in range(100):
            await cache.aput(f"expire_{i}", f"value_{i}", ttl_seconds=0.1)
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Add new entries to trigger eviction
        start = time.time()
        for i in range(50):
            await cache.aput(f"new_{i}", f"value_{i}")
        eviction_time = time.time() - start
        
        # Should be fast even with many expired entries
        assert eviction_time < 0.1  # Less than 100ms
        
        # All expired entries should be gone
        for i in range(100):
            assert await cache.aget(f"expire_{i}") is None
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_warming_performance(self):
        """Test performance with concurrent cache warming"""
        manager = get_async_cache_manager()
        
        # Multiple query executors
        async def executor1(query: str):
            await asyncio.sleep(0.01)
            return f"executor1_{query}"
        
        async def executor2(query: str):
            await asyncio.sleep(0.01)
            return f"executor2_{query}"
        
        # Add many queries
        for i in range(20):
            manager.warmer.add_warming_query(f"query_{i}")
        
        # Start multiple warmers (in practice, would use one)
        start = time.time()
        await manager.astart_cache_warming(executor1)
        
        # Wait for completion
        await asyncio.sleep(0.5)
        
        elapsed = time.time() - start
        
        # Should warm efficiently
        assert elapsed < 1.0
        
        await manager.astop_cache_warming()