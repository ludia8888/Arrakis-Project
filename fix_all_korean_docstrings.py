#!/usr/bin/env python3
"""Ultra comprehensive Korean to English translation script for all Python files."""

import os
import re

# Comprehensive Korean to English translation mappings
TRANSLATIONS = {
    # Common programming terms
    "환경 변수 기반 안전한 설정 관리": "Secure configuration management based on environment variables",
    "JWT 설정 구성": "JWT configuration settings",
    "서비스 설정 구성": "Service configuration settings",
    "필수 환경 변수 검증": "Required environment variable validation",
    "보안 설정 관리자 초기화 완료": "Security configuration manager initialization complete",
    # SIEM related
    "SIEM 이벤트 직렬화 도구": "SIEM event serialization tool",
    "복잡한 이벤트 변환 로직을 분리": "Separate complex event transformation logic",
    "SIEM 형식으로 이벤트를 직렬화하는 도구": "Tool for serializing events to SIEM format",
    "이벤트 객체를 SIEM 형식으로 직렬화": "Serialize event object to SIEM format",
    # CloudWatch/AWS related
    "OMS EventBridge 모니터링을 위한 CloudWatch 알람 설정": "CloudWatch alarm configuration for OMS EventBridge monitoring",
    "CloudWatch 알람 관리자": "CloudWatch alarm manager",
    "EventBridge 관련 CloudWatch 알람 생성": "Create EventBridge related CloudWatch alarms",
    # Circuit breaker
    "HTTP 서킷 브레이커 데코레이터": "HTTP circuit breaker decorator",
    "HTTP 응답 코드를 기반으로 서킷 브레이커를 적용합니다.": "Apply circuit breaker based on HTTP response codes.",
    "HTTP 에러를 나타내는 예외": "Exception representing HTTP error",
    "HTTP 응답 코드를 고려하는 서킷 브레이커 데코레이터": "Circuit breaker decorator that considers HTTP response codes",
    # Metrics/Monitoring
    "완전한 Prometheus 기반 엔터프라이즈 메트릭 시스템": "Complete Prometheus-based enterprise metrics system",
    "엔터프라이즈급 메트릭 레지스트리": "Enterprise-grade metrics registry",
    "모든 엔터프라이즈 메트릭 초기화": "Initialize all enterprise metrics",
    "실전급 Garbage Collection 및 메모리 모니터링": "Production-grade Garbage Collection and memory monitoring",
    "기존 리질리언스 대시보드를 Prometheus/Grafana/Jaeger 스택으로 완전 통합": "Fully integrate existing resilience dashboard with Prometheus/Grafana/Jaeger stack",
    # Issue tracking
    "엔터프라이즈급 이슈 추적, 감사, 승인 통합 미들웨어": "Enterprise-grade issue tracking, audit, and approval integrated middleware",
    # Exceptions
    "OMS 공통 예외 클래스들": "OMS common exception classes",
    "비즈니스 로직과 시스템 레벨 예외를 구분하여 정의": "Define business logic and system level exceptions separately",
    "OMS 시스템의 최상위 예외 클래스": "OMS system top-level exception class",
    "동시성 충돌 예외": "Concurrency conflict exception",
    # Domain/Models
    "이 전략은 TerminusDB 호환성과 Python 관례 사이의 균형을 맞추기 위함입니다.": "This strategy balances TerminusDB compatibility with Python conventions.",
    "각 모델 클래스에는 설계 의도가 주석으로 명시되어 있습니다.": "Each model class has design intentions specified in comments.",
    # Merge hints
    "병합 힌트 메타데이터 정의": "Merge hint metadata definition",
    "스키마에 병합 전략을 명시하기 위한 메타데이터 모델": "Metadata model for specifying merge strategy in schema",
    "병합 전략 타입": "Merge strategy type",
    "충돌 해결 전략": "Conflict resolution strategy",
    # Validation
    "엔티티 명명 규칙 검증 및 자동 교정 기능": "Entity naming convention validation and automatic correction functionality",
    # Security
    "민감 정보 감지 및 처리를 위한 모듈": "Module for sensitive information detection and processing",
    "PII 타입 정의": "PII type definition",
    # Database
    "표준 `httpx.AsyncClient`와 `httpx.Limits`를 사용하여 안정적인 연결 관리를 수행합니다.": "Perform stable connection management using standard `httpx.AsyncClient` and `httpx.Limits`.",
    # Verification
    "마이크로서비스 모드 검증 스크립트": "Microservice mode verification script",
    "점진적 마이그레이션 상태를 확인하고 게이트웨이 모드 작동을 검증": "Check gradual migration status and verify gateway mode operation",
    # API
    "권한 체크가 적용된 API 엔드포인트 예시": "API endpoint example with permission checks applied",
    # Testing
    "최종적으로 모든 근원적 문제를 식별하고 검증하는 포괄적 테스트": "Comprehensive test to finally identify and verify all root problems",
    # Production
    "프로덕션 배포 전 모든 체크리스트 항목 검증": "Verify all checklist items before production deployment",
    # Time units
    "5분": "5 minutes",
    "분": "minutes",
    "초": "seconds",
    "시간": "hours",
    # Common Korean comments
    "모델에 정의된 필드만 업데이트하도록 제한할 수 있습니다.": "Can restrict to update only fields defined in the model.",
    "여기서는 전달된 모든 키를 업데이트한다고 가정합니다.": "Here we assume all passed keys will be updated.",
    "수정자 및 수정 시간 업데이트": "Update modifier and modification time",
    "정확한 생성 시간을 알 수 없으므로 마지막 수정 시간으로 대체": "Replace with last modification time as exact creation time is unknown",
    "수정 시간이 없다면 생성 시간으로 대체": "Replace with creation time if modification time is missing",
    "롤백 로직은 정책에 따라 추가": "Add rollback logic according to policy",
    "구현되어 있다면": "if implemented",
    "이벤트 발행에 필요한 데이터 형식에 맞춰 전달해야 함": "Must pass data in format required for event publishing",
    "실패는 non-critical로 처리하고 로그만 남김": "Treat failure as non-critical and only log",
    "이 경우는 거의 발생하지 않아야 함": "This case should rarely occur",
    "네이티브 API로 브랜치 기본 정보 조회": "Query branch basic info with native API",
    "는 브랜치 정보에 마지막 수정 시간을 포함할 수 있습니다": " may include last modification time in branch info",
    "하지만 여기서는 메타데이터를 우선시하고, 없을 경우 현재 시간으로 대체합니다": "But here we prioritize metadata, replacing with current time if missing",
    "브랜치에서 브랜치 메타데이터 문서 조회": "Query branch metadata document from branch",
    "정보 조합하여": "Combine information",
    "객체 생성": "Create object",
    "특정 유형의 오류는 더 구체적으로 처리할 수 있습니다": "Specific types of errors can be handled more specifically",
    "브랜치에서": "from branch",
    "인 모든 문서를 가져오는": "get all documents of type",
    "쿼리": "query",
    "쿼리를 사용하여 문서의 전체 내용을 가져오도록 수정": "Modify to get full document content using query",
    "필터링 로직": "Filtering logic",
    "메타데이터 삭제 실패 시, 브랜치 삭제를 진행하지 않음": "If metadata deletion fails, do not proceed with branch deletion",
    "이미 지워졌거나 없는 경우, 경고만 로깅하고 성공으로 간주": "If already deleted or missing, just log warning and consider success",
    "네이티브 브랜치 삭제 실패는 심각한 오류. 하지만 메타데이터는 이미 지워진 상태.": "Native branch deletion failure is critical error. But metadata is already deleted.",
    "이 경우 수동 개입이 필요할 수 있음을 알리는 매우 심각한 로그를 남겨야 함": "In this case, must leave very critical log indicating manual intervention may be needed",
    # Branch service specific
    "브랜치 이름 유효성 검사": "Validate branch name",
    "브랜치": "branch",
    "롤백: 메타데이터 생성 실패 시 네이티브 브랜치 삭제 시도": "Rollback: attempt to delete native branch if metadata creation fails",
}


