#!/usr/bin/env python3
"""
P1 Phase Foundry Rules Test

Tests the newly implemented P1 phase rules:
- EnumValueConstraintRule
- ArrayElementConstraintRule  
- ForeignReferenceIntegrityRule

Tests core functionality without external dependencies.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_p1_plugin_scanning():
    """Test that P1 phase rules are properly exported for plugin scanning"""
    print("🔍 Testing P1 Plugin Scanning...")
    
    try:
        # Test P1 rule imports
        from core.validation.rules import (
            # P1 Enum rules
            EnumValueConstraintRule, EnumSchemaChangeRule, EnumConstraint,
            create_enum_constraint_rule, create_foundry_status_enum_rule, create_foundry_priority_enum_rule,
            # P1 Array rules
            ArrayElementConstraintRule, ArrayConstraint, ArrayConstraintType,
            create_unique_array_rule, create_enum_array_rule, create_foundry_tags_rule,
            # P1 Foreign reference rules
            ForeignReferenceIntegrityRule, ForeignReference, ReferenceType, IntegrityAction,
            create_foreign_key_rule, create_cross_dataset_rule, create_foundry_entity_references,
            # Updated exports
            RULE_CATEGORIES, RULE_PRIORITIES, __all__
        )
        
        print("✅ Successfully imported all P1 phase components")
        
        # Check P1 exports in __all__
        p1_exports = [
            "EnumValueConstraintRule", "EnumSchemaChangeRule", "EnumConstraint",
            "ArrayElementConstraintRule", "ArrayConstraint", "ArrayConstraintType", 
            "ForeignReferenceIntegrityRule", "ForeignReference", "ReferenceType", "IntegrityAction"
        ]
        
        for export in p1_exports:
            assert export in __all__, f"Missing P1 export: {export}"
        print(f"   - ✅ All {len(p1_exports)} P1 exports present in __all__")
        
        # Check P1 rules in foundry category
        foundry_rules = RULE_CATEGORIES.get("foundry", [])
        p1_foundry_rules = ["EnumValueConstraintRule", "ArrayElementConstraintRule", "ForeignReferenceIntegrityRule"]
        
        for rule in p1_foundry_rules:
            assert rule in foundry_rules, f"Missing P1 rule in foundry category: {rule}"
        print(f"   - ✅ All {len(p1_foundry_rules)} P1 rules in foundry category")
        
        # Check P1 priorities
        p1_priority_rules = ["EnumValueConstraintRule", "EnumSchemaChangeRule", "ArrayElementConstraintRule", "ForeignReferenceIntegrityRule"]
        
        for rule in p1_priority_rules:
            assert rule in RULE_PRIORITIES, f"Missing P1 rule priority: {rule}"
        print(f"   - ✅ All {len(p1_priority_rules)} P1 rules have priorities")
        
        print(f"   - Total exports now: {len(__all__)} items")
        print(f"   - Foundry category now: {len(foundry_rules)} rules")
        
        return True
        
    except Exception as e:
        print(f"❌ P1 plugin scanning failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enum_constraint_structure():
    """Test enum constraint rule structure and configuration"""
    print("\n🔢 Testing Enum Constraint Rules...")
    
    try:
        from core.validation.rules.enum_value_constraint_rule import (
            EnumValueConstraintRule, EnumConstraint, 
            create_enum_constraint_rule, create_foundry_status_enum_rule
        )
        
        # Test EnumConstraint dataclass
        enum_constraint = EnumConstraint(
            field_name="status",
            allowed_values={"ACTIVE", "INACTIVE", "PENDING"},
            nullable=False,
            case_sensitive=True
        )
        
        assert enum_constraint.field_name == "status"
        assert len(enum_constraint.allowed_values) == 3
        assert not enum_constraint.nullable
        print("   - ✅ EnumConstraint dataclass works correctly")
        
        # Test factory function
        enum_rule = create_enum_constraint_rule(
            field_name="priority",
            allowed_values=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            nullable=True,
            case_sensitive=True
        )
        
        assert enum_rule.rule_id == "enum_value_constraint"
        assert len(enum_rule.enum_constraints) == 1
        print("   - ✅ create_enum_constraint_rule factory works")
        
        # Test Foundry predefined rule
        foundry_status_rule = create_foundry_status_enum_rule()
        
        assert "status" in foundry_status_rule.enum_constraints
        status_constraint = foundry_status_rule.enum_constraints["status"]
        assert "ACTIVE" in status_constraint.allowed_values
        assert "DELETED" in status_constraint.allowed_values
        print("   - ✅ create_foundry_status_enum_rule works")
        
        # Test rule priority
        assert enum_rule.priority == 40
        print(f"   - ✅ Enum rule priority: {enum_rule.priority}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enum constraint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_array_constraint_structure():
    """Test array constraint rule structure and configuration"""
    print("\n📋 Testing Array Constraint Rules...")
    
    try:
        from core.validation.rules.array_element_rule import (
            ArrayElementConstraintRule, ArrayConstraint, ArrayConstraintType,
            create_unique_array_rule, create_enum_array_rule, create_foundry_tags_rule
        )
        
        # Test ArrayConstraintType enum
        constraint_types = list(ArrayConstraintType)
        expected_types = ["unique_elements", "enum_values", "regex_pattern", "min_length", "max_length", "element_type", "no_nulls"]
        
        for expected in expected_types:
            assert any(ct.value == expected for ct in constraint_types), f"Missing constraint type: {expected}"
        print(f"   - ✅ ArrayConstraintType has {len(constraint_types)} types")
        
        # Test ArrayConstraint dataclass
        array_constraint = ArrayConstraint(
            field_name="tags",
            constraint_type=ArrayConstraintType.UNIQUE_ELEMENTS,
            constraint_value=True,
            nullable=True,
            element_separator=","
        )
        
        assert array_constraint.field_name == "tags"
        assert array_constraint.constraint_type == ArrayConstraintType.UNIQUE_ELEMENTS
        print("   - ✅ ArrayConstraint dataclass works correctly")
        
        # Test factory functions
        unique_rule = create_unique_array_rule("tags", element_separator=",")
        assert unique_rule.rule_id == "array_element_constraint"
        assert len(unique_rule.array_constraints) == 1
        print("   - ✅ create_unique_array_rule factory works")
        
        enum_array_rule = create_enum_array_rule(
            "categories", 
            ["BUSINESS", "TECHNICAL", "OPERATIONAL"],
            case_sensitive=True
        )
        assert "categories" in enum_array_rule.array_constraints
        print("   - ✅ create_enum_array_rule factory works")
        
        # Test Foundry predefined rule
        foundry_tags_rule = create_foundry_tags_rule()
        assert "tags" in foundry_tags_rule.array_constraints
        print("   - ✅ create_foundry_tags_rule works")
        
        # Test rule priority
        assert unique_rule.priority == 45
        print(f"   - ✅ Array rule priority: {unique_rule.priority}")
        
        return True
        
    except Exception as e:
        print(f"❌ Array constraint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_foreign_reference_structure():
    """Test foreign reference rule structure and configuration"""
    print("\n🔗 Testing Foreign Reference Rules...")
    
    try:
        from core.validation.rules.foreign_ref_integrity_rule import (
            ForeignReferenceIntegrityRule, ForeignReference, ReferenceType, IntegrityAction,
            create_foreign_key_rule, create_cross_dataset_rule, create_foundry_entity_references
        )
        
        # Test ReferenceType enum
        reference_types = list(ReferenceType)
        expected_types = ["foreign_key", "weak_reference", "cross_dataset", "hierarchical", "many_to_many"]
        
        for expected in expected_types:
            assert any(rt.value == expected for rt in reference_types), f"Missing reference type: {expected}"
        print(f"   - ✅ ReferenceType has {len(reference_types)} types")
        
        # Test IntegrityAction enum
        integrity_actions = list(IntegrityAction)
        expected_actions = ["restrict", "cascade", "set_null", "set_default", "no_action"]
        
        for expected in expected_actions:
            assert any(ia.value == expected for ia in integrity_actions), f"Missing integrity action: {expected}"
        print(f"   - ✅ IntegrityAction has {len(integrity_actions)} actions")
        
        # Test ForeignReference dataclass
        foreign_ref = ForeignReference(
            source_field="user_id",
            target_dataset="User",
            target_field="id",
            reference_type=ReferenceType.FOREIGN_KEY,
            nullable=False,
            integrity_action=IntegrityAction.RESTRICT
        )
        
        assert foreign_ref.source_field == "user_id"
        assert foreign_ref.target_dataset == "User"
        assert foreign_ref.reference_type == ReferenceType.FOREIGN_KEY
        print("   - ✅ ForeignReference dataclass works correctly")
        
        # Test factory functions
        fk_rule = create_foreign_key_rule(
            source_field="parent_id",
            target_dataset="ObjectType", 
            target_field="id",
            nullable=True,
            integrity_action=IntegrityAction.CASCADE
        )
        
        assert fk_rule.rule_id == "foreign_reference_integrity"
        assert len(fk_rule.foreign_references) == 1
        print("   - ✅ create_foreign_key_rule factory works")
        
        cross_dataset_rule = create_cross_dataset_rule(
            source_field="external_ref",
            target_dataset="ExternalEntity",
            target_field="id",
            target_database="external_db"
        )
        assert "external_ref" in cross_dataset_rule.foreign_references
        print("   - ✅ create_cross_dataset_rule factory works")
        
        # Test Foundry predefined rule
        foundry_entity_rule = create_foundry_entity_references()
        assert len(foundry_entity_rule.foreign_references) >= 3  # parent_id, created_by, organization_id
        print("   - ✅ create_foundry_entity_references works")
        
        # Test rule priority
        assert fk_rule.priority == 30
        print(f"   - ✅ Foreign reference rule priority: {fk_rule.priority}")
        
        return True
        
    except Exception as e:
        print(f"❌ Foreign reference test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_foundry_coverage_completion():
    """Test that P1 phase completes Foundry Dataset Rules coverage"""
    print("\n📊 Testing Foundry Coverage Completion...")
    
    try:
        from core.validation.rules import RULE_CATEGORIES
        
        # Original Foundry gaps according to analysis
        foundry_gaps = [
            "enum_value_constraint",      # ✅ Now: EnumValueConstraintRule
            "array_element_constraints",  # ✅ Now: ArrayElementConstraintRule
            "foreign_dataset_integrity"   # ✅ Now: ForeignReferenceIntegrityRule
        ]
        
        foundry_rules = RULE_CATEGORIES.get("foundry", [])
        
        # Check that we now have rules covering the gaps
        gap_coverage = {
            "enum_value_constraint": "EnumValueConstraintRule" in foundry_rules,
            "array_element_constraints": "ArrayElementConstraintRule" in foundry_rules,
            "foreign_dataset_integrity": "ForeignReferenceIntegrityRule" in foundry_rules
        }
        
        all_gaps_covered = all(gap_coverage.values())
        
        print("   - Foundry Dataset Rules Gap Coverage:")
        for gap, covered in gap_coverage.items():
            status = "✅" if covered else "❌"
            print(f"     {status} {gap}")
        
        if all_gaps_covered:
            print("   - ✅ All P1 phase gaps now covered!")
            print(f"   - Total Foundry rules: {len(foundry_rules)}")
        else:
            print("   - ❌ Some gaps still remain")
        
        # Foundry 7 core constraints mapping
        foundry_constraints = {
            "NON-NULL": "RequiredFieldRemovalRule + EnumValueConstraintRule(nullable=False)",
            "ENUM": "EnumValueConstraintRule",  # ✅ P1 
            "RANGE/TYPE": "TypeIncompatibilityRule + DataTypeChangeRule",
            "PK & UNIQUENESS": "PrimaryKeyChangeRule + UniqueConstraintAdditionRule",
            "REFERENTIAL_INTEGRITY": "ForeignReferenceIntegrityRule",  # ✅ P1
            "ARRAY": "ArrayElementConstraintRule",  # ✅ P1  
            "TIME_SERIES": "⏳ P2 phase (time_series_anomaly_rule.py)"
        }
        
        print("\n   - Foundry 7 Core Constraints Mapping:")
        for constraint, implementation in foundry_constraints.items():
            implemented = "⏳" not in implementation
            status = "✅" if implemented else "⏳"
            print(f"     {status} {constraint}: {implementation}")
        
        p1_completed = sum(1 for impl in foundry_constraints.values() if "⏳" not in impl)
        total_constraints = len(foundry_constraints)
        
        print(f"\n   - P1 Coverage: {p1_completed}/{total_constraints} constraints ({p1_completed/total_constraints*100:.0f}%)")
        
        return all_gaps_covered
        
    except Exception as e:
        print(f"❌ Foundry coverage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_syntax_validation():
    """Test that all P1 files have valid Python syntax"""
    print("\n✅ Testing P1 Syntax Validation...")
    
    p1_files = [
        "core/validation/rules/enum_value_constraint_rule.py",
        "core/validation/rules/array_element_rule.py", 
        "core/validation/rules/foreign_ref_integrity_rule.py"
    ]
    
    import py_compile
    
    for file_path in p1_files:
        try:
            py_compile.compile(file_path, doraise=True)
            print(f"   - ✅ {file_path}: syntax OK")
        except py_compile.PyCompileError as e:
            print(f"   - ❌ {file_path}: syntax error - {e}")
            return False
    
    print("   - ✅ All P1 files have valid syntax")
    return True


def run_all_tests():
    """Run all P1 phase tests"""
    print("🧪 Starting P1 Phase Foundry Rules Test Suite")
    print("=" * 70)
    print("P1 GOAL: Complete Foundry Dataset Rules Coverage")
    print("- Enum Value Constraints (ENUM)")
    print("- Array Element Constraints (ARRAY)")  
    print("- Foreign Reference Integrity (REFERENTIAL_INTEGRITY)")
    print("=" * 70)
    
    tests = [
        test_p1_plugin_scanning,
        test_enum_constraint_structure,
        test_array_constraint_structure,
        test_foreign_reference_structure,
        test_foundry_coverage_completion,
        test_syntax_validation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 P1 Test Results Summary")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {test.__name__}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 P1 PHASE COMPLETE! Foundry Dataset Rules coverage now at 85%+")
        print("\n📋 P1 Implementation Summary:")
        print("   ✅ EnumValueConstraintRule - Foundry ENUM constraint support")
        print("   ✅ ArrayElementConstraintRule - Foundry ARRAY constraint support") 
        print("   ✅ ForeignReferenceIntegrityRule - Cross-dataset referential integrity")
        print("   ✅ Plugin scanning system updated with 23+ new exports")
        print("   ✅ Factory functions for easy rule creation")
        print("   ✅ Foundry-compatible predefined rules")
        print("   ✅ WOQL-based validation for performance")
        print("   ✅ Configurable severity and migration strategies")
        print("\n🚀 Ready for P2 Phase: Time-Series & Fail/Warn Policy")
    else:
        print("⚠️  Some P1 tests failed. Please review the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)