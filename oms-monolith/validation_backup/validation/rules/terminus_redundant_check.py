"""
TerminusDB Redundant Check Rule
TerminusDB가 이미 보장하는 제약사항 검증 규칙 (중복 방지)

TerminusDB 고유 기능과 중복되는 검증을 식별하고 경고하는 규칙
중복 검사 제거를 통한 성능 최적화 및 아키텍처 일관성 확보
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.validation.interfaces import BreakingChangeRule
from core.validation.models import (
    BreakingChange, Severity, MigrationStrategy, ValidationContext
)

logger = logging.getLogger(__name__)


@dataclass
class RedundantCheckInfo:
    """중복 검사 정보"""
    rule_name: str
    terminus_feature: str
    description: str
    recommendation: str
    risk_level: str  # low, medium, high


class TerminusRedundantCheckRule(BreakingChangeRule):
    """
    TerminusDB 중복 검사 탐지 규칙
    
    TerminusDB가 이미 제공하는 기능과 중복되는 검증 로직을 식별하고
    최적화 권장사항을 제공하는 규칙
    """
    
    def __init__(self):
        self.redundant_checks = {
            # Cardinality 검사 - TerminusDB 스키마에서 자동 처리
            "cardinality_validation": RedundantCheckInfo(
                rule_name="cardinality_validation",
                terminus_feature="Schema Cardinality Constraints",
                description="TerminusDB는 스키마 정의에서 카디널리티를 자동으로 검증합니다",
                recommendation="스키마에서 카디널리티를 정의하고 별도 검증 로직을 제거하세요",
                risk_level="medium"
            ),
            
            # Domain/Range 검사 - TerminusDB 스키마 타입 시스템에서 처리
            "domain_range_validation": RedundantCheckInfo(
                rule_name="domain_range_validation", 
                terminus_feature="Schema Type System",
                description="TerminusDB는 도메인/레인지 제약을 스키마 수준에서 강제합니다",
                recommendation="@schema 정의에서 타입 제약을 명시하고 중복 검증을 제거하세요",
                risk_level="high"
            ),
            
            # 필수 필드 검사 - TerminusDB required 속성에서 처리
            "required_field_validation": RedundantCheckInfo(
                rule_name="required_field_validation",
                terminus_feature="Schema Required Properties",
                description="TerminusDB는 required 속성을 통해 필수 필드를 강제합니다",
                recommendation="스키마에서 required 속성을 사용하고 별도 검증을 제거하세요",
                risk_level="medium"
            ),
            
            # 타입 검사 - TerminusDB 타입 시스템에서 처리
            "type_validation": RedundantCheckInfo(
                rule_name="type_validation",
                terminus_feature="Schema Type Validation",
                description="TerminusDB는 insert/update 시 타입 일치성을 자동 검증합니다",
                recommendation="스키마 타입 정의에 의존하고 중복 타입 검사를 제거하세요", 
                risk_level="high"
            ),
            
            # 유니크 제약 - TerminusDB key 속성에서 처리
            "unique_constraint_validation": RedundantCheckInfo(
                rule_name="unique_constraint_validation",
                terminus_feature="Schema Key Constraints",
                description="TerminusDB는 key 속성을 통해 유니크 제약을 보장합니다",
                recommendation="스키마에서 key 속성을 정의하고 별도 유니크 검사를 제거하세요",
                risk_level="medium"
            )
        }
    
    @property
    def rule_id(self) -> str:
        return "terminus_redundant_check"
    
    @property
    def severity(self) -> Severity:
        return Severity.LOW  # 최적화 권장사항이므로 낮은 심각도
    
    @property
    def description(self) -> str:
        return "Detects validation logic that duplicates TerminusDB built-in capabilities"
    
    def applies_to(self, entity_type: str) -> bool:
        """모든 엔티티 타입에 적용"""
        return True
    
    async def check(self, entity_data: Dict[str, Any], context: ValidationContext) -> Dict[str, Any]:
        """중복 검사 로직 탐지"""
        try:
            detected_redundancies = []
            warnings = []
            
            # 메타데이터에서 실행된 규칙 확인
            executed_rules = context.metadata.get('executed_rules', [])
            
            for rule_name in executed_rules:
                redundancy = self._check_rule_redundancy(rule_name, entity_data, context)
                if redundancy:
                    detected_redundancies.append(redundancy)
                    warnings.append(
                        f"Rule '{rule_name}' may be redundant with TerminusDB feature '{redundancy.terminus_feature}'"
                    )
            
            # 엔티티 데이터에서 중복 검사 패턴 식별
            schema_redundancies = self._analyze_schema_redundancies(entity_data)
            detected_redundancies.extend(schema_redundancies)
            
            if detected_redundancies:
                return {
                    "valid": True,  # 중복이지만 유효한 검증
                    "warnings": warnings,
                    "redundancies": [r.__dict__ for r in detected_redundancies],
                    "optimization_suggestions": self._generate_optimization_suggestions(detected_redundancies)
                }
            
            return {"valid": True, "warnings": [], "redundancies": []}
            
        except Exception as e:
            logger.error(f"TerminusDB redundancy check failed: {e}")
            return {
                "valid": True,
                "warnings": [f"Redundancy check failed: {str(e)}"],
                "redundancies": []
            }
    
    def _check_rule_redundancy(
        self, 
        rule_name: str, 
        entity_data: Dict[str, Any], 
        context: ValidationContext
    ) -> Optional[RedundantCheckInfo]:
        """특정 규칙의 중복성 검사"""
        
        # 규칙 이름 기반 중복성 확인
        for redundant_name, info in self.redundant_checks.items():
            if self._rule_matches_pattern(rule_name, redundant_name):
                return info
        
        # 규칙 동작 기반 중복성 확인
        return self._analyze_rule_behavior(rule_name, entity_data, context)
    
    def _rule_matches_pattern(self, rule_name: str, pattern: str) -> bool:
        """규칙 이름이 중복 패턴과 일치하는지 확인"""
        rule_lower = rule_name.lower()
        pattern_keywords = pattern.replace('_', ' ').split()
        
        return any(keyword in rule_lower for keyword in pattern_keywords)
    
    def _analyze_rule_behavior(
        self, 
        rule_name: str, 
        entity_data: Dict[str, Any], 
        context: ValidationContext
    ) -> Optional[RedundantCheckInfo]:
        """규칙 동작 분석을 통한 중복성 확인"""
        
        # 규칙 실행 결과에서 TerminusDB 기능과 겹치는 부분 찾기
        rule_result = context.metadata.get(f'rule_result_{rule_name}', {})
        
        if not rule_result:
            return None
        
        # Cardinality 관련 검사
        if any(keyword in str(rule_result).lower() for keyword in ['cardinality', 'required', 'missing']):
            return self.redundant_checks.get("cardinality_validation")
        
        # Type 관련 검사
        if any(keyword in str(rule_result).lower() for keyword in ['type', 'datatype', 'format']):
            return self.redundant_checks.get("type_validation")
        
        # Domain/Range 관련 검사
        if any(keyword in str(rule_result).lower() for keyword in ['domain', 'range', 'property']):
            return self.redundant_checks.get("domain_range_validation")
        
        return None
    
    def _analyze_schema_redundancies(self, entity_data: Dict[str, Any]) -> List[RedundantCheckInfo]:
        """스키마 데이터에서 중복성 분석"""
        redundancies = []
        
        entity_type = entity_data.get("@type", "")
        
        # ObjectType의 properties에서 중복 검사 로직 확인
        if entity_type == "ObjectType":
            properties = entity_data.get("properties", [])
            
            for prop in properties:
                # 타입 검증 로직이 있는지 확인
                if "validation" in prop or "constraint" in prop:
                    redundancies.append(self.redundant_checks["type_validation"])
                
                # 카디널리티 검증 로직 확인
                if any(key in prop for key in ["minOccurs", "maxOccurs", "cardinality"]):
                    redundancies.append(self.redundant_checks["cardinality_validation"])
        
        # SemanticType의 도메인/레인지 중복 검사
        elif entity_type == "SemanticType":
            if "domain" in entity_data or "range" in entity_data:
                redundancies.append(self.redundant_checks["domain_range_validation"])
        
        return list({r.rule_name: r for r in redundancies}.values())  # 중복 제거
    
    def _generate_optimization_suggestions(self, redundancies: List[RedundantCheckInfo]) -> List[str]:
        """최적화 제안 생성"""
        suggestions = []
        
        high_risk_redundancies = [r for r in redundancies if r.risk_level == "high"]
        medium_risk_redundancies = [r for r in redundancies if r.risk_level == "medium"]
        
        if high_risk_redundancies:
            suggestions.append("🔴 HIGH PRIORITY: Remove redundant validation logic that duplicates TerminusDB core features")
            for redundancy in high_risk_redundancies:
                suggestions.append(f"  • {redundancy.recommendation}")
        
        if medium_risk_redundancies:
            suggestions.append("🟡 MEDIUM PRIORITY: Consider removing redundant checks for performance optimization")
            for redundancy in medium_risk_redundancies:
                suggestions.append(f"  • {redundancy.recommendation}")
        
        suggestions.extend([
            "💡 ARCHITECTURE IMPROVEMENT:",
            "  • Move validation logic to TerminusDB schema definitions",
            "  • Use TerminusDB constraints instead of application-level validation",
            "  • Implement validation pipeline fail-fast mode to avoid redundant checks",
            "  • Consider TerminusDB transaction-level validation for complex constraints"
        ])
        
        return suggestions


class CardinalityValidationOptimizer(BreakingChangeRule):
    """
    카디널리티 검증 최적화 규칙
    TerminusDB 스키마 카디널리티와 중복되는 검증 로직 식별
    """
    
    @property
    def rule_id(self) -> str:
        return "cardinality_validation_optimizer"
    
    @property
    def severity(self) -> Severity:
        return Severity.LOW
    
    @property
    def description(self) -> str:
        return "Optimizes cardinality validation by leveraging TerminusDB schema constraints"
    
    def applies_to(self, entity_type: str) -> bool:
        return entity_type in ["ObjectType", "SemanticType"]
    
    async def check(self, entity_data: Dict[str, Any], context: ValidationContext) -> Dict[str, Any]:
        """카디널리티 검증 최적화 분석"""
        try:
            optimization_opportunities = []
            
            # ObjectType properties의 카디널리티 검사
            if entity_data.get("@type") == "ObjectType":
                properties = entity_data.get("properties", [])
                
                for prop in properties:
                    if self._has_redundant_cardinality_check(prop):
                        optimization_opportunities.append({
                            "property": prop.get("name", "unknown"),
                            "issue": "Redundant cardinality validation",
                            "solution": "Use TerminusDB schema cardinality constraints",
                            "impact": "Performance improvement, reduced code complexity"
                        })
            
            if optimization_opportunities:
                return {
                    "valid": True,
                    "warnings": [
                        f"Found {len(optimization_opportunities)} cardinality validation optimizations"
                    ],
                    "optimizations": optimization_opportunities,
                    "recommendation": "Migrate cardinality validation to TerminusDB schema level"
                }
            
            return {"valid": True, "optimizations": []}
            
        except Exception as e:
            logger.error(f"Cardinality optimization analysis failed: {e}")
            return {"valid": True, "warnings": [f"Analysis failed: {str(e)}"]}
    
    def _has_redundant_cardinality_check(self, property_def: Dict[str, Any]) -> bool:
        """속성에 중복된 카디널리티 검사가 있는지 확인"""
        # 애플리케이션 레벨 카디널리티 검사 패턴
        redundant_patterns = [
            "validation_rules",
            "cardinality_check", 
            "required_validation",
            "minOccurs",
            "maxOccurs"
        ]
        
        return any(pattern in property_def for pattern in redundant_patterns)


# 중복 Rule 비활성화 헬퍼
class RedundantRuleDeactivator:
    """중복 규칙 비활성화 도구"""
    
    @staticmethod
    def get_redundant_rule_ids() -> List[str]:
        """TerminusDB와 중복되는 규칙 ID 목록"""
        return [
            "basic_cardinality_check",
            "simple_type_validation", 
            "required_field_basic_check",
            "domain_range_basic_validation",
            "unique_constraint_basic"
        ]
    
    @staticmethod
    def should_skip_rule(rule_id: str, terminus_available: bool = True) -> bool:
        """규칙을 건너뛸지 결정"""
        if not terminus_available:
            return False  # TerminusDB를 사용하지 않으면 모든 규칙 실행
        
        redundant_rules = RedundantRuleDeactivator.get_redundant_rule_ids()
        return rule_id in redundant_rules
    
    @staticmethod
    def create_skip_message(rule_id: str) -> str:
        """규칙 건너뛰기 메시지 생성"""
        return f"Rule '{rule_id}' skipped: redundant with TerminusDB built-in validation"


# Factory functions
def create_terminus_redundant_check_rule() -> TerminusRedundantCheckRule:
    """TerminusDB 중복 검사 규칙 생성"""
    return TerminusRedundantCheckRule()


def create_cardinality_validation_optimizer() -> CardinalityValidationOptimizer:
    """카디널리티 검증 최적화 규칙 생성"""
    return CardinalityValidationOptimizer()