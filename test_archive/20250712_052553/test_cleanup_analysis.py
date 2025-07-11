#!/usr/bin/env python3
"""
Test File Cleanup Analysis Tool
Analyzes all test files in the project and provides recommendations for cleanup
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re

class TestFileAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.test_files = []
        self.categories = {
            "jwt_auth": {"pattern": r"jwt|auth|token|login", "files": []},
            "integration": {"pattern": r"integration|three.*service|full", "files": []},
            "circuit_breaker": {"pattern": r"circuit|resilience|breaker|bulkhead", "files": []},
            "business": {"pattern": r"business|scenario|workflow", "files": []},
            "middleware": {"pattern": r"middleware", "files": []},
            "schema_db": {"pattern": r"schema|terminus|branch", "files": []},
            "monitoring": {"pattern": r"monitoring|observability|metric|prometheus|jaeger", "files": []},
            "audit": {"pattern": r"audit", "files": []},
            "etag": {"pattern": r"etag|cache", "files": []},
            "misc": {"pattern": r".*", "files": []}
        }
        self.duplicates = {}
        self.similar_files = []
        
    def find_all_test_files(self):
        """Find all test files in the project"""
        test_patterns = ["test_*.py", "*_test.py", "test*.py"]
        
        for pattern in test_patterns:
            for file in self.project_root.glob(f"**/{pattern}"):
                if "venv" not in str(file) and "__pycache__" not in str(file):
                    self.test_files.append(file)
                    
        # Sort by modification time
        self.test_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
    def categorize_files(self):
        """Categorize test files based on their names and content"""
        for file in self.test_files:
            categorized = False
            file_name = file.name.lower()
            
            # Try to read first few lines for better categorization
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content_preview = f.read(500).lower()
            except:
                content_preview = ""
                
            # Check each category
            for category, info in self.categories.items():
                if category == "misc":
                    continue
                    
                pattern = info["pattern"]
                if (re.search(pattern, file_name) or 
                    re.search(pattern, content_preview)):
                    info["files"].append(file)
                    categorized = True
                    break
                    
            if not categorized:
                self.categories["misc"]["files"].append(file)
                
    def find_duplicates(self):
        """Find duplicate test files based on content hash"""
        content_hashes = {}
        
        for file in self.test_files:
            try:
                with open(file, 'rb') as f:
                    content = f.read()
                    # Remove comments and whitespace for better comparison
                    content_normalized = re.sub(rb'#.*?\n', b'', content)
                    content_normalized = re.sub(rb'\s+', b' ', content_normalized)
                    
                    file_hash = hashlib.md5(content_normalized).hexdigest()
                    
                    if file_hash in content_hashes:
                        if file_hash not in self.duplicates:
                            self.duplicates[file_hash] = [content_hashes[file_hash]]
                        self.duplicates[file_hash].append(file)
                    else:
                        content_hashes[file_hash] = file
            except:
                pass
                
    def find_similar_files(self):
        """Find files with similar names that might be versions of each other"""
        file_groups = {}
        
        for file in self.test_files:
            # Extract base name without version numbers or suffixes
            base_name = file.stem
            base_name = re.sub(r'_v?\d+$', '', base_name)
            base_name = re.sub(r'_fixed$', '', base_name)
            base_name = re.sub(r'_final$', '', base_name)
            base_name = re.sub(r'_simple$', '', base_name)
            base_name = re.sub(r'_complete$', '', base_name)
            base_name = re.sub(r'_detailed$', '', base_name)
            
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append(file)
            
        # Find groups with multiple files
        for base_name, files in file_groups.items():
            if len(files) > 1:
                self.similar_files.append({
                    "base_name": base_name,
                    "files": sorted(files, key=lambda x: os.path.getmtime(x))
                })
                
    def analyze_file_content(self, file: Path) -> Dict:
        """Analyze individual file content"""
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Count test functions
            test_functions = len(re.findall(r'def test_\w+', content))
            async_tests = len(re.findall(r'async def test_\w+', content))
            
            # Check imports to determine test type
            uses_pytest = 'import pytest' in content or 'from pytest' in content
            uses_unittest = 'import unittest' in content
            uses_requests = 'import requests' in content
            uses_asyncio = 'import asyncio' in content
            
            # Get file stats
            stats = os.stat(file)
            
            return {
                "path": str(file.relative_to(self.project_root)),
                "size": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "test_count": test_functions,
                "async_tests": async_tests,
                "test_framework": "pytest" if uses_pytest else "unittest" if uses_unittest else "custom",
                "is_integration": uses_requests,
                "is_async": uses_asyncio or async_tests > 0
            }
        except:
            return {
                "path": str(file.relative_to(self.project_root)),
                "error": "Could not analyze file"
            }
            
    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report"""
        self.find_all_test_files()
        self.categorize_files()
        self.find_duplicates()
        self.find_similar_files()
        
        report = {
            "summary": {
                "total_test_files": len(self.test_files),
                "duplicate_groups": len(self.duplicates),
                "similar_groups": len(self.similar_files),
                "timestamp": datetime.now().isoformat()
            },
            "categories": {},
            "duplicates": [],
            "similar_files": [],
            "recommendations": {
                "to_keep": [],
                "to_merge": [],
                "to_archive": [],
                "to_update": []
            }
        }
        
        # Process categories
        for category, info in self.categories.items():
            if info["files"]:
                report["categories"][category] = {
                    "count": len(info["files"]),
                    "files": [self.analyze_file_content(f) for f in info["files"]]
                }
                
        # Process duplicates
        for hash_val, files in self.duplicates.items():
            report["duplicates"].append({
                "files": [str(f.relative_to(self.project_root)) for f in files],
                "recommendation": f"Keep {files[-1].name}, archive others"
            })
            
        # Process similar files
        for group in self.similar_files:
            report["similar_files"].append({
                "base_name": group["base_name"],
                "files": [str(f.relative_to(self.project_root)) for f in group["files"]],
                "newest": str(group["files"][-1].relative_to(self.project_root)),
                "recommendation": f"Keep newest: {group['files'][-1].name}"
            })
            
        # Generate recommendations
        self._generate_recommendations(report)
        
        return report
        
    def _generate_recommendations(self, report: Dict):
        """Generate specific recommendations for cleanup"""
        # Files to definitely keep (newest versions, core tests)
        core_patterns = [
            "enterprise_integration_test_suite.py",
            "production_level_test_suite.py",
            "test_alerting_system.py",
            "test_core_modules_health.py"
        ]
        
        # Archive patterns (old, temporary, or one-off tests)
        archive_patterns = [
            r"test_.*_simple\.py$",
            r"test_.*_debug\.py$",
            r"test_.*_fix\.py$",
            r"test_.*_only\.py$",
            r"test_decode.*\.py$",
            r"test_token.*\.py$",
            r"test_immediate.*\.py$"
        ]
        
        # Merge candidates (similar functionality)
        merge_groups = [
            ["test_jwt_validation.py", "test_jwt_validation2.py", "test_jwt_decode.py"],
            ["test_audit_integration.py", "test_audit_service_integration.py", "test_oms_audit_integration.py"],
            ["test_circuit_breaker.py", "test_circuit_breaker_specific.py", "test_distributed_circuit_breaker.py"],
            ["test_integration.py", "test_basic_integration.py", "test_advanced_integration.py"],
            ["test_business_scenarios.py", "test_business_scenarios_fixed.py"]
        ]
        
        all_files = set()
        for file in self.test_files:
            file_name = file.name
            file_path = str(file.relative_to(self.project_root))
            all_files.add(file_path)
            
            # Check if it's a core file to keep
            if any(pattern in file_name for pattern in core_patterns):
                report["recommendations"]["to_keep"].append({
                    "file": file_path,
                    "reason": "Core test suite"
                })
                continue
                
            # Check if it should be archived
            if any(re.search(pattern, file_name) for pattern in archive_patterns):
                report["recommendations"]["to_archive"].append({
                    "file": file_path,
                    "reason": "Temporary or debug test"
                })
                continue
                
        # Process merge groups
        for merge_group in merge_groups:
            existing_files = [f for f in merge_group if f in [p.name for p in self.test_files]]
            if len(existing_files) > 1:
                report["recommendations"]["to_merge"].append({
                    "files": existing_files,
                    "target": existing_files[0],
                    "reason": "Duplicate functionality"
                })
                
        # Files that need updating (old test patterns)
        for file in self.test_files:
            try:
                with open(file, 'r') as f:
                    content = f.read(1000)
                    if 'unittest.TestCase' in content and file.name not in archive_patterns:
                        report["recommendations"]["to_update"].append({
                            "file": str(file.relative_to(self.project_root)),
                            "reason": "Uses old unittest framework"
                        })
            except:
                pass


def main():
    analyzer = TestFileAnalyzer("/Users/isihyeon/Desktop/Arrakis-Project")
    report = analyzer.generate_report()
    
    # Save detailed report
    with open("test_cleanup_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    # Print summary
    print("Test File Cleanup Analysis")
    print("=" * 60)
    print(f"Total test files found: {report['summary']['total_test_files']}")
    print(f"Duplicate groups: {report['summary']['duplicate_groups']}")
    print(f"Similar file groups: {report['summary']['similar_groups']}")
    print("\nCategories:")
    for category, info in report['categories'].items():
        print(f"  {category}: {info['count']} files")
        
    print("\nRecommendations:")
    print(f"  To keep: {len(report['recommendations']['to_keep'])} files")
    print(f"  To merge: {len(report['recommendations']['to_merge'])} groups")
    print(f"  To archive: {len(report['recommendations']['to_archive'])} files")
    print(f"  To update: {len(report['recommendations']['to_update'])} files")
    
    print(f"\nDetailed report saved to: test_cleanup_report.json")


if __name__ == "__main__":
    main()