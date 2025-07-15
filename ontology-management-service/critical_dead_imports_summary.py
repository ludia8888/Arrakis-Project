#!/usr/bin/env python3
"""
Critical Dead Imports Summary
Creates a focused summary of the most critical dead imports to fix for production readiness
"""

import json
from pathlib import Path


def analyze_critical_issues():
 """Analyze the dead imports report and create focused summaries"""

 # Load the analysis results
 with open("dead_imports_analysis.json", "r") as f:
 results = json.load(f)

 print("=" * 80)
 print("CRITICAL DEAD IMPORTS ANALYSIS - PRODUCTION READINESS")
 print("=" * 80)

 stats = results["statistics"]
 print("📊 ANALYSIS SUMMARY:")
 print(f" • Files analyzed: {stats['total_files_analyzed']}")
 print(f" • Unused imports: {stats['total_unused_imports']}")
 print(f" • Commented imports: {stats['total_commented_imports']}")
 print(f" • Duplicate imports: {stats['total_duplicate_imports']}")
 print(f" • Non-existent imports: {stats['total_nonexistent_imports']}")
 print(f" • TOTAL ISSUES: {stats['total_issues']}")
 print()

 # Group by file for easier cleanup
 file_issues = {}

 # Process unused imports
 for imp in results["unused_imports"]:
 file_path = imp["file"]
 if file_path not in file_issues:
 file_issues[file_path] = {
 "unused": [],
 "commented": [],
 "duplicate": [],
 "nonexistent": [],
 }
 file_issues[file_path]["unused"].append(imp)

 # Process commented imports
 for imp in results["commented_imports"]:
 file_path = imp["file"]
 if file_path not in file_issues:
 file_issues[file_path] = {
 "unused": [],
 "commented": [],
 "duplicate": [],
 "nonexistent": [],
 }
 file_issues[file_path]["commented"].append(imp)

 # Process duplicate imports
 for imp in results["duplicate_imports"]:
 file_path = imp["file"]
 if file_path not in file_issues:
 file_issues[file_path] = {
 "unused": [],
 "commented": [],
 "duplicate": [],
 "nonexistent": [],
 }
 file_issues[file_path]["duplicate"].append(imp)

 # Process non-existent imports
 for imp in results["nonexistent_imports"]:
 file_path = imp["file"]
 if file_path not in file_issues:
 file_issues[file_path] = {
 "unused": [],
 "commented": [],
 "duplicate": [],
 "nonexistent": [],
 }
 file_issues[file_path]["nonexistent"].append(imp)

 # Find files with the most issues
 file_issue_counts = {
 file: (
 len(issues["unused"])
 + len(issues["commented"])
 + len(issues["duplicate"])
 + len(issues["nonexistent"])
 )
 for file, issues in file_issues.items()
 }

 top_problem_files = sorted(
 file_issue_counts.items(), key = lambda x: x[1], reverse = True
 )[:20]

 print("🚨 TOP 20 FILES WITH MOST IMPORT ISSUES:")
 print("-" * 60)
 for file_path, issue_count in top_problem_files:
 # Get just the filename for display
 filename = Path(file_path).name
 directory = "/".join(Path(file_path).parts[-3:-1])
 print(f" {issue_count:2d} issues • {directory}/{filename}")
 print()

 # Show critical patterns
 print("🔍 CRITICAL PATTERNS TO FIX:")
 print("-" * 40)

 # Common unused imports
 unused_modules = {}
 for imp in results["unused_imports"]:
 module = imp.get("module", "unknown")
 if module not in unused_modules:
 unused_modules[module] = 0
 unused_modules[module] += 1

 top_unused = sorted(unused_modules.items(), key = lambda x: x[1], reverse = True)[:10]
 print(" Most commonly unused imports:")
 for module, count in top_unused:
 print(f" • {module}: {count} occurrences")
 print()

 # Show some example fixes
 print("🛠️ EXAMPLE FIXES NEEDED:")
 print("-" * 30)

 # Show first 10 unused imports as examples
 for i, imp in enumerate(results["unused_imports"][:10]):
 filename = Path(imp["file"]).name
 print(f" {i+1}. {filename}:{imp['line']} - Remove: {imp['import_statement']}")

 if len(results["unused_imports"]) > 10:
 print(f" ... and {len(results['unused_imports']) - 10} more unused imports")
 print()

 # Show commented imports that need removal
 if results["commented_imports"]:
 print("📝 COMMENTED IMPORTS TO REMOVE:")
 print("-" * 35)
 for imp in results["commented_imports"]:
 filename = Path(imp["file"]).name
 print(f" • {filename}:{imp['line']} - {imp['original']}")
 print()

 # Show duplicate imports
 if results["duplicate_imports"]:
 print("🔄 DUPLICATE IMPORTS TO REMOVE:")
 print("-" * 32)
 for imp in results["duplicate_imports"][:10]:
 filename = Path(imp["file"]).name
 print(f" • {filename}:{imp['line']} - Duplicate import")
 if len(results["duplicate_imports"]) > 10:
 print(
 f" ... and {len(results['duplicate_imports']) - 10} more duplicates"
 )
 print()

 # Priority cleanup recommendations
 print("📋 CLEANUP RECOMMENDATIONS:")
 print("-" * 30)
 print("1. 🥇 HIGH PRIORITY: Fix unused imports in core/ modules")
 print("2. 🥈 MEDIUM PRIORITY: Remove commented imports")
 print("3. 🥉 LOW PRIORITY: Fix duplicate imports")
 print("4. 🔧 INVESTIGATE: Non-existent imports (may be import path issues)")
 print()

 print("💡 AUTOMATION SUGGESTIONS:")
 print("-" * 25)
 print("• Use autoflake to remove unused imports: pip install autoflake")
 print("• Use isort to organize imports: pip install isort")
 print("• Use flake8 to detect import issues: pip install flake8")
 print()

 # Generate a focused cleanup script
 cleanup_script = []
 cleanup_script.append("#!/bin/bash")
 cleanup_script.append("# Automated import cleanup script")
 cleanup_script.append("")
 cleanup_script.append("echo 'Starting import cleanup...'")
 cleanup_script.append("")
 cleanup_script.append("# Remove unused imports")
 cleanup_script.append(
 "autoflake --remove-all-unused-imports --recursive --in-place \\"
 )
 cleanup_script.append(" --exclude = tests/,scripts/,examples/,migrations/ \\")
 cleanup_script.append(" .")
 cleanup_script.append("")
 cleanup_script.append("# Sort imports")
 cleanup_script.append("isort --profile black --line-length 88 \\")
 cleanup_script.append(
 " --skip tests/ --skip scripts/ --skip examples/ --skip migrations/ \\"
 )
 cleanup_script.append(" .")
 cleanup_script.append("")
 cleanup_script.append("echo 'Import cleanup completed!'")

 with open("cleanup_imports.sh", "w") as f:
 f.write("\n".join(cleanup_script))

 print("✅ Generated cleanup_imports.sh script for automated fixes")
 print("✅ Run: chmod +x cleanup_imports.sh && ./cleanup_imports.sh")
 print()

 return file_issues


if __name__ == "__main__":
 analyze_critical_issues()
