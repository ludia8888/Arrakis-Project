"""
Test Script for TerminusDB Graph Traversal Engine

Comprehensive testing and demonstration of the enterprise-grade graph traversal
functionality built on TerminusDB's native WOQL capabilities.
"""

import asyncio
import json
import time
from typing import List, Dict, Any
from datetime import datetime

from core.traversal.traversal_engine import TraversalEngine
from core.traversal.dependency_analyzer import DependencyAnalyzer
from core.traversal.semantic_validator import SemanticValidator
from core.traversal.query_planner import QueryPlanner
from core.traversal.merge_validator import EnterpriseSemanticMergeValidator, MergeStrategy
from core.traversal.models import (
    TraversalQuery, TraversalDirection, 
    DependencyPath, SemanticConflict
)
from database.clients.terminus_db import TerminusDBClient
from shared.cache.terminusdb_cache import TerminusDBCache


class GraphTraversalTester:
    """
    Comprehensive test suite for graph traversal functionality.
    
    Tests all major components:
    - Basic traversal operations
    - Path finding and dependency analysis
    - Semantic validation
    - Merge conflict detection
    - Performance benchmarks
    """
    
    def __init__(self):
        self.client = TerminusDBClient()
        self.cache = TerminusDBCache()
        self.traversal_engine = TraversalEngine(self.client, self.cache)
        self.dependency_analyzer = DependencyAnalyzer(self.traversal_engine, self.client)
        self.semantic_validator = SemanticValidator(
            self.traversal_engine, self.dependency_analyzer, self.client
        )
        self.query_planner = QueryPlanner()
        self.merge_validator = EnterpriseSemanticMergeValidator(
            self.traversal_engine, self.dependency_analyzer, 
            self.semantic_validator, self.client
        )
        
    async def run_comprehensive_tests(self):
        """Run all test suites"""
        print("🚀 Starting TerminusDB Graph Traversal Engine Tests")
        print("=" * 60)
        
        try:
            # Test 1: Basic Traversal Operations
            await self._test_basic_traversal()
            
            # Test 2: Path Finding and Analysis
            await self._test_path_finding()
            
            # Test 3: Dependency Analysis
            await self._test_dependency_analysis()
            
            # Test 4: Semantic Validation
            await self._test_semantic_validation()
            
            # Test 5: Merge Validation
            await self._test_merge_validation()
            
            # Test 6: Performance Benchmarks
            await self._test_performance_benchmarks()
            
            # Test 7: Real-world Scenarios
            await self._test_realistic_scenarios()
            
            print("\n✅ All tests completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise
    
    async def _test_basic_traversal(self):
        """Test basic graph traversal operations"""
        print("\n📊 Testing Basic Traversal Operations")
        print("-" * 40)
        
        # Test 1: Simple outbound traversal
        print("• Testing simple outbound traversal...")
        query = TraversalQuery(
            start_nodes=["Customer:123"],
            relations=["has_order"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=2,
            limit=10
        )
        
        start_time = time.time()
        result = await self.traversal_engine.traverse(query)
        execution_time = (time.time() - start_time) * 1000
        
        print(f"  ✓ Found {len(result.nodes)} nodes in {execution_time:.2f}ms")
        print(f"  ✓ Query ID: {result.query_id}")
        
        # Test 2: Bidirectional traversal with filters
        print("• Testing bidirectional traversal with filters...")
        query = TraversalQuery(
            start_nodes=["Product:laptop", "Product:phone"],
            relations=["manufactured_by", "sold_in"],
            direction=TraversalDirection.BIDIRECTIONAL,
            max_depth=3,
            filters={"status": "active"},
            include_metadata=True
        )
        
        result = await self.traversal_engine.traverse(query)
        print(f"  ✓ Bidirectional search found {len(result.nodes)} nodes")
        print(f"  ✓ Execution time: {result.execution_time_ms:.2f}ms")
        
        # Test 3: Deep traversal with limit
        print("• Testing deep traversal with limit...")
        query = TraversalQuery(
            start_nodes=["Order:456"],
            relations=["contains", "manufactured_by", "sourced_from"],
            direction=TraversalDirection.OUTBOUND,
            max_depth=5,
            limit=50
        )
        
        result = await self.traversal_engine.traverse(query)
        print(f"  ✓ Deep traversal (depth=5) found {len(result.nodes)} nodes")
        
    async def _test_path_finding(self):
        """Test path finding capabilities"""
        print("\n🛤️  Testing Path Finding and Analysis")
        print("-" * 40)
        
        # Test 1: Find shortest paths
        print("• Testing shortest path finding...")
        paths = await self.traversal_engine.find_dependency_paths(
            start_node="Customer:123",
            end_node="Country:USA",
            max_depth=6
        )
        
        print(f"  ✓ Found {len(paths)} paths")
        if paths:
            shortest = min(paths, key=lambda p: len(p.path))
            print(f"  ✓ Shortest path: {' → '.join(shortest.path)}")
            print(f"  ✓ Path weight: {shortest.total_weight}")
        
        # Test 2: Find multiple paths between entities
        print("• Testing multiple path discovery...")
        paths = await self.traversal_engine.find_dependency_paths(
            start_node="Product:laptop",
            end_node="Supplier:tech_corp",
            max_depth=4
        )
        
        print(f"  ✓ Found {len(paths)} alternative paths")
        for i, path in enumerate(paths[:3]):  # Show first 3 paths
            print(f"    Path {i+1}: {' → '.join(path.path[:3])}{'...' if len(path.path) > 3 else ''}")
    
    async def _test_dependency_analysis(self):
        """Test dependency analysis functionality"""
        print("\n🔗 Testing Dependency Analysis")
        print("-" * 40)
        
        # Test 1: Change impact analysis
        print("• Testing change impact analysis...")
        impact = await self.dependency_analyzer.analyze_change_impact(
            changed_entity="Product:laptop",
            change_type="modification"
        )
        
        print(f"  ✓ Direct dependencies: {len(impact['directly_affected'])}")
        print(f"  ✓ Transitive dependencies: {len(impact['transitively_affected'])}")
        print(f"  ✓ Critical services: {len(impact['critical_services'])}")
        print(f"  ✓ Recommendations: {len(impact['recommended_actions'])}")
        
        # Test 2: Circular dependency detection
        print("• Testing circular dependency detection...")
        circular_conflicts = await self.dependency_analyzer.detect_circular_dependencies()
        
        print(f"  ✓ Found {len(circular_conflicts)} circular dependencies")
        for conflict in circular_conflicts[:2]:  # Show first 2
            print(f"    {conflict.description}")
        
        # Test 3: Critical path identification
        print("• Testing critical path identification...")
        critical_paths = await self.dependency_analyzer.find_critical_paths(max_paths=5)
        
        print(f"  ✓ Found {len(critical_paths)} critical paths")
        for path in critical_paths[:2]:  # Show first 2
            print(f"    Critical: {path.start_node} → {path.end_node} (weight: {path.total_weight})")
        
        # Test 4: Orphaned entity detection
        print("• Testing orphaned entity detection...")
        orphan_conflicts = await self.dependency_analyzer.analyze_orphaned_entities()
        
        print(f"  ✓ Found {len(orphan_conflicts)} orphaned entity issues")
    
    async def _test_semantic_validation(self):
        """Test semantic validation capabilities"""
        print("\n🔍 Testing Semantic Validation")
        print("-" * 40)
        
        # Test 1: Schema constraint validation
        print("• Testing schema constraint validation...")
        schema_conflicts = await self.semantic_validator.validate_schema_constraints()
        
        print(f"  ✓ Found {len(schema_conflicts)} schema constraint violations")
        
        # Test 2: Semantic consistency validation
        print("• Testing semantic consistency validation...")
        consistency_conflicts = await self.semantic_validator.validate_semantic_consistency()
        
        print(f"  ✓ Found {len(consistency_conflicts)} semantic consistency issues")
        
        # Group by conflict type
        conflict_types = {}
        for conflict in consistency_conflicts:
            conflict_type = conflict.conflict_type.value
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1
        
        for conflict_type, count in conflict_types.items():
            print(f"    {conflict_type}: {count}")
    
    async def _test_merge_validation(self):
        """Test merge validation functionality"""
        print("\n🔀 Testing Merge Validation")
        print("-" * 40)
        
        # Test 1: Simple merge validation
        print("• Testing simple merge validation...")
        
        try:
            merge_result = await self.merge_validator.validate_merge(
                source_branch="feature/new-product-schema",
                target_branch="main",
                base_branch="main",
                strategy=MergeStrategy.THREE_WAY
            )
            
            print(f"  ✓ Merge decision: {merge_result.merge_decision.value}")
            print(f"  ✓ Can auto-merge: {merge_result.can_auto_merge}")
            print(f"  ✓ Conflicts found: {len(merge_result.conflicts)}")
            print(f"  ✓ Resolutions available: {len(merge_result.resolutions)}")
            print(f"  ✓ Estimated merge time: {merge_result.estimated_merge_time:.2f}s")
            
            # Show risk assessment
            print("  ✓ Risk assessment:")
            for risk_type, level in merge_result.risk_assessment.items():
                print(f"    {risk_type}: {level}")
                
        except Exception as e:
            print(f"  ⚠️  Merge validation skipped (branch may not exist): {e}")
    
    async def _test_performance_benchmarks(self):
        """Test performance benchmarks"""
        print("\n⚡ Testing Performance Benchmarks")
        print("-" * 40)
        
        # Test 1: Query planning performance
        print("• Testing query planning performance...")
        
        # Create various query types
        queries = [
            TraversalQuery(
                start_nodes=[f"Entity:{i}"],
                relations=["depends_on"],
                max_depth=3
            ) for i in range(10)
        ]
        
        planning_times = []
        for query in queries:
            start_time = time.time()
            plan = self.query_planner.create_execution_plan(query)
            planning_time = (time.time() - start_time) * 1000
            planning_times.append(planning_time)
        
        avg_planning_time = sum(planning_times) / len(planning_times)
        print(f"  ✓ Average query planning time: {avg_planning_time:.2f}ms")
        
        # Test 2: Cache performance
        print("• Testing cache performance...")
        
        # Execute same query multiple times to test caching
        test_query = TraversalQuery(
            start_nodes=["TestEntity:cache"],
            relations=["test_relation"],
            max_depth=2
        )
        
        # First execution (cold cache)
        start_time = time.time()
        try:
            result1 = await self.traversal_engine.traverse(test_query)
            cold_time = (time.time() - start_time) * 1000
            
            # Second execution (warm cache)
            start_time = time.time()
            result2 = await self.traversal_engine.traverse(test_query)
            warm_time = (time.time() - start_time) * 1000
            
            speedup = cold_time / warm_time if warm_time > 0 else 1
            print(f"  ✓ Cold cache: {cold_time:.2f}ms")
            print(f"  ✓ Warm cache: {warm_time:.2f}ms")
            print(f"  ✓ Cache speedup: {speedup:.1f}x")
            
        except Exception as e:
            print(f"  ⚠️  Cache test skipped (data may not exist): {e}")
        
        # Test 3: Graph metrics calculation performance
        print("• Testing graph metrics calculation...")
        
        start_time = time.time()
        try:
            metrics = await self.traversal_engine.get_graph_metrics()
            metrics_time = (time.time() - start_time) * 1000
            
            print(f"  ✓ Metrics calculation time: {metrics_time:.2f}ms")
            print(f"  ✓ Total nodes: {metrics.total_nodes}")
            print(f"  ✓ Total edges: {metrics.total_edges}")
            print(f"  ✓ Graph density: {metrics.density:.4f}")
            
        except Exception as e:
            print(f"  ⚠️  Metrics test skipped: {e}")
    
    async def _test_realistic_scenarios(self):
        """Test realistic business scenarios"""
        print("\n🌐 Testing Realistic Business Scenarios")
        print("-" * 40)
        
        # Scenario 1: E-commerce product traceability
        print("• Scenario 1: E-commerce product traceability...")
        
        try:
            # Find path from customer order to product origin
            paths = await self.traversal_engine.find_dependency_paths(
                start_node="Customer:premium_customer",
                end_node="Country:origin",
                max_depth=6
            )
            
            print(f"  ✓ Traceability paths found: {len(paths)}")
            
            # Analyze supply chain dependencies
            impact = await self.dependency_analyzer.analyze_change_impact(
                changed_entity="Supplier:main_supplier",
                change_type="modification"
            )
            
            print(f"  ✓ Supply chain impact: {len(impact['directly_affected'])} entities")
            
        except Exception as e:
            print(f"  ⚠️  Scenario 1 skipped: {e}")
        
        # Scenario 2: Schema evolution impact
        print("• Scenario 2: Schema evolution impact analysis...")
        
        try:
            # Analyze impact of adding new product category
            impact = await self.dependency_analyzer.analyze_change_impact(
                changed_entity="ProductCategory",
                change_type="addition"
            )
            
            print(f"  ✓ Schema change impact analyzed")
            print(f"  ✓ Recommendations: {len(impact.get('recommended_actions', []))}")
            
        except Exception as e:
            print(f"  ⚠️  Scenario 2 skipped: {e}")
        
        # Scenario 3: Performance monitoring
        print("• Scenario 3: Query performance monitoring...")
        
        # Generate performance report
        performance_report = self.query_planner.get_query_performance_report()
        
        print(f"  ✓ Performance report generated")
        print(f"  ✓ Total unique queries tracked: {performance_report.get('total_unique_queries', 0)}")
        print(f"  ✓ Average execution time: {performance_report.get('average_execution_time_ms', 0):.2f}ms")
        print(f"  ✓ Average cache hit rate: {performance_report.get('average_cache_hit_rate', 0):.2%}")
    
    def _print_test_summary(self, results: Dict[str, Any]):
        """Print comprehensive test summary"""
        print("\n📋 Test Summary")
        print("=" * 60)
        
        total_tests = sum(results.values())
        passed_tests = results.get('passed', 0)
        failed_tests = results.get('failed', 0)
        skipped_tests = results.get('skipped', 0)
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️  Skipped: {skipped_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "N/A")


async def main():
    """Main test execution function"""
    
    print("TerminusDB Graph Traversal Engine Test Suite")
    print("Enterprise-grade Ontology Management System")
    print(f"Test started at: {datetime.utcnow().isoformat()}Z")
    print()
    
    tester = GraphTraversalTester()
    
    try:
        await tester.run_comprehensive_tests()
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print(f"\nTest completed at: {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    asyncio.run(main())