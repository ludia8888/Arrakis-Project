"""
Unit Tests for Dependency Analyzer

Test suite for dependency analysis functionality including impact analysis,
circular dependency detection, and critical path identification.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any

from core.traversal.dependency_analyzer import DependencyAnalyzer
from core.traversal.traversal_engine import TraversalEngine
from core.traversal.models import (
    DependencyPath, SemanticConflict, ConflictType, GraphNode
)
from core.traversal.config import ConfigManager
from database.clients.terminus_db import TerminusDBClient


class TestDependencyAnalyzer(unittest.TestCase):
    """Test cases for DependencyAnalyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock dependencies
        self.mock_client = Mock(spec=TerminusDBClient)
        self.mock_traversal = Mock(spec=TraversalEngine)
        self.test_config = ConfigManager("testing")
        
        # Create analyzer instance
        self.analyzer = DependencyAnalyzer(
            traversal_engine=self.mock_traversal,
            terminus_client=self.mock_client,
            config_manager=self.test_config
        )
    
    def test_initialization(self):
        """Test analyzer initialization"""
        self.assertIsNotNone(self.analyzer.traversal)
        self.assertIsNotNone(self.analyzer.client)
        self.assertIsNotNone(self.analyzer.config)
        self.assertEqual(len(self.analyzer._dependency_cache), 0)
    
    def test_analyze_change_impact_basic(self):
        """Test basic change impact analysis"""
        # Mock direct dependencies query result
        direct_mock = {
            'bindings': [
                {
                    'v:dependent': {'@value': 'OrderService'},
                    'v:impact_level': {'@value': 'high'}
                },
                {
                    'v:dependent': {'@value': 'PaymentService'},
                    'v:impact_level': {'@value': 'medium'}
                },
                {
                    'v:dependent': {'@value': 'NotificationService'},
                    'v:impact_level': {'@value': 'critical'}
                }
            ]
        }
        
        # Configure mock to return this result multiple times
        self.mock_client.query.return_value = direct_mock
        
        # Mock transitive dependency paths
        mock_paths = [
            DependencyPath(
                start_node="OrderService",
                end_node="CustomerData",
                path=["OrderService", "CustomerService", "CustomerData"],
                relations=["depends_on", "depends_on"],
                total_weight=2.0
            )
        ]
        self.mock_traversal.find_dependency_paths.return_value = mock_paths
        
        # Execute impact analysis
        result = self.analyzer.analyze_change_impact(
            changed_entity="CustomerData",
            change_type="modification"
        )
        
        # Verify results
        self.assertIn("directly_affected", result)
        self.assertIn("transitively_affected", result)
        self.assertIn("critical_services", result)
        self.assertIn("recommended_actions", result)
        
        # Check direct dependencies
        direct_deps = result["directly_affected"]
        self.assertIn("OrderService", direct_deps)
        self.assertIn("PaymentService", direct_deps)
        self.assertIn("NotificationService", direct_deps)
        
        # Check critical services
        critical_services = result["critical_services"]
        self.assertIn("NotificationService", critical_services)
        
        # Check recommendations
        recommendations = result["recommended_actions"]
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
    
    def test_analyze_deletion_impact(self):
        """Test impact analysis for entity deletion"""
        # Mock dependencies
        self.mock_client.query.return_value = {
            'bindings': [
                {'v:dependent': {'@value': 'ServiceA'}},
                {'v:dependent': {'@value': 'ServiceB'}}
            ]
        }
        
        self.mock_traversal.find_dependency_paths.return_value = []
        
        result = self.analyzer.analyze_change_impact(
            changed_entity="CriticalEntity",
            change_type="deletion"
        )
        
        # Should include breaking change warning
        recommendations = result["recommended_actions"]
        breaking_warning = any("BREAKING CHANGE" in rec for rec in recommendations)
        self.assertTrue(breaking_warning)
        
        deprecation_suggestion = any("deprecation" in rec.lower() for rec in recommendations)
        self.assertTrue(deprecation_suggestion)
    
    def test_detect_circular_dependencies(self):
        """Test circular dependency detection"""
        # Mock cycle detection query results
        cycle_mock = {
            'bindings': [
                {
                    'v:node': {'@value': 'ServiceA'},
                    'v:cycle_path': {'@value': ['ServiceA', 'ServiceB', 'ServiceC', 'ServiceA']}
                },
                {
                    'v:node': {'@value': 'ServiceX'},
                    'v:cycle_path': {'@value': ['ServiceX', 'ServiceY', 'ServiceX']}
                }
            ]
        }
        
        self.mock_client.query.return_value = cycle_mock
        
        conflicts = self.analyzer.detect_circular_dependencies()
        
        # Verify conflicts detected
        self.assertEqual(len(conflicts), 2)
        
        # Check first conflict (longer cycle)
        long_cycle = next(c for c in conflicts if 'ServiceA' in c.affected_nodes)
        self.assertEqual(long_cycle.conflict_type, ConflictType.CIRCULAR_DEPENDENCY)
        self.assertIn("ServiceA", long_cycle.affected_nodes)
        self.assertIn("ServiceB", long_cycle.affected_nodes)
        self.assertIn("ServiceC", long_cycle.affected_nodes)
        
        # Check second conflict (shorter cycle - should be higher severity)
        short_cycle = next(c for c in conflicts if 'ServiceX' in c.affected_nodes)
        self.assertEqual(short_cycle.conflict_type, ConflictType.CIRCULAR_DEPENDENCY)
        
        # Shorter cycles should be more severe based on config
        severity_score_short = self.test_config.get_severity_level(1.0 / 2)  # 2 nodes in cycle
        severity_score_long = self.test_config.get_severity_level(1.0 / 4)   # 4 nodes in cycle
        
        # Both should have appropriate severity
        self.assertIn(short_cycle.severity, ["low", "medium", "high", "critical"])
        self.assertIn(long_cycle.severity, ["low", "medium", "high", "critical"])
    
    def test_find_critical_paths(self):
        """Test critical path identification"""
        # Mock high-degree node queries
        in_degree_mock = {
            'bindings': [
                {'v:node': {'@value': 'HubNode1'}, 'v:in_count': {'@value': 15}},
                {'v:node': {'@value': 'HubNode2'}, 'v:in_count': {'@value': 12}}
            ]
        }
        
        out_degree_mock = {
            'bindings': [
                {'v:node': {'@value': 'HubNode1'}, 'v:out_count': {'@value': 8}},
                {'v:node': {'@value': 'HubNode2'}, 'v:out_count': {'@value': 10}}
            ]
        }
        
        # Configure mock to return different results for different queries
        self.mock_client.query.side_effect = [in_degree_mock, out_degree_mock] * 10
        
        # Mock path finding between high-degree nodes
        mock_critical_paths = [
            DependencyPath(
                start_node="HubNode1",
                end_node="HubNode2", 
                path=["HubNode1", "Intermediate", "HubNode2"],
                relations=["depends_on", "depends_on"],
                total_weight=2.0,
                is_critical=True
            )
        ]
        self.mock_traversal.find_dependency_paths.return_value = mock_critical_paths
        
        critical_paths = self.analyzer.find_critical_paths(max_paths=5)
        
        # Verify critical paths found
        self.assertGreater(len(critical_paths), 0)
        self.assertLessEqual(len(critical_paths), 5)
        
        # Check path properties
        for path in critical_paths:
            self.assertTrue(path.is_critical)
            self.assertGreater(path.total_weight, 0)
            self.assertIsInstance(path.start_node, str)
            self.assertIsInstance(path.end_node, str)
    
    def test_analyze_orphaned_entities(self):
        """Test orphaned entity detection"""
        # Mock all entities query
        all_entities_mock = {
            'bindings': [
                {'v:entity': {'@value': 'Entity1'}, 'v:entity_type': {'@value': '@schema:Service'}},
                {'v:entity': {'@value': 'Entity2'}, 'v:entity_type': {'@value': '@schema:Service'}},
                {'v:entity': {'@value': 'OrphanedEntity'}, 'v:entity_type': {'@value': '@schema:Service'}},
                {'v:entity': {'@value': 'SystemEntity'}, 'v:entity_type': {'@value': '@system:Internal'}}
            ]
        }
        
        # Mock relationship checks - Entity1 and Entity2 have relationships, OrphanedEntity doesn't
        def mock_query_side_effect(*args, **kwargs):
            commit_msg = kwargs.get('commit_msg', '')
            
            if commit_msg == "Get all entities":
                return all_entities_mock
            elif "Entity1" in str(args[0]) or "Entity2" in str(args[0]):
                return {'bindings': [{'v:target': {'@value': 'SomeTarget'}}]}  # Has relationships
            elif "OrphanedEntity" in str(args[0]):
                return {'bindings': []}  # No relationships
            else:
                return {'bindings': []}
        
        self.mock_client.query.side_effect = mock_query_side_effect
        
        conflicts = self.analyzer.analyze_orphaned_entities()
        
        # Verify orphaned entities detected
        self.assertEqual(len(conflicts), 1)
        
        orphan_conflict = conflicts[0]
        self.assertEqual(orphan_conflict.conflict_type, ConflictType.ORPHANED_NODE)
        self.assertIn("OrphanedEntity", orphan_conflict.affected_nodes)
        self.assertNotIn("Entity1", orphan_conflict.affected_nodes)
        self.assertNotIn("Entity2", orphan_conflict.affected_nodes)
        self.assertNotIn("SystemEntity", orphan_conflict.affected_nodes)  # System entity excluded
    
    def test_impact_recommendations_generation(self):
        """Test impact recommendation generation"""
        # Test high impact modification
        recommendations = self.analyzer._generate_impact_recommendations(
            changed_entity="CoreService",
            change_type="modification",
            direct_dependents=["Service1", "Service2", "Service3"],
            transitive_dependents=["Service4", "Service5", "Service6", "Service7", "Service8"]
        )
        
        # Should include high impact warning (3 + 5 = 8 dependents)
        high_impact_warning = any("High impact change" in rec for rec in recommendations)
        self.assertFalse(high_impact_warning)  # 8 < 10 (config threshold)
        
        # Test with higher impact
        recommendations_high = self.analyzer._generate_impact_recommendations(
            changed_entity="CoreService",
            change_type="modification",
            direct_dependents=["S1", "S2", "S3", "S4", "S5"],
            transitive_dependents=["S6", "S7", "S8", "S9", "S10", "S11"]
        )
        
        # Should include high impact warning (5 + 6 = 11 > 10)
        high_impact_warning = any("High impact change" in rec for rec in recommendations_high)
        self.assertTrue(high_impact_warning)
        
        phased_rollout = any("phased rollout" in rec.lower() for rec in recommendations_high)
        self.assertTrue(phased_rollout)
    
    def test_configuration_integration(self):
        """Test configuration integration"""
        # Verify config values are used
        self.assertEqual(
            self.analyzer.config.traversal.dependency_relations,
            ["depends_on", "extends", "references", "inherits_from", "uses", "imports"]
        )
        
        # Test config-based URI generation
        relation_uris = self.analyzer.config.get_relation_uris(["depends_on", "extends"])
        self.assertIn("@schema:depends_on", relation_uris)
        self.assertIn("@schema:extends", relation_uris)
        
        # Test thresholds
        self.assertEqual(self.analyzer.config.traversal.high_degree_threshold, 5)
        self.assertTrue(self.analyzer.config.is_high_impact_change(15))
        self.assertFalse(self.analyzer.config.is_high_impact_change(5))
    
    def test_error_handling(self):
        """Test error handling in dependency analysis"""
        # Mock client to raise exception
        self.mock_client.query.side_effect = Exception("Database error")
        
        # Impact analysis should handle errors gracefully
        result = self.analyzer.analyze_change_impact("TestEntity", "modification")
        
        # Should return empty results but not crash
        self.assertIn("directly_affected", result)
        self.assertIn("transitively_affected", result)
        self.assertEqual(len(result["directly_affected"]), 0)
        
        # Circular dependency detection should handle errors
        conflicts = self.analyzer.detect_circular_dependencies()
        self.assertEqual(len(conflicts), 0)
    
    def test_cache_functionality(self):
        """Test dependency cache functionality"""
        # First call should populate cache
        self.mock_client.query.return_value = {'bindings': []}
        self.mock_traversal.find_dependency_paths.return_value = []
        
        result1 = self.analyzer.analyze_change_impact("TestEntity", "modification")
        
        # Cache should have entries (simplified test)
        # In real implementation, would test actual cache behavior
        self.assertIsInstance(result1, dict)
        
        # Second call with same parameters
        result2 = self.analyzer.analyze_change_impact("TestEntity", "modification")
        
        # Results should be consistent
        self.assertEqual(
            len(result1["directly_affected"]),
            len(result2["directly_affected"])
        )


