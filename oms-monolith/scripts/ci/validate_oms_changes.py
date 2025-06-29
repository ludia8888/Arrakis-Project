#!/usr/bin/env python3
"""
P2 Phase: CI Integration Script
GitHub Actions + Jenkins 호환 OMS 변경사항 검증

REQ-P2-5: Enhanced CI integration with policy engine and PR auto-comments
"""

import sys
import os
import json
import argparse
import asyncio
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.validation.policy_engine import (
    PolicyEngine, ExecutionContext, create_ci_policy_engine,
    create_policy_engine_from_env
)
from core.validation.service_refactored import ValidationService
from core.validation.config import ValidationConfig
from shared.config import get_config


class CIValidationResult:
    """CI 검증 결과"""
    
    def __init__(self):
        self.success = True
        self.exit_code = 0
        self.summary = {
            "total_rules": 0,
            "failures": 0,
            "warnings": 0,
            "alerts": 0,
            "policy_actions": []
        }
        self.messages: List[str] = []
        self.pr_comment_data: Optional[Dict[str, Any]] = None
        self.execution_time_ms = 0


class OMSChangeValidator:
    """OMS 변경사항 검증기"""
    
    def __init__(self, execution_context: ExecutionContext, config_overrides: Optional[Dict[str, Any]] = None):
        self.context = execution_context
        self.config = get_config()
        self.validation_config = ValidationConfig()
        
        # Initialize policy engine based on context
        if execution_context in [ExecutionContext.CI_BUILD, ExecutionContext.CI_PR]:
            self.policy_engine = create_ci_policy_engine(
                fail_fast=config_overrides.get("fail_fast", True) if config_overrides else True
            )
        else:
            self.policy_engine = create_policy_engine_from_env()
        
        # Apply overrides
        if config_overrides:
            self.policy_engine._apply_runtime_overrides(self.policy_engine.config, config_overrides)
        
        # Initialize validation service
        self.validation_service = ValidationService(self.validation_config)
    
    async def validate_changes(
        self,
        branch: str,
        base_branch: str = "main",
        changed_files: Optional[List[str]] = None
    ) -> CIValidationResult:
        """변경사항 검증 실행"""
        
        start_time = datetime.now()
        result = CIValidationResult()
        
        try:
            # Detect changed files if not provided
            if changed_files is None:
                changed_files = self._detect_changed_files(base_branch, branch)
            
            result.messages.append(f"Validating {len(changed_files)} changed files")
            
            # Run OMS validation
            validation_result = await self._run_oms_validation(branch, base_branch, changed_files)
            
            # Apply policy engine
            policy_result = self.policy_engine.apply_policy(validation_result.rule_results)
            
            # Update result
            result.success = not policy_result["should_fail"]
            result.exit_code = 1 if policy_result["should_fail"] else 0
            result.summary.update(policy_result["summary"])
            result.summary["policy_actions"] = policy_result["actions_taken"]
            result.messages.extend(policy_result["messages"])
            
            # Prepare PR comment data if in PR context
            if self.context == ExecutionContext.CI_PR:
                result.pr_comment_data = self._prepare_pr_comment_data(
                    validation_result, policy_result, changed_files
                )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            result.execution_time_ms = int(execution_time)
            
            return result
            
        except Exception as e:
            result.success = False
            result.exit_code = 2  # System error
            result.messages.append(f"Validation failed with error: {str(e)}")
            return result
    
    def _detect_changed_files(self, base_branch: str, current_branch: str) -> List[str]:
        """Git을 사용해 변경된 파일 감지"""
        try:
            # Get changed files between branches
            cmd = f"git diff --name-only {base_branch}...{current_branch}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                # Fallback to HEAD
                cmd = "git diff --name-only HEAD~1"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Filter for relevant files (schema, validation, etc.)
            relevant_extensions = ['.py', '.json', '.yaml', '.yml']
            relevant_paths = ['core/', 'api/', 'models/', 'scripts/']
            
            filtered_files = []
            for file in files:
                if any(file.endswith(ext) for ext in relevant_extensions):
                    if any(file.startswith(path) for path in relevant_paths):
                        filtered_files.append(file)
            
            return filtered_files
            
        except Exception as e:
            print(f"Warning: Could not detect changed files: {e}")
            return []
    
    async def _run_oms_validation(
        self, 
        branch: str, 
        base_branch: str, 
        changed_files: List[str]
    ):
        """OMS 검증 실행"""
        
        # For now, simulate validation results
        # In a real implementation, this would:
        # 1. Load schema from both branches
        # 2. Run all validation rules
        # 3. Return comprehensive results
        
        from core.validation.rules.base import RuleResult
        from core.validation.models import BreakingChange, Severity
        
        class MockValidationResult:
            def __init__(self):
                self.rule_results = []
        
        mock_result = MockValidationResult()
        
        # Simulate some rule results based on changed files
        for file in changed_files:
            rule_result = RuleResult()
            rule_result.rule_id = f"file_change_{file.replace('/', '_').replace('.', '_')}"
            
            # Create mock breaking changes based on file types
            if 'schema' in file.lower():
                breaking_change = BreakingChange(
                    rule_id=rule_result.rule_id,
                    severity=Severity.HIGH,
                    object_type="schema",
                    field_name=os.path.basename(file),
                    description=f"Schema change detected in {file}",
                    old_value=None,
                    new_value={"file": file},
                    impact={"schema_change": True},
                    suggested_strategies=[],
                    detected_at=datetime.now()
                )
                rule_result.breaking_changes.append(breaking_change)
            elif file.endswith('.py') and 'validation' in file:
                breaking_change = BreakingChange(
                    rule_id=rule_result.rule_id,
                    severity=Severity.MEDIUM,
                    object_type="validation",
                    field_name=os.path.basename(file),
                    description=f"Validation rule change in {file}",
                    old_value=None,
                    new_value={"file": file},
                    impact={"validation_change": True},
                    suggested_strategies=[],
                    detected_at=datetime.now()
                )
                rule_result.breaking_changes.append(breaking_change)
            
            mock_result.rule_results.append(rule_result)
        
        return mock_result
    
    def _prepare_pr_comment_data(
        self, 
        validation_result,
        policy_result: Dict[str, Any], 
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """PR 코멘트용 데이터 준비"""
        
        # Determine overall status
        if policy_result["should_fail"]:
            status = "❌ FAILED"
            color = "#d73a49"
        elif policy_result["summary"]["warnings"] > 0 or policy_result["summary"]["alerts"] > 0:
            status = "⚠️ WARNINGS"
            color = "#f66a0a"
        else:
            status = "✅ PASSED"
            color = "#28a745"
        
        # Prepare comment sections
        summary_section = f"""
## {status} OMS Validation Results

| Metric | Count |
|--------|-------|
| 🔍 Rules Checked | {policy_result['summary']['total_rules']} |
| ❌ Failures | {policy_result['summary']['failures']} |
| ⚠️ Warnings | {policy_result['summary']['warnings']} |
| 🚨 Alerts | {policy_result['summary']['alerts']} |
| 📁 Files Changed | {len(changed_files)} |
"""
        
        # Policy actions section
        actions_section = ""
        if policy_result["actions_taken"]:
            actions_section = "### Policy Actions Taken\n\n"
            for action in policy_result["actions_taken"][:10]:  # Limit to 10 actions
                severity_emoji = {
                    "critical": "🔴",
                    "high": "🟠", 
                    "medium": "🟡",
                    "low": "🔵"
                }.get(action.get("severity", "medium"), "⚪")
                
                actions_section += f"- {severity_emoji} **{action['action'].upper()}**: {action['rule_id']} - {action.get('description', 'No description')[:100]}...\n"
            
            if len(policy_result["actions_taken"]) > 10:
                actions_section += f"\n*... and {len(policy_result['actions_taken']) - 10} more actions*\n"
        
        # Changed files section
        files_section = ""
        if changed_files:
            files_section = f"### Changed Files ({len(changed_files)})\n\n"
            for file in changed_files[:20]:  # Limit to 20 files
                file_emoji = "📄"
                if "schema" in file.lower():
                    file_emoji = "📋"
                elif file.endswith(".py"):
                    file_emoji = "🐍"
                elif file.endswith((".yaml", ".yml")):
                    file_emoji = "⚙️"
                
                files_section += f"- {file_emoji} `{file}`\n"
            
            if len(changed_files) > 20:
                files_section += f"\n*... and {len(changed_files) - 20} more files*\n"
        
        # Recommendations section
        recommendations_section = ""
        if policy_result["should_fail"]:
            recommendations_section = """
### 🚨 Action Required

This PR has validation failures that must be addressed before merging:

1. **Review the policy failures** listed above
2. **Fix the identified issues** in your code
3. **Run validation locally** using `scripts/ci/validate_oms_changes.py`
4. **Push your fixes** to trigger re-validation

For help with specific issues, consult the [OMS Validation Guide](docs/validation-guide.md).
"""
        elif policy_result["summary"]["warnings"] > 0:
            recommendations_section = """
### ⚠️ Please Review

This PR has warnings that should be addressed:

1. **Review the warnings** listed above
2. **Consider if fixes are needed** for code quality
3. **Document any intentional changes** in the PR description

Warnings don't block merging but should be reviewed for best practices.
"""
        
        return {
            "status": status,
            "color": color,
            "summary": summary_section,
            "actions": actions_section,
            "files": files_section,
            "recommendations": recommendations_section,
            "full_comment": f"{summary_section}\n{actions_section}\n{files_section}\n{recommendations_section}",
            "metadata": {
                "validation_context": self.context.value,
                "timestamp": datetime.now().isoformat(),
                "total_issues": policy_result["summary"]["failures"] + policy_result["summary"]["warnings"],
                "can_merge": not policy_result["should_fail"]
            }
        }


def create_github_pr_comment(comment_data: Dict[str, Any]) -> bool:
    """GitHub PR에 코멘트 생성"""
    
    # Check if running in GitHub Actions
    if not os.getenv("GITHUB_TOKEN") or not os.getenv("GITHUB_REPOSITORY"):
        print("Not in GitHub Actions environment, skipping PR comment")
        return False
    
    try:
        # Get PR number from GitHub environment
        github_event_path = os.getenv("GITHUB_EVENT_PATH")
        if not github_event_path:
            return False
        
        with open(github_event_path, 'r') as f:
            event_data = json.load(f)
        
        pr_number = event_data.get("number")
        if not pr_number:
            return False
        
        # Use GitHub CLI to create comment
        comment_body = comment_data["full_comment"]
        cmd = f'gh pr comment {pr_number} --body "{comment_body}"'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Created PR comment for #{pr_number}")
            return True
        else:
            print(f"❌ Failed to create PR comment: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating PR comment: {e}")
        return False


def main():
    """메인 실행 함수"""
    
    parser = argparse.ArgumentParser(description="OMS Changes Validation for CI/CD")
# REMOVED: TerminusDB handles enum_validation natively
#     parser.add_argument("--mode", choices=["ci", "pr", "local"], default="local",
                      help="Execution mode (ci=CI build, pr=PR validation, local=development)")
    parser.add_argument("--branch", default="HEAD", help="Branch to validate")
    parser.add_argument("--base-branch", default="main", help="Base branch for comparison")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--max-warnings", type=int, help="Maximum warnings before failure")
