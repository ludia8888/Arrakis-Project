#!/usr/bin/env python3
"""
간단한 Validation 통합 테스트
의존성 문제를 최소화한 기본 테스트
"""
import sys
import asyncio
from typing import Dict, Any
from dataclasses import dataclass

# 필요한 모듈만 import
try:
    from core.validation.config import get_validation_config, reset_validation_config
    from core.validation.terminus_error_handler import TerminusErrorHandler, ValidationError, TerminusErrorType
    from core.validation.terminus_boundary_definition import get_boundary_manager, TerminusFeature, validate_terminus_integration
    print("✅ Core validation modules imported successfully")
except ImportError as e:
    print(f"❌ Failed to import core validation modules: {e}")
    sys.exit(1)


class SimpleTest:
    """간단한 검증 테스트"""
    
    def test_validation_config(self):
        """ValidationConfig 통합 설정 테스트"""
        print("\n🔧 Testing ValidationConfig integration...")
        
        try:
            reset_validation_config()
            config = get_validation_config()
            
            # 통합된 설정들이 존재하는지 확인
            required_attrs = [
                'common_entities_conflict_threshold',
                'max_diff_items', 
                'traversal_max_depth',
                'dependency_cycle_max_length',
                'rule_reload_interval',
                'terminus_db_url',
                'terminus_default_db',
                'enable_json_schema_validation',
                'enable_policy_validation',
                'fail_fast_mode'
            ]
            
            missing_attrs = []
            for attr in required_attrs:
                if not hasattr(config, attr):
                    missing_attrs.append(attr)
            
            if missing_attrs:
                print(f"❌ Missing config attributes: {missing_attrs}")
                return False
            
            # Helper 메서드 확인
            helper_methods = ['get_schema_uri', 'get_msa_service', 'is_high_impact_change']
            missing_methods = []
            for method in helper_methods:
                if not hasattr(config, method):
                    missing_methods.append(method)
            
            if missing_methods:
                print(f"❌ Missing helper methods: {missing_methods}")
                return False
            
            print("✅ ValidationConfig integration test passed")
            print(f"   - Common entities threshold: {config.common_entities_conflict_threshold}")
            print(f"   - Max diff items: {config.max_diff_items}")
            print(f"   - Traversal max depth: {config.traversal_max_depth}")
            print(f"   - Rule reload interval: {config.rule_reload_interval}")
            return True
            
        except Exception as e:
            print(f"❌ ValidationConfig test failed: {e}")
            return False
    
    def test_terminus_error_handler(self):
        """TerminusDB 오류 처리기 테스트"""
        print("\n🔧 Testing TerminusDB error handler...")
        
        try:
            error_handler = TerminusErrorHandler()
            
            # 다양한 TerminusDB 오류 시나리오 테스트
            test_errors = [
                {
                    "error": Exception("Schema violation: type mismatch for property 'age'"),
                    "expected_type": TerminusErrorType.SCHEMA_VIOLATION,
                    "context": {"entity_type": "ObjectType", "operation": "create"}
                },
                {
                    "error": Exception("Cardinality violation: required property 'name' missing"),
                    "expected_type": TerminusErrorType.CARDINALITY_VIOLATION,
                    "context": {"entity_type": "SemanticType", "operation": "update"}
                },
                {
                    "error": Exception("Constraint violation: duplicate key unique index"),
                    "expected_type": TerminusErrorType.CONSTRAINT_VIOLATION,
                    "context": {"entity_type": "Relationship", "operation": "create"}
                }
            ]
            
            for i, test_case in enumerate(test_errors):
                validation_error = error_handler.handle_terminus_error(
                    test_case["error"], 
                    test_case["context"]
                )
                
                if not isinstance(validation_error, ValidationError):
                    print(f"❌ Test {i+1}: Expected ValidationError, got {type(validation_error)}")
                    return False
                
                if validation_error.error_type != test_case["expected_type"]:
                    print(f"❌ Test {i+1}: Expected {test_case['expected_type']}, got {validation_error.error_type}")
                    return False
                
                if len(validation_error.resolution_hints) == 0:
                    print(f"❌ Test {i+1}: No resolution hints provided")
                    return False
            
            print("✅ TerminusDB error handler test passed")
            print(f"   - Tested {len(test_errors)} error scenarios")
            print(f"   - All errors properly classified and handled")
            return True
            
        except Exception as e:
            print(f"❌ TerminusDB error handler test failed: {e}")
            return False
    
    def test_terminus_boundary_definition(self):
        """TerminusDB 경계 정의 테스트"""
        print("\n🔧 Testing TerminusDB boundary definitions...")
        
        try:
            boundary_manager = get_boundary_manager()
            
            # 주요 TerminusDB 기능들의 경계 정의 확인
            features_to_test = [
                TerminusFeature.SCHEMA_VALIDATION,
                TerminusFeature.BRANCH_DIFF,
                TerminusFeature.MERGE_CONFLICTS,
                TerminusFeature.PATH_QUERIES,
                TerminusFeature.ACL_SYSTEM
            ]
            
            for feature in features_to_test:
                boundary = boundary_manager.get_boundary(feature)
                if not boundary:
                    print(f"❌ No boundary definition for {feature}")
                    return False
                
                # 필수 필드 확인
                required_fields = [
                    'terminus_feature',
                    'strategy',
                    'our_layer_responsibility',
                    'terminus_responsibility',
                    'integration_points',
                    'conflict_resolution'
                ]
                
                for field in required_fields:
                    if not hasattr(boundary, field) or getattr(boundary, field) is None:
                        print(f"❌ Missing {field} in boundary for {feature}")
                        return False
            
            # 통합 검증 테스트
            schema_integration = validate_terminus_integration(
                TerminusFeature.SCHEMA_VALIDATION,
                "test_operation"
            )
            
            if not schema_integration.get("valid"):
                print(f"❌ Schema validation integration failed")
                return False
            
            # 통합 요약 테스트
            summary = boundary_manager.get_integration_summary()
            if summary["total_features"] == 0:
                print("❌ No features defined in integration summary")
                return False
            
            print("✅ TerminusDB boundary definition test passed")
            print(f"   - Tested {len(features_to_test)} feature boundaries")
            print(f"   - Total features defined: {summary['total_features']}")
            print(f"   - Integration strategies: {list(summary['strategies'].keys())}")
            return True
            
        except Exception as e:
            print(f"❌ TerminusDB boundary definition test failed: {e}")
            return False
    
    def test_configuration_consistency(self):
        """설정 일관성 테스트"""
        print("\n🔧 Testing configuration consistency...")
        
        try:
            config = get_validation_config()
            
            # 임계값 일관성 확인
            thresholds = {
                'common_entities_conflict_threshold': config.common_entities_conflict_threshold,
                'max_diff_items': config.max_diff_items,
                'traversal_max_depth': config.traversal_max_depth,
                'dependency_cycle_max_length': config.dependency_cycle_max_length
            }
            
            for name, value in thresholds.items():
                if not isinstance(value, int) or value <= 0:
                    print(f"❌ Invalid threshold value for {name}: {value}")
                    return False
            
            # URL 형식 확인
            if not config.terminus_db_url.startswith(('http://', 'https://')):
                print(f"❌ Invalid TerminusDB URL format: {config.terminus_db_url}")
                return False
            
            # 시간 제한 확인
            if config.terminus_timeout <= 0:
                print(f"❌ Invalid timeout value: {config.terminus_timeout}")
                return False
            
            print("✅ Configuration consistency test passed")
            print(f"   - All threshold values are positive integers")
            print(f"   - TerminusDB URL format is valid")
            print(f"   - Timeout values are appropriate")
            return True
            
        except Exception as e:
            print(f"❌ Configuration consistency test failed: {e}")
            return False
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 Starting validation integration tests...")
        print("=" * 60)
        
        tests = [
            self.test_validation_config,
            self.test_terminus_error_handler,
            self.test_terminus_boundary_definition,
            self.test_configuration_consistency
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test {test.__name__} failed with exception: {e}")
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("\n🎉 All tests passed! Validation integration is working correctly.")
            return True
        else:
            print(f"\n⚠️  {failed} test(s) failed. Please check the implementation.")
            return False


def main():
    """메인 테스트 실행"""
    test_runner = SimpleTest()
    success = test_runner.run_all_tests()
    
    if success:
        print("\n✨ Validation system is ready for production!")
        return 0
    else:
        print("\n🔥 Validation system needs attention before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())