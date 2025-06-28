#!/usr/bin/env python3
"""
Safely refactor model files to remove custom validators
Keeps only Pydantic basic type definitions
"""

import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent

def remove_field_validators(content: str) -> Tuple[str, List[str]]:
    """Remove @field_validator decorators and their methods"""
    removed = []
    
    # Pattern to match @field_validator and the following method
    pattern = r'(\s*)@field_validator\([^)]+\).*?\n(\1def\s+\w+\s*\([^)]*\)[^:]*:(?:\n(?!\1\S).*)*)'
    
    matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
    
    # Remove from end to start to preserve positions
    for match in reversed(matches):
        validator_text = match.group(0)
        # Extract validator name for logging
        validator_name = re.search(r'def\s+(\w+)\s*\(', validator_text)
        if validator_name:
            removed.append(validator_name.group(1))
        
        # Remove the validator
        content = content[:match.start()] + content[match.end():]
    
    # Clean up extra blank lines
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    return content, removed

def remove_validator_imports(content: str) -> str:
    """Remove validator-related imports"""
    # Remove field_validator imports
    content = re.sub(r'from pydantic import.*field_validator.*\n', '', content)
    content = re.sub(r',\s*field_validator', '', content)
    
    # Clean up empty parentheses
    content = re.sub(r'from pydantic import\s*\(\s*\)', '', content)
    
    return content

def add_validation_comment(content: str, model_name: str) -> str:
    """Add comment about validation being handled by core"""
    comment = f'''"""
{model_name}

Note: Custom validation logic has been moved to core/validation/rules/
This model now contains only structure and type definitions.
All business validation is handled by the core validation service.
"""
'''
    
    # Replace existing docstring if found at start
    docstring_pattern = r'^(""".*?"""|\'\'\'.*?\'\'\')[\s\n]*'
    if re.match(docstring_pattern, content, re.DOTALL):
        content = re.sub(docstring_pattern, comment + '\n', content, 1, re.DOTALL)
    else:
        # Add at beginning if no docstring
        content = comment + '\n' + content
    
    return content

def refactor_model_file(file_path: Path, dry_run: bool = True) -> dict:
    """Refactor a single model file"""
    
    print(f"\n📄 Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    content = original_content
    
    # Remove field validators
    content, removed_validators = remove_field_validators(content)
    
    # Remove validator imports
    content = remove_validator_imports(content)
    
    # Add migration comment
    content = add_validation_comment(content, file_path.stem)
    
    changes = {
        'file': str(file_path),
        'validators_removed': removed_validators,
        'lines_removed': original_content.count('\n') - content.count('\n'),
        'changed': content != original_content
    }
    
    if changes['changed']:
        print(f"  ✓ Removed {len(removed_validators)} validators")
        print(f"  ✓ Reduced by {changes['lines_removed']} lines")
        
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("  ✓ File updated")
        else:
            print("  🔍 DRY RUN - no changes made")
    else:
        print("  ℹ️  No validators found")
    
    return changes

def main(dry_run: bool = True):
    """Main refactoring function"""
    
    print("🔧 Model Validation Refactoring Tool")
    print("=" * 50)
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no files will be modified\n")
    else:
        print("⚠️  Running in WRITE mode - files will be modified\n")
    
    # Files to refactor
    model_files = [
        PROJECT_ROOT / "models/domain.py",
        PROJECT_ROOT / "models/semantic_types.py", 
        PROJECT_ROOT / "models/struct_types.py"
    ]
    
    all_changes = []
    
    for file_path in model_files:
        if file_path.exists():
            changes = refactor_model_file(file_path, dry_run)
            all_changes.append(changes)
        else:
            print(f"\n⚠️  File not found: {file_path}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print("-" * 50)
    
    total_validators = sum(len(c['validators_removed']) for c in all_changes)
    total_lines = sum(c['lines_removed'] for c in all_changes)
    files_changed = sum(1 for c in all_changes if c['changed'])
    
    print(f"Files processed: {len(all_changes)}")
    print(f"Files changed: {files_changed}")
    print(f"Validators removed: {total_validators}")
    print(f"Lines removed: {total_lines}")
    
    if dry_run and files_changed > 0:
        print("\n💡 To apply changes, run:")
        print(f"   python {Path(__file__).name} --write")

if __name__ == "__main__":
    import sys
    dry_run = "--write" not in sys.argv
    main(dry_run)