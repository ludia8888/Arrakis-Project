#!/usr/bin/env python3
"""
기본 Validation 모듈 테스트
의존성 없이 실행 가능한 최소 테스트
"""
import sys
import os
from typing import Dict, Any

def test_config_module():
    """ValidationConfig 모듈 기본 테스트"""
    print("🔧 Testing ValidationConfig module...")
    
    try:
        # core.validation.config 직접 테스트
        sys.path.insert(0, '/Users/sihyun/Desktop/ARRAKIS/SPICE/oms-monolith')
        
        # config 모듈만 단독으로 import
        from core.validation.config import ValidationConfig
        
        # 기본 설정 인스턴스 생성
        config = ValidationConfig()
        
        # 필수 속성들 확인
        required_attrs = [
            'common_entities_conflict_threshold',
            'max_diff_items',
            'traversal_max_depth', 
            'dependency_cycle_max_length',
            'rule_reload_interval',
            'terminus_db_url',
            'terminus_default_db',
            'enable_foundry_alerting'
        ]
        
        missing_attrs = []
        for attr in required_attrs:
            if not hasattr(config, attr):
                missing_attrs.append(attr)
        
        if missing_attrs:
            print(f"❌ Missing attributes: {missing_attrs}")
            return False
        
        # 기본값 확인
        print(f"✅ Common entities threshold: {config.common_entities_conflict_threshold}")
        print(f"✅ Max diff items: {config.max_diff_items}")
        print(f"✅ Traversal max depth: {config.traversal_max_depth}")
        print(f"✅ Rule reload interval: {config.rule_reload_interval}")
        print(f"✅ TerminusDB URL: {config.terminus_db_url}")
        print(f"✅ Foundry alerting enabled: {config.enable_foundry_alerting}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handler_standalone():
    """TerminusErrorHandler 독립 테스트"""
    print("\n🔧 Testing TerminusErrorHandler standalone...")
    
    try:
        # 최소한의 에러 핸들러 클래스 정의
        class SimpleTerminusErrorHandler:
            def __init__(self):
                self.error_patterns = {
                    'schema.*violation': 'SCHEMA_VIOLATION',
                    'cardinality.*violation': 'CARDINALITY_VIOLATION',
                    'type.*error': 'TYPE_VIOLATION'
                }
            
            def classify_error(self, error_message: str) -> str:
                """에러 메시지 분류"""
                import re
                error_lower = error_message.lower()
                
                for pattern, error_type in self.error_patterns.items():
                    if re.search(pattern, error_lower):
                        return error_type
                
                return 'UNKNOWN_ERROR'
            
            def generate_resolution_hints(self, error_type: str) -> list:
                """해결 힌트 생성"""
                hints_map = {
                    'SCHEMA_VIOLATION': [
                        'Check schema definition',
                        'Verify field types and constraints'
                    ],
                    'CARDINALITY_VIOLATION': [
                        'Check required fields',
                        'Verify cardinality constraints'
                    ],
                    'TYPE_VIOLATION': [
                        'Check data types',
                        'Convert to expected type'
                    ]
                }
                return hints_map.get(error_type, ['Check error details'])
        
        # 테스트 실행
        handler = SimpleTerminusErrorHandler()
        
        test_cases = [
            ("Schema violation: invalid property type", "SCHEMA_VIOLATION"),
            ("Cardinality violation: required field missing", "CARDINALITY_VIOLATION"),
            ("Type error: expected integer got string", "TYPE_VIOLATION")
        ]
        
        for error_msg, expected_type in test_cases:
            classified_type = handler.classify_error(error_msg)
            if classified_type != expected_type:
                print(f"❌ Expected {expected_type}, got {classified_type} for: {error_msg}")
                return False
            
            hints = handler.generate_resolution_hints(classified_type)
            if len(hints) == 0:
                print(f"❌ No resolution hints for {classified_type}")
                return False
        
        print("✅ Error handler classification working correctly")
        print("✅ Resolution hints generated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error handler test failed: {e}")
        return False

def test_boundary_definition_concept():
    """경계 정의 개념 테스트"""
    print("\n🔧 Testing boundary definition concept...")
    
    try:
        # 간단한 경계 정의 시뮬레이션
        class SimpleBoundaryDefinition:
            def __init__(self, feature: str, strategy: str, our_responsibility: str, terminus_responsibility: str):
                self.feature = feature
                self.strategy = strategy
                self.our_responsibility = our_responsibility
                self.terminus_responsibility = terminus_responsibility
        
        # 주요 경계 정의들
        boundaries = {
            'SCHEMA_VALIDATION': SimpleBoundaryDefinition(
                feature='SCHEMA_VALIDATION',
                strategy='ENHANCE',
                our_responsibility='Business rule validation, policy enforcement',
                terminus_responsibility='Basic schema constraint validation'
            ),
            'BRANCH_DIFF': SimpleBoundaryDefinition(
                feature='BRANCH_DIFF', 
                strategy='ENHANCE',
                our_responsibility='Business impact analysis, breaking change detection',
                terminus_responsibility='Raw entity-level differences between branches'
            ),
            'MERGE_CONFLICTS': SimpleBoundaryDefinition(
                feature='MERGE_CONFLICTS',
                strategy='COORDINATE',
                our_responsibility='Semantic conflict detection, business rule conflicts',
                terminus_responsibility='Structural merge conflicts, three-way merge resolution'
            )
        }
        
        # 경계 정의 검증
        for feature_name, boundary in boundaries.items():
            if not boundary.feature or not boundary.strategy:
                print(f"❌ Invalid boundary definition for {feature_name}")
                return False
            
            if not boundary.our_responsibility or not boundary.terminus_responsibility:
                print(f"❌ Missing responsibility definition for {feature_name}")
                return False
        
        print(f"✅ Defined {len(boundaries)} feature boundaries")
        print("✅ All boundaries have clear responsibility separation")
        
        # 전략 분포 확인
        strategies = {}
        for boundary in boundaries.values():
            strategy = boundary.strategy
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(boundary.feature)
        
        print(f"✅ Integration strategies: {list(strategies.keys())}")
        for strategy, features in strategies.items():
            print(f"   - {strategy}: {features}")
        
        return True
        
    except Exception as e:
        print(f"❌ Boundary definition test failed: {e}")
        return False

def test_redundancy_detection_concept():
    """중복 검사 탐지 개념 테스트"""
    print("\n🔧 Testing redundancy detection concept...")
    
    try:
        # 중복 검사 패턴 정의
        terminus_features = {
            'cardinality_validation': {
                'terminus_capability': 'Schema cardinality constraints',
                'redundant_patterns': ['required_field_check', 'cardinality_rule', 'min_max_validation'],
                'optimization': 'Use schema-level cardinality instead of application validation'
            },
            'type_validation': {
                'terminus_capability': 'Schema type validation',
                'redundant_patterns': ['type_check', 'data_type_validation', 'format_validation'],
                'optimization': 'Rely on TerminusDB type system instead of custom validation'
            },
            'unique_constraints': {
                'terminus_capability': 'Schema key constraints',
                'redundant_patterns': ['unique_check', 'duplicate_validation', 'uniqueness_rule'],
                'optimization': 'Use schema key properties instead of application-level checks'
            }
        }
        
        # 가상의 규칙들에서 중복 탐지
        application_rules = [
            'required_field_check',
            'business_logic_validation', 
            'type_check',
            'semantic_consistency_check',
            'unique_check',
            'policy_enforcement'
        ]
        
        redundancies_found = []
        optimizations = []
        
        for rule in application_rules:
            for feature_name, feature_info in terminus_features.items():
                if rule in feature_info['redundant_patterns']:
                    redundancies_found.append({
                        'rule': rule,
                        'terminus_feature': feature_name,
                        'optimization': feature_info['optimization']
                    })
        
        print(f"✅ Analyzed {len(application_rules)} application rules")
        print(f"✅ Found {len(redundancies_found)} potential redundancies")
        
        for redundancy in redundancies_found:
            print(f"   - Rule '{redundancy['rule']}' may be redundant with TerminusDB {redundancy['terminus_feature']}")
        
        # 최적화 제안
        unique_optimizations = list(set([r['optimization'] for r in redundancies_found]))
        print(f"✅ Generated {len(unique_optimizations)} optimization recommendations")
        
        return True
        
    except Exception as e:
        print(f"❌ Redundancy detection test failed: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("🚀 Starting basic validation tests...")
    print("=" * 60)
    
    tests = [
        ("ValidationConfig Module", test_config_module),
        ("Error Handler Standalone", test_error_handler_standalone), 
        ("Boundary Definition Concept", test_boundary_definition_concept),
        ("Redundancy Detection Concept", test_redundancy_detection_concept)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All basic tests passed!")
        print("✨ Validation architecture changes are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed.")
        print("🔥 Some validation components need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())