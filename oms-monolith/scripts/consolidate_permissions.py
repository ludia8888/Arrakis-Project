#!/usr/bin/env python3
"""
Script to consolidate duplicate permission definitions
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

def find_duplicate_definitions() -> Dict[str, List[Tuple[str, int]]]:
    """Find all duplicate class definitions"""
    duplicates = {
        "ResourceType": [],
        "Action": [],
        "Role": [],
        "PERMISSION_MATRIX": []
    }
    
    # Define search patterns
    patterns = {
        "ResourceType": r"class ResourceType\s*\(",
        "Action": r"class Action\s*\(",
        "Role": r"class Role\s*\(",
        "PERMISSION_MATRIX": r"PERMISSION_MATRIX\s*[:=]"
    }
    
    # Search in Python files
    for root, dirs, files in os.walk("."):
        # Skip __pycache__ and virtual env directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'venv', '.venv', 'env']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for class_name, pattern in patterns.items():
                            for i, line in enumerate(lines, 1):
                                if re.search(pattern, line):
                                    duplicates[class_name].append((filepath, i))
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return duplicates

def main():
    print("Finding duplicate permission definitions...")
    duplicates = find_duplicate_definitions()
    
    # Filter out the canonical version
    canonical_file = "./models/permissions.py"
    
    print("\n=== Duplicate Permission Definitions ===\n")
    
    for class_name, locations in duplicates.items():
        if locations:
            print(f"\n{class_name}:")
            print(f"  Canonical: {canonical_file}")
            print("  Duplicates:")
            for filepath, line_num in locations:
                if filepath != canonical_file:
                    print(f"    - {filepath}:{line_num}")
    
    print("\n=== Files that need updating ===")
    files_to_update = set()
    for class_name, locations in duplicates.items():
        for filepath, _ in locations:
            if filepath != canonical_file:
                files_to_update.add(filepath)
    
    for filepath in sorted(files_to_update):
        print(f"  - {filepath}")

if __name__ == "__main__":
    main()