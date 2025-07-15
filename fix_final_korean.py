#!/usr/bin/env python3
"""Final comprehensive Korean to English translation for all remaining text."""

import os
import re

# Comprehensive final translations
FINAL_TRANSLATIONS = {
    # From models/exceptions.py
    "낙관적 잠금(Optimistic Locking) 실패 시 발생": "Raised when optimistic locking fails",
    "동일 리소스에 대한 동시 수정 시도": "Concurrent modification attempt on the same resource",
    "버전 불일치로 인한 업데이트 실패": "Update failure due to version mismatch",
    "비즈니스 로직 충돌 예외": "Business logic conflict exception",
    "비즈니스 규칙 위반 시 발생": "Raised when business rules are violated",
    "중복된 리소스 생성 시도": "Duplicate resource creation attempt",
    "유효하지 않은 상태 전환": "Invalid state transition",
    "권한 없는 작업 시도": "Unauthorized operation attempt",
    "데이터 검증 실패 예외": "Data validation failure exception",
    "입력 데이터가 유효성 검증에 실패했을 때 발생": "Raised when input data fails validation",
    "리소스를 찾을 수 없음 예외": "Resource not found exception",
    "요청한 리소스가 존재하지 않을 때 발생": "Raised when requested resource does not exist",
    "서비스 사용 불가 예외": "Service unavailable exception",
    "외부 서비스나 의존성이 일시적으로 사용 불가능할 때 발생": "Raised when external service or dependency is temporarily unavailable",
    # From observability/enterprise_metrics.py
    "시스템 레벨 메트릭": "System level metrics",
    "가비지 컬렉션 및 메모리 관리 메트릭": "Garbage collection and memory management metrics",
    "애플리케이션 성능 메트릭": "Application performance metrics",
    "리질리언스 메커니즘 통합 메트릭": "Resilience mechanism integrated metrics",
    "비즈니스 도메인 메트릭": "Business domain metrics",
    "보안 및 컴플라이언스 메트릭": "Security and compliance metrics",
    "성능 및 최적화 메트릭": "Performance and optimization metrics",
    "엔터프라이즈급 메트릭 수집기": "Enterprise-grade metrics collector",
    "모든 메트릭 수집": "Collect all metrics",
    "시스템 메트릭 수집": "Collect system metrics",
    "가비지 컬렉션 메트릭 수집": "Collect garbage collection metrics",
    "GC 통계": "GC statistics",
    "이전 값과 비교하여 증minutes만 추가": "Add only increments compared to previous value",
    "이전 값과 비교하여 증분만 추가": "Add only increments compared to previous value",
    "객체 수 추적": "Track object count",
    "상위 10개 객체 타입만 추적": "Track only top 10 object types",
    "프로세스 메모리 정보": "Process memory information",
    "애플리케이션 메트릭 수집": "Collect application metrics",
    "시스템 최대 FD 수 (Linux/Unix 기준)": "System max FD count (Linux/Unix based)",
    "AsyncIO 태스크 수집": "AsyncIO task collection",
    "메트릭 레지스트리 반환": "Return metrics registry",
    "메트릭 수집기 반환": "Return metrics collector",
    "메트릭 수집 시작": "Start metrics collection",
    "15seconds마다 수집": "Collect every 15 seconds",
    "15초마다 수집": "Collect every 15 seconds",
    "백그라운드 태스크로 실행": "Run as background task",
    "Prometheus 메트릭 엔드포인트": "Prometheus metrics endpoint",
    "메트릭 수집 데코레이터": "Metrics collection decorator",
    "HTTP 요청 메트릭 추적 데코레이터": "HTTP request metrics tracking decorator",
    "진행 중인 요청 증가": "Increment in-progress requests",
    "성공 메트릭 기록": "Record success metrics",
    "에러 메트릭 기록": "Record error metrics",
    "요청 완료": "Request completed",
    # From api/gateway/router.py
    "요청 라우팅": "Request routing",
    "서비스로 요청 전달": "Forward request to service",
    "서비스 사용 불가 오류": "Service unavailable error",
    "요청 라우터": "Request router",
    "라우트 맵 구성": "Configure route map",
    # Additional Korean words that might appear
    "기타": "Other",
    "분": "minute",
    "초": "second",
    "시간": "time",
    "부분": "part",
    "분리": "separation",
    "분석": "analysis",
    "초기화": "initialization",
    "구분": "distinction",
    "예": "example",
    "주민등록번호": "resident registration number",
    "마지막": "last",
    "설정": "setting",
    "단어": "word",
    "명명 규칙 엔진": "naming convention engine",
    "대소문자": "case",
    "각": "each",
    "다시": "again",
    "접미사": "suffix",
    "제외한": "excluding",
    "후": "after",
    # Common Korean technical terms
    "병합 힌트 메타데이터": "Merge hint metadata",
    "리스트/맵 항목을 식별하는 키": "Key identifying list/map items",
    "함께 처리되어야 하는 필드 그룹들": "Field groups that must be processed together",
    "병합 후 검증 규칙 (표현식)": "Post-merge validation rules (expressions)",
    "필드 이름": "Field name",
    "해당 필드의 병합 힌트": "Merge hint for the field",
    "기본 병합 전략": "Default merge strategy",
    "필드별 병합 힌트": "Per-field merge hints",
    "의미론적으로 연관된 필드 그룹 정의": "Semantically related field group definitions",
    "병합 후 실행할 검증 규칙들": "Validation rules to execute after merge",
    # Fix fragmented words
    "증minutes만": "increments only",
    "부minutes": "parts",
    "minutes리": "separation",
    "minutes석": "analysis",
    "hours대": "timezone",
    "seconds기화": "initialization",
    "구minutes": "distinction",
    "minutes을": "parts",
    "minutes": "minutes",
}


def fix_file(file_path):
    """Fix remaining Korean text in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply all translations
        for korean, english in FINAL_TRANSLATIONS.items():
            content = content.replace(korean, english)

        # Check if file was modified
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ Fixed: {file_path}")
            return True

        return False
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {e}")
        return False


def main():
    """Main function to fix final remaining Korean text."""
    base_dir = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"

    # Target files from grep results
    target_files = [
        "models/exceptions.py",
        "observability/enterprise_metrics.py",
        "api/gateway/router.py",
        "core/security/pii_handler.py",
        "core/validation/naming_convention.py",
        "models/merge_hints.py",
        "models/domain.py",
        "core/branch/service.py",
    ]

    fixed = 0
    for file_path in target_files:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            if fix_file(full_path):
                fixed += 1
        else:
            print(f"File not found: {full_path}")

    print(f"\n✨ Fixed {fixed} files with final Korean text")


if __name__ == "__main__":
    main()
