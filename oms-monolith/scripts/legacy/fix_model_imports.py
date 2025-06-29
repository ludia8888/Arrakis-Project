#!/usr/bin/env python3
"""
Fix missing Pydantic imports in model files
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def fix_imports(file_path: Path):
    """Add missing Pydantic imports"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if BaseModel is used but not imported
    if 'BaseModel' in content and 'from pydantic import' not in content:
        # Find the right place to insert the import (after other imports)
        lines = content.split('\n')
        import_index = 0
        
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                import_index = i + 1
            elif line.strip() and not line.startswith('#'):
                break
        
        # Insert Pydantic import
        lines.insert(import_index, 'from pydantic import BaseModel, Field')
        content = '\n'.join(lines)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Fixed imports in {file_path.name}")
        return True
    
    return False

def main():
    """Fix imports in all model files"""
    print("🔧 Fixing Model Imports")
    print("=" * 50)
    
    model_files = [
        PROJECT_ROOT / "models/domain.py",
        PROJECT_ROOT / "models/semantic_types.py",
        PROJECT_ROOT / "models/struct_types.py"
    ]
    
    fixed_count = 0
    for file_path in model_files:
        if file_path.exists():
            if fix_imports(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print(f"\n✅ Fixed {fixed_count} files")

if __name__ == "__main__":
    main()