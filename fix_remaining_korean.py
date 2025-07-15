#!/usr/bin/env python3
"""Fix remaining Korean text issues after initial translation."""

import os
import re

# Specific fixes for partial translations
FIXES = {
    # Time unit issues
    "부minutes": "part",
    "minutes리": "separation",
    "minutes석": "analysis",
    "minutes": "minutes",  # Keep as is if standalone
    "hours대": "timezone",
    "seconds기화": "initialization",
    "구minutes": "distinction",
    # Remaining Korean text
    "마지막 부분 설정": "Set last part",
    "단어 분리용": "For word separation",
    "명명 규칙 엔진 초기화": "Initialize naming convention engine",
    "대소문자 구분": "Case distinction",
    "각 부분을 다시 분석": "Reanalyze each part",
    "접미사 제외한 부분을": "Excluding suffix part",
    "단어 분리 후": "After word separation",
    # Fix partial translations in comments
    "순서가 중요한 리스트": "List where order matters",
    "순서가 중요하지 않은 집합": "Set where order doesn't matter",
    "키로 식별되는 맵": "Map identified by key",
    "원자적 단위로 처리": "Process as atomic unit",
    "커스텀 병합 로직": "Custom merge logic",
    "수동 해결 필요": "Manual resolution required",
    "소스 우선": "Prefer source",
    "타겟 우선": "Prefer target",
    "양쪽 병합 시도": "Attempt to merge both",
    "즉시 실패": "Fail immediately",
    "순서를 나타내는 필드 이름": "Field name indicating order",
    "순서 정보 보존 여부": "Whether to preserve order information",
    "명시적으로 표시": "Explicitly marked",
    "필드 그룹 병합 전략": "Field group merge strategy",
    "소스 branch의 값을 우선": "Prefer source branch value",
    "타겟 branch의 값을 우선": "Prefer target branch value",
    "그룹 내 하나라도 변경되면 전체 업데이트": "Update all if any in group changes",
    "양쪽이 동일한 변경만 허용": "Allow only identical changes on both sides",
}


def fix_file(file_path):
    """Fix remaining Korean text in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply all fixes
        for korean, english in FIXES.items():
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
    """Main function to fix remaining Korean text."""
    base_dir = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"

    # Target files that still have issues
    target_files = [
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

    print(f"\n✨ Fixed {fixed} files with remaining Korean text")


if __name__ == "__main__":
    main()
