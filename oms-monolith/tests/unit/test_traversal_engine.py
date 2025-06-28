"""
Unit Tests for TerminusDB Graph Traversal Engine

Comprehensive test suite for the refactored traversal engine with proper
TerminusDB SDK compatibility and configuration management.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any

from core.traversal.traversal_engine import TraversalEngine
from core.traversal.models import (
    TraversalQuery, TraversalResult, GraphNode, GraphEdge,
    DependencyPath, TraversalDirection, GraphMetrics
)
from core.traversal.config import TraversalConfig, ConfigManager
from database.clients.terminus_db import TerminusDBClient
from shared.cache.terminusdb_cache import TerminusDBCache


class TestTraversalEngine(unittest.TestCase):
    """Test cases for TraversalEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock dependencies
        self.mock_client = Mock(spec=TerminusDBClient)
        self.mock_cache = Mock(spec=TerminusDBCache)
        self.mock_metrics = Mock()
        
        # Create test config
        self.test_config = ConfigManager("testing")
        
        # Create engine instance
        self.engine = TraversalEngine(
            terminus_client=self.mock_client,
            config_manager=self.test_config,
            cache=self.mock_cache,
            metrics=self.mock_metrics
        )
    
    def test_initialization(self):
        """Test engine initialization"""
        self.assertIsNotNone(self.engine.client)
        self.assertIsNotNone(self.engine.config)
        self.assertEqual(self.engine.config.traversal.default_branch, "main")
        self.assertEqual(len(self.engine._query_cache), 0)
    
    def test_basic_traversal_query_construction(self):
        """Test basic traversal query construction"""
        # Create test query
        query = TraversalQuery(
            start_nodes=["Customer:123"],
            relations=["has_order"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=2,
            limit=10
        )
        
        # Mock query result
        mock_result = {
            'bindings': [
                {
                    'v:target': {'@value': 'Order:456'},
                    'v:target_type': {'@value': '@schema:Order'},
                    'v:target_label': {'@value': 'Order 456'}
                }
            ]
        }
        self.mock_client.query.return_value = mock_result
        
        # Execute traversal
        result = self.engine.traverse(query)
        
        # Verify results
        self.assertIsInstance(result, TraversalResult)
        self.assertEqual(len(result.nodes), 1)
        self.assertEqual(result.nodes[0].id, 'Order:456')
        self.assertEqual(result.nodes[0].type, '@schema:Order')
        
        # Verify client was called
        self.mock_client.query.assert_called_once()
        call_args = self.mock_client.query.call_args
        self.assertIn("Graph traversal query", call_args[1]['commit_msg'])
    
    def test_direct_traversal_woql_construction(self):
        """Test WOQL construction for direct (depth=1) traversal"""
        query = TraversalQuery(
            start_nodes=["Product:abc"],
            relations=["manufactured_by"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=1
        )
        
        # Test WOQL construction
        woql_query = self.engine._build_traversal_woql(query)
        
        # Verify the query is properly constructed
        self.assertIsNotNone(woql_query)
        
        # Mock execution
        self.mock_client.query.return_value = {'bindings': []}
        result = self.engine.traverse(query)
        
        self.assertIsInstance(result, TraversalResult)
        self.assertEqual(len(result.nodes), 0)
    
    def test_path_traversal_woql_construction(self):
        """Test WOQL construction for path-based (depth>1) traversal"""
        query = TraversalQuery(
            start_nodes=["Customer:123"],
            relations=["has_order", "contains"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=3
        )
        
        # Test WOQL construction
        woql_query = self.engine._build_traversal_woql(query)
        self.assertIsNotNone(woql_query)
        
        # Mock execution
        self.mock_client.query.return_value = {'bindings': []}\n        
        result = self.engine.traverse(query)
        self.assertIsInstance(result, TraversalResult)
    
    def test_bidirectional_traversal(self):
        """Test bidirectional traversal"""
        query = TraversalQuery(
            start_nodes=["Entity:central"],
            relations=["connected_to"],
            direction=TraversalDirection.BIDIRECTIONAL,
            max_depth=2
        )
        
        mock_result = {
            'bindings': [
                {
                    'v:target': {'@value': 'Entity:linked1'},
                    'v:target_type': {'@value': '@schema:Entity'},
                    'v:target_label': {'@value': 'Linked Entity 1'}
                },
                {
                    'v:target': {'@value': 'Entity:linked2'}, 
                    'v:target_type': {'@value': '@schema:Entity'},
                    'v:target_label': {'@value': 'Linked Entity 2'}
                }
            ]
        }
        self.mock_client.query.return_value = mock_result
        
        result = self.engine.traverse(query)
        
        self.assertEqual(len(result.nodes), 2)
        self.assertIn('Entity:linked1', [n.id for n in result.nodes])
        self.assertIn('Entity:linked2', [n.id for n in result.nodes])
    
    def test_traversal_with_filters(self):
        """Test traversal with property filters"""
        query = TraversalQuery(
            start_nodes=["Product:123"],
            relations=["has_review"],
            filters={"rating": "5", "verified": "true"},
            max_depth=1
        )
        
        mock_result = {
            'bindings': [
                {
                    'v:target': {'@value': 'Review:high_rated'},
                    'v:target_type': {'@value': '@schema:Review'},
                    'v:target_label': {'@value': 'High Rated Review'}
                }
            ]
        }
        self.mock_client.query.return_value = mock_result
        
        result = self.engine.traverse(query)
        
        self.assertEqual(len(result.nodes), 1)
        self.assertEqual(result.nodes[0].id, 'Review:high_rated')
    
    def test_dependency_path_finding(self):
        """Test dependency path finding functionality"""
        mock_result = {
            'bindings': [
                {
                    'v:path': {'@value': ['Customer:123', 'Order:456', 'Product:789']},
                    'v:path_length': {'@value': 3}
                }
            ]
        }
        self.mock_client.query.return_value = mock_result
        
        paths = self.engine.find_dependency_paths(
            start_node="Customer:123",
            end_node="Product:789",
            max_depth=5
        )
        
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].start_node, "Customer:123")
        self.assertEqual(paths[0].end_node, "Product:789")
        self.assertEqual(len(paths[0].path), 3)
        self.assertEqual(paths[0].total_weight, 3.0)
        self.assertTrue(paths[0].is_critical)  # Short path should be critical
    
    def test_graph_metrics_calculation(self):
        """Test graph metrics calculation"""
        # Mock node count query
        node_mock = {'bindings': [{'v:node_count': {'@value': 100}}]}
        # Mock edge count query  
        edge_mock = {'bindings': [{'v:edge_count': {'@value': 150}}]}
        
        # Configure mock to return different results for different queries
        self.mock_client.query.side_effect = [node_mock, edge_mock]
        
        metrics = self.engine.get_graph_metrics()
        
        self.assertIsInstance(metrics, GraphMetrics)
        self.assertEqual(metrics.total_nodes, 100)
        self.assertEqual(metrics.total_edges, 150)
        self.assertAlmostEqual(metrics.average_degree, 3.0, places=1)  # (2*150)/100
        self.assertGreater(metrics.density, 0)
    
    def test_cache_integration(self):
        """Test cache integration"""
        query = TraversalQuery(
            start_nodes=["Test:entity"],
            relations=["test_relation"],
            max_depth=1
        )
        
        # First call - should hit database
        mock_result = {'bindings': []}
        self.mock_client.query.return_value = mock_result
        
        result1 = self.engine.traverse(query)
        
        # Verify cache was populated
        cache_key = self.engine._generate_cache_key(query)
        self.assertIn(cache_key, self.engine._query_cache)
        
        # Second call - should hit cache
        result2 = self.engine.traverse(query)
        
        # Should be same result object from cache
        self.assertEqual(result1.query_id, result2.query_id)
        
        # Client should only be called once
        self.mock_client.query.assert_called_once()
    
    def test_error_handling(self):
        """Test error handling in traversal operations"""
        query = TraversalQuery(
            start_nodes=["Invalid:entity"],
            relations=["nonexistent_relation"],
            max_depth=1
        )
        
        # Mock client to raise exception
        self.mock_client.query.side_effect = Exception("Database connection failed")
        
        # Should raise RuntimeError
        with self.assertRaises(RuntimeError) as context:
            self.engine.traverse(query)
        
        self.assertIn("WOQL query execution failed", str(context.exception))
        
        # Verify metrics recorded error
        if self.mock_metrics:
            self.mock_metrics.record_traversal_error.assert_called_once()
    
    def test_configuration_integration(self):
        """Test configuration integration"""
        # Test that configuration values are used
        query = TraversalQuery(
            start_nodes=["Test:entity"],
            relations=["depends_on"],
            max_depth=1
        )
        
        # Mock successful query
        self.mock_client.query.return_value = {'bindings': []}
        
        # Execute query
        self.engine.traverse(query)
        
        # Verify configuration was used for relation URI generation
        expected_relations = self.test_config.get_relation_uris(["depends_on"])
        self.assertIn("@schema:depends_on", expected_relations)
    
    def test_query_cache_key_generation(self):
        """Test query cache key generation"""
        query1 = TraversalQuery(
            start_nodes=["A", "B"],
            relations=["rel1", "rel2"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=3
        )
        
        query2 = TraversalQuery(
            start_nodes=["B", "A"],  # Different order
            relations=["rel2", "rel1"],  # Different order
            direction=TraversalDirection.OUTBOUND,
            max_depth=3
        )
        
        # Should generate same cache key despite different order
        key1 = self.engine._generate_cache_key(query1)
        key2 = self.engine._generate_cache_key(query2)
        
        self.assertEqual(key1, key2)
        
        # Different query should generate different key
        query3 = TraversalQuery(
            start_nodes=["A", "B"],
            relations=["rel1", "rel2"],
            direction=TraversalDirection.INBOUND,  # Different direction
            max_depth=3
        )
        
        key3 = self.engine._generate_cache_key(query3)
        self.assertNotEqual(key1, key3)
    
    def test_result_metrics_calculation(self):
        """Test calculation of result metrics"""
        nodes = [
            GraphNode(id="n1", type="Type1", label="Node 1", depth=0),
            GraphNode(id="n2", type="Type1", label="Node 2", depth=1),
            GraphNode(id="n3", type="Type2", label="Node 3", depth=1)
        ]
        
        edges = [
            GraphEdge(source="n1", target="n2", relation="rel1"),
            GraphEdge(source="n1", target="n3", relation="rel2")
        ]
        
        metrics = self.engine._calculate_result_metrics(nodes, edges)
        
        self.assertEqual(metrics['node_count'], 3)
        self.assertEqual(metrics['edge_count'], 2)
        self.assertEqual(metrics['max_depth'], 1)
        self.assertEqual(metrics['unique_types'], 2)  # Type1 and Type2
        self.assertGreater(metrics['memory_usage_bytes'], 0)


class TestTraversalEngineIntegration(unittest.TestCase):
    """Integration tests for TraversalEngine"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.mock_client = Mock(spec=TerminusDBClient)
        self.config = ConfigManager("testing")
        self.engine = TraversalEngine(self.mock_client, self.config)
    
    def test_full_traversal_workflow(self):
        """Test complete traversal workflow"""
        # Simulate a complex query with multiple features
        query = TraversalQuery(
            start_nodes=["Customer:premium_123", "Customer:premium_456"],
            relations=["has_order", "contains", "manufactured_by"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=4,
            limit=50,
            filters={"status": "active", "priority": "high"},
            include_metadata=True
        )
        
        # Mock complex result
        mock_result = {
            'bindings': [
                {
                    'v:target': {'@value': 'Order:order_789'},
                    'v:target_type': {'@value': '@schema:Order'},
                    'v:target_label': {'@value': 'Premium Order 789'},
                    'v:created_at': {'@value': '2024-01-01T10:00:00Z'},
                    'v:modified_at': {'@value': '2024-01-02T15:30:00Z'}
                },
                {
                    'v:target': {'@value': 'Product:product_321'},
                    'v:target_type': {'@value': '@schema:Product'},
                    'v:target_label': {'@value': 'Premium Product 321'},
                    'v:created_at': {'@value': '2024-01-01T08:00:00Z'}
                }
            ]
        }
        self.mock_client.query.return_value = mock_result
        
        # Execute traversal
        result = self.engine.traverse(query)
        
        # Comprehensive result verification
        self.assertIsInstance(result, TraversalResult)
        self.assertEqual(len(result.nodes), 2)
        
        # Check first node
        order_node = next(n for n in result.nodes if n.id == 'Order:order_789')
        self.assertEqual(order_node.type, '@schema:Order')
        self.assertEqual(order_node.label, 'Premium Order 789')
        self.assertIn('created_at', order_node.properties)
        self.assertIn('modified_at', order_node.properties)
        
        # Check second node
        product_node = next(n for n in result.nodes if n.id == 'Product:product_321')
        self.assertEqual(product_node.type, '@schema:Product')
        self.assertIn('created_at', product_node.properties)
        
        # Check result metadata
        self.assertIsNotNone(result.query_id)
        self.assertGreater(result.execution_time_ms, 0)
        self.assertIsInstance(result.timestamp, type(result.timestamp))
        
        # Check metrics
        self.assertEqual(result.metrics['node_count'], 2)
        self.assertEqual(result.metrics['unique_types'], 2)
    
    def test_performance_under_load(self):
        """Test engine performance under multiple concurrent queries"""
        # Create multiple similar queries
        queries = []
        for i in range(10):
            query = TraversalQuery(
                start_nodes=[f"Entity:{i}"],
                relations=["test_relation"],
                max_depth=2
            )
            queries.append(query)
        
        # Mock consistent results
        self.mock_client.query.return_value = {'bindings': []}
        
        # Execute all queries
        results = []
        for query in queries:
            result = self.engine.traverse(query)
            results.append(result)
        
        # Verify all queries executed successfully
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIsInstance(result, TraversalResult)
            self.assertGreater(result.execution_time_ms, 0)
        
        # Verify caching worked (some queries should be cached)
        # Since we're using identical mock responses, cache should work
        self.assertGreaterEqual(len(self.engine._query_cache), 1)


if __name__ == '__main__':
    unittest.main()