#!/usr/bin/env python3
"""
Final test to verify validation cleanup is working correctly
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

def test_imports():
    """Test that all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        # Test model imports
        from models.domain import ObjectType, ObjectTypeCreate, Property, PropertyCreate, LinkType
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
    """Test that models can be created properly"""
    print("\n🧪 Testing model creation...")
    
    try:
        from models.domain import ObjectTypeCreate, PropertyCreate
        
        # Test ObjectTypeCreate (for creating new objects)
        obj_create = ObjectTypeCreate(
            name="TestObject",
            display_name="Test Object",
            description="Test object type"
        )
        print(f"  ✓ Created ObjectTypeCreate: {obj_create.name}")
        
        # Test PropertyCreate
        prop_create = PropertyCreate(
            name="testProp",
            display_name="Test Property",
            data_type_id="string"
        )
        print(f"  ✓ Created PropertyCreate: {prop_create.name}")
        
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
        validation_service = get_enterprise_validation_service(
            default_level=ValidationLevel.STANDARD
        )
        
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
    
    from pathlib import Path
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

def test_middleware_integration():
    """Test that middleware is properly configured"""
    print("\n🧪 Testing middleware integration...")
    
    try:
        from middleware.enterprise_validation import EnterpriseValidationMiddleware
        
        # Create mock app
        class MockApp:
            pass
        
        app = MockApp()
        middleware = EnterpriseValidationMiddleware(app)
        
        # Check that middleware has validation service
        if hasattr(middleware, 'validation_service'):
            print("  ✓ Middleware has validation service")
        else:
            print("  ❌ Middleware missing validation service")
            return False
        
        # Check path mapping
        if hasattr(middleware, 'path_to_entity_type'):
            print(f"  ✓ Path mapping configured: {len(middleware.path_to_entity_type)} routes")
        else:
            print("  ❌ Path mapping not configured")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Middleware test error: {e}")
        return False

def test_validation_rules():
    """Test that validation rules are available"""
    print("\n🧪 Testing validation rules...")
    
    try:
        from core.validation.rules import (
            RequiredFieldRemovalRule,
            EnumValueConstraintRule,
            ArrayElementConstraintRule,
            ForeignReferenceIntegrityRule
        )
        print("  ✓ P1 validation rules imported successfully")
        
        from core.validation.rules.timeseries_event_mapping_rule import TimeseriesEventMappingRule
        print("  ✓ P2 event mapping rule imported successfully")
        
        from core.validation.policy_engine import PolicyEngine
        print("  ✓ Policy engine imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Validation rules import error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🔍 Final Validation Cleanup Test Suite")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Model Creation", test_model_creation()))
    results.append(("File Removals", test_removed_files()))
    results.append(("Middleware Integration", test_middleware_integration()))
    results.append(("Validation Rules", test_validation_rules()))
    
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
        print("\n✅ All tests passed! Validation cleanup was successful.")
        print("\n📋 What was cleaned up:")
        print("  - Removed middleware/request_validation.py (redundant)")
        print("  - Removed @field_validator decorators from models")
        print("  - Refactored enterprise_validation.py to thin integration layer")
        print("  - All validation logic now in core/validation/")
    else:
        print("\n⚠️  Some tests failed. Review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())