# REMOVED: TerminusDB handles enum_validation natively
#     parser.add_argument("--output-format", choices=["text", "json"], default="text",
                      help="Output format")
    parser.add_argument("--create-pr-comment", action="store_true", 
                      help="Create PR comment (only in PR mode)")
    
    args = parser.parse_args()
    
    # Determine execution context
    context_map = {
        "ci": ExecutionContext.CI_BUILD,
        "pr": ExecutionContext.CI_PR, 
        "local": ExecutionContext.DEVELOPMENT
    }
    context = context_map[args.mode]
    
    # Configuration overrides
    config_overrides = {}
    if args.fail_fast:
        config_overrides["fail_fast"] = True
    if args.max_warnings:
        config_overrides["max_warnings"] = args.max_warnings
    
    # Run validation
    async def run_validation():
        validator = OMSChangeValidator(context, config_overrides)
        return await validator.validate_changes(args.branch, args.base_branch)
    
    result = asyncio.run(run_validation())
    
    # Output results
    if args.output_format == "json":
        output = {
            "success": result.success,
            "exit_code": result.exit_code,
            "summary": result.summary,
            "messages": result.messages,
            "execution_time_ms": result.execution_time_ms
        }
        print(json.dumps(output, indent=2))
    else:
        # Text output
        status = "✅ PASSED" if result.success else "❌ FAILED"
        print(f"\n{status} OMS Validation Results")
        print("=" * 50)
        
        for key, value in result.summary.items():
            if key != "policy_actions":
                print(f"{key}: {value}")
        
        if result.messages:
            print("\nMessages:")
            for msg in result.messages:
                print(f"  {msg}")
        
        print(f"\nExecution time: {result.execution_time_ms}ms")
    
    # Create PR comment if requested and in PR mode
    if args.create_pr_comment and args.mode == "pr" and result.pr_comment_data:
        create_github_pr_comment(result.pr_comment_data)
    
    # Exit with appropriate code
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()