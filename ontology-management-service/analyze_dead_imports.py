#!/usr/bin/env python3
"""
Comprehensive Dead Import Analysis Tool
Analyzes all Python files for unused, commented, duplicate, and problematic imports
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class ImportAnalyzer:
 """Analyzes Python files for various import issues"""

 def __init__(self, base_path: str):
 self.base_path = Path(base_path)
 self.results = {
 "unused_imports": [],
 "commented_imports": [],
 "duplicate_imports": [],
 "typo_imports": [],
 "nonexistent_imports": [],
 "statistics": {},
 }

 def find_production_files(self) -> List[Path]:
 """Find all Python files in production code (excluding tests, scripts, etc.)"""
 python_files = []

 for root, dirs, files in os.walk(self.base_path):
 # Skip test directories and other excluded paths
 relative_path = os.path.relpath(root, self.base_path)
 if any(
 excluded in relative_path
 for excluded in [
 "tests/",
 "scripts/",
 "examples/",
 "migrations/",
 "__pycache__",
 ".git",
 "venv/",
 "htmlcov/",
 "docs/",
 "test_env/",
 "monitoring/",
 "k8s/",
 "infrastructure/",
 ]
 ):
 continue

 for file in files:
 if file.endswith(".py") and not file.startswith("."):
 file_path = Path(root) / file
 # Skip analysis files themselves
 if file_path.name in [
 "analyze_dead_imports.py",
 "analyze_imports.py",
 "check_imports.py",
 "debug_imports.py",
 "fix_imports.py",
 "docker_check_imports.py",
 "archive_unused.py",
 "check_references.py",
 "check_all_references.py",
 "debug_python_path.py",
 "verify_microservices.py",
 ]:
 continue
 python_files.append(file_path)

 return sorted(python_files)

 def extract_imports_from_file(self, file_path: Path) -> Dict[str, Any]:
 """Extract all imports from a Python file"""
 try:
 with open(file_path, "r", encoding = "utf-8") as f:
 content = f.read()

 # Parse commented imports
 commented_imports = self._find_commented_imports(content)

 # Parse AST for regular imports
 tree = ast.parse(content)
 imports = []

 for node in ast.walk(tree):
 if isinstance(node, ast.Import):
 for alias in node.names:
 imports.append(
 {
 "type": "import",
 "module": alias.name,
 "alias": alias.asname,
 "line": node.lineno,
 }
 )
 elif isinstance(node, ast.ImportFrom):
 module = node.module or ""
 for alias in node.names:
 imports.append(
 {
 "type": "from",
 "module": module,
 "name": alias.name,
 "alias": alias.asname,
 "line": node.lineno,
 "level": node.level,
 }
 )

 return {
 "imports": imports,
 "commented_imports": commented_imports,
 "content": content,
 "lines": content.split("\n"),
 }

 except Exception as e:
 print(f"Error parsing {file_path}: {e}")
 return {"imports": [], "commented_imports": [], "content": "", "lines": []}

 def _find_commented_imports(self, content: str) -> List[Dict[str, Any]]:
 """Find commented import statements"""
 commented_imports = []
 lines = content.split("\n")

 for line_num, line in enumerate(lines, 1):
 stripped = line.strip()
 if stripped.startswith("#"):
 # Remove the # and check if it looks like an import
 potential_import = stripped[1:].strip()
 if (
 potential_import.startswith("import ")
 or potential_import.startswith("from ")
 or re.match(r"^\s*(import|from)\s+", potential_import)
 ):
 commented_imports.append(
 {
 "line": line_num,
 "content": potential_import,
 "original": line,
 }
 )

 return commented_imports

 def find_unused_imports(
 self, file_path: Path, file_data: Dict[str, Any]
 ) -> List[Dict[str, Any]]:
 """Find unused imports in a file"""
 unused = []
 content = file_data["content"]
 imports = file_data["imports"]

 for imp in imports:
 if imp["type"] == "import":
 # Check if module is used
 module_name = imp["alias"] or imp["module"]
 used = self._is_name_used(content, module_name, imp["line"])
 if not used:
 unused.append(
 {
 "file": str(file_path),
 "line": imp["line"],
 "type": "unused_import",
 "import_statement": f"import {imp['module']}"
 + (f" as {imp['alias']}" if imp["alias"] else ""),
 "module": imp["module"],
 }
 )

 elif imp["type"] == "from":
 # Check if imported name is used
 name = imp["alias"] or imp["name"]
 if imp["name"] != "*": # Skip star imports
 used = self._is_name_used(content, name, imp["line"])
 if not used:
 unused.append(
 {
 "file": str(file_path),
 "line": imp["line"],
 "type": "unused_from_import",
 "import_statement": f"from {imp['module']} import {imp['name']}"
 + (f" as {imp['alias']}" if imp["alias"] else ""),
 "module": imp["module"],
 "name": imp["name"],
 }
 )

 return unused

 def _is_name_used(self, content: str, name: str, import_line: int) -> bool:
 """Check if a name is used in the content after import line"""
 lines = content.split("\n")

 # Look for usage after the import line
 for line_num, line in enumerate(lines[import_line:], import_line + 1):
 # Skip comments and strings (basic check)
 if line.strip().startswith("#"):
 continue

 # Check for usage patterns
 patterns = [
 rf"\b{re.escape(name)}\b", # Direct usage
 rf"{re.escape(name)}\.", # Attribute access
 rf"{re.escape(name)}\(", # Function call
 rf"{re.escape(name)}\[", # Indexing
 ]

 for pattern in patterns:
 if re.search(pattern, line):
 return True

 return False

 def find_duplicate_imports(self, file_data: Dict[str, Any]) -> List[Dict[str, Any]]:
 """Find duplicate imports in a file"""
 imports = file_data["imports"]
 seen = set()
 duplicates = []

 for imp in imports:
 if imp["type"] == "import":
 key = (imp["module"], imp["alias"])
 else:
 key = (imp["module"], imp["name"], imp["alias"])

 if key in seen:
 duplicates.append(
 {
 "line": imp["line"],
 "type": "duplicate_import",
 "import_info": imp,
 }
 )
 else:
 seen.add(key)

 return duplicates

 def check_import_existence(
 self, file_path: Path, file_data: Dict[str, Any]
 ) -> List[Dict[str, Any]]:
 """Check if imported modules exist"""
 nonexistent = []
 imports = file_data["imports"]

 for imp in imports:
 module = imp["module"]
 if module and not self._can_import_module(module, file_path):
 nonexistent.append(
 {
 "file": str(file_path),
 "line": imp["line"],
 "type": "nonexistent_import",
 "module": module,
 "import_info": imp,
 }
 )

 return nonexistent

 def _can_import_module(self, module: str, file_path: Path) -> bool:
 """Check if a module can be imported"""
 try:
 # Add the project root to Python path
 project_root = str(self.base_path)
 if project_root not in sys.path:
 sys.path.insert(0, project_root)

 # Try to import the module
 __import__(module)
 return True
 except ImportError:
 # Check if it's a relative import that might be valid
 if module.startswith("."):
 return True # Skip relative imports for now

 # Check if it's a known third-party module
 try:
 result = subprocess.run(
 ["python", "-c", f"import {module}"],
 capture_output = True,
 text = True,
 timeout = 5,
 )
 return result.returncode == 0
 except (subprocess.TimeoutExpired, Exception):
 return False
 except Exception:
 return False

 def analyze_file(self, file_path: Path) -> Dict[str, Any]:
 """Analyze a single file for all import issues"""
 file_data = self.extract_imports_from_file(file_path)

 analysis = {
 "file": str(file_path),
 "unused_imports": self.find_unused_imports(file_path, file_data),
 "commented_imports": file_data["commented_imports"],
 "duplicate_imports": self.find_duplicate_imports(file_data),
 "nonexistent_imports": self.check_import_existence(file_path, file_data),
 "total_imports": len(file_data["imports"]),
 }

 return analysis

 def analyze_all_files(self) -> Dict[str, Any]:
 """Analyze all production files"""
 files = self.find_production_files()
 print(f"Found {len(files)} production Python files to analyze")

 total_issues = 0

 for i, file_path in enumerate(files, 1):
 print(f"Analyzing {i}/{len(files)}: {file_path}")

 analysis = self.analyze_file(file_path)

 # Collect results
 self.results["unused_imports"].extend(analysis["unused_imports"])
 self.results["commented_imports"].extend(
 [{**ci, "file": str(file_path)} for ci in analysis["commented_imports"]]
 )
 self.results["duplicate_imports"].extend(
 [{**di, "file": str(file_path)} for di in analysis["duplicate_imports"]]
 )
 self.results["nonexistent_imports"].extend(analysis["nonexistent_imports"])

 file_issues = (
 len(analysis["unused_imports"])
 + len(analysis["commented_imports"])
 + len(analysis["duplicate_imports"])
 + len(analysis["nonexistent_imports"])
 )
 total_issues += file_issues

 # Calculate statistics
 self.results["statistics"] = {
 "total_files_analyzed": len(files),
 "total_unused_imports": len(self.results["unused_imports"]),
 "total_commented_imports": len(self.results["commented_imports"]),
 "total_duplicate_imports": len(self.results["duplicate_imports"]),
 "total_nonexistent_imports": len(self.results["nonexistent_imports"]),
 "total_issues": total_issues,
 }

 return self.results

 def generate_report(self) -> str:
 """Generate a comprehensive report"""
 report = []
 report.append("=" * 80)
 report.append("COMPREHENSIVE DEAD IMPORT ANALYSIS REPORT")
 report.append("=" * 80)

 stats = self.results["statistics"]
 report.append(f"Files analyzed: {stats['total_files_analyzed']}")
 report.append(f"Total issues found: {stats['total_issues']}")
 report.append("")

 # Unused imports
 if self.results["unused_imports"]:
 report.append("UNUSED IMPORTS:")
 report.append("-" * 40)
 for imp in self.results["unused_imports"]:
 report.append(
 f" {imp['file']}:{imp['line']} - {imp['import_statement']}"
 )
 report.append(
 f"Total unused imports: {len(self.results['unused_imports'])}"
 )
 report.append("")

 # Commented imports
 if self.results["commented_imports"]:
 report.append("COMMENTED IMPORTS (should be removed):")
 report.append("-" * 40)
 for imp in self.results["commented_imports"]:
 report.append(f" {imp['file']}:{imp['line']} - {imp['original']}")
 report.append(
 f"Total commented imports: {len(self.results['commented_imports'])}"
 )
 report.append("")

 # Duplicate imports
 if self.results["duplicate_imports"]:
 report.append("DUPLICATE IMPORTS:")
 report.append("-" * 40)
 for imp in self.results["duplicate_imports"]:
 report.append(f" {imp['file']}:{imp['line']} - {imp['import_info']}")
 report.append(
 f"Total duplicate imports: {len(self.results['duplicate_imports'])}"
 )
 report.append("")

 # Nonexistent imports
 if self.results["nonexistent_imports"]:
 report.append("NONEXISTENT/PROBLEMATIC IMPORTS:")
 report.append("-" * 40)
 for imp in self.results["nonexistent_imports"]:
 report.append(f" {imp['file']}:{imp['line']} - {imp['module']}")
 report.append(
 f"Total nonexistent imports: {len(self.results['nonexistent_imports'])}"
 )
 report.append("")

 return "\n".join(report)


def main():
 """Main function"""
 base_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"

 analyzer = ImportAnalyzer(base_path)
 results = analyzer.analyze_all_files()

 # Generate report
 report = analyzer.generate_report()
 print(report)

 # Save detailed results
 with open(f"{base_path}/dead_imports_analysis.json", "w") as f:
 json.dump(results, f, indent = 2)

 # Save report
 with open(f"{base_path}/dead_imports_report.txt", "w") as f:
 f.write(report)

 print("\nDetailed results saved to dead_imports_analysis.json")
 print("Report saved to dead_imports_report.txt")


if __name__ == "__main__":
 main()
