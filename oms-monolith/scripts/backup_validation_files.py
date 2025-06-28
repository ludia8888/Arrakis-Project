#!/usr/bin/env python3
"""
Backup validation-related files before cleanup
This creates a timestamped backup of all validation files
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Files to backup
BACKUP_FILES = [
    "middleware/request_validation.py",
    "middleware/enterprise_validation.py", 
    "models/domain.py",
    "models/semantic_types.py",
    "models/struct_types.py",
]

def create_backup():
    """Create timestamped backup of validation files"""
    
    # Create backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_ROOT / f"backups/validation_cleanup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Creating backup in: {backup_dir}")
    
    # Backup each file
    backed_up = []
    for file_path in BACKUP_FILES:
        src = PROJECT_ROOT / file_path
        if src.exists():
            # Preserve directory structure
            dst_dir = backup_dir / Path(file_path).parent
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = backup_dir / file_path
            
            shutil.copy2(src, dst)
            backed_up.append(file_path)
            print(f"  ✓ Backed up: {file_path}")
        else:
            print(f"  ⚠️  Not found: {file_path}")
    
    # Create restore script
    restore_script = backup_dir / "restore.py"
    restore_content = f'''#!/usr/bin/env python3
"""Restore script for validation cleanup backup from {timestamp}"""
import shutil
from pathlib import Path

BACKUP_DIR = Path(__file__).parent
PROJECT_ROOT = BACKUP_DIR.parent.parent

files_to_restore = {backed_up!r}

print("🔄 Restoring validation files...")
for file_path in files_to_restore:
    src = BACKUP_DIR / file_path
    dst = PROJECT_ROOT / file_path
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  ✓ Restored: {{file_path}}")
    else:
        print(f"  ⚠️  Not found in backup: {{file_path}}")

print("✅ Restore complete!")
'''
    
    with open(restore_script, 'w') as f:
        f.write(restore_content)
    
    restore_script.chmod(0o755)
    
    print(f"\n✅ Backup complete! Total files: {len(backed_up)}")
    print(f"💡 To restore, run: python {restore_script}")
    
    return backup_dir

if __name__ == "__main__":
    backup_dir = create_backup()