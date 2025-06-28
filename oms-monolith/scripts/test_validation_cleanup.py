#!/usr/bin/env python3
"""
Test script to verify validation cleanup didn't break anything
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any

# Test if imports still work
def test_imports():
    """Test that all imports work correctly after cleanup"""
    print("🧪 Testing imports...")
    
    try:
        # Test model imports
        from models.domain import ObjectType, Property, LinkType
        print("  ✓ models.domain imports OK")
        
        from models.semantic_types import SemanticType
        print("  ✓ models.semantic_types imports OK")
        
        from models.struct_types import StructType
        print("  ✓ models.struct_types imports OK")
        
        # Test middleware import
        from middleware.enterprise_validation import EnterpriseValidationMiddleware
        print("  ✓ middleware.enterprise_validation imports OK")
        
        # Test core validation imports
        from core.validation.enterprise_service import get_enterprise_validation_service
        print("  ✓ core.validation.enterprise_service imports OK")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False

def test_model_creation():
    """Test that models can still be created without custom validators"""
    print("\n🧪 Testing model creation...")
    
    try:
        from models.domain import ObjectType, Property
        
        # Test ObjectType creation
        obj_type = ObjectType(
            name="TestObject",
            displayName="Test Object",
            description="Test object type"
        )
        print(f"  ✓ Created ObjectType: {obj_type.name}")
        
        # Test Property creation
        prop = Property(
            name="testProp",
            displayName="Test Property",
            dataType="string",
            isRequired=False
        )
        print(f"  ✓ Created Property: {prop.name}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Model creation error: {e}")
        return False

async def test_validation_service():
    """Test that validation service works correctly"""
    print("\n🧪 Testing validation service...")
    
    try:
        from core.validation.enterprise_service import get_enterprise_validation_service, ValidationLevel
        
        # Get validation service
        validation_service = get_enterprise_validation_service(default_level=ValidationLevel.STANDARD)
        
        # Test data
        test_data = {
            "name": "TestObject",
            "displayName": "Test Object", 
            "description": "A test object type"
        }
        
        # Test validation
        result = await validation_service.validate(
            data=test_data,
            entity_type="object_type",
            operation="create",
            context={"test": True}
        )
        
        print(f"  ✓ Validation completed: is_valid={result.is_valid}")
        print(f"  ✓ Performance: {result.performance_impact_ms:.2f}ms")
        
        if result.errors:
            print(f"  ⚠️  Validation errors: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"     - {error.field}: {error.message}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Validation service error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_removed_files():
    """Verify that removed files are actually gone"""
    print("\n🧪 Testing file removals...")
    
    removed_files = [
        "middleware/request_validation.py"
    ]
    
    all_removed = True
    for file_path in removed_files:
        full_path = Path(__file__).parent.parent / file_path
        if full_path.exists():
            print(f"  ❌ File still exists: {file_path}")
            all_removed = False
        else:
            print(f"  ✓ File removed: {file_path}")
    
    return all_removed

def verify_backup():
    """Verify backup was created"""
    print("\n🧪 Verifying backup...")
    
    backup_dir = Path(__file__).parent.parent / "backups"
    if not backup_dir.exists():
        print("  ❌ Backup directory not found")
        return False
    
    # Find latest backup
    backups = list(backup_dir.glob("validation_cleanup_*"))
    if not backups:
        print("  ❌ No backup found")
        return False
    
    latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
    print(f"  ✓ Found backup: {latest_backup.name}")
    
    # Check restore script
    restore_script = latest_backup / "restore.py"
    if restore_script.exists():
        print("  ✓ Restore script available")
        return True
    else:
        print("  ❌ Restore script not found")
        return False

async def main():
    """Run all tests"""
    print("🔍 Validation Cleanup Test Suite")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Model Creation", test_model_creation()))
    results.append(("File Removals", test_removed_files()))
    results.append(("Backup Verification", verify_backup()))
    
    # Run async tests
    results.append(("Validation Service", await test_validation_service()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print("-" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
    
    print("-" * 50)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Cleanup was successful.")
    else:
        print("\n⚠️  Some tests failed. Review the cleanup changes.")
        print("💡 You can restore using the backup if needed.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())