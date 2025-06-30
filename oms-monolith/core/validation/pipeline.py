"""
Unified Validation Pipeline
통합 검증 파이프라인 - Single Source of Truth

JSONSchema → Policy → TerminusDB → RuleEngine 순서로 실행
중복 검증 최소화 및 실패-Fast 최적화
"""
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from core.validation.config import get_validation_config
from core.validation.ports import (
    CachePort, TerminusPort, EventPort, 
    PolicyServerPort, RuleLoaderPort, ValidationContext
)
from core.validation.schema_validator import JsonSchemaValidator
from core.validation.rule_registry import RuleRegistry
from core.validation.interfaces import BreakingChangeRule
from core.validation.terminus_boundary_definition import (
    get_boundary_manager, TerminusFeature, validate_terminus_integration
)

logger = logging.getLogger(__name__)


class ValidationStage(str, Enum):
    """검증 단계"""
    JSON_SCHEMA = "json_schema"
    POLICY = "policy"
    TERMINUS_CHECK = "terminus_check"
    RULE_ENGINE = "rule_engine"
    FOUNDRY_ALERTING = "foundry_alerting"


@dataclass
class ValidationResult:
    """통합 검증 결과"""
    success: bool
    stage_results: Dict[ValidationStage, Dict[str, Any]]
    total_time_ms: float
    failed_at_stage: Optional[ValidationStage] = None
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class StageResult:
    """단일 단계 검증 결과"""
    stage: ValidationStage
    success: bool
    time_ms: float
    details: Dict[str, Any]
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class ValidationPipeline:
    """
    통합 검증 파이프라인
    TerminusDB 고유 기능과 중복을 최소화하면서 단계별 검증 수행
    """
    
    def __init__(
        self,
        cache: Optional[CachePort] = None,
        terminus: Optional[TerminusPort] = None,
        event: Optional[EventPort] = None,
        policy_server: Optional[PolicyServerPort] = None,
        rule_loader: Optional[RuleLoaderPort] = None,
        config=None
    ):
        self.config = config or get_validation_config()
        self.cache = cache
        self.terminus = terminus
        self.event = event
        self.policy_server = policy_server
        self.rule_loader = rule_loader
        
        # 검증기 초기화
        self.json_validator = JsonSchemaValidator() if self.config.enable_json_schema_validation else None
        self.rule_registry = None
        if self.config.enable_rule_engine:
            self.rule_registry = RuleRegistry(
                cache=cache,
                tdb=terminus,
                event=event,
                rule_loader=rule_loader
            )
    
    async def validate_entity(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str = "create",
        context: Optional[ValidationContext] = None,
        db: str = None,
        branch: str = None
    ) -> ValidationResult:
        """
        엔티티 검증 실행
        
        Args:
            entity_type: 엔티티 타입 (ObjectType, SemanticType 등)
            entity_data: 검증할 데이터
            operation: 작업 타입 (create, update, delete)
            context: 검증 컨텍스트
            db: TerminusDB 데이터베이스명
            branch: TerminusDB 브랜치명
        """
        start_time = time.time()
        stage_results = {}
        warnings = []
        
        db = db or self.config.terminus_default_db
        branch = branch or self.config.terminus_default_branch
        
        try:
            # Stage 1: JSON Schema 검증
            if self.config.enable_json_schema_validation and self.json_validator:
                result = await self._run_json_schema_validation(entity_type, entity_data)
                stage_results[ValidationStage.JSON_SCHEMA] = result.details
                
                if not result.success:
                    if self.config.fail_fast_mode:
                        return self._create_failed_result(
                            stage_results, ValidationStage.JSON_SCHEMA, 
                            result.errors[0] if result.errors else "JSON Schema validation failed",
                            time.time() - start_time
                        )
                else:
                    warnings.extend(result.warnings)
            
            # Stage 2: Policy 검증 (외부 정책 서버)
            if self.config.enable_policy_validation and self.policy_server:
                result = await self._run_policy_validation(entity_type, entity_data, operation, context)
                stage_results[ValidationStage.POLICY] = result.details
                
                if not result.success:
                    if self.config.fail_fast_mode:
                        return self._create_failed_result(
                            stage_results, ValidationStage.POLICY,
                            result.errors[0] if result.errors else "Policy validation failed",
                            time.time() - start_time
                        )
                else:
                    warnings.extend(result.warnings)
            
            # Stage 3: TerminusDB 시뮬레이션 검증 (스키마/제약 위반 사전 확인)
            if self.config.enable_terminus_validation and self.terminus:
                result = await self._run_terminus_validation(entity_type, entity_data, operation, db, branch)
                stage_results[ValidationStage.TERMINUS_CHECK] = result.details
                
                if not result.success:
                    if self.config.fail_fast_mode:
                        return self._create_failed_result(
                            stage_results, ValidationStage.TERMINUS_CHECK,
                            result.errors[0] if result.errors else "TerminusDB validation failed", 
                            time.time() - start_time
                        )
                else:
                    warnings.extend(result.warnings)
            
            # Stage 4: Rule Engine (Breaking Change 분석)
            if self.config.enable_rule_engine and self.rule_registry:
                result = await self._run_rule_engine_validation(entity_type, entity_data, operation, context, db, branch)
                stage_results[ValidationStage.RULE_ENGINE] = result.details
                
                if not result.success:
                    if self.config.fail_fast_mode:
                        return self._create_failed_result(
                            stage_results, ValidationStage.RULE_ENGINE,
                            result.errors[0] if result.errors else "Rule engine validation failed",
                            time.time() - start_time
                        )
                else:
                    warnings.extend(result.warnings)
            
            # Stage 5: Foundry Alerting (비동기 실행, 실패해도 전체 검증은 성공)
            if self.config.enable_foundry_alerting and self.event:
                result = await self._run_foundry_alerting(entity_type, entity_data, operation, context, db, branch)
                stage_results[ValidationStage.FOUNDRY_ALERTING] = result.details
                
                # Foundry 알람은 실패해도 전체 검증에 영향 없음 (non-blocking)
                if result.success:
                    warnings.extend(result.warnings)
                else:
                    warnings.append("Foundry alerting failed but validation continues")
                    logger.warning(f"Foundry alerting failed: {result.errors}")
            
            # 모든 단계 성공
            total_time = (time.time() - start_time) * 1000
            
            # 성능 지표 발행
            if self.config.enable_performance_metrics and self.event:
                await self._publish_metrics(stage_results, total_time, True)
            
            return ValidationResult(
                success=True,
                stage_results=stage_results,
                total_time_ms=total_time,
                warnings=warnings
            )
            
        except RuntimeError as e:
            logger.error(f"Validation pipeline error: {e}")
            total_time = (time.time() - start_time) * 1000
            
            return ValidationResult(
                success=False,
                stage_results=stage_results,
                total_time_ms=total_time,
                error_message=f"Pipeline error: {str(e)}"
            )
    
    async def _run_json_schema_validation(self, entity_type: str, entity_data: Dict[str, Any]) -> StageResult:
        """JSON Schema 검증 실행"""
        stage_start = time.time()
        
        try:
            # JSON Schema 파일명 매핑
            schema_name_map = {
                "ObjectType": "object_type.json",
                "SemanticType": "semantic_type.json", 
                "StructType": "struct_type.json",
                "Relationship": "relationship.json",
                "Batch": "batch.json"
            }
            
            schema_file = schema_name_map.get(entity_type)
            if not schema_file:
                return StageResult(
                    stage=ValidationStage.JSON_SCHEMA,
                    success=True,  # 스키마 파일 없으면 통과
                    time_ms=(time.time() - stage_start) * 1000,
                    details={"skipped": f"No schema file for {entity_type}"},
                    warnings=[f"No JSON schema defined for {entity_type}"]
                )
            
            # 검증 실행
            errors = await self.json_validator.validate_with_schema(entity_data, schema_file)
            
            return StageResult(
                stage=ValidationStage.JSON_SCHEMA,
                success=len(errors) == 0,
                time_ms=(time.time() - stage_start) * 1000,
                details={
                    "schema_file": schema_file,
                    "validation_errors": errors,
                    "entity_type": entity_type
                },
                errors=errors
            )
            
        except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON Schema validation error: {e}")
            return StageResult(
                stage=ValidationStage.JSON_SCHEMA,
                success=False,
                time_ms=(time.time() - stage_start) * 1000,
                details={"error": str(e)},
                errors=[f"JSON Schema validation failed: {str(e)}"]
            )
    
    async def _run_policy_validation(
        self, 
        entity_type: str, 
        entity_data: Dict[str, Any], 
        operation: str,
        context: Optional[ValidationContext]
    ) -> StageResult:
        """외부 정책 서버 검증 실행"""
        stage_start = time.time()
        
        try:
            policy_context = {}
            if context:
                policy_context = {
                    "source_branch": context.source_branch,
                    "target_branch": context.target_branch,
                    "user_id": context.user_id,
                    "metadata": context.metadata
                }
            
            result = await self.policy_server.validate_policy(
                entity_type=entity_type,
                entity_data=entity_data,
                operation=operation,
                context=policy_context
            )
            
            return StageResult(
                stage=ValidationStage.POLICY,
                success=result.get("valid", True),
                time_ms=(time.time() - stage_start) * 1000,
                details={
                    "policy_result": result,
                    "policy_version": result.get("policy_version"),
                    "fallback": result.get("fallback", False)
                },
                errors=result.get("violations", []),
                warnings=result.get("warnings", [])
            )
            
        except (ConnectionError, TimeoutError, RuntimeError) as e:
            logger.error(f"Policy validation error: {e}")
            return StageResult(
                stage=ValidationStage.POLICY,
                success=True,  # Fail-open: 정책 서버 오류시 통과
                time_ms=(time.time() - stage_start) * 1000,
                details={"error": str(e), "fallback": True},
                warnings=[f"Policy server error: {str(e)}"]
            )
    
    async def _run_terminus_validation(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        db: str,
        branch: str
    ) -> StageResult:
        """TerminusDB 스키마/제약 검증 (시뮬레이션)"""
        stage_start = time.time()
        
        try:
            # TerminusDB 스키마 위반 사전 확인
            # 실제 insert는 하지 않고 validation만 수행
            if operation == "create":
                # 임시 문서 생성하여 스키마 검증
                temp_doc = {
                    "@type": entity_type,
                    **entity_data
                }
                
                # TerminusDB에 임시 insert 시도 (dry-run)
                # 실제로는 validate_document API가 있다면 사용
                if hasattr(self.terminus, 'validate_document'):
                    validation_result = await self.terminus.validate_document(temp_doc, db=db, branch=branch)
                    
                    return StageResult(
                        stage=ValidationStage.TERMINUS_CHECK,
                        success=validation_result.get("valid", True),
                        time_ms=(time.time() - stage_start) * 1000,
                        details={
                            "terminus_validation": validation_result,
                            "entity_type": entity_type,
                            "operation": operation
                        },
                        errors=validation_result.get("errors", []),
                        warnings=validation_result.get("warnings", [])
                    )
            
            # TerminusDB validate_document API가 없으면 건너뛰기
            return StageResult(
                stage=ValidationStage.TERMINUS_CHECK,
                success=True,
                time_ms=(time.time() - stage_start) * 1000,
                details={"skipped": "TerminusDB validation not available", "entity_type": entity_type},
                warnings=["TerminusDB validation skipped - will be checked at actual insert time"]
            )
            
        except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
            logger.error(f"TerminusDB validation error: {e}")
            return StageResult(
                stage=ValidationStage.TERMINUS_CHECK,
                success=True,  # TerminusDB 오류시 실제 insert에서 처리
                time_ms=(time.time() - stage_start) * 1000,
                details={"error": str(e)},
                warnings=[f"TerminusDB validation error: {str(e)}"]
            )
    
    async def _run_rule_engine_validation(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        context: Optional[ValidationContext],
        db: str,
        branch: str
    ) -> StageResult:
        """Rule Engine (Breaking Change) 검증 실행"""
        stage_start = time.time()
        
        try:
            # 규칙 로드
            rules = await self.rule_registry.load_rules_from_package()
            
            # 엔티티 타입에 해당하는 규칙만 필터링
            applicable_rules = [
                rule for rule in rules 
                if hasattr(rule, 'applies_to') and rule.applies_to(entity_type)
            ]
            
            if not applicable_rules:
                return StageResult(
                    stage=ValidationStage.RULE_ENGINE,
                    success=True,
                    time_ms=(time.time() - stage_start) * 1000,
                    details={"skipped": f"No applicable rules for {entity_type}"},
                    warnings=[f"No breaking change rules defined for {entity_type}"]
                )
            
            # 검증 컨텍스트 생성
            if not context:
                context = ValidationContext(
                    source_branch=branch,
                    target_branch="main",
                    cache=self.cache,
                    terminus_client=self.terminus,
                    event_publisher=self.event
                )
            
            # 규칙 실행
            rule_results = []
            errors = []
            warnings = []
            
            for rule in applicable_rules:
                try:
                    # 규칙별로 검증 실행
                    result = await rule.check(entity_data, context)
                    rule_results.append({
                        "rule_id": rule.rule_id,
                        "result": result
                    })
                    
                    if not result.get("valid", True):
                        errors.extend(result.get("errors", []))
                    
                    warnings.extend(result.get("warnings", []))
                    
                except (RuntimeError, ValueError, TypeError) as e:
                    logger.error(f"Rule {rule.rule_id} execution error: {e}")
                    warnings.append(f"Rule {rule.rule_id} failed: {str(e)}")
            
            return StageResult(
                stage=ValidationStage.RULE_ENGINE,
                success=len(errors) == 0,
                time_ms=(time.time() - stage_start) * 1000,
                details={
                    "rules_executed": len(applicable_rules),
                    "rule_results": rule_results,
                    "entity_type": entity_type
                },
                errors=errors,
                warnings=warnings
            )
            
        except (ImportError, RuntimeError, ValueError) as e:
            logger.error(f"Rule engine validation error: {e}")
            return StageResult(
                stage=ValidationStage.RULE_ENGINE,
                success=False,
                time_ms=(time.time() - stage_start) * 1000,
                details={"error": str(e)},
                errors=[f"Rule engine failed: {str(e)}"]
            )
    
    def _create_failed_result(
        self,
        stage_results: Dict[ValidationStage, Dict[str, Any]],
        failed_stage: ValidationStage,
        error_message: str,
        elapsed_time: float
    ) -> ValidationResult:
        """실패 결과 생성"""
        return ValidationResult(
            success=False,
            stage_results=stage_results,
            total_time_ms=elapsed_time * 1000,
            failed_at_stage=failed_stage,
            error_message=error_message
        )
    
    async def _publish_metrics(
        self,
        stage_results: Dict[ValidationStage, Dict[str, Any]],
        total_time_ms: float,
        success: bool
    ):
        """검증 성능 지표 발행"""
        try:
            if self.event:
                await self.event.publish(
                    "validation.pipeline.completed",
                    {
                        "total_time_ms": total_time_ms,
                        "success": success,
                        "stages_executed": list(stage_results.keys()),
                        "stage_times": {
                            stage.value: details.get("time_ms", 0)
                            for stage, details in stage_results.items()
                        }
                    }
                )
        except (ConnectionError, TimeoutError, RuntimeError) as e:
            logger.error(f"Failed to publish validation metrics: {e}")
    
    async def _run_foundry_alerting(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        operation: str,
        context: Optional[ValidationContext],
        db: str,
        branch: str
    ) -> StageResult:
        """Foundry 알람 시스템 실행"""
        stage_start = time.time()
        
        try:
            # Foundry 알람 규칙 동적 로드
            from core.validation.rules.foundry_alerting_rule import (
                FoundryDatasetAlertingRule, AlertConfig
            )
            
            # AlertConfig 생성
            alert_config = AlertConfig(
                enabled=getattr(self.config, 'foundry_alerting_enabled', True),
                severity_threshold=getattr(self.config, 'foundry_alert_severity_threshold', 'medium'),
                cooldown_period_minutes=getattr(self.config, 'foundry_alert_cooldown_minutes', 60),
                max_alerts_per_hour=getattr(self.config, 'foundry_max_alerts_per_hour', 10),
                notification_channels=getattr(self.config, 'foundry_notification_channels', ['email', 'slack'])
            )
            
            # Foundry 알람 규칙 인스턴스 생성
            foundry_rule = FoundryDatasetAlertingRule(
                event_port=self.event,
                terminus_port=self.terminus,
                alert_config=alert_config
            )
            
            # ValidationContext 확장
            if not context:
                context = ValidationContext(
                    source_branch=branch,
                    target_branch="main",
                    cache=self.cache,
                    terminus_client=self.terminus,
                    event_publisher=self.event
                )
            
            # 스키마 변경 정보를 context에 추가
            context.schema_changes = {
                f"{operation}_{entity_type}": [entity_data]
            }
            context.context.update({
                "entity_type": entity_type,
                "operation": operation,
                "db": db,
                "branch": branch
            })
            
            # Foundry 알람 규칙 실행
            rule_result = await foundry_rule.execute(context)
            
            # 결과 처리
            alerts_generated = rule_result.metadata.get("alerts_generated", 0)
            alert_types = rule_result.metadata.get("alert_types", [])
            
            return StageResult(
                stage=ValidationStage.FOUNDRY_ALERTING,
                success=True,  # 알람은 항상 성공 (non-blocking)
                time_ms=(time.time() - stage_start) * 1000,
                details={
                    "alerts_generated": alerts_generated,
                    "alert_types": alert_types,
                    "foundry_alerting_enabled": alert_config.enabled,
                    "notification_channels": alert_config.notification_channels,
                    "rule_metadata": rule_result.metadata
                },
                warnings=[] if alerts_generated == 0 else [f"Generated {alerts_generated} Foundry alerts"]
            )
            
        except (ImportError, RuntimeError, ValueError) as e:
            logger.error(f"Foundry alerting error: {e}")
            return StageResult(
                stage=ValidationStage.FOUNDRY_ALERTING,
                success=False,
                time_ms=(time.time() - stage_start) * 1000,
                details={"error": str(e), "foundry_alerting_failed": True},
                errors=[f"Foundry alerting failed: {str(e)}"]
            )


# Factory function
def create_validation_pipeline(
    cache: Optional[CachePort] = None,
    terminus: Optional[TerminusPort] = None,
    event: Optional[EventPort] = None,
    policy_server: Optional[PolicyServerPort] = None,
    rule_loader: Optional[RuleLoaderPort] = None,
    config=None
) -> ValidationPipeline:
    """검증 파이프라인 생성"""
    return ValidationPipeline(
        cache=cache,
        terminus=terminus,
        event=event,
        policy_server=policy_server,
        rule_loader=rule_loader,
        config=config
    )