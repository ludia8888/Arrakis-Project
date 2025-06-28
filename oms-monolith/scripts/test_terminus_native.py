#!/usr/bin/env python3
"""
Test script for TerminusDB Native implementation
Run this to verify the native adapter is working correctly
"""
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if terminusdb_client is available
try:
    import terminusdb_client
    HAS_TERMINUS_CLIENT = True
except ImportError:
    HAS_TERMINUS_CLIENT = False
    print("Warning: terminusdb_client not installed. Using mock for testing.")

from core.branch.service_factory import get_branch_service, BranchServiceFactory
from core.monitoring.migration_monitor import migration_monitor
from shared.config import settings


async def test_native_implementation():
    """Test TerminusDB native implementation"""
    print("\n=== TerminusDB Native Implementation Test ===\n")
    
    # Test with native disabled
    print("1. Testing with LEGACY implementation...")
    settings.USE_TERMINUS_NATIVE_BRANCH = False
    BranchServiceFactory.reset()
    
    try:
        legacy_service = get_branch_service()
        print(f"   Service type: {type(legacy_service).__name__}")
        
        # Create a test branch (will fail without full setup, but shows it tries legacy)
        try:
            branch_name = await legacy_service.create_branch(
                "main", 
                "test-legacy",
                "Test branch from legacy"
            )
            print(f"   ✓ Created branch: {branch_name}")
        except Exception as e:
            print(f"   ✗ Expected error (no DB setup): {type(e).__name__}")
    except Exception as e:
        print(f"   ✗ Could not create legacy service: {e}")
    
    print("\n2. Testing with NATIVE implementation...")
    settings.USE_TERMINUS_NATIVE_BRANCH = True
    BranchServiceFactory.reset()
    
    # Mock TerminusDB client if not available
    mock_client = None
    if not HAS_TERMINUS_CLIENT:
        mock_client = MagicMock()
        mock_client.branch.return_value = True
        mock_client.list_branches.return_value = ["main"]
        mock_client.diff.return_value = {"changes": []}
        mock_client.merge.return_value = {"commit": "mock123"}
    
    with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
        if mock_client:
            mock_client_class.return_value = mock_client
        
        native_service = get_branch_service()
        print(f"   Service type: {type(native_service).__name__}")
    
    try:
        # Create a test branch
        branch_name = await native_service.create_branch(
            "main",
            "test-native", 
            "Test branch from native"
        )
        print(f"   ✓ Created branch: {branch_name}")
        
        # List branches
        branches = await native_service.list_branches()
        print(f"   ✓ Found {len(branches)} branches")
        
        # Get diff (should be empty for new branch)
        diff = await native_service.get_diff("main", branch_name)
        print(f"   ✓ Diff has {len(diff.changes)} changes")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Show migration stats
    print("\n3. Migration Statistics:")
    stats = migration_monitor.get_migration_progress()
    print(f"   Total operations: {stats['total_operations']}")
    print(f"   Native operations: {stats['native_operations']}")
    print(f"   Legacy operations: {stats['legacy_operations']}")
    print(f"   Native percentage: {stats['native_percentage']:.1f}%")
    
    # Generate report
    print("\n4. Generating migration report...")
    report = await migration_monitor.generate_migration_report("migration_test_report.json")
    print("   ✓ Report saved to migration_test_report.json")
    
    # Show recommendations
    print("\n5. Recommendations:")
    for rec in report["recommendations"]:
        print(f"   [{rec['priority']}] {rec['message']}")


async def interactive_test():
    """Interactive test mode"""
    print("\n=== Interactive TerminusDB Native Test ===\n")
    
    while True:
        print("\nOptions:")
        print("1. Toggle native implementation (currently: {})".format(
            "ENABLED" if settings.USE_TERMINUS_NATIVE_BRANCH else "DISABLED"
        ))
        print("2. Create a branch")
        print("3. List branches")
        print("4. Merge branches")
        print("5. Show migration stats")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ")
        
        if choice == "1":
            settings.USE_TERMINUS_NATIVE_BRANCH = not settings.USE_TERMINUS_NATIVE_BRANCH
            BranchServiceFactory.reset()
            print(f"Native implementation is now: {'ENABLED' if settings.USE_TERMINUS_NATIVE_BRANCH else 'DISABLED'}")
            
        elif choice == "2":
            name = input("Enter branch name: ")
            service = get_branch_service()
            try:
                branch = await service.create_branch("main", name, f"Test branch {name}")
                print(f"✓ Created branch: {branch}")
            except Exception as e:
                print(f"✗ Error: {e}")
                
        elif choice == "3":
            service = get_branch_service()
            try:
                branches = await service.list_branches()
                print(f"\nFound {len(branches)} branches:")
                for b in branches[:10]:  # Show first 10
                    print(f"  - {b.get('name', b)}")
            except Exception as e:
                print(f"✗ Error: {e}")
                
        elif choice == "4":
            source = input("Enter source branch: ")
            target = input("Enter target branch (default: main): ") or "main"
            service = get_branch_service()
            try:
                result = await service.merge_branches(source, target, "test_user", "Test merge")
                print(f"✓ Merge result: {result.status}")
                if result.message:
                    print(f"  Message: {result.message}")
            except Exception as e:
                print(f"✗ Error: {e}")
                
        elif choice == "5":
            stats = migration_monitor.get_migration_progress()
            print("\nMigration Statistics:")
            print(f"  Total operations: {stats['total_operations']}")
            print(f"  Native operations: {stats['native_operations']}")
            print(f"  Legacy operations: {stats['legacy_operations']}")
            print(f"  Native percentage: {stats['native_percentage']:.1f}%")
            
        elif choice == "6":
            break
            
        else:
            print("Invalid choice")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TerminusDB Native Implementation")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--native", "-n", action="store_true", help="Start with native enabled")
    
    args = parser.parse_args()
    
    if args.native:
        os.environ["USE_TERMINUS_NATIVE_BRANCH"] = "true"
    
    if args.interactive:
        asyncio.run(interactive_test())
    else:
        asyncio.run(test_native_implementation())