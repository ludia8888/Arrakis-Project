#!/usr/bin/env python3
"""
Carefully remove only @field_validator decorators and their methods
Keep all model classes and other functionality intact
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict

PROJECT_ROOT = Path(__file__).parent.parent

def find_validator_blocks(content: str) -> List[Tuple[int, int, str]]:
    """Find all @field_validator blocks with their start/end positions"""
    validators = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a @field_validator decorator
        if '@field_validator' in line:
            start_pos = sum(len(l) + 1 for l in lines[:i])
            validator_lines = [line]
            indent_level = len(line) - len(line.lstrip())
            
            # Collect the decorator and any following decorators
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('@'):
                validator_lines.append(lines[j])
                j += 1
            
            # Now we should be at the def line
            if j < len(lines) and lines[j].strip().startswith('def '):
                validator_lines.append(lines[j])
                method_indent = len(lines[j]) - len(lines[j].lstrip())
                j += 1
                
                # Collect the method body
                while j < len(lines):
                    if lines[j].strip() == '':
                        validator_lines.append(lines[j])
                        j += 1
                    elif len(lines[j]) - len(lines[j].lstrip()) > method_indent:
                        # Still inside the method
                        validator_lines.append(lines[j])
                        j += 1
                    else:
                        # We've reached the end of the method
                        break
                
                # Calculate end position
                end_pos = sum(len(l) + 1 for l in lines[:j])
                
                # Extract method name for logging
                method_match = re.search(r'def\s+(\w+)', '\n'.join(validator_lines))
                method_name = method_match.group(1) if method_match else 'unknown'
                
                validators.append((start_pos, end_pos, method_name))
                i = j - 1
        
        i += 1
    
    return validators

def remove_validators(content: str, model_file: str) -> Tuple[str, List[str], Dict[str, int]]:
    """Remove validator blocks from content"""
    validators = find_validator_blocks(content)
    removed_validators = []
    stats = {'validators_removed': 0, 'lines_removed': 0}
    
    # Remove from end to start to preserve positions
    for start, end, method_name in reversed(validators):
        removed_validators.append(method_name)
        
        # Count lines being removed
        removed_section = content[start:end]
        stats['lines_removed'] += removed_section.count('\n')
        
        # Remove the validator block
        content = content[:start] + content[end:]
        stats['validators_removed'] += 1
    
    # Clean up extra blank lines (more than 2 consecutive)
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    return content, removed_validators, stats

def update_imports(content: str) -> str:
    """Remove field_validator from imports if no longer needed"""
    if '@field_validator' not in content:
        # Remove field_validator from imports
        content = re.sub(r',\s*field_validator', '', content)
        content = re.sub(r'field_validator\s*,\s*', '', content)
        content = re.sub(r'from pydantic import field_validator\n', '', content)
    
    return content

def process_file(file_path: Path, dry_run: bool = True) -> Dict:
    """Process a single file to remove validators"""
    print(f"\n📄 Processing: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Remove validators
    content, removed_validators, stats = remove_validators(original_content, file_path.name)
    
    # Update imports if needed
    content = update_imports(content)
    
    # Calculate changes
    changes = {
        'file': str(file_path),
        'validators_removed': removed_validators,
        'stats': stats,
        'changed': content != original_content
    }
    
    if changes['changed']:
        print(f"  ✓ Found {len(removed_validators)} validators to remove:")
        for validator in removed_validators:
            print(f"    - {validator}")
        print(f"  ✓ Will remove {stats['lines_removed']} lines")
        
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("  ✅ File updated successfully")
        else:
            print("  🔍 DRY RUN - no changes made")
    else:
        print("  ℹ️  No validators found")
    
    return changes

def verify_model_integrity(file_path: Path) -> bool:
    """Verify that model classes are still intact"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for essential model classes
    essential_classes = {
        'domain.py': ['ObjectType', 'Property', 'LinkType', 'Interface'],
        'semantic_types.py': ['SemanticType'],
        'struct_types.py': ['StructType']
    }
    
    file_name = file_path.name
    if file_name in essential_classes:
        missing = []
        for class_name in essential_classes[file_name]:
            if f'class {class_name}' not in content:
                missing.append(class_name)
        
        if missing:
            print(f"  ⚠️  Warning: Missing classes in {file_name}: {', '.join(missing)}")
            return False
    
    return True

def main(dry_run: bool = True):
    """Main function to remove validators"""
    print("🔧 Validator Removal Tool (Safe Mode)")
    print("=" * 50)
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no files will be modified\n")
    else:
        print("⚠️  Running in WRITE mode - files will be modified\n")
    
    # Files to process
    model_files = [
        PROJECT_ROOT / "models/domain.py",
        PROJECT_ROOT / "models/semantic_types.py",
        PROJECT_ROOT / "models/struct_types.py"
    ]
    
    all_changes = []
    
    for file_path in model_files:
        if file_path.exists():
            changes = process_file(file_path, dry_run)
            all_changes.append(changes)
            
            # Verify integrity
            if not dry_run:
                verify_model_integrity(file_path)
        else:
            print(f"\n⚠️  File not found: {file_path}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print("-" * 50)
    
    total_validators = sum(len(c['validators_removed']) for c in all_changes)
    total_lines = sum(c['stats']['lines_removed'] for c in all_changes)
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