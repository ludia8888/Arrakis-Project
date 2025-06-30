#!/usr/bin/env python3
"""
Find any imports of the deprecated ultimate_killer module
Exit with non-zero status if found
"""
import os
import re
import sys
from pathlib import Path


def find_ultimate_killer_imports(root_dir: Path) -> list:
    """Find all Python files importing ultimate_killer"""
    import_pattern = re.compile(
        r'(from\s+core\.security\.ultimate_killer\s+import|'
        r'import\s+core\.security\.ultimate_killer|'
        r'from\s+.*ultimate_killer|'
        r'UltimateAttackKiller)'
    )
    
    violations = []
    
    # Directories to check
    check_dirs = ['api', 'core', 'middleware', 'services', 'shared']
    
    for dir_name in check_dirs:
        dir_path = root_dir / dir_name
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            # Skip __pycache__ and test files
            if '__pycache__' in str(py_file) or 'test_' in py_file.name:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                matches = import_pattern.findall(content)
                if matches:
                    # Find line numbers
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if import_pattern.search(line):
                            violations.append({
                                'file': str(py_file.relative_to(root_dir)),
                                'line': i,
                                'content': line.strip()
                            })
            except Exception as e:
                print(f"Error reading {py_file}: {e}", file=sys.stderr)
    
    return violations


def main():
    """Main entry point"""
    root_dir = Path(__file__).parent.parent
    
    violations = find_ultimate_killer_imports(root_dir)
    
    if violations:
        print("❌ Found ultimate_killer imports:")
        print("-" * 80)
        
        for v in violations:
            print(f"{v['file']}:{v['line']} - {v['content']}")
        
        print("-" * 80)
        print(f"Total violations: {len(violations)}")
        print("\n⚠️  ultimate_killer.py has been deprecated due to ReDoS vulnerabilities.")
        print("Please use InputSanitizer with PARANOID level instead.")
        print("See ADR-013 for migration guide.")
        
        sys.exit(1)
    else:
        print("✅ No ultimate_killer imports found")
        sys.exit(0)


if __name__ == "__main__":
    main()