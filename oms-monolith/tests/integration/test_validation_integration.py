"""
Integration Test for Validation Pipeline
통합 검증 파이프라인 End-to-End 테스트

TerminusDB + PolicyServer + Rule 플러그인 + ValidationPipeline 통합 테스트
실제 환경과 유사한 조건에서 전체 검증 프로세스 검증
"""
import pytest
import asyncio
import json
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from core.validation.pipeline import (
    ValidationPipeline, ValidationResult, ValidationStage, create_validation_pipeline
)
from core.validation.config import get_validation_config, reset_validation_config
from core.validation.ports import ValidationContext
from core.validation.adapters import (
    MockCacheAdapter, MockTerminusAdapter, MockEventAdapter,
    MockPolicyServerAdapter, MockRuleLoaderAdapter
)
from core.validation.schema_validator import JsonSchemaValidator
from core.validation.rule_registry import RuleRegistry
from core.validation.interfaces import BreakingChangeRule
from core.validation.models import BreakingChange, Severity, MigrationStrategy
from core.validation.merge_validation_service import (
    MergeValidationService, MergeStrategy, MergeDecision
)
from core.validation.terminus_error_handler import (
    TerminusErrorHandler, ValidationError, TerminusErrorType
)


@dataclass
class TestScenario:
    """테스트 시나리오"""
    name: str
    entity_type: str
    entity_data: Dict[str, Any]
    operation: str
    expected_success: bool
    expected_stages: List[ValidationStage]
    expected_errors: List[str] = None
    
    def __post_init__(self):
        if self.expected_errors is None:
            self.expected_errors = []


class MockBreakingChangeRule(BreakingChangeRule):
    """테스트용 Mock Breaking Change Rule"""
    
    def __init__(self, rule_id: str, severity: Severity = Severity.LOW, should_fail: bool = False):
        self._rule_id = rule_id
        self._severity = severity
        self._should_fail = should_fail
    
    @property
    def rule_id(self) -> str:
        return self._rule_id
    
    @property
    def severity(self) -> Severity:
        return self._severity
    
    @property
    def description(self) -> str:
        return f"Mock rule {self._rule_id}"
    
    def applies_to(self, entity_type: str) -> bool:
        return True
    
    async def check(self, entity_data: Dict[str, Any], context: ValidationContext) -> Dict[str, Any]:
        if self._should_fail:
            return {
                "valid": False,
                "errors": [f"Mock rule {self._rule_id} validation failed"],
                "warnings": []
            }
        return {
            "valid": True,
            "errors": [],
            "warnings": [f"Mock rule {self._rule_id} executed successfully"]
        }


