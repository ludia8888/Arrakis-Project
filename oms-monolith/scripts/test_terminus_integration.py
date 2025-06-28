#!/usr/bin/env python3
"""
Test actual TerminusDB integration
Requires TerminusDB running (docker-compose up terminusdb)
"""
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if terminusdb_client is available
try:
    from terminusdb_client import WOQLClient
    from terminusdb_client.woqlquery import WOQLQuery as WQ
    HAS_TERMINUS_CLIENT = True
except ImportError:
    print("Error: terminusdb-client not installed")
    print("Please run: pip install terminusdb-client")
    sys.exit(1)

from shared.config import settings
from core.branch.service_factory import BranchServiceFactory, get_branch_service
from core.merge.merge_factory import get_merge_engine
from core.monitoring.migration_monitor import migration_monitor


async def setup_terminus_db():
    """Setup TerminusDB with test database"""
    print("🔧 Setting up TerminusDB...")
    
    client = WOQLClient("http://localhost:16363")
    client.connect(user="admin", key="admin123", use_token=False)
    
    # Create test database if not exists
    db_name = "oms_test"
    try:
        existing_dbs = client.list_databases()
        # Handle both dict and string responses
        if isinstance(existing_dbs, list):
            db_names = [db.get('name', db) if isinstance(db, dict) else db for db in existing_dbs]
        else:
            db_names = []
            
        if db_name not in db_names:
            client.create_database(
                db_name,
                label="OMS Test Database",
                description="Test database for OMS integration"
            )
            print(f"✅ Created database: {db_name}")
        else:
            print(f"✅ Database already exists: {db_name}")
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Connect to the database
    client.db = db_name
    
    # Create a simple schema
    try:
        # Use direct schema creation with newer API
        schema = WQ().doctype("Customer").label("Customer").description("Customer entity").property("name", "xsd:string").property("email", "xsd:string").property("created_at", "xsd:dateTime")
        client.query(schema, commit_msg="Create Customer schema")
        
        schema2 = WQ().doctype("Order").label("Order").description("Order entity").property("order_number", "xsd:string").property("total_amount", "xsd:decimal").property("customer", "Customer")
        client.query(schema2, commit_msg="Create Order schema")
        
        print("✅ Schema created")
        
    except Exception as e:
        print(f"ℹ️ Schema might already exist: {e}")
    
    return client


async def test_native_branch_operations():
    """Test native branch operations with real TerminusDB"""
    print("\n📌 Testing Native Branch Operations")
    print("-" * 50)
    
    # Enable native branch service
    settings.USE_TERMINUS_NATIVE_BRANCH = True
    settings.TERMINUS_DB = "oms_test"
    BranchServiceFactory.reset()
    
    service = get_branch_service()
    print(f"Service type: {type(service).__name__}")
    
    try:
        # Create a branch
        print("\n1. Creating branch...")
        branch_name = await service.create_branch(
            "main",
            "feature-test",
            "Test feature branch"
        )
        print(f"✅ Created branch: {branch_name}")
        
        # List branches
        print("\n2. Listing branches...")
        branches = await service.list_branches()
        print(f"✅ Found {len(branches)} branches:")
        for b in branches[:5]:  # Show first 5
            print(f"   - {b.get('name', b)}")
        
        # Get diff
        print("\n3. Getting diff...")
        diff = await service.get_diff("main", branch_name)
        print(f"✅ Diff has {len(diff.changes)} changes")
        
        # Test merge
        print("\n4. Testing merge...")
        result = await service.merge_branches(
            branch_name,
            "main",
            "test_user",
            "Test merge from feature branch"
        )
        
        if result.merge_commit:
            print(f"✅ Merge successful! Commit: {result.merge_commit}")
        else:
            print(f"❌ Merge failed: {result.conflicts}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_unified_merge_with_terminus():
    """Test unified merge engine with real TerminusDB"""
    print("\n📌 Testing Unified Merge Engine with TerminusDB")
    print("-" * 50)
    
    # Get terminus client
    client = WOQLClient("http://localhost:16363")
    client.connect(user="admin", key="admin123", db="oms_test", use_token=False)
    
    # Get unified merge engine
    merge_engine = get_merge_engine()
    merge_engine.terminus = client  # Inject real client
    
    print(f"Engine type: {type(merge_engine).__name__}")
    
    try:
        # Create test branches
        print("\n1. Creating test branches...")
        client.branch = "main"
        
        # Delete branches if they exist
        try:
            client.delete_branch("feature_add_field")
        except:
            pass
        try:
            client.delete_branch("feature_modify_field")
        except:
            pass
            
        client.create_branch("feature_add_field")
        client.create_branch("feature_modify_field")
        print("✅ Created test branches")
        
        # Add some changes to branches
        print("\n2. Making changes in branches...")
        
        # In feature_add_field, add a new property
        client.branch = "feature_add_field"
        # Create a simple document to test
        customer_doc = {
            "@type": "Customer",
            "@id": "Customer/test_customer_1",
            "name": "Test Customer",
            "email": "test@example.com",
            "created_at": "2025-06-28T08:00:00Z"
        }
        client.insert_document(customer_doc, commit_msg="Add test customer")
        
        # In feature_modify_field, modify cardinality (this should be caught!)
        client.branch = "feature_modify_field"
        # This would need actual cardinality modification query
        
        # Test merge
        print("\n3. Testing merge with domain validation...")
        client.branch = "main"
        
        result = await merge_engine.merge(
            "feature_add_field",
            "main",
            "test_user",
            "Merge new phone field"
        )
        
        if result.merge_commit:
            print(f"✅ Merge successful! Commit: {result.merge_commit}")
        elif result.conflicts:
            print(f"⚠️ Conflicts detected:")
            for conflict in result.conflicts:
                print(f"   - {conflict.conflict_type}: {conflict.description}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_migration_monitoring():
    """Show migration statistics"""
    print("\n📊 Migration Statistics")
    print("-" * 50)
    
    stats = migration_monitor.get_migration_progress()
    print(f"Total operations: {stats['total_operations']}")
    print(f"Native operations: {stats['native_operations']} ({stats['native_percentage']:.1f}%)")
    print(f"Legacy operations: {stats['legacy_operations']}")
    
    print("\nOperations by type:")
    for op, count in stats['operations_by_type'].items():
        print(f"  {op}: {count}")


async def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("🚀 TerminusDB Integration Test Suite")
    print("="*60)
    
    # Check if TerminusDB is running
    print("\n📌 Checking TerminusDB connection...")
    try:
        client = WOQLClient("http://localhost:16363")
        client.connect(user="admin", key="admin123", use_token=False)
        print("✅ TerminusDB is running")
    except Exception as e:
        print(f"❌ TerminusDB is not accessible at http://localhost:16363")
        print(f"   Error: {e}")
        print("\n💡 Please run: docker-compose up terminusdb")
        return
    
    # Setup database
    client = await setup_terminus_db()
    if not client:
        return
    
    # Run tests
    await test_native_branch_operations()
    await test_unified_merge_with_terminus()
    await test_migration_monitoring()
    
    print("\n" + "="*60)
    print("✅ Integration tests completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())