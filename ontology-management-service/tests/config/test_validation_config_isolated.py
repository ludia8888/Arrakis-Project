"""
Production ValidationConfig test - 100% Real Implementation
전체 시스템과 연동하여 실제 validation_config를 테스트한다.
Zero Mock patterns - 실제 파일 시스템과 환경변수 사용.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add data-kernel-service to path manually
data_kernel_path = Path(__file__).parent.parent.parent.parent / "data-kernel-service"
sys.path.insert(0, str(data_kernel_path))

# Import ValidationConfig directly from the file to avoid package dependencies
validation_config_path = data_kernel_path / "hook" / "validation_config.py"
spec = sys.modules.get("validation_config_module")
if spec is None:
 import importlib.util

 spec = importlib.util.spec_from_file_location(
 "validation_config_module", validation_config_path
 )
 validation_config_module = importlib.util.module_from_spec(spec)
 sys.modules["validation_config_module"] = validation_config_module
 spec.loader.exec_module(validation_config_module)
else:
 validation_config_module = spec

ValidationConfig = validation_config_module.ValidationConfig


class TestValidationConfigIsolated:
 """완전히 독립적인 ValidationConfig 테스트"""

 def test_validation_config_basic_initialization(self):
 """기본 초기화 테스트"""
 config = ValidationConfig()

 # 기본 스키마들이 로드되었는지 확인
 assert config.get_schema("ObjectType") is not None
 assert config.get_schema("Branch") is not None
 assert config.get_schema("ValidationRule") is not None
 assert config.get_schema("AuditEvent") is not None

 def test_validation_config_settings(self):
 """기본 설정 테스트"""
 config = ValidationConfig()
 settings = config.get_all_settings()

 # 필수 설정들이 있는지 확인
 assert "strict_mode" in settings
 assert "enable_custom_rules" in settings
 assert "max_validation_errors" in settings
 assert "validation_timeout_seconds" in settings

 # 기본값 확인
 assert settings["strict_mode"] is False
 assert settings["enable_custom_rules"] is True
 assert settings["max_validation_errors"] == 10
 assert settings["validation_timeout_seconds"] == 30.0

 def test_environment_variable_override(self):
 """실제 환경변수 오버라이드 테스트"""
 # 현재 환경변수 백업
 original_vars = {}
 test_vars = {
 "SCHEMA_NAME_MAX_LENGTH": "200",
 "VALIDATION_STRICT_MODE": "true",
 "MAX_VALIDATION_ERRORS": "20",
 }

 for key in test_vars:
 original_vars[key] = os.environ.get(key)
 os.environ[key] = test_vars[key]

 try:
 config = ValidationConfig()

 # 환경변수가 반영되었는지 확인
 object_schema = config.get_schema("ObjectType")
 assert object_schema["properties"]["name"]["maxLength"] == 200

 settings = config.get_all_settings()
 assert settings["strict_mode"] is True
 assert settings["max_validation_errors"] == 20

 finally:
 # 환경변수 복원
 for key, original_value in original_vars.items():
 if original_value is None:
 os.environ.pop(key, None)
 else:
 os.environ[key] = original_value

 def test_custom_config_file_loading(self):
 """실제 커스텀 설정 파일 로딩 테스트"""
 custom_config = {
 "schemas": {
 "CustomType": {
 "required": ["name"],
 "properties": {"name": {"type": "string", "maxLength": 50}},
 }
 },
 "validation_settings": {
 "custom_setting": "custom_value",
 "max_validation_errors": 5,
 },
 }

 # 실제 임시 파일 생성
 with tempfile.NamedTemporaryFile(
 mode = "w", suffix = ".json", delete = False
 ) as temp_file:
 json.dump(custom_config, temp_file, indent = 2)
 temp_config_path = temp_file.name

 try:
 # 실제 파일로 ValidationConfig 초기화
 config = ValidationConfig(config_file = temp_config_path)

 # 커스텀 스키마가 로드되었는지 확인
 custom_schema = config.get_schema("CustomType")
 assert custom_schema is not None
 assert custom_schema["properties"]["name"]["maxLength"] == 50

 # 커스텀 설정이 로드되었는지 확인
 assert config.get_setting("custom_setting") == "custom_value"
 assert config.get_setting("max_validation_errors") == 5

 finally:
 # 임시 파일 정리
 os.unlink(temp_config_path)

 def test_schema_validation_patterns(self):
 """스키마 유효성 검사 패턴 테스트"""
 config = ValidationConfig()

 # Branch 스키마의 이름 패턴 확인
 branch_schema = config.get_schema("Branch")
 name_pattern = branch_schema["properties"]["name"]["pattern"]
 assert name_pattern == "^[a-zA-Z0-9_/-]+$"

 # ValidationRule 스키마의 enum 값 확인
 rule_schema = config.get_schema("ValidationRule")
 rule_types = rule_schema["properties"]["rule_type"]["enum"]
 assert "schema" in rule_types
 assert "business" in rule_types
 assert "security" in rule_types

 def test_configurable_rule_types(self):
 """실제 설정 가능한 규칙 타입 테스트"""
 # 기본 규칙 타입
 config = ValidationConfig()
 schema = config.get_schema("ValidationRule")
 rule_types = schema["properties"]["rule_type"]["enum"]
 assert rule_types == ["schema", "business", "security"]

 # 커스텀 규칙 타입 - 실제 환경변수 설정
 original_value = os.environ.get("VALIDATION_RULE_TYPES")
 os.environ["VALIDATION_RULE_TYPES"] = "custom1,custom2,custom3"

 try:
 config = ValidationConfig()
 schema = config.get_schema("ValidationRule")
 rule_types = schema["properties"]["rule_type"]["enum"]
 assert rule_types == ["custom1", "custom2", "custom3"]
 finally:
 # 환경변수 복원
 if original_value is None:
 os.environ.pop("VALIDATION_RULE_TYPES", None)
 else:
 os.environ["VALIDATION_RULE_TYPES"] = original_value

 def test_error_handling(self):
 """실제 파일 오류 처리 테스트"""
 # 존재하지 않는 파일 경로로 테스트
 non_existent_path = "/tmp/definitely_missing_config_file_12345.json"

 # 파일이 존재하지 않음을 확인
 assert not Path(non_existent_path).exists()

 # 파일 읽기 오류 시 기본값 사용
 config = ValidationConfig(config_file = non_existent_path)

 # 기본 스키마들이 여전히 사용 가능한지 확인
 assert config.get_schema("ObjectType") is not None
 assert config.get_schema("Branch") is not None
 print("✓ Non-existent config file handled gracefully with fallback to defaults")

 # 잘못된 JSON 파일로 테스트
 with tempfile.NamedTemporaryFile(
 mode = "w", suffix = ".json", delete = False
 ) as bad_json_file:
 bad_json_file.write("{invalid json content}")
 bad_json_path = bad_json_file.name

 try:
 # 잘못된 JSON 파일로 초기화
 config = ValidationConfig(config_file = bad_json_path)

 # 기본 스키마들이 여전히 사용 가능한지 확인
 assert config.get_schema("ObjectType") is not None
 assert config.get_schema("Branch") is not None
 print(
 "✓ Invalid JSON config file handled gracefully with fallback to defaults"
 )

 finally:
 # 임시 파일 정리
 os.unlink(bad_json_path)


def run_tests():
 """테스트를 직접 실행"""
 test_instance = TestValidationConfigIsolated()

 tests = [
 test_instance.test_validation_config_basic_initialization,
 test_instance.test_validation_config_settings,
 test_instance.test_environment_variable_override,
 test_instance.test_custom_config_file_loading,
 test_instance.test_schema_validation_patterns,
 test_instance.test_configurable_rule_types,
 test_instance.test_error_handling,
 ]

 passed = 0
 failed = 0

 for test in tests:
 try:
 print(f"Running {test.__name__}... ", end = "")
 test()
 print("✓ PASSED")
 passed += 1
 except Exception as e:
 print(f"✗ FAILED: {e}")
 failed += 1

 print(f"\nResults: {passed} passed, {failed} failed")
 return failed == 0


if __name__ == "__main__":
 # pytest 없이 직접 실행
 success = run_tests()
 exit(0 if success else 1)