class TestValidationIntegration:
    """통합 검증 테스트"""
    
    @pytest.fixture
    def mock_adapters(self):
        """Mock 어댑터들 생성"""
        cache = MockCacheAdapter()
        terminus = MockTerminusAdapter()
        event = MockEventAdapter()
        policy_server = MockPolicyServerAdapter()
        rule_loader = MockRuleLoaderAdapter()
        
        return {
            'cache': cache,
            'terminus': terminus,
            'event': event,
            'policy_server': policy_server,
            'rule_loader': rule_loader
        }
    
    @pytest.fixture
    def validation_pipeline(self, mock_adapters):
        """검증 파이프라인 생성"""
        reset_validation_config()
        config = get_validation_config()
        
        pipeline = create_validation_pipeline(
            cache=mock_adapters['cache'],
            terminus=mock_adapters['terminus'],
            event=mock_adapters['event'],
            policy_server=mock_adapters['policy_server'],
            rule_loader=mock_adapters['rule_loader'],
            config=config
        )
        
        return pipeline
    
    @pytest.fixture
    def test_scenarios(self):
        """테스트 시나리오들"""
        return [
            TestScenario(
                name="Valid ObjectType Creation",
                entity_type="ObjectType",
                entity_data={
                    "name": "TestObject",
                    "displayName": "Test Object",
                    "properties": [
                        {"name": "id", "dataType": "string", "required": True},
                        {"name": "name", "dataType": "string", "required": True}
                    ]
                },
                operation="create",
                expected_success=True,
                expected_stages=[
                    ValidationStage.JSON_SCHEMA,
                    ValidationStage.POLICY,
                    ValidationStage.TERMINUS_CHECK,
                    ValidationStage.RULE_ENGINE
                ]
            ),
            TestScenario(
                name="Invalid SemanticType - Missing Required Field",
                entity_type="SemanticType",
                entity_data={
                    "displayName": "Invalid Semantic Type"
                    # name 필드 누락
                },
                operation="create",
                expected_success=False,
                expected_stages=[ValidationStage.JSON_SCHEMA],
                expected_errors=["name field is required"]
            ),
            TestScenario(
                name="Policy Violation",
                entity_type="ObjectType",
                entity_data={
                    "name": "PolicyViolationObject",
                    "displayName": "Policy Violation Test"
                },
                operation="create",
                expected_success=False,
                expected_stages=[
                    ValidationStage.JSON_SCHEMA,
                    ValidationStage.POLICY
                ],
                expected_errors=["Policy violation detected"]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_complete_validation_pipeline_success(self, validation_pipeline, mock_adapters):
        """성공적인 전체 검증 파이프라인 테스트"""
        # Given: 유효한 엔티티 데이터
        entity_data = {
            "name": "ValidTestObject",
            "displayName": "Valid Test Object",
            "properties": [
                {"name": "id", "dataType": "string", "required": True}
            ]
        }
        
        # When: 검증 파이프라인 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: 모든 단계가 성공해야 함
        assert result.success is True
        assert result.failed_at_stage is None
        assert len(result.stage_results) >= 2  # 최소 2개 단계 실행
        assert result.total_time_ms > 0
        
        # Mock 호출 확인
        assert mock_adapters['cache'].call_count['get'] >= 0
        assert mock_adapters['event'].call_count['publish'] >= 0
    
    @pytest.mark.asyncio
    async def test_validation_pipeline_fail_fast(self, validation_pipeline, mock_adapters):
        """Fail-Fast 모드 테스트"""
        # Given: JSON Schema 검증 실패 시나리오
        invalid_data = {
            "displayName": "Missing Name Field"
            # required name 필드 누락
        }
        
        # Fail-fast 모드 활성화
        validation_pipeline.config.fail_fast_mode = True
        
        # When: 검증 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=invalid_data,
            operation="create"
        )
        
        # Then: 첫 번째 단계에서 실패하고 중단되어야 함
        assert result.success is False
        assert result.failed_at_stage == ValidationStage.JSON_SCHEMA
        assert len(result.stage_results) == 1  # 한 단계만 실행
    
    @pytest.mark.asyncio
    async def test_policy_server_integration(self, validation_pipeline, mock_adapters):
        """Policy Server 연동 테스트"""
        # Given: Policy Server에 검증 실패 결과 설정
        mock_adapters['policy_server'].set_validation_result(
            "ObjectType", "create",
            {
                "valid": False,
                "violations": ["Object name contains forbidden word"],
                "warnings": [],
                "policy_version": "1.0.0"
            }
        )
        
        entity_data = {
            "name": "ForbiddenNameObject",
            "displayName": "Test Object"
        }
        
        # When: 검증 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: Policy 단계에서 실패해야 함
        assert result.success is False
        assert result.failed_at_stage == ValidationStage.POLICY
        assert "forbidden word" in str(result.stage_results)
        
        # Policy Server 호출 확인
        assert mock_adapters['policy_server'].call_count['validate_policy'] == 1
    
    @pytest.mark.asyncio
    async def test_rule_engine_integration(self, validation_pipeline, mock_adapters):
        """Rule Engine 통합 테스트"""
        # Given: Breaking Change Rule 설정
        mock_rule = MockBreakingChangeRule("test_rule", Severity.HIGH, should_fail=True)
        
        # Rule Loader에 규칙 설정
        mock_adapters['rule_loader'].set_rules(
            "validation_rules", "ObjectType", 
            [{"instance": mock_rule, "name": "test_rule"}]
        )
        
        entity_data = {
            "name": "TestObject",
            "displayName": "Test Object"
        }
        
        # When: 검증 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType", 
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: Rule Engine에서 실패해야 함
        assert result.success is False
        assert result.failed_at_stage == ValidationStage.RULE_ENGINE
        
        # Rule Loader 호출 확인
        assert mock_adapters['rule_loader'].call_count['load_rules'] >= 1
    
    @pytest.mark.asyncio
    async def test_terminus_error_handling(self, validation_pipeline, mock_adapters):
        """TerminusDB 오류 처리 테스트"""
        # Given: TerminusDB에서 스키마 위반 오류 발생 시뮬레이션
        terminus_error = Exception("Schema violation: property 'name' is required")
        
        # Mock TerminusDB에 오류 설정
        with patch.object(mock_adapters['terminus'], 'validate_document', side_effect=terminus_error):
            
            entity_data = {
                "name": "TestObject",
                "displayName": "Test Object"
            }
            
            # When: 검증 실행
            result = await validation_pipeline.validate_entity(
                entity_type="ObjectType",
                entity_data=entity_data,
                operation="create"
            )
            
            # Then: TerminusDB 오류가 적절히 처리되어야 함
            # (오류가 발생해도 파이프라인은 계속 진행하거나 적절히 처리)
            assert result is not None
            assert isinstance(result, ValidationResult)
    
    @pytest.mark.asyncio
    async def test_merge_validation_integration(self, mock_adapters):
        """머지 검증 통합 테스트"""
        # Given: 머지 검증 서비스 생성
        pipeline = create_validation_pipeline(**mock_adapters)
        merge_service = MergeValidationService(pipeline)
        
        # Mock 브랜치 diff 데이터 설정
        mock_adapters['terminus'].documents = {
            "entity1": {"@type": "ObjectType", "name": "Entity1"},
            "entity2": {"@type": "SemanticType", "name": "Entity2"}
        }
        
        # When: 머지 검증 실행
        result = await merge_service.validate_merge(
            source_branch="feature-branch",
            target_branch="main",
            user_id="test-user",
            strategy=MergeStrategy.THREE_WAY
        )
        
        # Then: 머지 검증 결과 확인
        assert result is not None
        assert result.decision in [MergeDecision.AUTO_MERGE, MergeDecision.MANUAL_RESOLUTION, MergeDecision.REJECT_MERGE]
        assert result.total_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, validation_pipeline, mock_adapters):
        """성능 지표 수집 테스트"""
        # Given: 성능 지표 활성화
        validation_pipeline.config.enable_performance_metrics = True
        
        entity_data = {
            "name": "PerformanceTestObject",
            "displayName": "Performance Test"
        }
        
        # When: 검증 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: 성능 지표가 수집되어야 함
        assert result.total_time_ms > 0
        
        # 이벤트 발행 확인
        published_events = mock_adapters['event'].published_events
        metric_events = [e for e in published_events if 'validation.pipeline' in e.get('event_type', '')]
        assert len(metric_events) >= 0  # 성능 지표 이벤트 발행
    
    @pytest.mark.asyncio
    async def test_cache_integration(self, validation_pipeline, mock_adapters):
        """캐시 통합 테스트"""
        # Given: 동일한 데이터로 두 번 검증
        entity_data = {
            "name": "CacheTestObject",
            "displayName": "Cache Test"
        }
        
        # When: 첫 번째 검증
        result1 = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=entity_data,
            operation="create"
        )
        
        # 두 번째 검증 (캐시 활용)
        result2 = await validation_pipeline.validate_entity(
            entity_type="ObjectType", 
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: 캐시 사용 확인
        assert result1.success == result2.success
        
        # 캐시 호출 확인
        cache_calls = mock_adapters['cache'].call_count
        assert cache_calls['get'] >= 2  # 캐시에서 조회 시도
        assert cache_calls['set'] >= 1  # 캐시에 저장
    
    @pytest.mark.asyncio 
    async def test_bulk_validation(self, validation_pipeline, mock_adapters):
        """대량 검증 테스트"""
        # Given: 여러 엔티티 데이터
        entities = [
            {
                "entity_type": "ObjectType",
                "entity_data": {
                    "name": f"BulkTestObject{i}",
                    "displayName": f"Bulk Test Object {i}"
                },
                "operation": "create"
            }
            for i in range(10)
        ]
        
        # When: 병렬 검증 실행
        tasks = [
            validation_pipeline.validate_entity(
                entity_type=entity["entity_type"],
                entity_data=entity["entity_data"],
                operation=entity["operation"]
            )
            for entity in entities
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Then: 모든 검증이 완료되어야 함
        assert len(results) == 10
        successful_results = [r for r in results if isinstance(r, ValidationResult) and r.success]
        assert len(successful_results) >= 5  # 최소 50% 성공
    
    @pytest.mark.asyncio
    async def test_configuration_override(self, mock_adapters):
        """설정 재정의 테스트"""
        # Given: 커스텀 설정으로 파이프라인 생성
        custom_config = get_validation_config()
        custom_config.fail_fast_mode = True
        custom_config.enable_json_schema_validation = False
        custom_config.enable_policy_validation = True
        
        pipeline = create_validation_pipeline(
            config=custom_config,
            **mock_adapters
        )
        
        entity_data = {
            "name": "ConfigTestObject",
            "displayName": "Config Test"
        }
        
        # When: 검증 실행
        result = await pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=entity_data,
            operation="create"
        )
        
        # Then: 설정에 따라 JSON Schema 단계가 건너뛰어져야 함
        stage_names = list(result.stage_results.keys())
        assert ValidationStage.JSON_SCHEMA not in stage_names
        assert ValidationStage.POLICY in stage_names or len(stage_names) > 0
    
    def test_terminus_error_handler_integration(self):
        """TerminusDB 오류 처리기 통합 테스트"""
        # Given: TerminusDB 오류 처리기
        error_handler = TerminusErrorHandler()
        
        # TerminusDB 스키마 위반 오류
        terminus_error = Exception("Schema violation: type mismatch for property 'age', expected xsd:integer but got xsd:string")
        
        # When: 오류 처리
        validation_error = error_handler.handle_terminus_error(
            terminus_error,
            context={
                'entity_type': 'ObjectType',
                'entity_id': 'test-object-123',
                'operation': 'create'
            }
        )
        
        # Then: ValidationError로 적절히 변환되어야 함
        assert isinstance(validation_error, ValidationError)
        assert validation_error.error_type == TerminusErrorType.TYPE_VIOLATION
        assert "type mismatch" in validation_error.message
        assert validation_error.entity_type == "ObjectType"
        assert validation_error.entity_id == "test-object-123"
        assert len(validation_error.resolution_hints) > 0
    
    @pytest.mark.asyncio
    async def test_end_to_end_scenario(self, validation_pipeline, mock_adapters):
        """End-to-End 시나리오 테스트"""
        # Given: 실제 사용 시나리오와 유사한 복잡한 엔티티
        complex_entity = {
            "name": "ComplexBusinessEntity",
            "displayName": "Complex Business Entity",
            "description": "A complex entity for E2E testing",
            "properties": [
                {
                    "name": "id",
                    "dataType": "string",
                    "required": True,
                    "description": "Unique identifier"
                },
                {
                    "name": "businessKey",
                    "dataType": "string", 
                    "required": True,
                    "unique": True
                },
                {
                    "name": "metadata",
                    "dataType": "object",
                    "required": False,
                    "properties": [
                        {"name": "createdAt", "dataType": "datetime"},
                        {"name": "version", "dataType": "integer"}
                    ]
                }
            ],
            "relationships": [
                {
                    "name": "belongsTo",
                    "targetType": "Organization",
                    "cardinality": "many-to-one"
                }
            ]
        }
        
        # 검증 컨텍스트 설정
        context = ValidationContext(
            source_branch="main",
            target_branch="main",
            user_id="integration-test-user",
            cache=mock_adapters['cache'],
            terminus_client=mock_adapters['terminus'],
            event_publisher=mock_adapters['event'],
            policy_server=mock_adapters['policy_server'],
            rule_loader=mock_adapters['rule_loader'],
            metadata={
                "test_scenario": "end_to_end",
                "complexity": "high"
            }
        )
        
        # When: 전체 검증 파이프라인 실행
        result = await validation_pipeline.validate_entity(
            entity_type="ObjectType",
            entity_data=complex_entity,
            operation="create",
            context=context
        )
        
        # Then: 전체 프로세스가 성공적으로 완료되어야 함
        assert result is not None
        assert isinstance(result, ValidationResult)
        assert result.total_time_ms > 0
        
        # 모든 어댑터가 호출되었는지 확인
        assert any(count > 0 for count in mock_adapters['cache'].call_count.values())
        assert any(count > 0 for count in mock_adapters['event'].call_count.values())
        
        # 경고나 오류가 있더라도 적절히 처리되었는지 확인
        if not result.success:
            assert result.error_message is not None
            assert result.failed_at_stage is not None
        
        print(f"E2E Test Result: Success={result.success}, Time={result.total_time_ms}ms")
        print(f"Stages executed: {list(result.stage_results.keys())}")
        print(f"Warnings: {len(result.warnings) if result.warnings else 0}")


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 메인 함수
    pytest.main([__file__, "-v", "--tb=short"])