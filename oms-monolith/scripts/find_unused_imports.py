#!/usr/bin/env python3
"""
Script to find unused imports in Python files.
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Set, List, Dict, Tuple

class ImportAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.from_imports = []
        self.used_names = set()
        self.wildcard_imports = []
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                'module': alias.name,
                'alias': alias.asname or alias.name,
                'line': node.lineno
            })
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                if alias.name == '*':
                    self.wildcard_imports.append({
                        'module': node.module,
                        'line': node.lineno
                    })
                else:
                    self.from_imports.append({
                        'module': node.module,
                        'name': alias.name,
                        'alias': alias.asname or alias.name,
                        'line': node.lineno
                    })
        self.generic_visit(node)
        
    def visit_Name(self, node):
        self.used_names.add(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

def analyze_file(filepath: Path) -> Dict:
    """Analyze a single Python file for import issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None
        
    try:
        tree = ast.parse(content)
    except:
        return None
        
    analyzer = ImportAnalyzer()
    analyzer.visit(tree)
    
    # Find unused imports
    unused_imports = []
    for imp in analyzer.imports:
        if imp['alias'] not in analyzer.used_names:
            unused_imports.append(imp)
            
    for imp in analyzer.from_imports:
        if imp['alias'] not in analyzer.used_names:
            unused_imports.append(imp)
    
    # Find duplicate imports
    import_counts = defaultdict(int)
    for imp in analyzer.imports:
        import_counts[imp['module']] += 1
    for imp in analyzer.from_imports:
        import_counts[f"{imp['module']}.{imp['name']}"] += 1
        
    duplicates = {k: v for k, v in import_counts.items() if v > 1}
    
    return {
        'unused': unused_imports,
        'wildcard': analyzer.wildcard_imports,
        'duplicates': duplicates,
        'all_imports': analyzer.imports + analyzer.from_imports
    }

def find_deprecated_imports(all_imports: List[Dict]) -> List[Dict]:
    """Find imports from potentially deprecated modules."""
    deprecated_patterns = [
        'mock_auth_middleware',
        'test_',
        'simple_schema_test',
        'check_enum_compatibility',
        'check_schema_completeness',
        'run_phase6_tests',
        'data_types',  # from shared/models/data_types.py which was deleted
    ]
    
    deprecated = []
    for imp in all_imports:
        module = imp.get('module', '')
        if any(pattern in module for pattern in deprecated_patterns):
            deprecated.append(imp)
            
    return deprecated

def main():
    directories = ['../api', '../core', '../shared', '../models', '../middleware', '../infrastructure', '../utils']
    
    results = {
        'unused': defaultdict(list),
        'wildcard': defaultdict(list),
        'duplicates': defaultdict(list),
        'deprecated': defaultdict(list)
    }
    
    total_files = 0
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    total_files += 1
                    
                    analysis = analyze_file(filepath)
                    if analysis:
                        relative_path = str(filepath.relative_to('..'))
                        
                        if analysis['unused']:
                            results['unused'][relative_path] = analysis['unused']
                            
                        if analysis['wildcard']:
                            results['wildcard'][relative_path] = analysis['wildcard']
                            
                        if analysis['duplicates']:
                            results['duplicates'][relative_path] = analysis['duplicates']
                            
                        deprecated = find_deprecated_imports(analysis['all_imports'])
                        if deprecated:
                            results['deprecated'][relative_path] = deprecated
    
    # Print results
    print(f"Analyzed {total_files} Python files\n")
    
    print("=== UNUSED IMPORTS ===")
    if results['unused']:
        for file, imports in sorted(results['unused'].items()):
            print(f"\n{file}:")
            for imp in imports:
                if 'name' in imp:
                    print(f"  Line {imp['line']}: from {imp['module']} import {imp['name']}")
                else:
                    print(f"  Line {imp['line']}: import {imp['module']}")
    else:
        print("No unused imports found.")
        
    print("\n\n=== WILDCARD IMPORTS ===")
    if results['wildcard']:
        for file, imports in sorted(results['wildcard'].items()):
            print(f"\n{file}:")
            for imp in imports:
                print(f"  Line {imp['line']}: from {imp['module']} import *")
    else:
        print("No wildcard imports found.")
        
    print("\n\n=== DUPLICATE IMPORTS ===")
    if results['duplicates']:
        for file, duplicates in sorted(results['duplicates'].items()):
            print(f"\n{file}:")
            for module, count in duplicates.items():
                print(f"  {module}: imported {count} times")
    else:
        print("No duplicate imports found.")
        
    print("\n\n=== IMPORTS FROM DEPRECATED/REMOVED MODULES ===")
    if results['deprecated']:
        for file, imports in sorted(results['deprecated'].items()):
            print(f"\n{file}:")
            for imp in imports:
                if 'name' in imp:
                    print(f"  Line {imp['line']}: from {imp['module']} import {imp['name']}")
                else:
                    print(f"  Line {imp['line']}: import {imp['module']}")
    else:
        print("No imports from deprecated modules found.")

if __name__ == "__main__":
    main()