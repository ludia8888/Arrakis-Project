#!/usr/bin/env python3
"""Fix final indentation issues in domain.py and merge_hints.py"""


def fix_domain_final():
    """Fix remaining indentation issues in domain.py"""
    file_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/models/domain.py"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Fix line 89 onwards (FieldGroup class)
    for i in range(len(lines)):
        if i >= 88 and i <= 96:  # Lines 89-97 (0-indexed)
            if (
                lines[i].startswith(' """')
                or lines[i].startswith(" name:")
                or lines[i].startswith(" members:")
                or lines[i].startswith(" merge_strategy:")
                or lines[i].startswith(" default =")
                or lines[i].startswith(" description =")
                or lines[i].startswith(" )")
                or lines[i].startswith(" description:")
            ):
                # Add proper indentation
                lines[i] = "    " + lines[i].lstrip()

        # Fix line 148 (def from_document)
        if i == 148:  # Line 149 (0-indexed)
            lines[i] = lines[i].lstrip()  # Remove all leading spaces

        # Fix lines 153-158 (inside from_document method)
        if i >= 152 and i <= 158:
            if (
                lines[i].startswith(" #")
                or lines[i].startswith(" required_fields")
                or lines[i].startswith(" missing")
                or lines[i].startswith(" if missing")
                or lines[i].startswith(" raise")
            ):
                lines[i] = "        " + lines[i].lstrip()

        # Fix line 161 (parse_datetime def)
        if i == 160:  # Line 161 (0-indexed)
            if "def parse_datetime" in lines[i]:
                lines[i] = lines[i].lstrip()

        # Fix lines 169-193 (return statement and its contents)
        if i >= 168 and i <= 193:
            if (
                lines[i].startswith(" return")
                or lines[i].startswith(" id =")
                or lines[i].startswith(" object_type_id")
                or lines[i].startswith(" name =")
                or lines[i].startswith(" display_name")
                or lines[i].startswith(" description =")
                or lines[i].startswith(" data_type_id")
                or lines[i].startswith(" semantic_type_id")
                or lines[i].startswith(" shared_property_id")
                or lines[i].startswith(" is_")
                or lines[i].startswith(" default_value")
                or lines[i].startswith(" enum_values")
                or lines[i].startswith(" reference_type")
                or lines[i].startswith(" sort_order")
                or lines[i].startswith(" visibility")
                or lines[i].startswith(" validation_rules")
                or lines[i].startswith(" version_hash")
                or lines[i].startswith(" created_at")
                or lines[i].startswith(" modified_at")
                or lines[i].startswith(" )")
            ):
                lines[i] = "        " + lines[i].lstrip()

        # Fix line 240 (from_document docstring)
        if i == 239:  # Line 240 (0-indexed)
            if '"""' in lines[i] and "설계" in lines[i]:
                lines[
                    i
                ] = '        """Design intent: DB camelCase → domain snake_case conversion (See Doc 8.1.2)"""\n'

        # Fix line 241 (from datetime import)
        if i == 240:  # Line 241 (0-indexed)
            if "from datetime import" in lines[i]:
                lines[i] = "        " + lines[i].lstrip()

        # Fix lines 243-248 (validation in from_document)
        if i >= 242 and i <= 248:
            if (
                lines[i].startswith(" #")
                or lines[i].startswith(" required_fields")
                or lines[i].startswith(" missing")
                or lines[i].startswith(" if missing")
                or lines[i].startswith(" raise")
            ):
                lines[i] = "        " + lines[i].lstrip()

        # Fix line 251 (parse_datetime def)
        if i == 250:  # Line 251 (0-indexed)
            if "def parse_datetime" in lines[i]:
                lines[i] = lines[i].lstrip()

        # Fix lines 259-278 (return statement in from_document)
        if i >= 258 and i <= 278:
            if (
                lines[i].startswith(" return")
                or lines[i].startswith(" id =")
                or lines[i].startswith(" name =")
                or lines[i].startswith(" display_name")
                or lines[i].startswith(" plural_display_name")
                or lines[i].startswith(" description =")
                or lines[i].startswith(" status =")
                or lines[i].startswith(" type_class")
                or lines[i].startswith(" version_hash")
                or lines[i].startswith(" created_by")
                or lines[i].startswith(" created_at")
                or lines[i].startswith(" modified_by")
                or lines[i].startswith(" modified_at")
                or lines[i].startswith(" properties =")
                or lines[i].startswith(" parent_types")
                or lines[i].startswith(" interfaces")
                or lines[i].startswith(" is_abstract")
                or lines[i].startswith(" icon =")
                or lines[i].startswith(" color =")
                or lines[i].startswith(" )")
            ):
                lines[i] = "        " + lines[i].lstrip()

        # Fix Korean text
        if "설계 의도:" in lines[i]:
            lines[i] = lines[i].replace("설계 의도:", "Design intent:")
        if "필드 그룹 정의 - 의미론적으로 연관된 필드들" in lines[i]:
            lines[i] = lines[i].replace(
                "필드 그룹 정의 - 의미론적으로 연관된 필드들",
                "Field group definitions - semantically related fields",
            )
        if "상태별 전이 규칙" in lines[i]:
            lines[i] = lines[i].replace("상태별 전이 규칙", "State transition rules by state")
        if "문서 관리" in lines[i]:
            lines[i] = lines[i].replace("문서 관리", "Document management")
        if "문서가 속한 ObjectType" in lines[i]:
            lines[i] = lines[i].replace(
                "문서가 속한 ObjectType", "ObjectType that the document belongs to"
            )
        if "문서의 실제 내용" in lines[i]:
            lines[i] = lines[i].replace("문서의 실제 내용", "Actual content of the document")

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✓ Fixed domain.py indentation")


def fix_merge_hints_final():
    """Fix remaining indentation issues in merge_hints.py"""
    file_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/models/merge_hints.py"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Fix line 144 (class Config)
    for i in range(len(lines)):
        if i == 143:  # Line 144 (0-indexed)
            if "class Config:" in lines[i]:
                lines[i] = "    class Config:\n"

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✓ Fixed merge_hints.py indentation")


if __name__ == "__main__":
    fix_domain_final()
    fix_merge_hints_final()
