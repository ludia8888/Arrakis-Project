#!/usr/bin/env python3
"""
Manual Cleanup Guide for Dead Imports
Provides specific files and line numbers for manual cleanup
"""

import json
from collections import defaultdict
from pathlib import Path


def generate_manual_cleanup_guide():
 """Generate a detailed manual cleanup guide"""

 # Load the analysis results
 with open("dead_imports_analysis.json", "r") as f:
 results = json.load(f)

 print("=" * 80)
 print("MANUAL CLEANUP GUIDE - DEAD IMPORTS")
 print("=" * 80)
 print()

 # Group by file and sort by importance
 file_issues = defaultdict(lambda: {"unused": [], "commented": [], "duplicate": []})

 for imp in results["unused_imports"]:
 file_path = imp["file"]
 file_issues[file_path]["unused"].append(imp)

 for imp in results["commented_imports"]:
 file_path = imp["file"]
 file_issues[file_path]["commented"].append(imp)

 for imp in results["duplicate_imports"]:
 file_path = imp["file"]
 file_issues[file_path]["duplicate"].append(imp)

 # Sort files by priority (core/ first, then api/, then others)
 def get_priority(file_path):
 if "/core/" in file_path:
 return 1
 elif "/api/" in file_path:
 return 2
 elif "/bootstrap/" in file_path:
 return 3
 elif "/middleware/" in file_path:
 return 4
 else:
 return 5

 sorted_files = sorted(file_issues.keys(), key = get_priority)

 print("🎯 PRIORITY-ORDERED FILE-BY-FILE CLEANUP GUIDE")
 print("=" * 50)

 for file_path in sorted_files:
 issues = file_issues[file_path]
 total_issues = (
 len(issues["unused"]) + len(issues["commented"]) + len(issues["duplicate"])
 )

 if total_issues == 0:
 continue

 # Get relative path for display
 rel_path = file_path.replace(
 "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/", ""
 )

 print(f"\n📁 {rel_path}")
 print(f" {total_issues} issues total")
 print("-" * 60)

 # Show unused imports
 if issues["unused"]:
 print(f" 🗑️ UNUSED IMPORTS ({len(issues['unused'])} items):")
 for imp in sorted(issues["unused"], key = lambda x: x["line"]):
 print(f" Line {imp['line']:3d}: {imp['import_statement']}")

 # Show commented imports
 if issues["commented"]:
 print(f" 💬 COMMENTED IMPORTS ({len(issues['commented'])} items):")
 for imp in sorted(issues["commented"], key = lambda x: x["line"]):
 print(f" Line {imp['line']:3d}: {imp['original']}")

 # Show duplicate imports
 if issues["duplicate"]:
 print(f" 🔄 DUPLICATE IMPORTS ({len(issues['duplicate'])} items):")
 for imp in sorted(issues["duplicate"], key = lambda x: x["line"]):
 print(f" Line {imp['line']:3d}: Duplicate import")

 # Generate quick reference for most common issues
 print("\n\n" + "=" * 80)
 print("QUICK REFERENCE - MOST COMMON PATTERNS")
 print("=" * 80)

 # Most common unused imports
 unused_counts = defaultdict(int)
 for imp in results["unused_imports"]:
 if imp["type"] == "unused_from_import":
 unused_counts[f"from {imp['module']} import {imp['name']}"] += 1
 else:
 unused_counts[f"import {imp['module']}"] += 1

 print("\n🔥 TOP 20 MOST COMMON UNUSED IMPORTS:")
 print("-" * 50)
 for import_stmt, count in sorted(
 unused_counts.items(), key = lambda x: x[1], reverse = True
 )[:20]:
 print(f" {count:2d}x: {import_stmt}")

 # Critical core module issues
 print("\n\n🚨 CRITICAL CORE MODULE ISSUES:")
 print("-" * 40)

 core_files = [f for f in sorted_files if "/core/" in f]
 core_issue_count = 0

 for file_path in core_files[:10]: # Show top 10 core files
 issues = file_issues[file_path]
 total = (
 len(issues["unused"]) + len(issues["commented"]) + len(issues["duplicate"])
 )
 if total > 0:
 rel_path = file_path.replace(
 "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/",
 "",
 )
 print(f" {total:2d} issues: {rel_path}")
 core_issue_count += total

 print(f"\n Total core module issues: {core_issue_count}")

 # Generate cleanup commands
 print("\n\n🛠️ AUTOMATED CLEANUP COMMANDS:")
 print("-" * 35)
 print("1. Install tools:")
 print(" pip install autoflake isort black flake8")
 print()
 print("2. Remove unused imports:")
 print(" autoflake --remove-all-unused-imports --recursive --in-place \\")
 print(" --exclude = tests/,scripts/,examples/,migrations/ .")
 print()
 print("3. Sort imports:")
 print(" isort --profile black --line-length 88 \\")
 print(" --skip tests/ --skip scripts/ --skip examples/ --skip migrations/ .")
 print()
 print("4. Format code:")
 print(
 " black --line-length 88 --exclude '/(tests|scripts|examples|migrations)/' ."
 )
 print()
 print("5. Check for remaining issues:")
 print(
 " flake8 --select = F401,F811 --exclude = tests/,scripts/,examples/,migrations/ ."
 )

 # Save individual file cleanup tasks
 print("\n\n💾 SAVING INDIVIDUAL FILE TASKS...")

 cleanup_tasks = []
 for file_path in sorted_files:
 issues = file_issues[file_path]
 total_issues = (
 len(issues["unused"]) + len(issues["commented"]) + len(issues["duplicate"])
 )

 if total_issues > 0:
 rel_path = file_path.replace(
 "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/",
 "",
 )

 task = {
 "file": rel_path,
 "absolute_path": file_path,
 "total_issues": total_issues,
 "unused_count": len(issues["unused"]),
 "commented_count": len(issues["commented"]),
 "duplicate_count": len(issues["duplicate"]),
 "unused_imports": issues["unused"],
 "commented_imports": issues["commented"],
 "duplicate_imports": issues["duplicate"],
 }
 cleanup_tasks.append(task)

 with open("manual_cleanup_tasks.json", "w") as f:
 json.dump(cleanup_tasks, f, indent = 2)

 print(
 f"✅ Saved {len(cleanup_tasks)} file cleanup tasks to manual_cleanup_tasks.json"
 )
 print()

 # Summary
 print("📊 CLEANUP SUMMARY:")
 print("-" * 20)
 print(f"Files needing cleanup: {len(cleanup_tasks)}")
 print(f"Total unused imports: {len(results['unused_imports'])}")
 print(f"Total commented imports: {len(results['commented_imports'])}")
 print(f"Total duplicate imports: {len(results['duplicate_imports'])}")
 print(
 f"Total issues: {len(results['unused_imports']) + len(results['commented_imports']) + len(results['duplicate_imports'])}"
 )
 print()
 print("🎯 RECOMMENDED APPROACH:")
 print("1. Start with core/ modules (highest priority)")
 print("2. Use automated tools for bulk cleanup")
 print("3. Manually review commented imports before removal")
 print("4. Test thoroughly after cleanup")
 print("5. Consider adding pre-commit hooks to prevent future issues")


if __name__ == "__main__":
 generate_manual_cleanup_guide()
