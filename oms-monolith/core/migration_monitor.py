"""
Migration Monitoring System
Tracks and reports on TerminusDB native migration progress
"""
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import json
import os

import logging

logger = logging.getLogger(__name__)


class MigrationMonitor:
    """
    Monitors the gradual migration from legacy to native TerminusDB implementation
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.operation_counts = defaultdict(lambda: defaultdict(int))
        self.error_counts = defaultdict(lambda: defaultdict(int))
        self.operation_times = defaultdict(lambda: defaultdict(list))
        self.checkpoints = []
        
    def track_operation(
        self,
        operation: str,
        implementation: str,
        duration: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track a single operation execution
        
        Args:
            operation: Operation name (e.g., 'create_branch', 'merge')
            implementation: 'legacy' or 'native'
            duration: Operation duration in seconds
            success: Whether operation succeeded
            metadata: Additional context
        """
        # Update counts
        self.operation_counts[operation][implementation] += 1
        
        if duration is not None:
            self.operation_times[operation][implementation].append(duration)
            
        if not success:
            self.error_counts[operation][implementation] += 1
            
        # Log significant events
        if implementation == "native" and success:
            logger.info(
                f"Native operation successful: {operation} "
                f"(duration: {duration:.3f}s)" if duration else ""
            )
            
    def get_migration_progress(self) -> Dict[str, Any]:
        """Get current migration progress statistics"""
        total_ops = 0
        native_ops = 0
        legacy_ops = 0
        
        operations_by_type = defaultdict(lambda: {"native": 0, "legacy": 0})
        
        for operation, implementations in self.operation_counts.items():
            for impl, count in implementations.items():
                operations_by_type[operation][impl] = count
                total_ops += count
                
                if impl == "native":
                    native_ops += count
                else:
                    legacy_ops += count
                    
        # Calculate percentages
        native_percentage = (native_ops / total_ops * 100) if total_ops > 0 else 0
        
        # Calculate average operation times
        avg_times = {}
        for operation, implementations in self.operation_times.items():
            avg_times[operation] = {}
            for impl, times in implementations.items():
                if times:
                    avg_times[operation][impl] = sum(times) / len(times)
                    
        # Error rates
        error_rates = {}
        for operation, implementations in self.error_counts.items():
            error_rates[operation] = {}
            for impl, error_count in implementations.items():
                total = self.operation_counts[operation][impl]
                error_rates[operation][impl] = (error_count / total * 100) if total > 0 else 0
                
        return {
            "total_operations": total_ops,
            "native_operations": native_ops,
            "legacy_operations": legacy_ops,
            "native_percentage": native_percentage,
            "operations_by_type": dict(operations_by_type),
            "average_operation_times": avg_times,
            "error_rates": error_rates,
            "uptime_seconds": time.time() - self.start_time
        }
        
    def create_checkpoint(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Create a migration checkpoint for tracking progress over time"""
        checkpoint = {
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "progress": self.get_migration_progress(),
            "metadata": metadata or {}
        }
        
        self.checkpoints.append(checkpoint)
        
        # Save checkpoint to file
        self._save_checkpoint(checkpoint)
        
        logger.info(f"Migration checkpoint created: {name}")
        
    def get_operation_comparison(self, operation: str) -> Dict[str, Any]:
        """Compare legacy vs native performance for a specific operation"""
        comparison = {
            "operation": operation,
            "executions": {
                "legacy": self.operation_counts[operation].get("legacy", 0),
                "native": self.operation_counts[operation].get("native", 0)
            },
            "errors": {
                "legacy": self.error_counts[operation].get("legacy", 0),
                "native": self.error_counts[operation].get("native", 0)
            }
        }
        
        # Calculate average times
        legacy_times = self.operation_times[operation].get("legacy", [])
        native_times = self.operation_times[operation].get("native", [])
        
        if legacy_times:
            comparison["avg_time_legacy"] = sum(legacy_times) / len(legacy_times)
        if native_times:
            comparison["avg_time_native"] = sum(native_times) / len(native_times)
            
        # Calculate improvement
        if legacy_times and native_times:
            avg_legacy = sum(legacy_times) / len(legacy_times)
            avg_native = sum(native_times) / len(native_times)
            comparison["improvement_percent"] = ((avg_legacy - avg_native) / avg_legacy) * 100
            comparison["speedup"] = avg_legacy / avg_native
            
        return comparison
        
    def should_rollback(self) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should rollback to legacy implementation
        
        Returns:
            (should_rollback, reason)
        """
        progress = self.get_migration_progress()
        
        # Check error rates
        for operation, rates in progress["error_rates"].items():
            native_error_rate = rates.get("native", 0)
            legacy_error_rate = rates.get("legacy", 0)
            
            # Rollback if native error rate is significantly higher
            if native_error_rate > 5 and native_error_rate > legacy_error_rate * 2:
                return True, f"High error rate in {operation}: {native_error_rate:.1f}%"
                
        # Check performance degradation
        for operation, times in progress["average_operation_times"].items():
            native_time = times.get("native")
            legacy_time = times.get("legacy")
            
            if native_time and legacy_time:
                # Rollback if native is significantly slower
                if native_time > legacy_time * 2:
                    return True, f"Performance degradation in {operation}: {native_time/legacy_time:.1f}x slower"
                    
        return False, None
        
    def generate_report(self) -> str:
        """Generate a human-readable migration report"""
        progress = self.get_migration_progress()
        
        report = []
        report.append("="*60)
        report.append("TERMINUS NATIVE MIGRATION REPORT")
        report.append("="*60)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append(f"Uptime: {progress['uptime_seconds']/3600:.1f} hours")
        report.append("")
        
        # Overall progress
        report.append("OVERALL PROGRESS")
        report.append("-"*30)
        report.append(f"Total Operations: {progress['total_operations']:,}")
        report.append(f"Native Operations: {progress['native_operations']:,} ({progress['native_percentage']:.1f}%)")
        report.append(f"Legacy Operations: {progress['legacy_operations']:,}")
        report.append("")
        
        # Operations breakdown
        report.append("OPERATIONS BREAKDOWN")
        report.append("-"*30)
        for operation, counts in progress['operations_by_type'].items():
            total = counts['native'] + counts['legacy']
            native_pct = (counts['native'] / total * 100) if total > 0 else 0
            report.append(f"{operation}:")
            report.append(f"  Native: {counts['native']:,} ({native_pct:.1f}%)")
            report.append(f"  Legacy: {counts['legacy']:,}")
            
        # Performance comparison
        report.append("\nPERFORMANCE COMPARISON")
        report.append("-"*30)
        for operation in self.operation_counts:
            comparison = self.get_operation_comparison(operation)
            if "improvement_percent" in comparison:
                report.append(f"{operation}:")
                report.append(f"  Improvement: {comparison['improvement_percent']:.1f}%")
                report.append(f"  Speedup: {comparison['speedup']:.2f}x")
                
        # Error rates
        report.append("\nERROR RATES")
        report.append("-"*30)
        for operation, rates in progress['error_rates'].items():
            if rates:
                report.append(f"{operation}:")
                for impl, rate in rates.items():
                    report.append(f"  {impl}: {rate:.2f}%")
                    
        # Rollback check
        should_rollback, reason = self.should_rollback()
        report.append("\nROLLBACK STATUS")
        report.append("-"*30)
        if should_rollback:
            report.append(f"⚠️  ROLLBACK RECOMMENDED: {reason}")
        else:
            report.append("✅ No rollback needed")
            
        return "\n".join(report)
        
    def _save_checkpoint(self, checkpoint: Dict[str, Any]):
        """Save checkpoint to file for persistence"""
        checkpoint_dir = "migration_checkpoints"
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        filename = f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{checkpoint['name']}.json"
        filepath = os.path.join(checkpoint_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(checkpoint, f, indent=2)
            
        logger.info(f"Checkpoint saved to {filepath}")


# Global instance
migration_monitor = MigrationMonitor()


# Context manager for tracking operations
class track_operation:
    """Context manager for automatically tracking operation execution"""
    
    def __init__(self, operation: str, implementation: str):
        self.operation = operation
        self.implementation = implementation
        self.start_time = None
        self.success = True
        self.metadata = {}
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is not None:
            self.success = False
            self.metadata["error_type"] = exc_type.__name__
            self.metadata["error_message"] = str(exc_val)
            
        migration_monitor.track_operation(
            self.operation,
            self.implementation,
            duration,
            self.success,
            self.metadata
        )
        
        # Don't suppress exceptions
        return False


# Decorators for automatic tracking
def track_native_operation(operation: str):
    """Decorator to track native implementation operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with track_operation(operation, "native") as tracker:
                result = await func(*args, **kwargs)
                return result
        return wrapper
    return decorator


def track_legacy_operation(operation: str):
    """Decorator to track legacy implementation operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with track_operation(operation, "legacy") as tracker:
                result = await func(*args, **kwargs)
                return result
        return wrapper
    return decorator