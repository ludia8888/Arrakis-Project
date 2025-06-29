#!/usr/bin/env python3
"""
Script to identify and remove validation code that duplicates TerminusDB native functionality.

This script will:
1. Identify validation code that TerminusDB can handle natively
2. Create backups of files before modification
3. Remove or comment out duplicate validation logic
4. Generate a report of changes made
"""

import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# TerminusDB native validation capabilities
TERMINUS_NATIVE_CAPABILITIES = {
    "type_validation": [
        "data_type", "dataType", "xsd:", "@type", "type_check",
        "isinstance", "type(", "__class__"
    ],
    "required_field": [
# REMOVED: TerminusDB handles required_field natively
#         "is_required", "isRequired", "required", "min_cardinality",
        "minCardinality", "@min", "nullable"
    ],
    "enum_validation": [
# REMOVED: TerminusDB handles enum_validation natively
#         "enum_values", "enumValues", "@oneOf", "oneOf", "allowed_values",
        "valid_values", "choices"
    ],
    "foreign_key": [
        "@link", "reference", "referenceType", "foreign_key", "fk_",
        "relationship", "@ref"
    ],
    "array_validation": [
# REMOVED: TerminusDB handles array_validation natively
#         "is_array", "isArray", "List[", "array_type", "element_type",
        "@container", "maxItems", "minItems"
    ],
    "cardinality": [
        "cardinality", "@min", "@max", "min_cardinality", "max_cardinality",
        "minCardinality", "maxCardinality"
    ],
    "pattern_validation": [
        "pattern", "@pattern", "regex", "regexp", "match"
    ],
    "range_validation": [
        "minimum", "maximum", "@min", "@max", "min_value", "max_value",
        "range", "bounds"
    ]
}

# Files/patterns to exclude from modification
EXCLUDE_PATTERNS = [
    "test_", "_test.py", "tests/", "migrations/", "backup",
    "terminus_native", "business_rules", "merge_validation.py"
]


class ValidationCleanupAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.backup_dir = self.root_dir / f"validation_terminus_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.report = {
            "analyzed_files": 0,
            "modified_files": 0,
            "removed_validations": {},
            "preserved_validations": {},
            "errors": []
        }
        
    def analyze_and_cleanup(self):
        """Main method to analyze and clean up validation code."""
        print(f"Starting TerminusDB duplicate validation cleanup in {self.root_dir}")
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        
        # Find all Python files
        python_files = self._find_python_files()
        
        for file_path in python_files:
            try:
                self._analyze_file(file_path)
            except Exception as e:
                self.report["errors"].append(f"Error processing {file_path}: {str(e)}")
                print(f"Error processing {file_path}: {e}")
        
        # Generate report
        self._generate_report()
        
    def _find_python_files(self) -> List[Path]:
        """Find all Python files to analyze."""
        python_files = []
        
        for file_path in self.root_dir.rglob("*.py"):
            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in EXCLUDE_PATTERNS):
                continue
                
            # Focus on validation-related files
            if any(keyword in str(file_path).lower() for keyword in ["validat", "rule", "check", "constraint"]):
                python_files.append(file_path)
                
        return python_files
    
    def _analyze_file(self, file_path: Path):
        """Analyze a single file for duplicate validation logic."""
        self.report["analyzed_files"] += 1
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        modifications = []
        
        # Analyze each type of validation
        for validation_type, patterns in TERMINUS_NATIVE_CAPABILITIES.items():
            matches = self._find_validation_patterns(content, patterns)
            
            for match in matches:
                line_num, line_content, context = match
                
                # Determine if this is a duplicate of TerminusDB functionality
                if self._is_terminus_duplicate(line_content, context, validation_type):
                    # Record the validation for removal
                    modifications.append((line_num, line_content, validation_type))
        
        # Apply modifications if any found
        if modifications:
            self._backup_file(file_path)
            modified_content = self._apply_modifications(original_content, modifications)
            
            # Write modified content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
                
            self.report["modified_files"] += 1
            self.report["removed_validations"][str(file_path)] = [
                {"line": m[0], "type": m[2], "content": m[1][:100]} for m in modifications
            ]
            
            print(f"Modified {file_path}: Removed {len(modifications)} duplicate validations")
    
    def _find_validation_patterns(self, content: str, patterns: List[str]) -> List[Tuple[int, str, List[str]]]:
        """Find validation patterns in content."""
        matches = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            for pattern in patterns:
                if pattern in line:
                    # Get context (3 lines before and after)
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    context = lines[start:end]
                    
                    matches.append((i + 1, line, context))
                    break
                    
        return matches
    
    def _is_terminus_duplicate(self, line: str, context: List[str], validation_type: str) -> bool:
        """Determine if this validation is a duplicate of TerminusDB functionality."""
        
        # Business rule keywords that should be preserved
        business_keywords = [
            "business", "custom", "special", "workflow", "process",
            "calculate", "derive", "transform", "aggregate"
        ]
        
        # Check if this is a business rule (should be preserved)
        context_str = '\n'.join(context).lower()
        if any(keyword in context_str for keyword in business_keywords):
            return False
            
        # Specific checks for each validation type
        if validation_type == "type_validation":
            # Check if it's basic type checking
            if re.search(r'isinstance\s*\([^,]+,\s*(str|int|bool|float|list|dict)\)', line):
                return True
            if re.search(r'type\s*\([^)]+\)\s*==\s*(str|int|bool|float|list|dict)', line):
                return True
                
        elif validation_type == "required_field":
            # Check if it's basic required field validation
