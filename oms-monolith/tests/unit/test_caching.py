"""
Unit Tests for Enterprise Caching System

Test suite for multi-level caching, LRU cache implementation,
cache warming, and traversal cache manager.
"""

import pytest
import unittest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Any

from core.traversal.caching import (
    LRUCache, MultiLevelCache, CacheWarmer, TraversalCacheManager,
    CacheEntry, CacheLevel, EvictionPolicy
)
from core.traversal.models import TraversalQuery, TraversalResult, TraversalDirection
from core.traversal.config import CacheConfig


class TestCacheEntry(unittest.TestCase):
    """Test cases for CacheEntry"""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation and properties"""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl_seconds=300,
            size_bytes=100
        )
        
        self.assertEqual(entry.key, "test_key")
        self.assertEqual(entry.value, "test_value")
        self.assertEqual(entry.ttl_seconds, 300)
        self.assertEqual(entry.size_bytes, 100)
        self.assertEqual(entry.access_count, 0)
        self.assertFalse(entry.is_expired)
    
    def test_cache_entry_expiration(self):
        """Test cache entry TTL expiration"""
        # Create entry with very short TTL
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl_seconds=0.001  # 1ms
        )
        
        # Should not be expired immediately
        self.assertFalse(entry.is_expired)
        
        # Wait for expiration
        time.sleep(0.01)  # 10ms
        
        # Should now be expired
        self.assertTrue(entry.is_expired)
    
    def test_cache_entry_touch(self):
        """Test cache entry access tracking"""
        entry = CacheEntry(key="test", value="value")
        
        original_access_time = entry.last_accessed
        original_count = entry.access_count
        
        # Small delay to ensure time difference
        time.sleep(0.001)
        
        entry.touch()
        
        self.assertGreater(entry.last_accessed, original_access_time)
        self.assertEqual(entry.access_count, original_count + 1)
    
    def test_cache_entry_age(self):
        """Test cache entry age calculation"""
        entry = CacheEntry(key="test", value="value")
        
        # Should have minimal age
        self.assertGreaterEqual(entry.age_seconds, 0)
        self.assertLess(entry.age_seconds, 1.0)
        
        # Wait and check age increased
        time.sleep(0.01)
        self.assertGreater(entry.age_seconds, 0.01)


class TestLRUCache(unittest.TestCase):
    """Test cases for LRU Cache implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache = LRUCache(max_size=3, default_ttl=300)
    
    def test_basic_put_get(self):
        """Test basic put and get operations"""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertEqual(self.cache.get("key2"), "value2")
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        # Fill cache to capacity
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        self.cache.put("key3", "value3")
        
        # Access key1 to make it recently used
        self.cache.get("key1")
        
        # Add key4, should evict key2 (least recently used)
        self.cache.put("key4", "value4")
        
        self.assertEqual(self.cache.get("key1"), "value1")  # Still there
        self.assertIsNone(self.cache.get("key2"))  # Evicted
        self.assertEqual(self.cache.get("key3"), "value3")  # Still there
        self.assertEqual(self.cache.get("key4"), "value4")  # New entry
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        # Put entry with short TTL
        self.cache.put("short_ttl", "value", ttl_seconds=0.01)  # 10ms
        
        # Should be available immediately
        self.assertEqual(self.cache.get("short_ttl"), "value")
        
        # Wait for expiration
        time.sleep(0.02)  # 20ms
        
        # Should be expired and return None
        self.assertIsNone(self.cache.get("short_ttl"))
    
    def test_cache_statistics(self):
        """Test cache statistics tracking"""
        # Initial stats
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["current_size"], 0)
        
        # Add some entries and access them
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        # Hit
        self.cache.get("key1")
        
        # Miss
        self.cache.get("nonexistent")
        
        # Check updated stats
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["current_size"], 2)
        self.assertAlmostEqual(stats["hit_rate"], 0.5, places=2)
    
    def test_thread_safety(self):
        """Test thread safety of cache operations"""
        cache = LRUCache(max_size=100)
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(50):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"value_{i}"
                    
                    cache.put(key, value)
                    retrieved = cache.get(key)
                    
                    if retrieved == value:
                        results.append(True)
                    else:
                        results.append(False)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0)
        
        # Verify most operations succeeded
        success_rate = sum(results) / len(results)
        self.assertGreater(success_rate, 0.8)  # At least 80% success
    
    def test_cache_clear(self):
        """Test cache clearing"""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        self.assertEqual(self.cache.size(), 2)
        
        self.cache.clear()
        
        self.assertEqual(self.cache.size(), 0)
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))
        
        # Stats should be reset
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
    
    def test_cache_delete(self):
        """Test cache entry deletion"""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        # Delete existing key
        self.assertTrue(self.cache.delete("key1"))
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "value2")
        
        # Delete non-existent key
        self.assertFalse(self.cache.delete("nonexistent"))


