#!/usr/bin/env python3
"""
Code Quality Fix Script

This script systematically fixes common code quality issues in the Arrakis project.
Focuses only on project files, not dependencies or virtual environments.
"""

import os
import re
from pathlib import Path
from typing import List, Dict


class CodeQualityFixer:
    """Fixes common code quality issues in Python files"""
    
    def __init__(self):
        self.fixes_applied = 0
        self.files_processed = 0
        
    def fix_file(self, file_path: str) -> bool:
        """Fix code quality issues in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            lines = content.split('\n')
            fixed_lines = []
            
            for i, line in enumerate(lines):
                fixed_line = line
                
                # Fix trailing whitespace (W291, W293)
                fixed_line = fixed_line.rstrip()
                
                # Fix missing whitespace around operators (E225) - basic cases
                # Assignment operators
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])=([a-zA-Z0-9_"\'\[])', r'\1 = \2', fixed_line)
                # Comparison operators
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])!=([a-zA-Z0-9_"\'\[])', r'\1 != \2', fixed_line)
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])<=([a-zA-Z0-9_"\'\[])', r'\1 <= \2', fixed_line)
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])>=([a-zA-Z0-9_"\'\[])', r'\1 >= \2', fixed_line)
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])<([a-zA-Z0-9_"\'\[])', r'\1 < \2', fixed_line)
                fixed_line = re.sub(r'([a-zA-Z0-9_\]])>([a-zA-Z0-9_"\'\[])', r'\1 > \2', fixed_line)
                
                # Avoid double spaces
                fixed_line = re.sub(r' +', ' ', fixed_line)
                
                fixed_lines.append(fixed_line)
            
            # Remove extra blank lines at end of file
            while fixed_lines and fixed_lines[-1].strip() == '':
                fixed_lines.pop()
            
            # Ensure file ends with single newline
            if fixed_lines:
                fixed_lines.append('')
            
            fixed_content = '\n'.join(fixed_lines)
            
            # Only write if changes were made
            if fixed_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                return True
                
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
            return False
        
        return False
    
    def is_project_file(self, file_path: str) -> bool:
        """Check if file is part of project (not dependencies)"""
        exclude_patterns = [
            'test_env/', 'venv/', '__pycache__/', '.git/', 
            'node_modules/', 'htmlcov/', 'logs/', '.pytest_cache/',
            'site-packages/', 'lib/python', 'dist/', 'build/',
            '.venv/', 'env/'
        ]
        
        return not any(pattern in file_path for pattern in exclude_patterns)
    
    def fix_directory(self, directory: str) -> Dict[str, int]:
        """Fix all Python files in a directory"""
        stats = {'files_processed': 0, 'files_fixed': 0}
        
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if self.is_project_file(os.path.join(root, d))]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    if self.is_project_file(file_path):
                        stats['files_processed'] += 1
                        if self.fix_file(file_path):
                            stats['files_fixed'] += 1
                            print(f"✅ Fixed: {os.path.relpath(file_path, directory)}")
        
        return stats


def main():
    """Main function to fix code quality issues"""
    print("🔧 Code Quality Fix - Starting systematic repair...")
    
    fixer = CodeQualityFixer()
    
    # Focus on main project directories only
    project_dirs = [
        'arrakis-common',
        'ontology-management-service',
        'user-service',
        'audit-service', 
        'data-kernel-service',
        'embedding-service',
        'event-gateway',
        'scheduler-service'
    ]
    
    total_stats = {'files_processed': 0, 'files_fixed': 0}
    
    for directory in project_dirs:
        if os.path.exists(directory):
            print(f"\n📁 Processing {directory}...")
            stats = fixer.fix_directory(directory)
            total_stats['files_processed'] += stats['files_processed']
            total_stats['files_fixed'] += stats['files_fixed']
            print(f"   📊 Processed {stats['files_processed']} files, fixed {stats['files_fixed']}")
    
    print(f"\n🎉 Code quality fix complete!")
    print(f"   📂 Total files processed: {total_stats['files_processed']}")
    print(f"   🔧 Total files fixed: {total_stats['files_fixed']}")
    print(f"   📈 Fix rate: {total_stats['files_fixed']/max(total_stats['files_processed'], 1)*100:.1f}%")
    
    if total_stats['files_fixed'] > 0:
        print(f"\n🚀 Code quality improvements applied!")
        print(f"   Fixed common issues: trailing whitespace, operator spacing")
        print(f"   Improved maintainability and consistency")
    else:
        print(f"\n✨ Code quality already excellent!")


if __name__ == "__main__":
    main()