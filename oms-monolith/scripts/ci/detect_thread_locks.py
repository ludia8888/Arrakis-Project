#!/usr/bin/env python3
"""
CI Gate: Detect potential thread lock issues in async code paths
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Set


class ThreadLockDetector(ast.NodeVisitor):
    """AST visitor to detect threading lock usage in async contexts"""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[Tuple[int, str]] = []
        self.in_async_function = False
        self.async_class_methods: Set[str] = set()
        self.imports_threading = False
        self.imports_asyncio = False
        
    def visit_Import(self, node: ast.Import):
        """Track threading and asyncio imports"""
        for alias in node.names:
            if alias.name == 'threading':
                self.imports_threading = True
            elif alias.name == 'asyncio':
                self.imports_asyncio = True
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from imports"""
        if node.module == 'threading':
            self.imports_threading = True
        elif node.module == 'asyncio':
            self.imports_asyncio = True
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Enter async function context"""
        old_in_async = self.in_async_function
        self.in_async_function = True
        self.async_class_methods.add(node.name)
        self.generic_visit(node)
        self.in_async_function = old_in_async
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check for sync functions that might be called from async"""
        # Check if function uses threading locks
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Attribute):
                if (hasattr(stmt.value, 'id') and 
                    stmt.value.id in ['threading', 'self'] and
                    stmt.attr in ['Lock', 'RLock', '_lock']):
                    # This function uses threading locks
                    if node.name.startswith('a') or node.name in self.async_class_methods:
                        self.issues.append((
                            stmt.lineno,
                            f"Function '{node.name}' appears to be async-related but uses threading locks"
                        ))
        self.generic_visit(node)
        
    def visit_With(self, node: ast.With):
        """Check for lock usage in with statements"""
        if self.in_async_function:
            for item in node.items:
                if isinstance(item.context_expr, ast.Attribute):
                    attr_name = getattr(item.context_expr, 'attr', '')
                    if attr_name in ['_lock', '_sync_lock'] or 'lock' in attr_name.lower():
                        # Check if it's a threading lock
                        if isinstance(item.context_expr.value, ast.Attribute):
                            if item.context_expr.value.attr == 'threading':
                                self.issues.append((
                                    node.lineno,
                                    f"Threading lock used in async function"
                                ))
                        elif isinstance(item.context_expr.value, ast.Name):
                            if item.context_expr.value.id == 'self' and '_sync_lock' not in attr_name:
                                self.issues.append((
                                    node.lineno,
                                    f"Potential threading lock '{attr_name}' used in async function"
                                ))
        self.generic_visit(node)


def check_file(filepath: Path) -> List[Tuple[str, int, str]]:
    """Check a single Python file for thread lock issues"""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content, filename=str(filepath))
        detector = ThreadLockDetector(str(filepath))
        detector.visit(tree)
        
        # Only report issues if both threading and asyncio are used
        if detector.imports_threading and detector.imports_asyncio and detector.issues:
            for line_no, issue in detector.issues:
                issues.append((str(filepath), line_no, issue))
                
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}", file=sys.stderr)
        
    return issues


def main():
    """Main entry point for CI gate"""
    # Directories to check
    check_dirs = [
        'api/graphql',
        'core/traversal',
        'core/validation',
        'core/event_publisher',
        'middleware'
    ]
    
    # Files to explicitly exclude
    exclude_files = {
        'core/traversal/cache/implementations/lru_cache.py',  # Has proper sync/async separation
        'core/traversal/cache/implementations/cache_warmer.py',  # Uses threading appropriately
    }
    
    all_issues = []
    
    for check_dir in check_dirs:
        if not os.path.exists(check_dir):
            continue
            
        for root, _, files in os.walk(check_dir):
            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    
                    # Skip excluded files
                    if str(filepath) in exclude_files:
                        continue
                        
                    issues = check_file(filepath)
                    all_issues.extend(issues)
    
    # Report results
    if all_issues:
        print("❌ Thread lock issues detected in async code paths:\n")
        for filepath, line_no, issue in all_issues:
            print(f"{filepath}:{line_no} - {issue}")
        print(f"\nTotal issues: {len(all_issues)}")
        print("\nSuggestions:")
        print("1. Use asyncio.Lock instead of threading.Lock in async functions")
        print("2. Keep sync and async code paths separate")
        print("3. Use AsyncLRUCache instead of LRUCache in async contexts")
        return 1
    else:
        print("✅ No thread lock issues detected in async code paths")
        return 0


if __name__ == "__main__":
    sys.exit(main())