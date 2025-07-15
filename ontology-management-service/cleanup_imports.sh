#!/bin/bash
# Automated import cleanup script

echo 'Starting import cleanup...'

# Remove unused imports
autoflake --remove-all-unused-imports --recursive --in-place \
  --exclude=tests/,scripts/,examples/,migrations/ \
  .

# Sort imports
isort --profile black --line-length 88 \
  --skip tests/ --skip scripts/ --skip examples/ --skip migrations/ \
  .

echo 'Import cleanup completed!'
