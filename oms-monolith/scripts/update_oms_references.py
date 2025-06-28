#!/usr/bin/env python3
"""
Script to help identify remaining OMS references that need updating
"""
import os
import re
from pathlib import Path

def find_oms_references(directory="."):
    """Find all files containing OMS references"""
    oms_pattern = re.compile(r'\bOMS\b', re.IGNORECASE)
    results = []
    
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv']]
        
        for file in files:
            # Skip binary and hidden files
            if file.startswith('.') or file.endswith(('.pyc', '.pyo', '.so', '.dylib')):
                continue
                
            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = list(oms_pattern.finditer(content))
                    if matches:
                        results.append({
                            'file': filepath,
                            'count': len(matches),
                            'contexts': [content[max(0, m.start()-30):m.end()+30] for m in matches[:3]]
                        })
            except (UnicodeDecodeError, IOError):
                # Skip files that can't be read as text
                pass
    
    return results

if __name__ == "__main__":
    print("Searching for remaining OMS references...")
    results = find_oms_references()
    
    if results:
        print(f"\nFound {len(results)} files with OMS references:\n")
        for result in results:
            print(f"📄 {result['file']} ({result['count']} occurrences)")
            for context in result['contexts']:
                print(f"   ...{context.strip()}...")
            print()
    else:
        print("\n✅ No OMS references found!")
    
    print("\nSummary:")
    print(f"- Total files with OMS: {len(results)}")
    print(f"- Total occurrences: {sum(r['count'] for r in results)}")