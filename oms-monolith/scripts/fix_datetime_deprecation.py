#!/usr/bin/env python3
"""
Fix datetime.now(timezone.utc) deprecation warnings
Replace with datetime.now(timezone.utc)
"""
import os
import re
import sys
from pathlib import Path

def fix_datetime_in_file(filepath):
    """Fix datetime.now(timezone.utc) in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        
        # Check if timezone is imported
        has_timezone_import = 'from datetime import timezone' in content or 'import timezone' in content
        has_datetime_import = 'from datetime import' in content or 'import datetime' in content
        
        # Replace datetime.now(timezone.utc) with datetime.now(timezone.utc)
        content = re.sub(
            r'datetime\.utcnow\(\)',
            'datetime.now(timezone.utc)',
            content
        )
        
        # If we made changes and timezone wasn't imported
        if content != original_content and not has_timezone_import and has_datetime_import:
            # Add timezone to existing datetime import
            content = re.sub(
                r'from datetime import ([^\\n]+)(?<!timezone)',
                lambda m: f"from datetime import {m.group(1)}, timezone" if ', timezone' not in m.group(0) else m.group(0),
                content
            )
            
            # If still no timezone import, add it after datetime import
            if 'timezone' not in content.split('import datetime')[0]:
                content = re.sub(
                    r'(import datetime\\s*\\n)',
                    r'\\1from datetime import timezone\\n',
                    content
                )
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Fix datetime.now(timezone.utc) in all Python files"""
    root_dir = Path('.')
    
    # Directories to skip
    skip_dirs = {'.git', '__pycache__', 'venv', '.venv', 'legacy_backup*', '.pytest_cache'}
    
    fixed_files = []
    
    for py_file in root_dir.rglob('*.py'):
        # Skip if in excluded directory
        if any(skip_dir in str(py_file) for skip_dir in skip_dirs):
            continue
            
        if fix_datetime_in_file(py_file):
            fixed_files.append(py_file)
            
    print(f"Fixed {len(fixed_files)} files:")
    for f in fixed_files:
        print(f"  - {f}")
        
    # Test by importing a fixed file
    if fixed_files:
        print("\nTesting import of fixed files...")
        test_file = str(fixed_files[0])
        try:
            # Just check syntax
            with open(test_file, 'r') as f:
                compile(f.read(), test_file, 'exec')
            print("✅ Syntax check passed!")
        except SyntaxError as e:
            print(f"❌ Syntax error in {test_file}: {e}")
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())