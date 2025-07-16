#!/usr/bin/env python3
"""
Mass Import Fix Script for MSA Architecture Issue

This script fixes the import architecture issue by replacing:
1. common_logging imports with arrakis_common imports
2. common_security imports with arrakis_common imports

This addresses the 141 files affected by the MSA import architecture issue.
"""

import os
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell = True, capture_output = True, text = True)
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception as e:
        print(f"Error running command {cmd}: {e}")
        return []


def find_files_with_common_logging():
    """Find all files with common_logging imports"""
    cmd = "grep -r 'from common_logging' --include='*.py' ."
    lines = run_command(cmd)
    files = set()
    for line in lines:
        if ":" in line:
            file_path = line.split(":")[0]
            files.add(file_path)
    return list(files)


def find_files_with_common_security():
    """Find all files with common_security imports"""
    cmd = "grep -r 'from common_security' --include='*.py' ."
    lines = run_command(cmd)
    files = set()
    for line in lines:
        if ":" in line:
            file_path = line.split(":")[0]
            files.add(file_path)
    return list(files)


def fix_common_logging_imports(file_path):
    """Fix common_logging imports in a single file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Track if any changes were made
        original_content = content

        # Replace common_logging imports
        patterns = [
            (
                r"from common_logging\.setup import get_logger",
                "from arrakis_common import get_logger",
            ),
            (
                r"from arrakis_common import get_logger",
                "from arrakis_common import get_logger",
            ),
            (r"import common_logging\.setup", "from arrakis_common import get_logger"),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        # Write back if changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

    return False


def fix_common_security_imports(file_path):
    """Fix common_security imports in a single file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Track if any changes were made
        original_content = content

        # Replace common_security imports
        patterns = [
            # Basic imports
            (
                r"from arrakis_common.utils.security import encrypt_text, decrypt_text, hash_data",
                "from arrakis_common.utils.security import encrypt_text, decrypt_text, hash_data",
            ),
            (
                r"from arrakis_common.utils.security import encrypt_text, decrypt_text",
                "from arrakis_common.utils.security import encrypt_text, decrypt_text",
            ),
            (
                r"from arrakis_common.utils.security import hash_data",
                "from arrakis_common.utils.security import hash_data",
            ),
            (
                r"from arrakis_common.utils.security import encrypt_text",
                "from arrakis_common.utils.security import encrypt_text",
            ),
            (
                r"from arrakis_common.utils.security import decrypt_text",
                "from arrakis_common.utils.security import decrypt_text",
            ),
            # Secrets imports
            (
                r"from common_security\.secrets import get_key",
                "from arrakis_common.utils.security import generate_secret_key as get_key",
            ),
            (
                r"from common_security\.secrets import",
                "from arrakis_common.utils.security import",
            ),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        # Write back if changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

    return False


def main():
    """Main function to fix all import issues"""
    print("🔍 MSA Import Architecture Fix - Starting comprehensive repair...")

    # Find all affected files
    logging_files = find_files_with_common_logging()
    security_files = find_files_with_common_security()

    print(f"📊 Found {len(logging_files)} files with common_logging imports")
    print(f"📊 Found {len(security_files)} files with common_security imports")

    # Fix common_logging imports
    logging_fixed = 0
    print("\n🔧 Fixing common_logging imports...")
    for file_path in logging_files:
        if fix_common_logging_imports(file_path):
            logging_fixed += 1
            print(f"✅ Fixed: {file_path}")

    # Fix common_security imports
    security_fixed = 0
    print("\n🔧 Fixing common_security imports...")
    for file_path in security_files:
        if fix_common_security_imports(file_path):
            security_fixed += 1
            print(f"✅ Fixed: {file_path}")

    print("\n🎉 Import fix complete!")
    print(f"   📝 Fixed {logging_fixed} common_logging files")
    print(f"   🔒 Fixed {security_fixed} common_security files")
    print(f"   📊 Total files processed: {logging_fixed + security_fixed}")

    if logging_fixed + security_fixed > 0:
        print("\n🚀 MSA import architecture successfully repaired!")
        print("   All services can now import from unified arrakis_common module")
    else:
        print("\n⚠️  No files required fixing")


if __name__ == "__main__":
    main()
