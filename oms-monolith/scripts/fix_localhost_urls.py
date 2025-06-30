#!/usr/bin/env python3
"""
Script to find and report remaining hardcoded localhost URLs
"""
import os
import re
from pathlib import Path
from typing import List, Tuple

# Patterns to find localhost URLs
LOCALHOST_PATTERNS = [
    r'localhost:\d+',
    r'127\.0\.0\.1:\d+',
    r'http://localhost',
    r'https://localhost',
    r'redis://localhost',
    r'postgres://localhost',
    r'postgresql://localhost',
    r'nats://localhost',
    r'ws://localhost',
    r'wss://localhost',
]

# Files to exclude from checking
EXCLUDE_PATTERNS = [
    '*.pyc',
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    '*.log',
    '*.md',
    '*.txt',
    'docker-compose*.yml',
    'Dockerfile*',
    'Makefile',
    '*.sh',
    'scripts/',
    'tests/',
    'docs/',
    'monitoring/',
]

def should_check_file(filepath: Path) -> bool:
    """Check if file should be scanned"""
    # Only check Python files
    if not filepath.suffix == '.py':
        return False
    
    # Check exclusion patterns
    for pattern in EXCLUDE_PATTERNS:
        if pattern in str(filepath):
            return False
    
    return True

def find_localhost_urls(filepath: Path) -> List[Tuple[int, str, str]]:
    """Find localhost URLs in a file"""
    results = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            for pattern in LOCALHOST_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    # Skip if it's in a comment
                    if '#' in line and line.index('#') < match.start():
                        continue
                    # Skip if it's in a docstring or test
                    if 'test' in str(filepath).lower():
                        continue
                    results.append((line_num, match.group(), line.strip()))
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return results

def main():
    """Main function"""
    root_dir = Path('.')
    total_files = 0
    files_with_localhost = 0
    total_occurrences = 0
    
    print("Scanning for hardcoded localhost URLs...\n")
    
    # Find all Python files
    for filepath in root_dir.rglob('*.py'):
        if not should_check_file(filepath):
            continue
        
        total_files += 1
        results = find_localhost_urls(filepath)
        
        if results:
            files_with_localhost += 1
            total_occurrences += len(results)
            
            print(f"\n{filepath}:")
            for line_num, match, line in results:
                print(f"  Line {line_num}: {match}")
                print(f"    {line}")
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total Python files scanned: {total_files}")
    print(f"  Files with localhost URLs: {files_with_localhost}")
    print(f"  Total occurrences: {total_occurrences}")
    
    if total_occurrences > 0:
        print(f"\nRecommendation:")
        print(f"  Replace these with calls to shared.config.environment.get_config()")
        print(f"  Example:")
        print(f"    from shared.config.environment import get_config")
        print(f"    config = get_config()")
        print(f"    url = config.get_terminus_db_url()")

if __name__ == "__main__":
    main()