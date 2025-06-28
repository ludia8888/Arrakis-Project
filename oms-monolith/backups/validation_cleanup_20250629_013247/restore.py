#!/usr/bin/env python3
"""Restore script for validation cleanup backup from 20250629_013247"""
import shutil
from pathlib import Path

BACKUP_DIR = Path(__file__).parent
PROJECT_ROOT = BACKUP_DIR.parent.parent

files_to_restore = ['middleware/request_validation.py', 'middleware/enterprise_validation.py', 'models/domain.py', 'models/semantic_types.py', 'models/struct_types.py']

print("🔄 Restoring validation files...")
for file_path in files_to_restore:
    src = BACKUP_DIR / file_path
    dst = PROJECT_ROOT / file_path
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  ✓ Restored: {file_path}")
    else:
        print(f"  ⚠️  Not found in backup: {file_path}")

print("✅ Restore complete!")
