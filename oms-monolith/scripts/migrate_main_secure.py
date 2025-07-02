#!/usr/bin/env python3
"""
Migration script for main_secure.py
Demonstrates the migration pattern from os.getenv() to unified_env
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import unified_env


def show_migration_example():
    """Show before and after migration examples"""
    
    print("=" * 80)
    print("MIGRATION EXAMPLE: main_secure.py")
    print("=" * 80)
    print()
    
    print("BEFORE (Line 262):")
    print('    "environment": os.getenv("ENVIRONMENT", "production"),')
    print()
    
    print("AFTER:")
    print('    "environment": unified_env.get("ENVIRONMENT", namespace="core").value,')
    print()
    
    print("Alternative patterns:")
    print()
    
    print("1. Simple get with default handling:")
    print('    from shared.config import get_env')
    print('    environment = get_env("ENVIRONMENT", "production")')
    print()
    
    print("2. Required variable (will fail if not set):")
    print('    from shared.config import require_env')
    print('    jwt_secret = require_env("JWT_SECRET")')
    print()
    
    print("3. With validation:")
    print('    # The unified_env system automatically validates based on the')
    print('    # variable definition in namespace_configs.py')
    print()
    
    print("=" * 80)
    print("FULL MIGRATION STEPS:")
    print("=" * 80)
    print()
    
    print("1. Update imports:")
    print("   - Remove: import os")
    print("   - Add: from shared.config import unified_env, get_env")
    print()
    
    print("2. Replace os.getenv() calls:")
    print("   - os.getenv('VAR') → unified_env.get('VAR')")
    print("   - os.getenv('VAR', default) → get_env('VAR', default)")
    print()
    
    print("3. Update environment detection:")
    print("   - The unified_env system returns typed values")
    print("   - ENVIRONMENT returns an Environment enum, not a string")
    print()
    
    print("4. Test the migration:")
    print("   - Ensure all required variables are defined in namespace_configs.py")
    print("   - Run with validate_env() to check configuration")
    print()


def generate_migration_patch():
    """Generate a patch file for the migration"""
    
    patch_content = """--- a/main_secure.py
+++ b/main_secure.py
@@ -11,7 +11,6 @@
 
 This replaces simple_main.py with enterprise-grade, life-critical implementation.
 """
-import os
 import asyncio
 from datetime import datetime, timezone
 from fastapi import FastAPI, HTTPException, Depends, Request
@@ -22,7 +21,7 @@ from typing import Optional, Dict, Any
 
 # Early environment validation before any other imports
-from shared.config import validate_env
+from shared.config import validate_env, unified_env, get_env
 # Validate environment at import time - fail fast for life-critical system
 validate_env(fail_fast=True)
 
@@ -259,7 +258,7 @@ async def health_check():
         "service": "oms-life-critical",
         "timestamp": datetime.now(timezone.utc).isoformat(),
         "version": "1.0.0-life-critical",
-        "environment": os.getenv("ENVIRONMENT", "production"),
+        "environment": get_env("ENVIRONMENT", "production"),
         "features": {
             "circuit_breaker": "ENABLED (10 success threshold)",
             "case_insensitive_env": "ENABLED",
"""
    
    with open("main_secure_migration.patch", "w") as f:
        f.write(patch_content)
    
    print("Generated migration patch: main_secure_migration.patch")
    print()
    print("Apply with: git apply main_secure_migration.patch")


def check_current_usage():
    """Check current environment variable usage in main_secure.py"""
    
    print("=" * 80)
    print("CURRENT USAGE ANALYSIS")
    print("=" * 80)
    print()
    
    main_secure_path = Path("main_secure.py")
    if not main_secure_path.exists():
        print("ERROR: main_secure.py not found")
        return
    
    with open(main_secure_path, "r") as f:
        lines = f.readlines()
    
    env_vars_found = []
    for i, line in enumerate(lines, 1):
        if "os.getenv" in line:
            env_vars_found.append((i, line.strip()))
    
    print(f"Found {len(env_vars_found)} os.getenv() calls:")
    for line_no, line in env_vars_found:
        print(f"  Line {line_no}: {line}")
    
    print()
    
    # Extract variable names
    import re
    var_pattern = r'os\.getenv\(["\']([^"\']+)["\']'
    
    variables = []
    for _, line in env_vars_found:
        matches = re.findall(var_pattern, line)
        variables.extend(matches)
    
    print("Environment variables used:")
    for var in set(variables):
        print(f"  - {var}")
    
    print()
    print("These variables should be defined in namespace_configs.py")
    print("in the appropriate namespace (likely 'core' for ENVIRONMENT)")


def main():
    """Main migration helper"""
    print("main_secure.py Migration Helper")
    print()
    
    # Show current usage
    check_current_usage()
    
    # Show migration example
    show_migration_example()
    
    # Generate patch
    generate_migration_patch()
    
    print()
    print("Next steps:")
    print("1. Review the generated patch file")
    print("2. Ensure ENVIRONMENT is defined in the core namespace in namespace_configs.py")
    print("3. Apply the patch and test the application")
    print("4. Run validation: python -c 'from shared.config import validate_env; validate_env()'")


if __name__ == "__main__":
    main()