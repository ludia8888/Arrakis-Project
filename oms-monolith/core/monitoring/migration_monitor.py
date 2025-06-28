"""
Migration Monitoring
Tracks the progress of TerminusDB native migration
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from collections import defaultdict
import asyncio

from prometheus_client import Counter, Gauge, Histogram
from shared.config import settings

logger = logging.getLogger(__name__)

# Prometheus metrics
operation_counter = Counter(
    'oms_branch_operations_total',
    'Total number of branch operations',
    ['operation', 'implementation']
)

operation_duration = Histogram(
    'oms_branch_operation_duration_seconds',
    'Duration of branch operations',
    ['operation', 'implementation']
)

native_usage_gauge = Gauge(
    'oms_terminus_native_usage_percentage',
    'Percentage of operations using TerminusDB native'
)

error_counter = Counter(
    'oms_branch_operation_errors_total',
    'Total number of operation errors',
    ['operation', 'implementation', 'error_type']
)


class MigrationMonitor:
    """
    Monitors the migration from legacy to TerminusDB native implementation
    """
    
    def __init__(self):
        self.metrics = defaultdict(int)
        self.start_time = datetime.utcnow()
        self.operation_times = defaultdict(list)
        
    async def track_operation(
        self, 
        operation: str, 
        implementation: str,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error_type: Optional[str] = None
    ):
        """
        Track a branch operation
        
        Args:
            operation: Operation name (create_branch, merge, etc.)
            implementation: Implementation used (native or legacy)
            duration_ms: Operation duration in milliseconds
            success: Whether operation succeeded
            error_type: Type of error if failed
        """
        # Update counters
        key = f"{operation}:{implementation}"
        self.metrics[key] += 1
        
        # Update Prometheus metrics
        operation_counter.labels(
            operation=operation,
            implementation=implementation
        ).inc()
        
        if duration_ms is not None:
            self.operation_times[key].append(duration_ms)
            operation_duration.labels(
                operation=operation,
                implementation=implementation
            ).observe(duration_ms / 1000.0)  # Convert to seconds
        
        if not success and error_type:
            error_counter.labels(
                operation=operation,
                implementation=implementation,
                error_type=error_type
            ).inc()
        
        # Update native usage percentage
        self._update_native_percentage()
        
        logger.info(
            f"Tracked operation: {operation} using {implementation} "
            f"(duration: {duration_ms}ms, success: {success})"
        )
    
    def _update_native_percentage(self):
        """Update the native usage percentage gauge"""
        total = sum(self.metrics.values())
        if total == 0:
            return
        
        native = sum(
            count for key, count in self.metrics.items() 
            if "native" in key.lower()
        )
        
        percentage = (native / total) * 100
        native_usage_gauge.set(percentage)
    
    def get_migration_progress(self) -> Dict[str, Any]:
        """
        Get current migration progress statistics
        
        Returns:
            Dictionary with migration statistics
        """
        total = sum(self.metrics.values())
        native = sum(
            count for key, count in self.metrics.items() 
            if "native" in key.lower()
        )
        legacy = total - native
        
        # Calculate average operation times
        avg_times = {}
        for key, times in self.operation_times.items():
            if times:
                avg_times[key] = sum(times) / len(times)
        
        return {
            "start_time": self.start_time.isoformat(),
            "duration_hours": (datetime.utcnow() - self.start_time).total_seconds() / 3600,
            "total_operations": total,
            "native_operations": native,
            "legacy_operations": legacy,
            "native_percentage": (native / total * 100) if total > 0 else 0,
            "operations_by_type": dict(self.metrics),
            "average_duration_ms": avg_times,
            "current_flags": {
                "USE_TERMINUS_NATIVE_BRANCH": settings.USE_TERMINUS_NATIVE_BRANCH,
                "USE_TERMINUS_NATIVE_MERGE": settings.USE_TERMINUS_NATIVE_MERGE,
                "USE_TERMINUS_NATIVE_DIFF": settings.USE_TERMINUS_NATIVE_DIFF,
            }
        }
    
    def get_comparison_report(self) -> Dict[str, Any]:
        """
        Get detailed comparison between implementations
        
        Returns:
            Comparison report with performance metrics
        """
        report = {
            "performance_comparison": {},
            "error_rates": {},
            "feature_adoption": {}
        }
        
        # Compare performance by operation
        operations = set()
        for key in self.operation_times.keys():
            operation = key.split(":")[0]
            operations.add(operation)
        
        for operation in operations:
            native_key = f"{operation}:native"
            legacy_key = f"{operation}:legacy"
            
            native_times = self.operation_times.get(native_key, [])
            legacy_times = self.operation_times.get(legacy_key, [])
            
            if native_times and legacy_times:
                report["performance_comparison"][operation] = {
                    "native_avg_ms": sum(native_times) / len(native_times),
                    "legacy_avg_ms": sum(legacy_times) / len(legacy_times),
                    "improvement_percentage": (
                        (sum(legacy_times) / len(legacy_times) - 
                         sum(native_times) / len(native_times)) / 
                        (sum(legacy_times) / len(legacy_times)) * 100
                    ) if legacy_times else 0
                }
        
        return report
    
    async def generate_migration_report(self, output_file: str = "migration_report.json"):
        """Generate and save a detailed migration report"""
        import json
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "progress": self.get_migration_progress(),
            "comparison": self.get_comparison_report(),
            "recommendations": self._generate_recommendations()
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Migration report generated: {output_file}")
        return report
    
    def _generate_recommendations(self) -> list:
        """Generate recommendations based on current metrics"""
        recommendations = []
        
        progress = self.get_migration_progress()
        native_pct = progress["native_percentage"]
        
        if native_pct == 0:
            recommendations.append({
                "priority": "HIGH",
                "message": "Native implementation not yet enabled. Consider enabling USE_TERMINUS_NATIVE_BRANCH for testing."
            })
        elif native_pct < 50:
            recommendations.append({
                "priority": "MEDIUM",
                "message": f"Native adoption at {native_pct:.1f}%. Consider increasing native usage for more operations."
            })
        elif native_pct >= 90:
            recommendations.append({
                "priority": "LOW",
                "message": "High native adoption achieved. Consider completing migration and removing legacy code."
            })
        
        # Check performance
        comparison = self.get_comparison_report()
        for op, metrics in comparison.get("performance_comparison", {}).items():
            if metrics["improvement_percentage"] < 0:
                recommendations.append({
                    "priority": "MEDIUM",
                    "message": f"Native {op} is slower than legacy. Investigate performance issues."
                })
        
        return recommendations


# Global instance
migration_monitor = MigrationMonitor()


# Decorator for tracking operations
def track_migration(operation: str):
    """Decorator to track migration metrics"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Determine implementation from class name
            if args and hasattr(args[0], '__class__'):
                class_name = args[0].__class__.__name__
                implementation = "native" if "Native" in class_name else "legacy"
            else:
                implementation = "unknown"
            
            start_time = datetime.utcnow()
            error_type = None
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                await migration_monitor.track_operation(
                    operation=operation,
                    implementation=implementation,
                    duration_ms=duration_ms,
                    success=success,
                    error_type=error_type
                )
        
        return wrapper
    return decorator