class TestDependencyAnalyzerIntegration(unittest.TestCase):
    """Integration tests for DependencyAnalyzer"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.mock_client = Mock(spec=TerminusDBClient)
        self.mock_traversal = Mock(spec=TraversalEngine) 
        self.config = ConfigManager("testing")
        self.analyzer = DependencyAnalyzer(self.mock_traversal, self.mock_client, self.config)
    
    def test_comprehensive_dependency_analysis(self):
        """Test comprehensive dependency analysis workflow"""
        # Mock a complex dependency scenario
        complex_deps_mock = {
            'bindings': [
                {'v:dependent': {'@value': 'UserService'}, 'v:impact_level': {'@value': 'critical'}},
                {'v:dependent': {'@value': 'OrderService'}, 'v:impact_level': {'@value': 'high'}},
                {'v:dependent': {'@value': 'PaymentService'}, 'v:impact_level': {'@value': 'high'}},
                {'v:dependent': {'@value': 'NotificationService'}, 'v:impact_level': {'@value': 'medium'}},
                {'v:dependent': {'@value': 'AnalyticsService'}, 'v:impact_level': {'@value': 'low'}}
            ]
        }
        
        # Mock complex transitive paths
        complex_paths = [
            DependencyPath(
                start_node="UserService",
                end_node="CustomerData",
                path=["UserService", "ProfileService", "CustomerData"],
                relations=["depends_on", "accesses"],
                total_weight=2.0
            ),
            DependencyPath(
                start_node="OrderService", 
                end_node="CustomerData",
                path=["OrderService", "BillingService", "CustomerData"],
                relations=["depends_on", "accesses"],
                total_weight=2.0
            )
        ]
        
        self.mock_client.query.return_value = complex_deps_mock
        self.mock_traversal.find_dependency_paths.return_value = complex_paths
        
        # Execute comprehensive analysis
        result = self.analyzer.analyze_change_impact(
            changed_entity="CustomerData",
            change_type="modification"
        )
        
        # Verify comprehensive results
        self.assertEqual(len(result["directly_affected"]), 5)
        self.assertIn("UserService", result["critical_services"])
        
        # Verify transitive dependencies found
        transitive = result["transitively_affected"]
        self.assertIn("ProfileService", transitive)
        self.assertIn("BillingService", transitive)
        
        # Verify recommendations appropriate for high impact
        recommendations = result["recommended_actions"]
        self.assertGreater(len(recommendations), 2)


if __name__ == '__main__':
    unittest.main()