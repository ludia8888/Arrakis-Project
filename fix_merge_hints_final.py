#!/usr/bin/env python3
"""Fix all indentation issues in merge_hints.py"""


def fix_merge_hints_indentation():
    """Fix all indentation issues in merge_hints.py"""
    file_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/models/merge_hints.py"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Fix all indentation issues
    for i in range(len(lines)):
        # Fix docstring indentation (lines starting with triple quotes)
        if lines[i].strip() and lines[i].strip()[0] == '"' and i > 100:
            # This is within SchemaMergeMetadata class
            lines[i] = "    " + lines[i].lstrip()

        # Fix field definitions in SchemaMergeMetadata (lines 108-142)
        if i >= 107 and i <= 141:
            if lines[i].strip() and not lines[i].startswith("    "):
                # Add proper indentation
                lines[i] = "    " + lines[i].lstrip()

        # Fix json_schema_extra content (lines 147-172)
        if i >= 146 and i <= 172:
            if lines[i].startswith(' "'):
                # This should be indented 16 spaces (4 levels deep)
                lines[i] = "                " + lines[i].lstrip()
            elif lines[i].startswith(" },") or lines[i].startswith(" }"):
                # Closing braces
                lines[i] = "            " + lines[i].lstrip()

        # Fix function definitions at module level
        if i >= 174:
            # Functions should not be indented
            if "def " in lines[i] and lines[i].startswith(" def"):
                lines[i] = lines[i].lstrip()
            # Docstrings at function level should be indented 4 spaces
            if lines[i].strip().startswith('"""') and i > 175 and "def" in lines[i - 1]:
                lines[i] = "    " + lines[i].lstrip()
            # Code inside functions should be indented 4 spaces
            if (
                i > 180
                and lines[i].strip()
                and not lines[i].startswith("def")
                and not lines[i].startswith("class")
            ):
                if lines[i].startswith(" ") and not lines[i].startswith("    "):
                    lines[i] = "    " + lines[i].lstrip()

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✓ Fixed all indentation in merge_hints.py")


if __name__ == "__main__":
    fix_merge_hints_indentation()