# REMOVED: TerminusDB handles required_field natively
#             if re.search(r'is_required|isRequired|required.*=.*True', line):
                return True
            if re.search(r'if\s+not\s+.*\.\s*get\s*\(["\'][\w_]+["\']\)', line):
                return True
                
        elif validation_type == "enum_validation":
            # Check if it's basic enum validation
# REMOVED: TerminusDB handles enum_validation natively
#             if re.search(r'in\s+\[.*\]|in\s+\(.*\)|choices\s*=|enum_values', line):
                return True
                
        elif validation_type == "array_validation":
            # Check if it's basic array type validation
# REMOVED: TerminusDB handles array_validation natively
#             if re.search(r'is_array|isArray|isinstance.*list', line):
                return True
                
        # Add more specific checks as needed
        
        return False
    
    def _backup_file(self, file_path: Path):
        """Create a backup of the file."""
        relative_path = file_path.relative_to(self.root_dir)
        backup_path = self.backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        
    def _apply_modifications(self, content: str, modifications: List[Tuple[int, str, str]]) -> str:
        """Apply modifications to remove duplicate validations."""
        lines = content.split('\n')
        
        # Sort modifications by line number in reverse order
        modifications.sort(key=lambda x: x[0], reverse=True)
        
        for line_num, line_content, validation_type in modifications:
            idx = line_num - 1
            if idx < len(lines):
                # Comment out the line with explanation
                lines[idx] = f"# REMOVED: TerminusDB handles {validation_type} natively\n# {lines[idx]}"
                
        return '\n'.join(lines)
    
    def _generate_report(self):
        """Generate a detailed report of the cleanup."""
        report_path = self.root_dir / f"terminus_validation_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Summary statistics
        total_removed = sum(len(v) for v in self.report["removed_validations"].values())
        
        summary = {
            "summary": {
                "total_files_analyzed": self.report["analyzed_files"],
                "total_files_modified": self.report["modified_files"],
                "total_validations_removed": total_removed,
                "backup_location": str(self.backup_dir)
            },
            "removed_validations": self.report["removed_validations"],
            "errors": self.report["errors"]
        }
        
        with open(report_path, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"\nCleanup Summary:")
        print(f"- Files analyzed: {self.report['analyzed_files']}")
        print(f"- Files modified: {self.report['modified_files']}")
        print(f"- Validations removed: {total_removed}")
        print(f"- Backup location: {self.backup_dir}")
        print(f"- Report saved to: {report_path}")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    analyzer = ValidationCleanupAnalyzer(root_dir)
    analyzer.analyze_and_cleanup()


if __name__ == "__main__":
    main()