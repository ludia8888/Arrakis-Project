#!/usr/bin/env python3
"""
Find and analyze error handling issues in the codebase
"""

import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent

class ErrorHandlingAnalyzer:
    """Analyze error handling patterns in Python code"""
    
    def __init__(self):
        self.issues = {
            "bare_except": [],
            "broad_exception": [],
            "empty_except": [],
            "no_logging": [],
            "pass_in_except": []
        }
        
    def analyze_file(self, file_path: Path) -> Dict[str, List]:
        """Analyze a single Python file for error handling issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            self._analyze_ast(tree, file_path, content.splitlines())
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            
        return self.issues
    
    def _analyze_ast(self, tree: ast.AST, file_path: Path, lines: List[str]):
        """Analyze AST for error handling patterns"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                self._analyze_try_block(node, file_path, lines)
    
    def _analyze_try_block(self, node: ast.Try, file_path: Path, lines: List[str]):
        """Analyze a try-except block"""
        for handler in node.handlers:
            # Check for bare except
            if handler.type is None:
                self.issues["bare_except"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": handler.lineno,
                    "code": lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else ""
                })
            
            # Check for broad Exception
            elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                # Check if there's proper logging
                has_logging = self._has_logging_in_handler(handler)
                
                self.issues["broad_exception"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": handler.lineno,
                    "code": lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else "",
                    "has_logging": has_logging
                })
                
                if not has_logging:
                    self.issues["no_logging"].append({
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "line": handler.lineno,
                        "code": lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else ""
                    })
            
            # Check for empty except blocks or pass statements
            if len(handler.body) == 0:
                self.issues["empty_except"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": handler.lineno,
                    "code": lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else ""
                })
            elif len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                self.issues["pass_in_except"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": handler.lineno,
                    "code": lines[handler.lineno - 1].strip() if handler.lineno <= len(lines) else ""
                })
    
    def _has_logging_in_handler(self, handler: ast.ExceptHandler) -> bool:
        """Check if exception handler has logging"""
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                # Check for logging calls
                if isinstance(node.func, ast.Attribute):
                    if any(log_method in node.func.attr for log_method in 
                           ['error', 'warning', 'exception', 'critical', 'debug', 'info']):
                        return True
                # Check for print statements (basic logging)
                elif isinstance(node.func, ast.Name) and node.func.id == 'print':
                    return True
        return False
    
    def scan_directory(self, directory: Path):
        """Scan entire directory for Python files"""
        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', 'venv', '.pytest_cache', 
                'htmlcov', 'dist', 'build', 'node_modules'
            ]]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    self.analyze_file(file_path)
    
    def get_priority_files(self) -> List[Tuple[str, int]]:
        """Get files with most issues for prioritization"""
        file_issue_count = {}
        
        for issue_type, issues in self.issues.items():
            for issue in issues:
                file_path = issue["file"]
                if file_path not in file_issue_count:
                    file_issue_count[file_path] = 0
                file_issue_count[file_path] += 1
        
        # Sort by issue count
        return sorted(file_issue_count.items(), key=lambda x: x[1], reverse=True)
    
    def generate_report(self):
        """Generate analysis report"""
        print("\n" + "=" * 70)
        print("Error Handling Analysis Report")
        print("=" * 70)
        
        # Summary
        print("\nSummary:")
        print("-" * 50)
        for issue_type, issues in self.issues.items():
            if issues:
                print(f"{issue_type.replace('_', ' ').title()}: {len(issues)} occurrences")
        
        # Priority files
        priority_files = self.get_priority_files()[:10]
        if priority_files:
            print("\nTop 10 Files with Most Issues:")
            print("-" * 50)
            for file_path, count in priority_files:
                print(f"{file_path}: {count} issues")
        
        # Detailed issues
        print("\nDetailed Issues by Type:")
        print("-" * 50)
        
        if self.issues["bare_except"]:
            print("\nBare Except Clauses (most critical):")
            for issue in self.issues["bare_except"][:5]:
                print(f"  {issue['file']}:{issue['line']} - {issue['code']}")
        
        if self.issues["pass_in_except"]:
            print("\nPass Statements in Except Blocks:")
            for issue in self.issues["pass_in_except"][:5]:
                print(f"  {issue['file']}:{issue['line']} - {issue['code']}")
        
        if self.issues["broad_exception"]:
            print("\nBroad Exception Catches without Logging:")
            for issue in self.issues["broad_exception"][:5]:
                if not issue["has_logging"]:
                    print(f"  {issue['file']}:{issue['line']} - {issue['code']}")

def main():
    """Main execution"""
    analyzer = ErrorHandlingAnalyzer()
    
    print("Analyzing error handling patterns...")
    analyzer.scan_directory(PROJECT_ROOT)
    
    analyzer.generate_report()
    
    # Save detailed results
    import json
    with open(PROJECT_ROOT / "scripts" / "error_handling_analysis.json", "w") as f:
        json.dump(analyzer.issues, f, indent=2)
    
    print(f"\nDetailed results saved to: scripts/error_handling_analysis.json")

if __name__ == "__main__":
    main()