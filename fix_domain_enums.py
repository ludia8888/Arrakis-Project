#!/usr/bin/env python3
"""Fix all enum indentation issues in domain.py"""

import re


def fix_domain_enums():
    """Fix all enum class indentation issues in domain.py"""
    file_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/models/domain.py"

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix Status enum
    content = content.replace(
        'class Status(str, Enum):\n """Entity status enumeration"""\n ACTIVE = "active"\n EXPERIMENTAL = "experimental"\n DEPRECATED = "deprecated"\n EXAMPLE = "example"\n ARCHIVED = "archived"',
        'class Status(str, Enum):\n    """Entity status enumeration"""\n    ACTIVE = "active"\n    EXPERIMENTAL = "experimental"\n    DEPRECATED = "deprecated"\n    EXAMPLE = "example"\n    ARCHIVED = "archived"',
    )

    # Fix TypeClass enum
    content = content.replace(
        'class TypeClass(str, Enum):\n """Object type classification"""\n OBJECT = "object"\n INTERFACE = "interface"\n LINK = "link"\n EMBEDDED = "embedded"',
        'class TypeClass(str, Enum):\n    """Object type classification"""\n    OBJECT = "object"\n    INTERFACE = "interface"\n    LINK = "link"\n    EMBEDDED = "embedded"',
    )

    # Fix MergeStrategy enum
    content = content.replace(
        'class MergeStrategy(str, Enum):\n """Field group merge strategy"""\n PREFER_SOURCE = "prefer_source" # Prefer source branch value\n PREFER_TARGET = "prefer_target" # Prefer target branch value\n ATOMIC_UPDATE = "atomic_update" # Update all if any in group changes\n REQUIRE_CONSENSUS = "require_consensus" # Allow only identical changes on both sides',
        'class MergeStrategy(str, Enum):\n    """Field group merge strategy"""\n    PREFER_SOURCE = "prefer_source" # Prefer source branch value\n    PREFER_TARGET = "prefer_target" # Prefer target branch value\n    ATOMIC_UPDATE = "atomic_update" # Update all if any in group changes\n    REQUIRE_CONSENSUS = "require_consensus" # Allow only identical changes on both sides',
    )

    # Fix Cardinality enum
    content = content.replace(
        'class Cardinality(str, Enum):\n """Link cardinality types"""\n ONE_TO_ONE = "one-to-one"\n ONE_TO_MANY = "one-to-many"\n MANY_TO_MANY = "many-to-many"',
        'class Cardinality(str, Enum):\n    """Link cardinality types"""\n    ONE_TO_ONE = "one-to-one"\n    ONE_TO_MANY = "one-to-many"\n    MANY_TO_MANY = "many-to-many"',
    )

    # Fix Directionality enum
    content = content.replace(
        'class Directionality(str, Enum):\n """Link directionality types"""\n UNIDIRECTIONAL = "unidirectional"\n BIDIRECTIONAL = "bidirectional"',
        'class Directionality(str, Enum):\n    """Link directionality types"""\n    UNIDIRECTIONAL = "unidirectional"\n    BIDIRECTIONAL = "bidirectional"',
    )

    # Fix Visibility enum
    content = content.replace(
        'class Visibility(str, Enum):\n """Property visibility enumeration"""\n VISIBLE = "visible"\n HIDDEN = "hidden"\n ADVANCED = "advanced"',
        'class Visibility(str, Enum):\n    """Property visibility enumeration"""\n    VISIBLE = "visible"\n    HIDDEN = "hidden"\n    ADVANCED = "advanced"',
    )

    # Fix PropertyType enum
    content = content.replace(
        'class PropertyType(str, Enum):\n """Property data types"""\n STRING = "string"\n INTEGER = "integer"\n DECIMAL = "decimal"\n BOOLEAN = "boolean"\n DATE = "date"\n DATETIME = "datetime"\n REFERENCE = "reference"\n ENUM = "enum"\n TEXT = "text"\n JSON = "json"',
        'class PropertyType(str, Enum):\n    """Property data types"""\n    STRING = "string"\n    INTEGER = "integer"\n    DECIMAL = "decimal"\n    BOOLEAN = "boolean"\n    DATE = "date"\n    DATETIME = "datetime"\n    REFERENCE = "reference"\n    ENUM = "enum"\n    TEXT = "text"\n    JSON = "json"',
    )

    # Fix Korean text in comments
    content = content.replace(
        "필드 그룹 정의 - 함께 움직여야 하는 필드들의 집합",
        "Field group definition - set of fields that must move together",
    )
    content = content.replace("그룹 이름", "Group name")
    content = content.replace(
        "그룹에 속한 Field name들", "Field names belonging to the group"
    )
    content = content.replace("그룹 단위 병합 전략", "Group-level merge strategy")
    content = content.replace("그룹 설명", "Group description")
    content = content.replace("상태 전이 규칙 정의", "State transition rule definition")
    content = content.replace("허용된 이전 상태들", "Allowed previous states")
    content = content.replace(
        "이 상태가 되기 위해 필요한 필드들", "Required fields to reach this state"
    )
    content = content.replace("추가 검증을 위한 표현식", "Expression for additional validation")
    content = content.replace(
        "설계 의도: snake_case 도메인 모델", "Design intent: snake_case domain model"
    )
    content = content.replace("기타 Create/Update 모델", "Other Create/Update models")
    content = content.replace("명시적 변환 수행", "Perform explicit conversion")

    # Fix any remaining Korean text
    content = content.replace(
        "모델에 정의된 필드만 업데이트하도록 제한할 수 있습니다.",
        "Can restrict to update only fields defined in the model.",
    )
    content = content.replace(
        "여기서는 전달된 모든 키를 업데이트한다고 가정합니다.",
        "Here we assume all passed keys will be updated.",
    )
    content = content.replace(
        "수정자 및 수정 시간 업데이트", "Update modifier and modification time"
    )
    content = content.replace(
        "정확한 생성 시간을 알 수 없으므로 마지막 수정 시간으로 대체",
        "Replace with last modification time as exact creation time is unknown",
    )
    content = content.replace(
        "수정 시간이 없다면 생성 시간으로 대체",
        "Replace with creation time if modification time is missing",
    )

    # Fix parse_datetime indentation issues
    content = re.sub(
        r"( |\t)# Parse datetime safely with defensive checks\n( |\t)def parse_datetime",
        "        # Parse datetime safely with defensive checks\n        def parse_datetime",
        content,
    )

    # Fix nested function indentation pattern
    content = re.sub(
        r' def parse_datetime\(value: Any\) -> datetime:\n if not value:\n return datetime\.utcnow\(\)\n if isinstance\(value, str\):\n # TerminusDB returns ISO format with Z suffix\n return datetime\.fromisoformat\(value\.replace\("Z", "\+00:00"\)\)\n return datetime\.utcnow\(\)',
        '        def parse_datetime(value: Any) -> datetime:\n            if not value:\n                return datetime.utcnow()\n            if isinstance(value, str):\n                # TerminusDB returns ISO format with Z suffix\n                return datetime.fromisoformat(value.replace("Z", "+00:00"))\n            return datetime.utcnow()',
        content,
    )

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("✓ Fixed all enum indentation issues in domain.py")


if __name__ == "__main__":
    fix_domain_enums()
