#!/usr/bin/env python3
"""
Test File Cleanup Executor
Performs aggressive cleanup of test files in the Arrakis project
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import json
import re

# ANSI colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class TestCleanupExecutor:
    def __init__(self, project_root: str, dry_run: bool = False):
        self.project_root = Path(project_root)
        self.dry_run = dry_run
        self.archive_dir = self.project_root / "test_archive" / datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define what to keep - these are the ONLY test files we want to keep
        self.essential_tests = {
            # Core test suites
            "enterprise_integration_test_suite.py",
            "production_level_test_suite.py",
            
            # Service-specific unit tests (in their respective directories)
            "user-service/tests/test_jwt.py",
            "user-service/tests/test_user_service.py",
            "user-service/tests/test_auth_service.py",
            "user-service/tests/test_validators.py",
            "user-service/tests/test_e2e.py",
            "user-service/tests/test_security.py",
            "user-service/tests/test_rate_limit.py",
            "user-service/tests/test_password_security.py",
            "user-service/tests/test_mfa_service.py",
            "user-service/tests/test_user_model.py",
            "user-service/test_role_service_fixed.py",
            
            "audit-service/tests/test_simple.py",
            "audit-service/tests/test_core_functionality.py",
            "audit-service/tests/test_integration.py",
            
            "ontology-management-service/tests/conftest.py",
            "ontology-management-service/tests/integration/test_time_travel_queries.py",
            "ontology-management-service/tests/integration/test_metadata_frames.py",
            "ontology-management-service/tests/integration/test_unfoldable_documents.py",
            "ontology-management-service/tests/integration/test_delta_encoding.py",
            "ontology-management-service/tests/unit/core/branch/test_branch_service.py",
            "ontology-management-service/tests/unit/core/schema/test_conflict_resolver.py",
            "ontology-management-service/tests/unit/core/versioning/test_merge_engine.py",
            
            # Keep recent important tests
            "test_alerting_system.py",
            "test_core_modules_health.py",
        }
        
        # Patterns for tests to merge into consolidated files
        self.merge_patterns = {
            "consolidated_auth_tests.py": [
                r"test_jwt.*\.py",
                r"test_token.*\.py",
                r"test_auth.*\.py",
                r"test_login.*\.py",
                r"test_decode.*\.py"
            ],
            "consolidated_integration_tests.py": [
                r"test_.*integration.*\.py",
                r"test_three_service.*\.py",
                r"test_full_.*\.py",
                r"test_comprehensive.*\.py"
            ],
            "consolidated_resilience_tests.py": [
                r"test_circuit.*\.py",
                r"test_.*resilience.*\.py",
                r"test_bulkhead.*\.py",
                r"test_retry.*\.py"
            ],
            "consolidated_monitoring_tests.py": [
                r"test_.*monitoring.*\.py",
                r"test_.*observability.*\.py",
                r"test_prometheus.*\.py",
                r"test_jaeger.*\.py",
                r"test_pyroscope.*\.py"
            ]
        }
        
        self.stats = {
            "total_files": 0,
            "kept": 0,
            "archived": 0,
            "merged": 0,
            "errors": 0
        }
        
    def execute_cleanup(self):
        """Execute the cleanup process"""
        print(f"{BOLD}{BLUE}Starting Test File Cleanup{RESET}")
        print(f"Dry run: {self.dry_run}")
        
        if not self.dry_run:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            
        # Find all test files
        test_files = self._find_all_test_files()
        self.stats["total_files"] = len(test_files)
        
        print(f"\nFound {len(test_files)} test files")
        
        # Process each file
        for test_file in test_files:
            self._process_file(test_file)
            
        # Create consolidated test files
        self._create_consolidated_tests()
        
        # Print summary
        self._print_summary()
        
    def _find_all_test_files(self) -> list:
        """Find all test files in the project"""
        test_files = []
        patterns = ["test_*.py", "*_test.py", "test*.py"]
        
        for pattern in patterns:
            for file in self.project_root.glob(f"**/{pattern}"):
                if self._should_process_file(file):
                    test_files.append(file)
                    
        return test_files
        
    def _should_process_file(self, file: Path) -> bool:
        """Check if file should be processed"""
        exclude_dirs = ["venv", "__pycache__", "node_modules", ".git", "test_archive"]
        
        for exclude in exclude_dirs:
            if exclude in str(file):
                return False
                
        return file.is_file() and file.suffix == ".py"
        
    def _process_file(self, file: Path):
        """Process individual test file"""
        relative_path = file.relative_to(self.project_root)
        
        # Check if it's an essential test
        if str(relative_path) in self.essential_tests or file.name in self.essential_tests:
            print(f"{GREEN}✓ Keeping:{RESET} {relative_path}")
            self.stats["kept"] += 1
            return
            
        # Archive the file
        self._archive_file(file)
        
    def _archive_file(self, file: Path):
        """Archive a test file"""
        relative_path = file.relative_to(self.project_root)
        archive_path = self.archive_dir / relative_path
        
        try:
            if not self.dry_run:
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(archive_path))
                print(f"{YELLOW}→ Archived:{RESET} {relative_path}")
            else:
                print(f"{YELLOW}→ Would archive:{RESET} {relative_path}")
                
            self.stats["archived"] += 1
        except Exception as e:
            print(f"{RED}✗ Error archiving {relative_path}: {e}{RESET}")
            self.stats["errors"] += 1
            
    def _create_consolidated_tests(self):
        """Create consolidated test files from patterns"""
        print(f"\n{BOLD}Creating Consolidated Test Files{RESET}")
        
        for consolidated_name, patterns in self.merge_patterns.items():
            content = self._generate_consolidated_content(consolidated_name, patterns)
            
            if content and not self.dry_run:
                consolidated_path = self.project_root / consolidated_name
                with open(consolidated_path, 'w') as f:
                    f.write(content)
                print(f"{GREEN}✓ Created:{RESET} {consolidated_name}")
                
    def _generate_consolidated_content(self, name: str, patterns: list) -> str:
        """Generate content for consolidated test file"""
        # This is a template - in reality, you'd merge actual test content
        category = name.replace("consolidated_", "").replace("_tests.py", "")
        
        return f'''#!/usr/bin/env python3
"""
Consolidated {category.title()} Tests
Generated on {datetime.now().isoformat()}
"""

import pytest
import asyncio
from typing import Any, Dict

# TODO: Merge test functions from archived files matching patterns:
# {', '.join(patterns)}

class Test{category.title().replace("_", "")}:
    """Consolidated {category} test suite"""
    
    @pytest.fixture
    async def setup(self):
        """Setup for tests"""
        # Add setup code here
        pass
        
    async def test_placeholder(self, setup):
        """Placeholder test - replace with actual merged tests"""
        assert True, "Replace this with actual test content"
        
# Add more test functions here from the archived files
'''
        
    def _print_summary(self):
        """Print cleanup summary"""
        print(f"\n{BOLD}{BLUE}Cleanup Summary{RESET}")
        print(f"{'='*60}")
        print(f"Total files processed: {self.stats['total_files']}")
        print(f"{GREEN}Kept:{RESET} {self.stats['kept']}")
        print(f"{YELLOW}Archived:{RESET} {self.stats['archived']}")
        print(f"{BLUE}Consolidated:{RESET} {len(self.merge_patterns)} files created")
        print(f"{RED}Errors:{RESET} {self.stats['errors']}")
        
        if not self.dry_run:
            print(f"\nArchived files moved to: {self.archive_dir}")
            
        # Create summary report
        summary = {
            "timestamp": datetime.now().isoformat(),
            "stats": self.stats,
            "archive_location": str(self.archive_dir),
            "essential_tests_kept": list(self.essential_tests),
            "consolidated_files_created": list(self.merge_patterns.keys())
        }
        
        summary_path = self.project_root / "test_cleanup_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"\nSummary saved to: {summary_path}")
        
        # Print recommendations
        print(f"\n{BOLD}Next Steps:{RESET}")
        print("1. Review the consolidated test files and add actual test content")
        print("2. Run the essential tests to ensure they still work")
        print("3. Update CI/CD pipelines to use the new test structure")
        print("4. Delete the archive directory once you're confident")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up test files in Arrakis project")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    parser.add_argument("--project-root", default="/Users/isihyeon/Desktop/Arrakis-Project", help="Project root directory")
    
    args = parser.parse_args()
    
    executor = TestCleanupExecutor(args.project_root, args.dry_run)
    executor.execute_cleanup()


if __name__ == "__main__":
    main()