def translate_korean_to_english(text):
    """Translate Korean text to English using our mapping."""
    for korean, english in TRANSLATIONS.items():
        text = text.replace(korean, english)
    return text


def process_file(file_path):
    """Process a single Python file to translate Korean docstrings and comments."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if file contains Korean characters
        if not re.search(r"[\uac00-\ud7af]", content):
            return False

        print(f"Processing: {file_path}")

        # Translate all Korean text
        new_content = translate_korean_to_english(content)

        # Write back if changed
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  ✓ Translated Korean text")
            return True

        return False
    except Exception as e:
        print(f"  ✗ Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process all Python files."""
    base_dir = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"

    # List of specific files to process
    target_files = [
        "config/secure_config.py",
        "infra/siem/serializer.py",
        "infrastructure/aws/cloudwatch_alarms.py",
        "middleware/_deprecated/circuit_breaker_http.py",
        "observability/enterprise_metrics.py",
        "middleware/issue_tracking_middleware.py",
        "models/exceptions.py",
        "models/domain.py",
        "models/merge_hints.py",
        "core/validation/naming_convention.py",
        "core/security/pii_handler.py",
        "database/clients/terminus_db.py",
        "verify_microservices.py",
        "api/auth_examples.py",
        "tests/utils/comprehensive_validation.py",
        "scripts/production_readiness_check.py",
        "observability/advanced_gc_monitoring.py",
        "observability/enterprise_integration.py",
        "core/branch/service.py",  # Still has Korean comments
    ]

    processed = 0
    for file_path in target_files:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            if process_file(full_path):
                processed += 1
        else:
            print(f"File not found: {full_path}")

    print(f"\n✨ Processed {processed} files with Korean text")


if __name__ == "__main__":
    main()
