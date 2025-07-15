#!/usr/bin/env python3
"""
Analyze import errors and categorize them by severity and type
"""

import json
from collections import defaultdict
from pathlib import Path


def analyze_import_errors():
 """Analyze import errors and categorize them"""

 # Load the validation results
 with open("import_validation_results.json", "r") as f:
 results = json.load(f)

 errors = results.get("errors", [])

 # Categorize errors
 categories = {
 "missing_modules": [],
 "missing_attributes": [],
 "syntax_errors": [],
 "circular_imports": [],
 "config_errors": [],
 "third_party_missing": [],
 }

 # Track missing modules
 missing_modules = defaultdict(list)
 third_party_modules = {
 "celery",
 "orjson",
 "pybreaker",
 "dependency_injector",
 "boto3",
 "botocore",
 }

 for error in errors:
 error_type = error.get("type", "")
 file_path = error.get("file", "")
 module = error.get("module", "")

 if error_type == "syntax_error":
 categories["syntax_errors"].append(error)
 elif error_type == "missing_attribute":
 categories["missing_attributes"].append(error)
 elif error_type == "import_error":
 if any(tp in module for tp in third_party_modules):
 categories["third_party_missing"].append(error)
 else:
 categories["missing_modules"].append(error)
 missing_modules[module].append(file_path)
 elif error_type == "validation_error":
 categories["config_errors"].append(error)

 # Generate summary report
 report = []
 report.append("=" * 80)
 report.append("IMPORT ERROR ANALYSIS SUMMARY")
 report.append("=" * 80)
 report.append("")

 # Overall statistics
 report.append(f"📊 OVERALL STATISTICS")
 report.append(f"Total files analyzed: {results['total_files']}")
 report.append(f"Total imports: {results['total_imports']}")
 report.append(f"Valid imports: {results['valid_imports']}")
 report.append(f"Total errors: {len(errors)}")
 report.append(
 f"Success rate: {(results['valid_imports'] / results['total_imports'] * 100):.1f}%"
 )
 report.append("")

 # Error categories
 report.append("📈 ERROR CATEGORIES")
 report.append("-" * 40)
 report.append(f"Missing modules: {len(categories['missing_modules'])}")
 report.append(f"Missing attributes: {len(categories['missing_attributes'])}")
 report.append(f"Syntax errors: {len(categories['syntax_errors'])}")
 report.append(f"Configuration errors: {len(categories['config_errors'])}")
 report.append(f"Third-party missing: {len(categories['third_party_missing'])}")
 report.append("")

 # Most critical issues
 report.append("🔥 MOST CRITICAL ISSUES")
 report.append("-" * 40)

 # Syntax errors (prevent execution)
 if categories["syntax_errors"]:
 report.append("1. SYNTAX ERRORS (CRITICAL - PREVENTS EXECUTION)")
 for error in categories["syntax_errors"]:
 report.append(f" 📄 {Path(error['file']).name}:{error['line']}")
 report.append(f" ❌ {error['error']}")
 report.append("")

 # Missing third-party modules
 if categories["third_party_missing"]:
 report.append("2. MISSING THIRD-PARTY MODULES")
 third_party_counts = defaultdict(int)
 for error in categories["third_party_missing"]:
 module = error.get("module", "")
 for tp in third_party_modules:
 if tp in module:
 third_party_counts[tp] += 1

 for module, count in sorted(
 third_party_counts.items(), key = lambda x: x[1], reverse = True
 ):
 report.append(f" 📦 {module}: {count} import failures")
 report.append("")

 # Most frequently missing internal modules
 if categories["missing_modules"]:
 report.append("3. MISSING INTERNAL MODULES")
 sorted_modules = sorted(
 missing_modules.items(), key = lambda x: len(x[1]), reverse = True
 )
 for module, files in sorted_modules[:10]: # Top 10
 report.append(f" 📁 {module}: {len(files)} files affected")
 report.append("")

 # Missing attributes
 if categories["missing_attributes"]:
 report.append("4. MISSING ATTRIBUTES")
 attr_counts = defaultdict(int)
 for error in categories["missing_attributes"]:
 module = error.get("module", "")
 attr = error.get("attribute", "")
 attr_counts[f"{module}.{attr}"] += 1

 for attr, count in sorted(
 attr_counts.items(), key = lambda x: x[1], reverse = True
 )[:10]:
 report.append(f" 🔗 {attr}: {count} failures")
 report.append("")

 # Detailed breakdown
 report.append("📋 DETAILED BREAKDOWN")
 report.append("-" * 40)

 # Missing third-party modules detail
 if categories["third_party_missing"]:
 report.append("MISSING THIRD-PARTY MODULES (Add to requirements.txt):")
 for module in sorted(third_party_modules):
 count = sum(
 1
 for error in categories["third_party_missing"]
 if module in error.get("module", "")
 )
 if count > 0:
 report.append(f" - {module} ({count} import failures)")
 report.append("")

 # Most problematic files
 report.append("MOST PROBLEMATIC FILES:")
 file_error_counts = defaultdict(int)
 for error in errors:
 file_path = error.get("file", "")
 file_error_counts[file_path] += 1

 sorted_files = sorted(file_error_counts.items(), key = lambda x: x[1], reverse = True)
 for file_path, count in sorted_files[:15]: # Top 15
 report.append(f" 📄 {Path(file_path).name}: {count} errors")
 report.append("")

 # Recommendations
 report.append("🎯 RECOMMENDATIONS")
 report.append("-" * 40)

 if categories["syntax_errors"]:
 report.append("1. Fix syntax errors first (prevents execution)")
 for error in categories["syntax_errors"]:
 report.append(f" - Fix {Path(error['file']).name}:{error['line']}")

 if categories["third_party_missing"]:
 report.append("2. Add missing third-party dependencies to requirements.txt:")
 for module in sorted(third_party_modules):
 count = sum(
 1
 for error in categories["third_party_missing"]
 if module in error.get("module", "")
 )
 if count > 0:
 report.append(f" - {module}")

 if categories["missing_modules"]:
 report.append("3. Create or fix missing internal modules:")
 for module, files in sorted_modules[:5]: # Top 5
 report.append(f" - {module}")

 if categories["missing_attributes"]:
 report.append("4. Fix missing attributes in modules:")
 for error in categories["missing_attributes"][:5]: # Top 5
 module = error.get("module", "")
 attr = error.get("attribute", "")
 report.append(f" - Add {attr} to {module}")

 report.append("")

 # Conclusion
 report.append("🏁 CONCLUSION")
 report.append("-" * 40)
 if len(errors) == 0:
 report.append(
 "✅ All imports are valid! The code should run without import errors."
 )
 else:
 report.append(
 "❌ CRITICAL: The codebase has import errors that prevent execution."
 )
 report.append(f" - {len(categories['syntax_errors'])} syntax errors")
 report.append(
 f" - {len(categories['third_party_missing'])} third-party module issues"
 )
 report.append(
 f" - {len(categories['missing_modules'])} missing internal modules"
 )
 report.append(
 f" - {len(categories['missing_attributes'])} missing attributes"
 )
 report.append("")
 report.append("The code CANNOT run in its current state.")

 return "\n".join(report)


if __name__ == "__main__":
 report = analyze_import_errors()
 print(report)

 # Save report
 with open("import_error_analysis.txt", "w") as f:
 f.write(report)
 print("\nReport saved to import_error_analysis.txt")
