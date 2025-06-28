"""
TerminusDB Error Handler
TerminusDB 예외를 ValidationError로 변환하는 Mediator

TerminusDB의 다양한 오류를 비즈니스 문맥이 포함된 Validation 오류로 래핑
"""
import logging
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TerminusErrorType(str, Enum):
    """TerminusDB 오류 타입"""
    SCHEMA_VIOLATION = "schema_violation"
    CONSTRAINT_VIOLATION = "constraint_violation"
    CARDINALITY_VIOLATION = "cardinality_violation"
    TYPE_VIOLATION = "type_violation"
    UNIQUE_VIOLATION = "unique_violation"
    REFERENCE_VIOLATION = "reference_violation"
    TRANSACTION_ERROR = "transaction_error"
    CONNECTION_ERROR = "connection_error"
    QUERY_ERROR = "query_error"
    AUTHORIZATION_ERROR = "authorization_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ValidationError:
    """통합 검증 오류 모델"""
    error_type: TerminusErrorType
    message: str
    field_name: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    constraint_name: Optional[str] = None
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    business_context: Optional[str] = None
    resolution_hints: List[str] = None
    original_error: Optional[Exception] = None
    
    def __post_init__(self):
        if self.resolution_hints is None:
            self.resolution_hints = []


class TerminusErrorHandler:
    """
    TerminusDB 오류 처리기
    다양한 TerminusDB 오류를 비즈니스 문맥이 포함된 ValidationError로 변환
    """
    
    def __init__(self):
        # TerminusDB 오류 패턴 매핑
        self.error_patterns = {
            # Schema 위반
            r"schema violation.*?([A-Za-z_]+).*?expected.*?([A-Za-z_]+)": TerminusErrorType.SCHEMA_VIOLATION,
            r"type error.*?expected.*?([A-Za-z_]+).*?got.*?([A-Za-z_]+)": TerminusErrorType.TYPE_VIOLATION,
            
            # Cardinality 위반
            r"cardinality violation.*?([A-Za-z_]+).*?expected.*?(\d+)": TerminusErrorType.CARDINALITY_VIOLATION,
            r"required property.*?([A-Za-z_]+).*?missing": TerminusErrorType.CARDINALITY_VIOLATION,
            
            # 제약 위반
            r"constraint violation.*?([A-Za-z_]+)": TerminusErrorType.CONSTRAINT_VIOLATION,
            r"unique constraint.*?([A-Za-z_]+)": TerminusErrorType.UNIQUE_VIOLATION,
            
            # 참조 위반
            r"reference error.*?([A-Za-z_]+).*?not found": TerminusErrorType.REFERENCE_VIOLATION,
            r"foreign key.*?([A-Za-z_]+).*?violation": TerminusErrorType.REFERENCE_VIOLATION,
            
            # 트랜잭션 오류
            r"transaction.*?failed": TerminusErrorType.TRANSACTION_ERROR,
            r"concurrent.*?modification": TerminusErrorType.TRANSACTION_ERROR,
            
            # 연결 오류
            r"connection.*?failed": TerminusErrorType.CONNECTION_ERROR,
            r"timeout.*?connecting": TerminusErrorType.CONNECTION_ERROR,
            
            # 쿼리 오류
            r"query.*?error": TerminusErrorType.QUERY_ERROR,
            r"invalid.*?WOQL": TerminusErrorType.QUERY_ERROR,
            
            # 권한 오류
            r"access.*?denied": TerminusErrorType.AUTHORIZATION_ERROR,
            r"permission.*?denied": TerminusErrorType.AUTHORIZATION_ERROR,
        }
        
        # 비즈니스 문맥 매핑
        self.business_context_map = {
            TerminusErrorType.SCHEMA_VIOLATION: "스키마 정의와 일치하지 않는 데이터 구조",
            TerminusErrorType.CONSTRAINT_VIOLATION: "비즈니스 규칙 위반",
            TerminusErrorType.CARDINALITY_VIOLATION: "필수 필드 누락 또는 중복 데이터",
            TerminusErrorType.TYPE_VIOLATION: "데이터 타입 불일치",
            TerminusErrorType.UNIQUE_VIOLATION: "고유성 제약 위반",
            TerminusErrorType.REFERENCE_VIOLATION: "관련 엔티티 참조 오류",
            TerminusErrorType.TRANSACTION_ERROR: "동시성 충돌 또는 트랜잭션 롤백",
            TerminusErrorType.CONNECTION_ERROR: "데이터베이스 연결 문제",
            TerminusErrorType.QUERY_ERROR: "쿼리 구문 또는 실행 오류",
            TerminusErrorType.AUTHORIZATION_ERROR: "권한 부족",
            TerminusErrorType.UNKNOWN_ERROR: "알 수 없는 오류"
        }
    
    def handle_terminus_error(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationError:
        """
        TerminusDB 오류를 ValidationError로 변환
        
        Args:
            error: TerminusDB에서 발생한 원본 오류
            context: 추가 컨텍스트 정보 (entity_type, operation 등)
        """
        error_message = str(error)
        error_type = self._classify_error(error_message)
        
        # 에러 메시지에서 세부 정보 추출
        details = self._extract_error_details(error_message, error_type)
        
        # 컨텍스트에서 추가 정보 가져오기
        entity_type = context.get('entity_type') if context else None
        entity_id = context.get('entity_id') if context else None
        operation = context.get('operation') if context else None
        
        # ValidationError 생성
        validation_error = ValidationError(
            error_type=error_type,
            message=self._create_user_friendly_message(error_type, details, operation),
            field_name=details.get('field_name'),
            entity_type=entity_type,
            entity_id=entity_id,
            constraint_name=details.get('constraint_name'),
            expected_value=details.get('expected_value'),
            actual_value=details.get('actual_value'),
            business_context=self.business_context_map.get(error_type),
            resolution_hints=self._generate_resolution_hints(error_type, details, context),
            original_error=error
        )
        
        logger.warning(f"TerminusDB error converted to ValidationError: {validation_error.message}")
        return validation_error
    
    def _classify_error(self, error_message: str) -> TerminusErrorType:
        """오류 메시지를 분석하여 오류 타입 분류"""
        error_message_lower = error_message.lower()
        
        for pattern, error_type in self.error_patterns.items():
            if re.search(pattern, error_message_lower):
                return error_type
        
        # 패턴 매칭이 안 되면 키워드로 분류
        if any(keyword in error_message_lower for keyword in ['schema', 'type']):
            return TerminusErrorType.SCHEMA_VIOLATION
        elif any(keyword in error_message_lower for keyword in ['constraint', 'violation']):
            return TerminusErrorType.CONSTRAINT_VIOLATION
        elif any(keyword in error_message_lower for keyword in ['cardinality', 'required', 'missing']):
            return TerminusErrorType.CARDINALITY_VIOLATION
        elif any(keyword in error_message_lower for keyword in ['unique', 'duplicate']):
            return TerminusErrorType.UNIQUE_VIOLATION
        elif any(keyword in error_message_lower for keyword in ['reference', 'foreign', 'not found']):
            return TerminusErrorType.REFERENCE_VIOLATION
        elif any(keyword in error_message_lower for keyword in ['transaction', 'concurrent']):
            return TerminusErrorType.TRANSACTION_ERROR
        elif any(keyword in error_message_lower for keyword in ['connection', 'timeout']):
            return TerminusErrorType.CONNECTION_ERROR
        elif any(keyword in error_message_lower for keyword in ['query', 'woql']):
            return TerminusErrorType.QUERY_ERROR
        elif any(keyword in error_message_lower for keyword in ['access', 'permission', 'denied']):
            return TerminusErrorType.AUTHORIZATION_ERROR
        else:
            return TerminusErrorType.UNKNOWN_ERROR
    
    def _extract_error_details(self, error_message: str, error_type: TerminusErrorType) -> Dict[str, Any]:
        """오류 메시지에서 세부 정보 추출"""
        details = {}
        error_message_lower = error_message.lower()
        
        # 필드명 추출
        field_match = re.search(r"property\s+([A-Za-z_][A-Za-z0-9_]*)", error_message_lower)
        if field_match:
            details['field_name'] = field_match.group(1)
        
        # 제약 이름 추출
        constraint_match = re.search(r"constraint\s+([A-Za-z_][A-Za-z0-9_]*)", error_message_lower)
        if constraint_match:
            details['constraint_name'] = constraint_match.group(1)
        
        # 타입 관련 정보 추출
        if error_type == TerminusErrorType.TYPE_VIOLATION:
            expected_match = re.search(r"expected\s+([A-Za-z_]+)", error_message_lower)
            actual_match = re.search(r"got\s+([A-Za-z_]+)", error_message_lower)
            if expected_match:
                details['expected_value'] = expected_match.group(1)
            if actual_match:
                details['actual_value'] = actual_match.group(1)
        
        # Cardinality 관련 정보 추출
        elif error_type == TerminusErrorType.CARDINALITY_VIOLATION:
            cardinality_match = re.search(r"expected\s+(\d+)", error_message_lower)
            if cardinality_match:
                details['expected_value'] = int(cardinality_match.group(1))
        
        return details
    
    def _create_user_friendly_message(
        self, 
        error_type: TerminusErrorType, 
        details: Dict[str, Any], 
        operation: Optional[str]
    ) -> str:
        """사용자 친화적인 오류 메시지 생성"""
        operation_text = f" during {operation}" if operation else ""
        
        if error_type == TerminusErrorType.SCHEMA_VIOLATION:
            field = details.get('field_name', 'unknown field')
            return f"Schema validation failed{operation_text}: {field} does not match expected schema definition"
        
        elif error_type == TerminusErrorType.TYPE_VIOLATION:
            field = details.get('field_name', 'field')
            expected = details.get('expected_value', 'expected type')
            actual = details.get('actual_value', 'actual type')
            return f"Type mismatch{operation_text}: {field} expected {expected} but got {actual}"
        
        elif error_type == TerminusErrorType.CARDINALITY_VIOLATION:
            field = details.get('field_name', 'field')
            expected = details.get('expected_value', 'required')
            return f"Cardinality violation{operation_text}: {field} requires {expected} value(s)"
        
        elif error_type == TerminusErrorType.UNIQUE_VIOLATION:
            field = details.get('field_name', 'field')
            return f"Uniqueness constraint violated{operation_text}: {field} value already exists"
        
        elif error_type == TerminusErrorType.REFERENCE_VIOLATION:
            field = details.get('field_name', 'field')
            return f"Reference integrity violated{operation_text}: {field} references non-existent entity"
        
        elif error_type == TerminusErrorType.CONSTRAINT_VIOLATION:
            constraint = details.get('constraint_name', 'business rule')
            return f"Constraint violation{operation_text}: {constraint} rule not satisfied"
        
        elif error_type == TerminusErrorType.TRANSACTION_ERROR:
            return f"Transaction failed{operation_text}: concurrent modification detected or rollback occurred"
        
        elif error_type == TerminusErrorType.CONNECTION_ERROR:
            return f"Database connection error{operation_text}: unable to connect to TerminusDB"
        
        elif error_type == TerminusErrorType.QUERY_ERROR:
            return f"Query execution error{operation_text}: invalid or malformed query"
        
        elif error_type == TerminusErrorType.AUTHORIZATION_ERROR:
            return f"Authorization error{operation_text}: insufficient permissions for requested operation"
        
        else:
            return f"Unknown database error{operation_text}: {str(details)}"
    
    def _generate_resolution_hints(
        self, 
        error_type: TerminusErrorType, 
        details: Dict[str, Any], 
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """해결 방법 힌트 생성"""
        hints = []
        
        if error_type == TerminusErrorType.SCHEMA_VIOLATION:
            hints.extend([
                "Check that all required fields are provided",
                "Verify field names match schema definition",
                "Ensure data structure follows expected schema format"
            ])
        
        elif error_type == TerminusErrorType.TYPE_VIOLATION:
            expected = details.get('expected_value')
            if expected:
                hints.append(f"Convert field value to {expected} type")
            hints.extend([
                "Validate input data types before submission",
                "Check type conversion logic"
            ])
        
        elif error_type == TerminusErrorType.CARDINALITY_VIOLATION:
            hints.extend([
                "Provide required fields that are missing",
                "Remove excess values if cardinality limit exceeded",
                "Check field requirements in schema definition"
            ])
        
        elif error_type == TerminusErrorType.UNIQUE_VIOLATION:
            field = details.get('field_name')
            if field:
                hints.append(f"Use a different value for {field}")
            hints.extend([
                "Check existing records for duplicate values",
                "Consider using auto-generated unique identifiers"
            ])
        
        elif error_type == TerminusErrorType.REFERENCE_VIOLATION:
            hints.extend([
                "Verify referenced entity exists",
                "Create referenced entity before creating relationship",
                "Check reference field value format"
            ])
        
        elif error_type == TerminusErrorType.CONSTRAINT_VIOLATION:
            hints.extend([
                "Review business rules and constraints",
                "Adjust data to satisfy constraint requirements",
                "Consider exception handling for special cases"
            ])
        
        elif error_type == TerminusErrorType.TRANSACTION_ERROR:
            hints.extend([
                "Retry the operation after a brief delay",
                "Implement optimistic locking strategy",
                "Check for concurrent modifications"
            ])
        
        elif error_type == TerminusErrorType.CONNECTION_ERROR:
            hints.extend([
                "Check TerminusDB server status",
                "Verify network connectivity",
                "Review connection configuration"
            ])
        
        elif error_type == TerminusErrorType.QUERY_ERROR:
            hints.extend([
                "Validate WOQL query syntax",
                "Check variable bindings and types",
                "Simplify complex queries for debugging"
            ])
        
        elif error_type == TerminusErrorType.AUTHORIZATION_ERROR:
            hints.extend([
                "Check user permissions for the operation",
                "Verify authentication credentials",
                "Contact administrator for access rights"
            ])
        
        return hints
    
    def handle_bulk_errors(
        self, 
        errors: List[Exception], 
        contexts: List[Dict[str, Any]] = None
    ) -> List[ValidationError]:
        """여러 TerminusDB 오류를 일괄 처리"""
        if contexts is None:
            contexts = [{}] * len(errors)
        
        validation_errors = []
        for i, error in enumerate(errors):
            context = contexts[i] if i < len(contexts) else {}
            validation_error = self.handle_terminus_error(error, context)
            validation_errors.append(validation_error)
        
        return validation_errors
    
    def create_summary_report(self, validation_errors: List[ValidationError]) -> Dict[str, Any]:
        """검증 오류 요약 보고서 생성"""
        error_counts = {}
        for error in validation_errors:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            "total_errors": len(validation_errors),
            "error_breakdown": error_counts,
            "most_common_error": max(error_counts.items(), key=lambda x: x[1])[0] if error_counts else None,
            "resolution_required": any(
                error.error_type in [
                    TerminusErrorType.SCHEMA_VIOLATION,
                    TerminusErrorType.CONSTRAINT_VIOLATION,
                    TerminusErrorType.REFERENCE_VIOLATION
                ] for error in validation_errors
            )
        }


# Factory function
def create_terminus_error_handler() -> TerminusErrorHandler:
    """TerminusDB 오류 처리기 생성"""
    return TerminusErrorHandler()


# Context manager for TerminusDB operations
class TerminusOperationContext:
    """TerminusDB 작업 컨텍스트 매니저"""
    
    def __init__(
        self, 
        error_handler: TerminusErrorHandler,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        self.error_handler = error_handler
        self.context = {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'operation': operation
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            # TerminusDB 관련 오류인 경우 ValidationError로 변환
            if self._is_terminus_error(exc_val):
                validation_error = self.error_handler.handle_terminus_error(exc_val, self.context)
                # ValidationError를 로그로 기록하고 원본 예외 대신 발생시킬지 결정
                logger.error(f"TerminusDB operation failed: {validation_error.message}")
                # 여기서는 원본 예외를 그대로 전파하되, 나중에 호출부에서 처리할 수 있도록 함
        return False  # 예외를 재발생시킴
    
    def _is_terminus_error(self, error: Exception) -> bool:
        """TerminusDB 관련 오류인지 확인"""
        error_message = str(error).lower()
        terminus_keywords = [
            'terminus', 'woql', 'schema', 'constraint', 'cardinality',
            'reference', 'transaction', 'query', 'type error'
        ]
        return any(keyword in error_message for keyword in terminus_keywords)