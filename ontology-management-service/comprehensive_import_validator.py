#!/usr/bin/env python3
"""
Ultra-thorough import validation script for ontology-management-service
This script validates ALL imports in production Python files to ensure they work without errors.
"""

import ast
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class ImportValidator:
 def __init__(self, root_path: str):
 self.root_path = Path(root_path)
 self.errors: List[Dict] = []
 self.warnings: List[Dict] = []
 self.circular_imports: List[Dict] = []
 self.missing_modules: Set[str] = set()
 self.analyzed_files: Set[str] = set()
 self.import_graph: Dict[str, Set[str]] = {}
 self.production_files: List[Path] = []

 def find_production_files(self) -> List[Path]:
 """Find all Python files in production code (excluding tests, scripts, examples, migrations)"""
 exclude_patterns = [
 "test",
 "tests",
 "testing",
 "examples",
 "migrations",
 "scripts",
 "venv",
 "__pycache__",
 ".pytest_cache",
 ".git",
 "node_modules",
 ".tox",
 ".venv",
 "build",
 "dist",
 ".egg-info",
 ]

 production_files = []
 for py_file in self.root_path.rglob("*.py"):
 # Skip if any part of the path contains excluded patterns
 if any(pattern in str(py_file) for pattern in exclude_patterns):
 continue
 production_files.append(py_file)

 self.production_files = production_files
 return production_files

 def extract_imports_from_file(self, file_path: Path) -> List[Dict]:
 """Extract all import statements from a Python file using AST"""
 try:
 with open(file_path, "r", encoding = "utf-8") as f:
 content = f.read()

 tree = ast.parse(content, filename = str(file_path))
 imports = []

 for node in ast.walk(tree):
 if isinstance(node, ast.Import):
 for alias in node.names:
 imports.append(
 {
 "type": "import",
 "module": alias.name,
 "name": alias.asname or alias.name,
 "line": node.lineno,
 "file": str(file_path),
 }
 )
 elif isinstance(node, ast.ImportFrom):
 module = node.module or ""
 level = node.level
 for alias in node.names:
 imports.append(
 {
 "type": "from_import",
 "module": module,
 "name": alias.name,
 "asname": alias.asname,
 "level": level,
 "line": node.lineno,
 "file": str(file_path),
 }
 )

 return imports
 except SyntaxError as e:
 self.errors.append(
 {
 "type": "syntax_error",
 "file": str(file_path),
 "error": str(e),
 "line": e.lineno,
 }
 )
 return []
 except Exception as e:
 self.errors.append(
 {"type": "parse_error", "file": str(file_path), "error": str(e)}
 )
 return []

 def validate_import(self, import_info: Dict) -> bool:
 """Validate if an import can be resolved"""
 try:
 if import_info["type"] == "import":
 # Try to import the module
 importlib.import_module(import_info["module"])
 return True
 elif import_info["type"] == "from_import":
 module_name = import_info["module"]

 # Handle relative imports
 if import_info["level"] > 0:
 # Get the package name from the file path
 file_path = Path(import_info["file"])
 relative_path = file_path.relative_to(self.root_path)
 package_parts = relative_path.parts[:-1] # Remove filename

 # Calculate the actual module name for relative imports
 if import_info["level"] == 1:
 # Same level import
 if package_parts:
 full_module = ".".join(package_parts)
 if module_name:
 full_module = f"{full_module}.{module_name}"
 else:
 full_module = module_name or ""
 else:
 # Parent level imports
 if len(package_parts) >= import_info["level"] - 1:
 parent_parts = package_parts[: -(import_info["level"] - 1)]
 if parent_parts:
 full_module = ".".join(parent_parts)
 if module_name:
 full_module = f"{full_module}.{module_name}"
 else:
 full_module = module_name or ""
 else:
 # Invalid relative import
 return False
 else:
 full_module = module_name

 if full_module:
 # Try to import the module
 module = importlib.import_module(full_module)

 # Check if the imported name exists in the module
 if import_info["name"] != "*":
 if not hasattr(module, import_info["name"]):
 self.errors.append(
 {
 "type": "missing_attribute",
 "file": import_info["file"],
 "line": import_info["line"],
 "module": full_module,
 "attribute": import_info["name"],
 "error": f"Module '{full_module}' has no attribute '{import_info['name']}'",
 }
 )
 return False

 return True
 except ImportError as e:
 self.errors.append(
 {
 "type": "import_error",
 "file": import_info["file"],
 "line": import_info["line"],
 "module": import_info.get("module", ""),
 "error": str(e),
 }
 )
 return False
 except Exception as e:
 self.errors.append(
 {
 "type": "validation_error",
 "file": import_info["file"],
 "line": import_info["line"],
 "error": str(e),
 }
 )
 return False

 def check_circular_imports(self):
 """Check for circular imports using the import graph"""

 def dfs(node, visited, rec_stack, path):
 visited.add(node)
 rec_stack.add(node)

 if node in self.import_graph:
 for neighbor in self.import_graph[node]:
 if neighbor not in visited:
 cycle = dfs(neighbor, visited, rec_stack, path + [neighbor])
 if cycle:
 return cycle
 elif neighbor in rec_stack:
 # Found a cycle
 cycle_start = path.index(neighbor)
 return path[cycle_start:] + [neighbor]

 rec_stack.remove(node)
 return None

 visited = set()
 for node in self.import_graph:
 if node not in visited:
 cycle = dfs(node, visited, set(), [node])
 if cycle:
 self.circular_imports.append(
 {
 "type": "circular_import",
 "cycle": cycle,
 "description": f"Circular import detected: {' -> '.join(cycle)}",
 }
 )

 def validate_syntax(self, file_path: Path) -> bool:
 """Validate Python syntax of a file"""
 try:
 with open(file_path, "r", encoding = "utf-8") as f:
 content = f.read()
 compile(content, str(file_path), "exec")
 return True
 except SyntaxError as e:
 self.errors.append(
 {
 "type": "syntax_error",
 "file": str(file_path),
 "line": e.lineno,
 "error": str(e),
 }
 )
 return False
 except Exception as e:
 self.errors.append(
 {"type": "compilation_error", "file": str(file_path), "error": str(e)}
 )
 return False

 def check_python_execution(self, file_path: Path) -> bool:
 """Check if Python file can be executed without import errors"""
 try:
 # Use subprocess to run python -m py_compile on the file
 result = subprocess.run(
 [sys.executable, "-m", "py_compile", str(file_path)],
 capture_output = True,
 text = True,
 timeout = 30,
 )

 if result.returncode != 0:
 self.errors.append(
 {
 "type": "compilation_error",
 "file": str(file_path),
 "error": result.stderr.strip(),
 }
 )
 return False
 return True
 except subprocess.TimeoutExpired:
 self.warnings.append(
 {
 "type": "compilation_timeout",
 "file": str(file_path),
 "warning": "Compilation check timed out",
 }
 )
 return False
 except Exception as e:
 self.errors.append(
 {
 "type": "execution_check_error",
 "file": str(file_path),
 "error": str(e),
 }
 )
 return False

 def run_validation(self) -> Dict:
 """Run comprehensive import validation"""
 print("🔍 Starting ultra-thorough import validation...")

 # Find production files
 production_files = self.find_production_files()
 print(f"📁 Found {len(production_files)} production Python files")

 # Add project root to Python path
 sys.path.insert(0, str(self.root_path))

 all_imports = []

 # Step 1: Extract imports from all files
 print("📋 Extracting imports from all files...")
 for file_path in production_files:
 print(f" 📄 Processing {file_path.relative_to(self.root_path)}")

 # Check syntax first
 if not self.validate_syntax(file_path):
 continue

 # Check compilation
 if not self.check_python_execution(file_path):
 continue

 # Extract imports
 imports = self.extract_imports_from_file(file_path)
 all_imports.extend(imports)

 # Build import graph for circular import detection
 rel_path = str(file_path.relative_to(self.root_path))
 self.import_graph[rel_path] = set()

 for imp in imports:
 if imp["type"] == "import":
 self.import_graph[rel_path].add(imp["module"])
 elif imp["type"] == "from_import" and imp["module"]:
 self.import_graph[rel_path].add(imp["module"])

 print(f"🔍 Found {len(all_imports)} total imports")

 # Step 2: Validate each import
 print("✅ Validating imports...")
 valid_imports = 0
 for import_info in all_imports:
 if self.validate_import(import_info):
 valid_imports += 1
 else:
 print(
 f" ❌ {import_info['file']}:{import_info['line']} - {import_info}"
 )

 print(f"✅ {valid_imports}/{len(all_imports)} imports validated successfully")

 # Step 3: Check for circular imports
 print("🔄 Checking for circular imports...")
 self.check_circular_imports()

 # Step 4: Compile results
 results = {
 "total_files": len(production_files),
 "total_imports": len(all_imports),
 "valid_imports": valid_imports,
 "errors": self.errors,
 "warnings": self.warnings,
 "circular_imports": self.circular_imports,
 "missing_modules": list(self.missing_modules),
 }

 return results

 def generate_report(self, results: Dict) -> str:
 """Generate a comprehensive report"""
 report = []
 report.append("=" * 80)
 report.append("ULTRA-THOROUGH PYTHON IMPORT VALIDATION REPORT")
 report.append("=" * 80)
 report.append("")

 # Summary
 report.append("📊 SUMMARY")
 report.append("-" * 40)
 report.append(f"Total files analyzed: {results['total_files']}")
 report.append(f"Total imports found: {results['total_imports']}")
 report.append(f"Valid imports: {results['valid_imports']}")
 report.append(f"Import errors: {len(results['errors'])}")
 report.append(f"Warnings: {len(results['warnings'])}")
 report.append(f"Circular imports: {len(results['circular_imports'])}")
 report.append("")

 # Import Errors
 if results["errors"]:
 report.append("❌ IMPORT ERRORS")
 report.append("-" * 40)
 for error in results["errors"]:
 report.append(f"File: {error['file']}")
 if "line" in error:
 report.append(f"Line: {error['line']}")
 report.append(f"Type: {error['type']}")
 report.append(f"Error: {error['error']}")
 report.append("")

 # Warnings
 if results["warnings"]:
 report.append("⚠️ WARNINGS")
 report.append("-" * 40)
 for warning in results["warnings"]:
 report.append(f"File: {warning['file']}")
 report.append(f"Warning: {warning['warning']}")
 report.append("")

 # Circular Imports
 if results["circular_imports"]:
 report.append("🔄 CIRCULAR IMPORTS")
 report.append("-" * 40)
 for circ in results["circular_imports"]:
 report.append(f"Description: {circ['description']}")
 report.append(f"Cycle: {' -> '.join(circ['cycle'])}")
 report.append("")

 # Missing Modules
 if results["missing_modules"]:
 report.append("📦 MISSING MODULES")
 report.append("-" * 40)
 for module in results["missing_modules"]:
 report.append(f"- {module}")
 report.append("")

 # Conclusion
 report.append("🎯 CONCLUSION")
 report.append("-" * 40)
 if not results["errors"] and not results["circular_imports"]:
 report.append(
 "✅ ALL IMPORTS ARE VALID! Code should run without import errors."
 )
 else:
 report.append("❌ IMPORT ERRORS DETECTED! Code will fail to run.")
 report.append(
 "Fix the errors above to ensure the code can execute properly."
 )

 return "\n".join(report)


def main():
 """Main function to run the validation"""
 root_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"

 validator = ImportValidator(root_path)
 results = validator.run_validation()

 # Generate and print report
 report = validator.generate_report(results)
 print("\n" + report)

 # Save results to file
 with open(f"{root_path}/import_validation_results.json", "w") as f:
 json.dump(results, f, indent = 2)

 with open(f"{root_path}/import_validation_report.txt", "w") as f:
 f.write(report)

 print(f"\n📁 Results saved to:")
 print(f" - import_validation_results.json")
 print(f" - import_validation_report.txt")

 # Exit with error code if there are issues
 if results["errors"] or results["circular_imports"]:
 sys.exit(1)
 else:
 sys.exit(0)


if __name__ == "__main__":
 main()
