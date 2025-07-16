#!/usr/bin/env python3
"""
Automated Naming Pattern Checker for Arrakis Platform
Detects inconsistent class, function, and variable naming patterns
"""

import ast
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ANSI color codes
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


@dataclass
class NamingViolation:
    """Represents a naming convention violation"""
    file_path: str
    line_number: int
    name: str
    violation_type: str
    expected_pattern: str
    suggestion: Optional[str] = None


class NamingPatternChecker:
    """Check Python files for naming pattern consistency"""

    # Naming conventions
    CLASS_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*$')  # PascalCase
    FUNCTION_PATTERN = re.compile(r'^[a-z_][a-z0-9_]*$')  # snake_case
    CONSTANT_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')  # UPPER_SNAKE_CASE
    PRIVATE_PATTERN = re.compile(r'^_[a-z_][a-z0-9_]*$')  # _private_method
    DUNDER_PATTERN = re.compile(r'^__[a-z]+__$')  # __dunder__

    # Special patterns for different types
    TEST_FUNCTION_PATTERN = re.compile(r'^test_[a-z0-9_]+$')
    EXCEPTION_CLASS_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*Error$|^[A-Z][a-zA-Z0-9]*Exception$')
    MIXIN_CLASS_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*Mixin$')
    ABSTRACT_CLASS_PATTERN = re.compile(r'^Abstract[A-Z][a-zA-Z0-9]*$|^Base[A-Z][a-zA-Z0-9]*$')

    # Common abbreviations that should be expanded
    ABBREVIATIONS = {
        'cfg': 'config',
        'ctx': 'context',
        'conn': 'connection',
        'resp': 'response',
        'req': 'request',
        'msg': 'message',
        'auth': 'authentication',
        'authz': 'authorization',
        'db': 'database',
        'err': 'error',
        'func': 'function',
        'impl': 'implementation',
        'info': 'information',
        'init': 'initialize',
        'max': 'maximum',
        'min': 'minimum',
        'num': 'number',
        'obj': 'object',
        'param': 'parameter',
        'pwd': 'password',
        'ref': 'reference',
        'res': 'result',
        'ret': 'return',
        'str': 'string',
        'temp': 'temporary',
        'val': 'value',
        'var': 'variable',
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.violations: List[NamingViolation] = []
        self.statistics = defaultdict(int)
        self.naming_patterns = defaultdict(list)

    def check_project(self, exclude_dirs: Optional[Set[str]] = None) -> List[NamingViolation]:
        """Check all Python files in the project"""
        exclude_dirs = exclude_dirs or {
            '__pycache__', '.git', 'venv', '.venv', 'node_modules',
            'build', 'dist', '.pytest_cache', '.mypy_cache'
        }

        for root, dirs, files in os.walk(self.project_root):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    self.check_file(file_path)

        return self.violations

    def check_file(self, file_path: Path) -> None:
        """Check a single Python file for naming violations"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))
            self._check_node(tree, file_path)

        except Exception as e:
            print(f"{YELLOW}Warning: Could not parse {file_path}: {e}{NC}")

    def _check_node(self, node: ast.AST, file_path: Path, class_context: Optional[str] = None) -> None:
        """Recursively check AST nodes for naming violations"""
        for child in ast.walk(node):
            if isinstance(child, ast.ClassDef):
                self._check_class_name(child, file_path)
                # Check methods within class
                for item in child.body:
                    if isinstance(item, ast.FunctionDef):
                        self._check_method_name(item, file_path, child.name)

            elif isinstance(child, ast.FunctionDef) and not class_context:
                self._check_function_name(child, file_path)

            elif isinstance(child, ast.Assign):
                self._check_variable_name(child, file_path)

    def _check_class_name(self, node: ast.ClassDef, file_path: Path) -> None:
        """Check class naming conventions"""
        name = node.name
        line_number = node.lineno

        # Check for exception classes
        if any(base.id for base in node.bases if hasattr(base, 'id') and
               base.id in ['Exception', 'BaseException', 'Error']):
            if not self.EXCEPTION_CLASS_PATTERN.match(name):
                self.violations.append(NamingViolation(
                    file_path=str(file_path),
                    line_number=line_number,
                    name=name,
                    violation_type="exception_class_naming",
                    expected_pattern="Should end with 'Error' or 'Exception'",
                    suggestion=f"{name}Error" if not name.endswith(('Error', 'Exception')) else None
                ))
                return

        # Check for mixin classes
        if 'mixin' in name.lower() and not self.MIXIN_CLASS_PATTERN.match(name):
            self.violations.append(NamingViolation(
                file_path=str(file_path),
                line_number=line_number,
                name=name,
                violation_type="mixin_class_naming",
                expected_pattern="Should end with 'Mixin'",
                suggestion=f"{name}Mixin" if not name.endswith('Mixin') else None
            ))
            return

        # Check for abstract/base classes
        if any(decorator.id for decorator in node.decorator_list
               if hasattr(decorator, 'id') and decorator.id == 'abstractmethod'):
            if not self.ABSTRACT_CLASS_PATTERN.match(name):
                self.violations.append(NamingViolation(
                    file_path=str(file_path),
                    line_number=line_number,
                    name=name,
                    violation_type="abstract_class_naming",
                    expected_pattern="Should start with 'Abstract' or 'Base'",
                    suggestion=f"Abstract{name}" if not name.startswith(('Abstract', 'Base')) else None
                ))
                return

        # General class naming
        if not self.CLASS_PATTERN.match(name):
            self.violations.append(NamingViolation(
                file_path=str(file_path),
                line_number=line_number,
                name=name,
                violation_type="class_naming",
                expected_pattern="PascalCase (e.g., MyClass)",
                suggestion=self._to_pascal_case(name)
            ))

        # Check for abbreviations
        self._check_abbreviations(name, file_path, line_number, "class")

        # Track naming pattern
        self.naming_patterns['classes'].append(name)
        self.statistics['total_classes'] += 1

    def _check_function_name(self, node: ast.FunctionDef, file_path: Path) -> None:
        """Check function naming conventions"""
        name = node.name
        line_number = node.lineno

        # Check if it's a test function
        if 'test' in str(file_path) or name.startswith('test'):
            if not self.TEST_FUNCTION_PATTERN.match(name):
                self.violations.append(NamingViolation(
                    file_path=str(file_path),
                    line_number=line_number,
                    name=name,
                    violation_type="test_function_naming",
                    expected_pattern="Should start with 'test_'",
                    suggestion=f"test_{name}" if not name.startswith('test_') else None
                ))
                return

        # General function naming
        if not self.FUNCTION_PATTERN.match(name):
            self.violations.append(NamingViolation(
                file_path=str(file_path),
                line_number=line_number,
                name=name,
                violation_type="function_naming",
                expected_pattern="snake_case (e.g., my_function)",
                suggestion=self._to_snake_case(name)
            ))

        # Check for abbreviations
        self._check_abbreviations(name, file_path, line_number, "function")

        self.naming_patterns['functions'].append(name)
        self.statistics['total_functions'] += 1

    def _check_method_name(self, node: ast.FunctionDef, file_path: Path, class_name: str) -> None:
        """Check method naming conventions"""
        name = node.name
        line_number = node.lineno

        # Dunder methods
        if name.startswith('__') and name.endswith('__'):
            if not self.DUNDER_PATTERN.match(name):
                self.violations.append(NamingViolation(
                    file_path=str(file_path),
                    line_number=line_number,
                    name=name,
                    violation_type="dunder_method_naming",
                    expected_pattern="__method__ (lowercase between dunders)",
                    suggestion=None
                ))
            return

        # Private methods
        if name.startswith('_') and not name.startswith('__'):
            if not self.PRIVATE_PATTERN.match(name):
                self.violations.append(NamingViolation(
                    file_path=str(file_path),
                    line_number=line_number,
                    name=name,
                    violation_type="private_method_naming",
                    expected_pattern="_snake_case",
                    suggestion=f"_{self._to_snake_case(name[1:])}" if name.startswith('_') else None
                ))
            return

        # Public methods
        if not self.FUNCTION_PATTERN.match(name):
            self.violations.append(NamingViolation(
                file_path=str(file_path),
                line_number=line_number,
                name=name,
                violation_type="method_naming",
                expected_pattern="snake_case",
                suggestion=self._to_snake_case(name)
            ))

        self.naming_patterns['methods'].append(f"{class_name}.{name}")
        self.statistics['total_methods'] += 1

    def _check_variable_name(self, node: ast.Assign, file_path: Path) -> None:
        """Check variable naming conventions"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                line_number = node.lineno

                # Check if it's likely a constant (all caps or module level)
                if name.isupper() or (isinstance(node.value, ast.Constant) and
                                     name == name.upper()):
                    if not self.CONSTANT_PATTERN.match(name):
                        self.violations.append(NamingViolation(
                            file_path=str(file_path),
                            line_number=line_number,
                            name=name,
                            violation_type="constant_naming",
                            expected_pattern="UPPER_SNAKE_CASE",
                            suggestion=self._to_upper_snake_case(name)
                        ))
                else:
                    # Regular variable
                    if not self.FUNCTION_PATTERN.match(name):
                        self.violations.append(NamingViolation(
                            file_path=str(file_path),
                            line_number=line_number,
                            name=name,
                            violation_type="variable_naming",
                            expected_pattern="snake_case",
                            suggestion=self._to_snake_case(name)
                        ))

                self.statistics['total_variables'] += 1

    def _check_abbreviations(self, name: str, file_path: Path, line_number: int,
                            context: str) -> None:
        """Check for common abbreviations that should be expanded"""
        name_lower = name.lower()
        for abbr, full in self.ABBREVIATIONS.items():
            if abbr in name_lower:
                # Check if it's a whole word (not part of another word)
                pattern = rf'\b{abbr}\b'
                if re.search(pattern, name_lower):
                    self.violations.append(NamingViolation(
                        file_path=str(file_path),
                        line_number=line_number,
                        name=name,
                        violation_type="abbreviation",
                        expected_pattern=f"Use '{full}' instead of '{abbr}'",
                        suggestion=re.sub(pattern, full, name_lower)
                    ))

    def _to_snake_case(self, name: str) -> str:
        """Convert name to snake_case"""
        # Handle acronyms
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase"""
        parts = name.split('_')
        return ''.join(word.capitalize() for word in parts if word)

    def _to_upper_snake_case(self, name: str) -> str:
        """Convert name to UPPER_SNAKE_CASE"""
        return self._to_snake_case(name).upper()

    def generate_report(self) -> str:
        """Generate a detailed report of violations"""
        report = []

        # Header
        report.append(f"\n{BLUE}{'='*60}")
        report.append("    NAMING PATTERN ANALYSIS REPORT")
        report.append(f"{'='*60}{NC}\n")

        # Statistics
        report.append(f"{CYAN}📊 Statistics:{NC}")
        report.append(f"  • Total files analyzed: {self.statistics.get('total_files', 0)}")
        report.append(f"  • Total classes: {self.statistics['total_classes']}")
        report.append(f"  • Total functions: {self.statistics['total_functions']}")
        report.append(f"  • Total methods: {self.statistics['total_methods']}")
        report.append(f"  • Total variables checked: {self.statistics['total_variables']}")
        report.append(f"  • Total violations: {len(self.violations)}\n")

        if not self.violations:
            report.append(f"{GREEN}✅ No naming violations found!{NC}")
            return '\n'.join(report)

        # Group violations by type
        violations_by_type = defaultdict(list)
        for violation in self.violations:
            violations_by_type[violation.violation_type].append(violation)

        # Report violations by type
        report.append(f"{RED}❌ Naming Violations:{NC}\n")

        for vtype, violations in sorted(violations_by_type.items()):
            report.append(f"{YELLOW}▶ {vtype.replace('_', ' ').title()} ({len(violations)} violations):{NC}")

            for v in violations[:10]:  # Show first 10 of each type
                rel_path = os.path.relpath(v.file_path, self.project_root)
                report.append(f"  📍 {rel_path}:{v.line_number}")
                report.append(f"     Name: {v.name}")
                report.append(f"     Expected: {v.expected_pattern}")
                if v.suggestion:
                    report.append(f"     Suggestion: {v.suggestion}")
                report.append("")

            if len(violations) > 10:
                report.append(f"  ... and {len(violations) - 10} more\n")

        # Most common violations
        report.append(f"\n{CYAN}📈 Most Common Issues:{NC}")
        violation_counts = defaultdict(int)
        for v in self.violations:
            violation_counts[v.violation_type] += 1

        for vtype, count in sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            report.append(f"  • {vtype.replace('_', ' ').title()}: {count} violations")

        return '\n'.join(report)

    def export_violations(self, output_file: Path) -> None:
        """Export violations to JSON file"""
        import json

        violations_data = []
        for v in self.violations:
            violations_data.append({
                'file': str(v.file_path),
                'line': v.line_number,
                'name': v.name,
                'type': v.violation_type,
                'expected': v.expected_pattern,
                'suggestion': v.suggestion
            })

        with open(output_file, 'w') as f:
            json.dump({
                'summary': dict(self.statistics),
                'violations': violations_data
            }, f, indent=2)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Check Python naming patterns in the Arrakis project'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='.',
        help='Path to check (default: current directory)'
    )
    parser.add_argument(
        '--export',
        type=str,
        help='Export violations to JSON file'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix simple naming violations (experimental)'
    )
    parser.add_argument(
        '--exclude',
        type=str,
        nargs='+',
        default=[],
        help='Additional directories to exclude'
    )

    args = parser.parse_args()

    # Run checker
    checker = NamingPatternChecker(Path(args.path))

    # Add exclusions
    exclude_dirs = {
        '__pycache__', '.git', 'venv', '.venv', 'node_modules',
        'build', 'dist', '.pytest_cache', '.mypy_cache'
    }
    exclude_dirs.update(args.exclude)

    print(f"{BLUE}🔍 Analyzing naming patterns in: {args.path}{NC}")
    violations = checker.check_project(exclude_dirs)

    # Generate and print report
    report = checker.generate_report()
    print(report)

    # Export if requested
    if args.export:
        checker.export_violations(Path(args.export))
        print(f"\n{GREEN}📄 Violations exported to: {args.export}{NC}")

    # Return non-zero exit code if violations found
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
