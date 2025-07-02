#!/bin/bash
# Architecture quality checks for CI pipeline

set -e

echo "=== Running Architecture Quality Checks ==="

# 1. Import Linter Check
echo "1. Checking import dependencies..."
if command -v import-linter &> /dev/null; then
    import-linter
else
    echo "⚠️  import-linter not installed, skipping..."
fi

# 2. Thread Lock Detection
echo -e "\n2. Detecting thread locks in async code..."
python scripts/ci/detect_thread_locks.py

# 3. God Object Detection
echo -e "\n3. Checking for God Objects (files > 800 lines)..."
large_files=$(find core api middleware -name "*.py" -type f -exec wc -l {} + | awk '$1 > 800 {print}' | grep -v "total" || true)

if [ -n "$large_files" ]; then
    echo "⚠️  Large files detected (potential God Objects):"
    echo "$large_files"
    echo "Consider refactoring these files using 3-layer architecture"
else
    echo "✅ No God Objects detected"
fi

# 4. Layer Structure Validation
echo -e "\n4. Validating 3-layer architecture..."
for module in "core/traversal/cache" "core/validation/enterprise"; do
    if [ -d "$module" ]; then
        if [ -d "$module/interfaces" ] && [ -d "$module/implementations" ] && [ -d "$module/services" ]; then
            echo "✅ $module follows 3-layer architecture"
        else
            echo "❌ $module missing required layers"
            exit 1
        fi
    fi
done

echo -e "\n=== Architecture checks completed ==="