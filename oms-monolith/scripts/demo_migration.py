#!/usr/bin/env python3
"""
Demo script showing the migration path
"""
import asyncio
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from core.branch.service_factory import BranchServiceFactory
from core.monitoring.migration_monitor import migration_monitor


async def demo_migration():
    """Demonstrate the migration from legacy to native"""
    print("\n" + "="*60)
    print("🚀 TerminusDB Native Migration Demo")
    print("="*60 + "\n")
    
    # Step 1: Show current state with legacy
    print("📌 Step 1: Current state with LEGACY implementation")
    print("-" * 50)
    settings.USE_TERMINUS_NATIVE_BRANCH = False
    BranchServiceFactory.reset()
    
    print(f"Feature Flag USE_TERMINUS_NATIVE_BRANCH: {settings.USE_TERMINUS_NATIVE_BRANCH}")
    print("Creating service...")
    
    # Mock TerminusDB to avoid connection errors
    with patch('database.clients.terminus_db.TerminusDBClient') as mock_tdb:
        mock_tdb_instance = MagicMock()
        mock_tdb.return_value = mock_tdb_instance
        
        service = BranchServiceFactory.create_branch_service()
        print(f"✅ Service type: {type(service).__name__}")
        print(f"   This is the existing implementation that does custom merge logic\n")
    
    # Step 2: Enable native and show the difference
    print("📌 Step 2: Enable TerminusDB Native implementation")
    print("-" * 50)
    settings.USE_TERMINUS_NATIVE_BRANCH = True
    BranchServiceFactory.reset()
    
    print(f"Feature Flag USE_TERMINUS_NATIVE_BRANCH: {settings.USE_TERMINUS_NATIVE_BRANCH}")
    print("Creating service...")
    
    with patch('core.branch.terminus_adapter.WOQLClient') as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        service = BranchServiceFactory.create_branch_service()
        print(f"✅ Service type: {type(service).__name__}")
        print(f"   This uses TerminusDB's native branch/merge/diff capabilities\n")
    
    # Step 3: Show monitoring capabilities
    print("📌 Step 3: Migration Monitoring")
    print("-" * 50)
    
    # Simulate some operations
    for i in range(3):
        await migration_monitor.track_operation(
            operation="create_branch",
            implementation="legacy",
            duration_ms=150 + i * 10,
            success=True
        )
    
    for i in range(5):
        await migration_monitor.track_operation(
            operation="create_branch", 
            implementation="native",
            duration_ms=50 + i * 5,
            success=True
        )
    
    # Show stats
    stats = migration_monitor.get_migration_progress()
    print(f"Total operations tracked: {stats['total_operations']}")
    print(f"Legacy operations: {stats['legacy_operations']}")
    print(f"Native operations: {stats['native_operations']}")
    print(f"Native adoption: {stats['native_percentage']:.1f}%")
    print()
    
    # Show performance comparison
    comparison = migration_monitor.get_comparison_report()
    if comparison['performance_comparison']:
        print("Performance Comparison:")
        for op, metrics in comparison['performance_comparison'].items():
            print(f"  {op}:")
            print(f"    Legacy avg: {metrics['legacy_avg_ms']:.1f}ms")
            print(f"    Native avg: {metrics['native_avg_ms']:.1f}ms")
            print(f"    Improvement: {metrics['improvement_percentage']:.1f}%")
    
    print("\n" + "="*60)
    print("✅ Migration path is ready!")
    print("   - Feature flags control which implementation is used")
    print("   - Both implementations follow the same interface")
    print("   - Performance and errors are tracked")
    print("   - Rollback is instant (just flip the flag)")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_migration())