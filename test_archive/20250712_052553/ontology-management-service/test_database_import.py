#!/usr/bin/env python3
"""Test database.clients import to diagnose the exact issue"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Python version:", sys.version)
print("Python path:")
for path in sys.path:
    print(f"  - {path}")

print("\nTesting imports...")

# Test 1: Import database module
try:
    import database
    print("✅ Successfully imported 'database'")
    print(f"   Location: {database.__file__ if hasattr(database, '__file__') else 'No __file__ attribute'}")
except Exception as e:
    print(f"❌ Failed to import 'database': {type(e).__name__}: {e}")

# Test 2: Import database.clients
try:
    import database.clients
    print("✅ Successfully imported 'database.clients'")
    print(f"   Location: {database.clients.__file__ if hasattr(database.clients, '__file__') else 'No __file__ attribute'}")
except Exception as e:
    print(f"❌ Failed to import 'database.clients': {type(e).__name__}: {e}")

# Test 3: Import specific client
try:
    from database.clients.unified_http_client import UnifiedHTTPClient
    print("✅ Successfully imported UnifiedHTTPClient")
except Exception as e:
    print(f"❌ Failed to import UnifiedHTTPClient: {type(e).__name__}: {e}")

# Test 4: Check directory structure
print("\nDirectory structure check:")
db_dir = os.path.join(os.path.dirname(__file__), "database")
if os.path.exists(db_dir):
    print(f"✅ database/ directory exists at: {db_dir}")
    clients_dir = os.path.join(db_dir, "clients")
    if os.path.exists(clients_dir):
        print(f"✅ database/clients/ directory exists at: {clients_dir}")
        print("   Files in database/clients/:")
        for file in os.listdir(clients_dir):
            print(f"     - {file}")
    else:
        print("❌ database/clients/ directory does not exist")
else:
    print("❌ database/ directory does not exist")

# Test 5: Check if running from wrong directory
cwd = os.getcwd()
print(f"\nCurrent working directory: {cwd}")
if "/app" in sys.path[0] or cwd == "/app":
    print("⚠️  WARNING: Script is looking for modules in /app directory")
    print("   This suggests you're running in a Docker container context")
    print("   but the files are in a different location.")