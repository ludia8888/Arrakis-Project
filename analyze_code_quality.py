#!/usr/bin/env python3
"""
Code Quality Analysis Script

This script analyzes common code quality issues in Python files,
similar to what Flake8 would detect, without requiring external dependencies.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


class CodeQualityAnalyzer:
    """Analyzes Python code for common quality issues"""

    def __init__(self):
        self.issues = []
        self.files_analyzed = 0

    def analyze_file(self, file_path: str) -> List[str]:
        """Analyze a single Python file for code quality issues"""
        issues = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            # Line-by-line analysis
            for i, line in enumerate(lines, 1):
                # E501: Line too long
                if len(line) > 88:
                    issues.append(
                        f"{file_path}:{i}: E501 line too long ({len(line)} > 88)"
                    )

                # W291: Trailing whitespace
                if line.endswith(" ") or line.endswith("\t"):
                    issues.append(f"{file_path}:{i}: W291 trailing whitespace")

                # W293: Blank line contains whitespace
                if line.strip() == "" and len(line) > 0:
                    issues.append(
                        f"{file_path}:{i}: W293 blank line contains whitespace"
                    )

                # E225: Missing whitespace around operator
                if (
                    "=" in line
                    and "==" not in line
                    and "!=" not in line
                    and "<=" not in line
                    and ">=" not in line
                ):
                    # Simple check for assignment operators
                    if re.search(r"[a-zA-Z0-9_]\=[a-zA-Z0-9_]", line):
                        issues.append(
                            f"{file_path}:{i}: E225 missing whitespace around operator"
                        )

                # E302: Expected 2 blank lines, found fewer
                if (
                    line.strip().startswith("class ")
                    or line.strip().startswith("def ")
                    and not line.strip().startswith("def _")
                ):
                    if i > 2:
                        prev_lines = [
                            lines[j].strip() for j in range(max(0, i - 3), i - 1)
                        ]
                        if not all(l == "" for l in prev_lines[-2:]):
                            issues.append(
                                f"{file_path}:{i}: E302 expected 2 blank lines"
                            )

                # E261: At least two spaces before inline comment
                if "#" in line and not line.strip().startswith("#"):
                    comment_pos = line.find("#")
                    if (
                        comment_pos > 0
                        and not line[comment_pos - 2 : comment_pos] == "  "
                    ):
                        issues.append(
                            f"{file_path}:{i}: E261 at least two spaces before inline comment"
                        )

                # E303: Too many blank lines
                if i > 3 and all(lines[j].strip() == "" for j in range(i - 4, i - 1)):
                    issues.append(f"{file_path}:{i}: E303 too many blank lines")

            # Check for unused imports (basic)
            import_lines = [
                line for line in lines if line.strip().startswith(("import ", "from "))
            ]
            for i, line in enumerate(lines, 1):
                if line.strip().startswith("import "):
                    module = line.strip().split()[1].split(".")[0]
                    if (
                        module not in ["os", "sys", "json", "logging"]
                        and content.count(module) <= 1
                    ):
                        issues.append(
                            f"{file_path}:{i}: F401 '{module}' imported but unused"
                        )

        except Exception as e:
            issues.append(f"{file_path}:1: ERROR unable to analyze file: {e}")

        return issues

    def analyze_directory(
        self, directory: str, exclude_dirs: List[str] = None
    ) -> Dict[str, List[str]]:
        """Analyze all Python files in a directory"""
        if exclude_dirs is None:
            exclude_dirs = [
                "__pycache__",
                ".git",
                "venv",
                "node_modules",
                "htmlcov",
                "logs",
                ".pytest_cache",
            ]

        results = {}

        for root, dirs, files in os.walk(directory):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, directory)

                    issues = self.analyze_file(file_path)
                    if issues:
                        results[relative_path] = issues

                    self.files_analyzed += 1

        return results

    def categorize_issues(self, all_issues: Dict[str, List[str]]) -> Dict[str, int]:
        """Categorize issues by type for statistics"""
        categories = {}

        for file_path, issues in all_issues.items():
            for issue in issues:
                if ":" in issue:
                    code = issue.split(":")[2].strip().split()[0]
                    categories[code] = categories.get(code, 0) + 1

        return categories


def main():
    """Main analysis function"""
    print("🔍 Code Quality Analysis - Starting comprehensive check...")

    analyzer = CodeQualityAnalyzer()

    # Analyze key directories
    directories = [
        "arrakis-common/arrakis_common",
        "ontology-management-service",
        "user-service/src",
        "audit-service/src",
        "data-kernel-service",
        "embedding-service/app",
        "event-gateway/app",
        "scheduler-service",
    ]

    all_issues = {}

    for directory in directories:
        if os.path.exists(directory):
            print(f"📁 Analyzing {directory}...")
            issues = analyzer.analyze_directory(directory)
            all_issues.update(issues)

    # Generate statistics
    issue_stats = analyzer.categorize_issues(all_issues)
    total_issues = sum(issue_stats.values())

    print("\n📊 Code Quality Analysis Results:")
    print(f"   📂 Files analyzed: {analyzer.files_analyzed}")
    print(f"   🐛 Total issues found: {total_issues}")
    print(f"   📄 Files with issues: {len(all_issues)}")

    # Show top issue types
    if issue_stats:
        print("\n🔥 Top Issue Types:")
        sorted_issues = sorted(issue_stats.items(), key=lambda x: x[1], reverse=True)
        for code, count in sorted_issues[:10]:
            print(f"   {code}: {count} occurrences")

    # Show files with most issues
    if all_issues:
        print("\n📋 Files with Most Issues:")
        sorted_files = sorted(all_issues.items(), key=lambda x: len(x[1]), reverse=True)
        for file_path, issues in sorted_files[:10]:
            print(f"   {file_path}: {len(issues)} issues")

    # Sample issues for fixing
    if all_issues:
        print("\n🔧 Sample Issues to Fix:")
        count = 0
        for file_path, issues in all_issues.items():
            for issue in issues[:2]:  # Show first 2 issues per file
                print(f"   {issue}")
                count += 1
                if count >= 10:
                    break
            if count >= 10:
                break

    return total_issues > 0


if __name__ == "__main__":
    main()