class TestMultiLevelCache(unittest.TestCase):
    """Test cases for Multi-Level Cache"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = CacheConfig()
        self.cache = MultiLevelCache(self.config)
    
    def test_l1_cache_hit(self):
        """Test L1 cache hit"""
        self.cache.put("key1", "value1", "query_results")
        
        # Should hit L1 cache
        result = self.cache.get("key1", "query_results")
        self.assertEqual(result, "value1")
        
        # Check stats
        stats = self.cache.stats()
        self.assertGreater(stats["multi_level_stats"]["l1_hit_rate"], 0)
    
    def test_l2_cache_promotion(self):
        """Test L2 cache hit and promotion to L1"""
        # Put directly in L2 cache
        self.cache.l2_cache.put("key1", "value1")
        
        # Clear L1 cache to ensure L2 hit
        self.cache.l1_cache.clear()
        
        # Get should hit L2 and promote to L1
        result = self.cache.get("key1", "query_results")
        self.assertEqual(result, "value1")
        
        # Verify promotion to L1
        l1_result = self.cache.l1_cache.get("key1")
        self.assertEqual(l1_result, "value1")
    
    def test_cache_miss(self):
        """Test cache miss across all levels"""
        result = self.cache.get("nonexistent", "query_results")
        self.assertIsNone(result)
        
        # Check miss stats
        stats = self.cache.stats()
        self.assertGreaterEqual(stats["multi_level_stats"]["total_requests"], 1)
    
    def test_cache_type_preferences(self):
        """Test different cache type preferences"""
        # Query results should go to both L1 and L2
        self.cache.put("query_key", "query_value", "query_results")
        
        # Query plans should only go to L1
        self.cache.put("plan_key", "plan_value", "query_plans")
        
        # Verify L1 has both
        self.assertEqual(self.cache.l1_cache.get("query_key"), "query_value")
        self.assertEqual(self.cache.l1_cache.get("plan_key"), "plan_value")
        
        # Verify L2 only has query results
        self.assertEqual(self.cache.l2_cache.get("query_key"), "query_value")
        self.assertIsNone(self.cache.l2_cache.get("plan_key"))
    
    def test_comprehensive_stats(self):
        """Test comprehensive statistics"""
        # Add some data and access it
        self.cache.put("key1", "value1", "query_results")
        self.cache.put("key2", "value2", "query_plans")
        
        self.cache.get("key1")  # L1 hit
        self.cache.get("key2")  # L1 hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.stats()
        
        # Verify structure
        self.assertIn("multi_level_stats", stats)
        self.assertIn("l1_cache", stats)
        self.assertIn("l2_cache", stats)
        
        # Verify multi-level stats
        ml_stats = stats["multi_level_stats"]
        self.assertIn("l1_hit_rate", ml_stats)
        self.assertIn("total_requests", ml_stats)
        
        # Verify individual cache stats
        self.assertIn("cache_type", stats["l1_cache"])
        self.assertIn("hit_rate", stats["l1_cache"])


class TestTraversalCacheManager(unittest.TestCase):
    """Test cases for Traversal Cache Manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = CacheConfig()
        self.cache_manager = TraversalCacheManager(self.config)
    
    def test_query_result_caching(self):
        """Test query result caching"""
        # Create test query and result
        query = TraversalQuery(
            start_nodes=["Node1"],
            relations=["rel1"],
            max_depth=2
        )
        
        result = TraversalResult(
            query_id="test_query",
            nodes=[],
            edges=[], 
            paths=[],
            execution_time_ms=100.0
        )
        
        # Cache result
        self.cache_manager.cache_query_result(query, result)
        
        # Retrieve result
        cached_result = self.cache_manager.get_query_result(query)
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result.query_id, "test_query")
        self.assertEqual(cached_result.execution_time_ms, 100.0)
    
    def test_query_plan_caching(self):
        """Test query plan caching"""
        plan = {"cost": 100, "strategy": "direct"}
        fingerprint = "test_fingerprint_123"
        
        # Cache plan
        self.cache_manager.cache_query_plan(fingerprint, plan)
        
        # Retrieve plan
        cached_plan = self.cache_manager.get_query_plan(fingerprint)
        
        self.assertIsNotNone(cached_plan)
        self.assertEqual(cached_plan["cost"], 100)
        self.assertEqual(cached_plan["strategy"], "direct")
    
    def test_graph_metrics_caching(self):
        """Test graph metrics caching"""
        metrics = {
            "node_count": 1000,
            "edge_count": 1500,
            "density": 0.15
        }
        
        # Cache metrics
        self.cache_manager.cache_graph_metrics("global_metrics", metrics)
        
        # Retrieve metrics
        cached_metrics = self.cache_manager.get_graph_metrics("global_metrics")
        
        self.assertIsNotNone(cached_metrics)
        self.assertEqual(cached_metrics["node_count"], 1000)
        self.assertEqual(cached_metrics["density"], 0.15)
    
    def test_cache_key_generation(self):
        """Test cache key generation for queries"""
        query1 = TraversalQuery(
            start_nodes=["A", "B"],
            relations=["rel1", "rel2"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=3,
            filters={"status": "active"}
        )
        
        query2 = TraversalQuery(
            start_nodes=["B", "A"],  # Different order
            relations=["rel2", "rel1"],  # Different order
            direction=TraversalDirection.OUTBOUND,
            max_depth=3,
            filters={"status": "active"}
        )
        
        # Should generate same cache key
        key1 = self.cache_manager._generate_query_cache_key(query1)
        key2 = self.cache_manager._generate_query_cache_key(query2)
        
        self.assertEqual(key1, key2)
        
        # Different query should generate different key
        query3 = TraversalQuery(
            start_nodes=["A", "B"],
            relations=["rel1", "rel2"],
            direction=TraversalDirection.INBOUND,  # Different direction
            max_depth=3,
            filters={"status": "active"}
        )
        
        key3 = self.cache_manager._generate_query_cache_key(query3)
        self.assertNotEqual(key1, key3)
    
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        # Add some cached data
        query = TraversalQuery(
            start_nodes=["Node1"],
            relations=["rel1"],
            max_depth=1
        )
        
        result = TraversalResult(
            query_id="test",
            nodes=[],
            edges=[],
            paths=[],
            execution_time_ms=50.0
        )
        
        self.cache_manager.cache_query_result(query, result)
        
        # Verify cached
        self.assertIsNotNone(self.cache_manager.get_query_result(query))
        
        # Invalidate cache
        self.cache_manager.invalidate_query_cache()
        
        # Should be gone
        self.assertIsNone(self.cache_manager.get_query_result(query))
    
    def test_cache_statistics(self):
        """Test cache statistics reporting"""
        # Add some data to generate stats
        query = TraversalQuery(start_nodes=["N1"], relations=["r1"], max_depth=1)
        result = TraversalResult(query_id="test", nodes=[], edges=[], paths=[], execution_time_ms=10.0)
        
        self.cache_manager.cache_query_result(query, result)
        self.cache_manager.get_query_result(query)  # Generate hit
        
        stats = self.cache_manager.get_cache_statistics()
        
        # Verify structure
        self.assertIn("multi_level_stats", stats)
        self.assertIn("traversal_cache", stats)
        
        # Verify traversal-specific stats
        traversal_stats = stats["traversal_cache"]
        self.assertIn("result_cache_enabled", traversal_stats)
        self.assertIn("plan_cache_enabled", traversal_stats)
        self.assertIn("eviction_policy", traversal_stats)


class TestCacheWarmer(unittest.TestCase):
    """Test cases for Cache Warmer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = CacheConfig()
        self.config.enable_cache_warming = True
        self.config.cache_warming_queries = ["test_query_1", "test_query_2"]
        
        self.cache = MultiLevelCache(self.config)
        self.warmer = CacheWarmer(self.cache, self.config)
    
    def test_cache_warmer_initialization(self):
        """Test cache warmer initialization"""
        self.assertFalse(self.warmer._warming_active)
        self.assertEqual(len(self.warmer._warming_queries), 2)
        self.assertIn("test_query_1", self.warmer._warming_queries)
    
    def test_cache_warming_disabled(self):
        """Test cache warming when disabled"""
        config = CacheConfig()
        config.enable_cache_warming = False
        
        warmer = CacheWarmer(self.cache, config)
        
        # Mock query executor
        mock_executor = Mock(return_value="result")
        
        # Should not start warming
        warmer.start_warming(mock_executor)
        
        self.assertFalse(warmer._warming_active)
        self.assertIsNone(warmer._warming_thread)
    
    def test_add_warming_query(self):
        """Test adding warming queries"""
        initial_count = len(self.warmer._warming_queries)
        
        self.warmer.add_warming_query("new_query")
        
        self.assertEqual(len(self.warmer._warming_queries), initial_count + 1)
        self.assertIn("new_query", self.warmer._warming_queries)
        
        # Adding same query again should not duplicate
        self.warmer.add_warming_query("new_query")
        self.assertEqual(len(self.warmer._warming_queries), initial_count + 1)
    
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_cache_warming_execution(self, mock_sleep):
        """Test cache warming execution"""
        # Mock query executor
        executed_queries = []
        
        def mock_executor(query):
            executed_queries.append(query)
            return f"result_for_{query}"
        
        # Start warming
        self.warmer.start_warming(mock_executor)
        
        # Give warmer a moment to execute
        time.sleep(0.1)
        
        # Stop warming
        self.warmer.stop_warming()
        
        # Verify queries were executed
        self.assertGreater(len(executed_queries), 0)
        self.assertIn("test_query_1", executed_queries)
    
    def test_cache_key_generation(self):
        """Test cache key generation for warming"""
        key1 = self.warmer._generate_cache_key("test_query")
        key2 = self.warmer._generate_cache_key("test_query")
        key3 = self.warmer._generate_cache_key("different_query")
        
        # Same query should generate same key
        self.assertEqual(key1, key2)
        
        # Different query should generate different key
        self.assertNotEqual(key1, key3)
        
        # Key should have warming prefix
        self.assertTrue(key1.startswith("warming:"))


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for caching system"""
    
    def test_end_to_end_caching_workflow(self):
        """Test complete caching workflow"""
        # Create cache manager
        config = CacheConfig()
        cache_manager = TraversalCacheManager(config)
        
        # Create test query
        query = TraversalQuery(
            start_nodes=["Customer:123", "Customer:456"],
            relations=["has_order", "contains"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=3,
            limit=100,
            filters={"status": "active", "priority": "high"}
        )
        
        # Create test result
        result = TraversalResult(
            query_id="integration_test",
            nodes=[],
            edges=[],
            paths=[],
            execution_time_ms=250.0
        )
        
        # Cache the result
        cache_manager.cache_query_result(query, result, ttl_seconds=600)
        
        # Retrieve from cache
        cached_result = cache_manager.get_query_result(query)
        
        # Verify result
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result.query_id, "integration_test")
        self.assertEqual(cached_result.execution_time_ms, 250.0)
        
        # Test cache statistics
        stats = cache_manager.get_cache_statistics()
        self.assertGreater(stats["multi_level_stats"]["l1_hit_rate"], 0)
        
        # Test invalidation
        cache_manager.invalidate_query_cache()
        invalidated_result = cache_manager.get_query_result(query)
        self.assertIsNone(invalidated_result)
    
    def test_concurrent_cache_access(self):
        """Test concurrent cache access"""
        cache_manager = TraversalCacheManager()
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for i in range(20):
                    query = TraversalQuery(
                        start_nodes=[f"Node_{worker_id}_{i}"],
                        relations=["test_rel"],
                        max_depth=1
                    )
                    
                    result = TraversalResult(
                        query_id=f"worker_{worker_id}_query_{i}",
                        nodes=[],
                        edges=[],
                        paths=[],
                        execution_time_ms=10.0
                    )
                    
                    # Cache result
                    cache_manager.cache_query_result(query, result)
                    
                    # Retrieve result
                    cached = cache_manager.get_query_result(query)
                    
                    if cached and cached.query_id == result.query_id:
                        results.append(True)
                    else:
                        results.append(False)
                        
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors
        self.assertEqual(len(errors), 0)
        
        # Verify high success rate
        success_rate = sum(results) / len(results)
        self.assertGreater(success_rate, 0.9)


if __name__ == '__main__':
    unittest.main()