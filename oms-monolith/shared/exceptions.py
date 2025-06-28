"""
공통 예외 정의
"""

class OntologyException(Exception):
    """Ontology Management System 기본 예외"""
    pass

class ValidationError(OntologyException):
    """검증 오류"""
    pass

class ConflictError(OntologyException):
    """충돌 오류"""
    pass

class NotFoundError(OntologyException):
    """리소스를 찾을 수 없음"""
    pass

class PermissionError(OntologyException):
    """권한 없음"""
    pass