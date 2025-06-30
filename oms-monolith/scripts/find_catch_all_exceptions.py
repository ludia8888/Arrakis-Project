#!/usr/bin/env python3
"""
Find and categorize catch-all exceptions in the codebase.

This script can be used as a pre-commit hook or CI check to ensure
that overly broad exception handlers are not introduced.
"""
import os
import sys
import re
import ast
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

def find_catch_all_exceptions(filepath: Path) -> List[Tuple[int, str, str]]:
    """Find catch-all exceptions in a file with context"""
    results = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=str(filepath))
            
        lines = content.splitlines()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                    # Get the line content
                    line_num = node.lineno
                    line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                    
                    # Try to get context (what's in the try block)
                    context = "Unknown context"
                    parent = None
                    for potential_parent in ast.walk(tree):
                        if hasattr(potential_parent, 'handlers') and node in potential_parent.handlers:
                            parent = potential_parent
                            break
                    
                    if parent and hasattr(parent, 'body') and parent.body:
                        first_stmt = parent.body[0]
                        if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Call):
                            if hasattr(first_stmt.value.func, 'attr'):
                                context = f"Calling {first_stmt.value.func.attr}"
                        elif isinstance(first_stmt, ast.Assign):
                            context = "Variable assignment"
                        elif isinstance(first_stmt, ast.Return):
                            context = "Return statement"
                    
                    results.append((line_num, line_content.strip(), context))
                    
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    
    return results

def categorize_exceptions(filepath: Path, exceptions: List[Tuple[int, str, str]]) -> Dict[str, List[Tuple[int, str]]]:
    """Categorize exceptions by likely domain"""
    categories = {
        'database': [],
        'validation': [],
        'service': [],
        'infrastructure': [],
        'unknown': []
    }
    
    filepath_str = str(filepath).lower()
    
    for line_num, line, context in exceptions:
        # Categorize based on file path and context
        if 'database' in filepath_str or 'db' in filepath_str or 'terminus' in filepath_str:
            categories['database'].append((line_num, context))
        elif 'validation' in filepath_str or 'validate' in context.lower():
            categories['validation'].append((line_num, context))
        elif 'service' in filepath_str or 'client' in filepath_str:
            categories['service'].append((line_num, context))
        elif 'event' in filepath_str or 'publisher' in filepath_str:
            categories['infrastructure'].append((line_num, context))
        else:
            categories['unknown'].append((line_num, context))
    
    return categories

def main():
    """Main function"""
    root_dir = Path('.')
    total_count = 0
    files_by_category = {
        'database': [],
        'validation': [],
        'service': [],
        'infrastructure': [],
        'unknown': []
    }
    
    # Only check core and api directories
    for directory in ['core', 'api']:
        if not (root_dir / directory).exists():
            continue
            
        for filepath in (root_dir / directory).rglob('*.py'):
            exceptions = find_catch_all_exceptions(filepath)
            
            if exceptions:
                total_count += len(exceptions)
                categories = categorize_exceptions(filepath, exceptions)
                
                for category, items in categories.items():
                    if items:
                        files_by_category[category].append((filepath, items))
    
    # Print summary
    print("CATCH-ALL EXCEPTION ANALYSIS")
    print("=" * 60)
    print(f"Total catch-all exceptions in core+api: {total_count}")
    print()
    
    # Print by category with recommendations
    recommendations = {
        'database': "Use DatabaseConnectionError, QueryExecutionError, DatabaseTimeoutError",
        'validation': "Use ValidationError, SchemaValidationError, PolicyViolationError",
        'service': "Use ServiceException, ServiceTimeoutError, ServiceUnavailableError",
        'infrastructure': "Use InfrastructureException, MessageQueueError, EventPublishError",
        'unknown': "Analyze context and use appropriate domain exception"
    }
    
    for category, files in files_by_category.items():
        if not files:
            continue
            
        count = sum(len(items) for _, items in files)
        print(f"\n{category.upper()} ({count} exceptions)")
        print("-" * 40)
        print(f"Recommendation: {recommendations[category]}")
        print("\nTop files to fix:")
        
        # Sort by number of exceptions
        sorted_files = sorted(files, key=lambda x: len(x[1]), reverse=True)[:5]
        
        for filepath, items in sorted_files:
            print(f"\n  {filepath} ({len(items)} exceptions):")
            for line_num, context in items[:3]:  # Show first 3
                print(f"    Line {line_num}: {context}")

if __name__ == "__main__":
    main()