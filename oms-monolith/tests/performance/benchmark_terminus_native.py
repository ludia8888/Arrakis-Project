#!/usr/bin/env python3
"""
Performance Benchmark Suite for TerminusDB Native vs Legacy Implementation
Measures and compares performance across key operations
"""
import asyncio
import time
import statistics
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import settings
from core.branch.service_factory import BranchServiceFactory, get_branch_service
from core.merge.merge_factory import get_merge_engine
from core.monitoring.metrics import operation_histogram, operation_counter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Comprehensive performance benchmarking for TerminusDB migration"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operations": {},
            "summary": {}
        }
        
    async def setup(self):
        """Initialize test environment"""
        logger.info("Setting up benchmark environment...")
        
        # Create test branches for benchmarking
        self.test_branches = []
        for i in range(10):
            branch_name = f"benchmark_branch_{i}"
            self.test_branches.append(branch_name)
            
    async def cleanup(self):
        """Clean up test data"""
        logger.info("Cleaning up benchmark environment...")
        
        # Delete test branches
        service = get_branch_service()
        for branch in self.test_branches:
            try:
                await service.delete_branch(branch)
            except:
                pass  # Branch might not exist
                
    async def benchmark_operation(
        self, 
        operation_name: str, 
        operation_func, 
        iterations: int = 100,
        warmup: int = 10
    ) -> Dict[str, Any]:
        """Benchmark a single operation"""
        logger.info(f"Benchmarking {operation_name} ({iterations} iterations)...")
        
        # Warmup runs
        for _ in range(warmup):
            await operation_func()
            
        # Actual benchmark
        times = []
        errors = 0
        
        for i in range(iterations):
            try:
                start = time.perf_counter()
                await operation_func()
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                
                # Record metric
                operation_histogram.labels(
                    operation=operation_name,
                    implementation="native" if settings.USE_TERMINUS_NATIVE_BRANCH else "legacy"
                ).observe(elapsed)
                
            except Exception as e:
                errors += 1
                logger.error(f"Error in {operation_name}: {e}")
                
        if times:
            return {
                "count": len(times),
                "errors": errors,
                "min": min(times),
                "max": max(times),
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "stdev": statistics.stdev(times) if len(times) > 1 else 0,
                "p95": sorted(times)[int(len(times) * 0.95)] if times else 0,
                "p99": sorted(times)[int(len(times) * 0.99)] if times else 0
            }
        else:
            return {"count": 0, "errors": errors}
            
    async def benchmark_branch_operations(self):
        """Benchmark branch-related operations"""
        results = {}
        
        # Test branch creation
        branch_counter = 0
        async def create_branch():
            nonlocal branch_counter
            service = get_branch_service()
            branch_name = f"perf_test_{branch_counter}"
            branch_counter += 1
            result = await service.create_branch("main", branch_name, "Performance test branch")
            # Clean up immediately
            await service.delete_branch(result)
            
        results["create_branch"] = await self.benchmark_operation(
            "create_branch", 
            create_branch,
            iterations=50
        )
        
        # Test branch listing
        async def list_branches():
            service = get_branch_service()
            branches = await service.list_branches()
            return len(branches)
            
        results["list_branches"] = await self.benchmark_operation(
            "list_branches",
            list_branches,
            iterations=100
        )
        
        # Test diff generation
        async def get_diff():
            service = get_branch_service()
            # Assume we have at least main branch
            diff = await service.get_diff("main", "main")
            return diff
            
        results["get_diff"] = await self.benchmark_operation(
            "get_diff",
            get_diff,
            iterations=50
        )
        
        return results
        
    async def benchmark_merge_operations(self):
        """Benchmark merge-related operations"""
        results = {}
        
        # Create test branches for merging
        service = get_branch_service()
        merge_engine = get_merge_engine()
        
        # Test fast-forward merge
        merge_counter = 0
        async def fast_forward_merge():
            nonlocal merge_counter
            source = f"ff_source_{merge_counter}"
            merge_counter += 1
            
            # Create source branch
            await service.create_branch("main", source)
            
            # Merge (should be fast-forward)
            result = await merge_engine.merge(source, "main", "benchmark_user")
            
            # Cleanup
            await service.delete_branch(source)
            return result
            
        results["fast_forward_merge"] = await self.benchmark_operation(
            "fast_forward_merge",
            fast_forward_merge,
            iterations=30
        )
        
        # Test conflict detection
        async def detect_conflicts():
            # This would need actual conflicting branches
            # For now, just test the diff operation
            diff = await service.get_diff("main", "main")
            return diff
            
        results["conflict_detection"] = await self.benchmark_operation(
            "conflict_detection",
            detect_conflicts,
            iterations=50
        )
        
        return results
        
    async def compare_implementations(self):
        """Run benchmarks for both legacy and native implementations"""
        comparison = {
            "legacy": {},
            "native": {}
        }
        
        # Benchmark legacy implementation
        logger.info("Benchmarking LEGACY implementation...")
        settings.USE_TERMINUS_NATIVE_BRANCH = False
        settings.USE_UNIFIED_MERGE_ENGINE = False
        BranchServiceFactory.reset()
        
        comparison["legacy"]["branch_ops"] = await self.benchmark_branch_operations()
        comparison["legacy"]["merge_ops"] = await self.benchmark_merge_operations()
        
        # Benchmark native implementation
        logger.info("Benchmarking NATIVE implementation...")
        settings.USE_TERMINUS_NATIVE_BRANCH = True
        settings.USE_UNIFIED_MERGE_ENGINE = True
        BranchServiceFactory.reset()
        
        comparison["native"]["branch_ops"] = await self.benchmark_branch_operations()
        comparison["native"]["merge_ops"] = await self.benchmark_merge_operations()
        
        # Calculate improvements
        improvements = {}
        for op_category in ["branch_ops", "merge_ops"]:
            improvements[op_category] = {}
            for op_name in comparison["legacy"][op_category]:
                legacy_mean = comparison["legacy"][op_category][op_name].get("mean", 0)
                native_mean = comparison["native"][op_category][op_name].get("mean", 0)
                
                if legacy_mean > 0 and native_mean > 0:
                    improvement = ((legacy_mean - native_mean) / legacy_mean) * 100
                    improvements[op_category][op_name] = {
                        "legacy_mean": legacy_mean,
                        "native_mean": native_mean,
                        "improvement_percent": improvement,
                        "speedup": legacy_mean / native_mean
                    }
                    
        return {
            "comparison": comparison,
            "improvements": improvements
        }
        
    def generate_report(self, results: Dict[str, Any]):
        """Generate a human-readable performance report"""
        report = []
        report.append("=" * 80)
        report.append("TERMINUS NATIVE PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {results['timestamp']}")
        report.append("")
        
        # Summary of improvements
        report.append("PERFORMANCE IMPROVEMENTS SUMMARY")
        report.append("-" * 40)
        
        improvements = results.get("improvements", {})
        for category, ops in improvements.items():
            report.append(f"\n{category.upper()}:")
            for op_name, stats in ops.items():
                report.append(f"  {op_name}:")
                report.append(f"    Legacy: {stats['legacy_mean']*1000:.2f}ms")
                report.append(f"    Native: {stats['native_mean']*1000:.2f}ms")
                report.append(f"    Improvement: {stats['improvement_percent']:.1f}%")
                report.append(f"    Speedup: {stats['speedup']:.2f}x faster")
                
        # Detailed statistics
        report.append("\n" + "=" * 80)
        report.append("DETAILED STATISTICS")
        report.append("=" * 80)
        
        comparison = results.get("comparison", {})
        for impl, impl_results in comparison.items():
            report.append(f"\n{impl.upper()} IMPLEMENTATION:")
            report.append("-" * 40)
            
            for category, ops in impl_results.items():
                report.append(f"\n{category}:")
                for op_name, stats in ops.items():
                    if stats.get("count", 0) > 0:
                        report.append(f"  {op_name}:")
                        report.append(f"    Samples: {stats['count']}")
                        report.append(f"    Errors: {stats['errors']}")
                        report.append(f"    Mean: {stats['mean']*1000:.2f}ms")
                        report.append(f"    Median: {stats['median']*1000:.2f}ms")
                        report.append(f"    Min: {stats['min']*1000:.2f}ms")
                        report.append(f"    Max: {stats['max']*1000:.2f}ms")
                        report.append(f"    StdDev: {stats['stdev']*1000:.2f}ms")
                        report.append(f"    P95: {stats['p95']*1000:.2f}ms")
                        report.append(f"    P99: {stats['p99']*1000:.2f}ms")
                        
        return "\n".join(report)
        
    async def run_full_benchmark(self):
        """Run complete benchmark suite"""
        try:
            await self.setup()
            
            # Run comparison benchmarks
            results = await self.compare_implementations()
            results["timestamp"] = self.results["timestamp"]
            
            # Generate report
            report = self.generate_report(results)
            print(report)
            
            # Save results
            output_dir = "benchmark_results"
            os.makedirs(output_dir, exist_ok=True)
            
            # Save JSON results
            json_path = os.path.join(
                output_dir, 
                f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2)
                
            # Save text report
            report_path = os.path.join(
                output_dir,
                f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            with open(report_path, 'w') as f:
                f.write(report)
                
            logger.info(f"Results saved to {json_path} and {report_path}")
            
        finally:
            await self.cleanup()


async def main():
    """Run performance benchmarks"""
    benchmark = PerformanceBenchmark()
    await benchmark.run_full_benchmark()


if __name__ == "__main__":
    asyncio.run(main())