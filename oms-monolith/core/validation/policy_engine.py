"""
P2 Phase: Rule Policy Engine
FAIL/WARN/ALERT 정책 시스템 with CI/Runtime 컨텍스트 분리

REQ-P2-3: Configurable rule policy system for different execution contexts
"""

import logging
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import os

from core.validation.models import Severity, ValidationContext, BreakingChange, MigrationStrategy
from core.validation.rules.base import RuleResult

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    """Policy actions for rule violations"""
    FAIL = "fail"         # Fail immediately, stop processing
    WARN = "warn"         # Log warning, continue processing  
    ALERT = "alert"       # Send alert, continue processing
    IGNORE = "ignore"     # Silently ignore violation
    CUSTOM = "custom"     # Custom action defined by handler


class ExecutionContext(str, Enum):
    """Execution contexts with different policy defaults"""
    CI_BUILD = "ci_build"           # CI/CD build pipelines
    CI_PR = "ci_pr"                 # Pull request validation
    RUNTIME_BATCH = "runtime_batch" # Batch processing
    RUNTIME_STREAM = "runtime_stream" # Stream processing
    DEVELOPMENT = "development"     # Development environment
    PRODUCTION = "production"       # Production environment
    TESTING = "testing"            # Test execution


@dataclass
class PolicyRule:
    """Individual policy rule definition"""
    rule_pattern: str                    # Rule ID pattern (supports wildcards)
    severity_threshold: Severity         # Minimum severity to trigger
    action: PolicyAction                 # Action to take
    context: Optional[ExecutionContext] = None  # Specific context (None = all contexts)
    custom_handler: Optional[str] = None # Custom handler function name
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyConfig:
    """Complete policy configuration"""
    context: ExecutionContext
    default_action: PolicyAction = PolicyAction.WARN
    rules: List[PolicyRule] = field(default_factory=list)
    global_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Context-specific overrides
    fail_fast: bool = False              # Stop on first FAIL action
    max_warnings: int = 100              # Maximum warnings before FAIL
    max_alerts: int = 50                 # Maximum alerts before FAIL
    enable_notifications: bool = True     # Enable external notifications


class PolicyEngine:
    """
    Rule Policy Engine
    
    Applies configurable policies to rule results based on execution context.
    Supports multiple policy sources and context-specific defaults.
    
    Features:
    - Context-aware policy application
    - Pattern-based rule matching  
    - Configurable fail-fast behavior
    - External notification integration
    - Policy override capability
    - Comprehensive result tracking
    """
    
    def __init__(
        self,
        context: ExecutionContext,
        config_source: Optional[str] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None
    ):
        self.context = context
        self.config = self._load_policy_config(config_source, runtime_overrides)
        self.execution_stats = {
            "rules_processed": 0,
            "actions_taken": {action.value: 0 for action in PolicyAction},
            "failures": [],
            "warnings": [],
            "alerts": []
        }
        
        # Custom handlers registry
        self._custom_handlers: Dict[str, callable] = {}
        self._register_default_handlers()
    
    def _load_policy_config(
        self, 
        config_source: Optional[str], 
        runtime_overrides: Optional[Dict[str, Any]]
    ) -> PolicyConfig:
        """Load policy configuration from source with runtime overrides"""
        
        # Start with context-specific defaults
        config = self._get_default_policy_config(self.context)
        
        # Load from config file if specified
        if config_source:
            try:
                file_config = self._load_config_from_file(config_source)
                config = self._merge_configs(config, file_config)
            except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load policy config from {config_source}: {e}")
        
        # Apply runtime overrides
        if runtime_overrides:
            config = self._apply_runtime_overrides(config, runtime_overrides)
        
        return config
    
    def _get_default_policy_config(self, context: ExecutionContext) -> PolicyConfig:
        """Get default policy configuration for execution context"""
        
        if context == ExecutionContext.CI_BUILD:
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.FAIL,
                fail_fast=True,
                max_warnings=10,
                max_alerts=5,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.FAIL),
                    PolicyRule("*", Severity.HIGH, PolicyAction.FAIL),  
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.IGNORE),
                ]
            )
        
        elif context == ExecutionContext.CI_PR:
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.WARN,
                fail_fast=False,
                max_warnings=50,
                max_alerts=20,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.FAIL),
                    PolicyRule("*", Severity.HIGH, PolicyAction.WARN),
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.IGNORE),
                ]
            )
        
        elif context == ExecutionContext.RUNTIME_BATCH:
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.ALERT,
                fail_fast=False,
                max_warnings=1000,
                max_alerts=100,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.FAIL),
                    PolicyRule("*", Severity.HIGH, PolicyAction.ALERT),
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.IGNORE),
                ]
            )
        
        elif context == ExecutionContext.RUNTIME_STREAM:
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.ALERT,
                fail_fast=False,
                max_warnings=10000,
                max_alerts=1000,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.ALERT),  # Don't fail stream
                    PolicyRule("*", Severity.HIGH, PolicyAction.ALERT),
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.IGNORE),
                ]
            )
        
        elif context == ExecutionContext.PRODUCTION:
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.ALERT,
                fail_fast=False,
                max_warnings=500,
                max_alerts=50,
                enable_notifications=True,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.ALERT),
                    PolicyRule("*", Severity.HIGH, PolicyAction.ALERT),
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.WARN),
                ]
            )
        
        else:  # DEVELOPMENT, TESTING, default
            return PolicyConfig(
                context=context,
                default_action=PolicyAction.WARN,
                fail_fast=False,
                max_warnings=1000,
                max_alerts=100,
                rules=[
                    PolicyRule("*", Severity.CRITICAL, PolicyAction.WARN),
                    PolicyRule("*", Severity.HIGH, PolicyAction.WARN),
                    PolicyRule("*", Severity.MEDIUM, PolicyAction.WARN),
                    PolicyRule("*", Severity.LOW, PolicyAction.IGNORE),
                ]
            )
    
    def _load_config_from_file(self, config_path: str) -> PolicyConfig:
        """Load policy config from YAML/JSON file"""
        # Implementation would load from actual config file
        # For now, return empty config
        return PolicyConfig(context=self.context)
    
    def _merge_configs(self, base: PolicyConfig, override: PolicyConfig) -> PolicyConfig:
        """Merge two policy configurations"""
        # Simple merge - override rules replace base rules
        merged = PolicyConfig(
            context=base.context,
            default_action=override.default_action if override.default_action != PolicyAction.WARN else base.default_action,
            rules=override.rules if override.rules else base.rules,
            fail_fast=override.fail_fast if hasattr(override, 'fail_fast') else base.fail_fast,
            max_warnings=override.max_warnings if hasattr(override, 'max_warnings') else base.max_warnings,
            max_alerts=override.max_alerts if hasattr(override, 'max_alerts') else base.max_alerts
        )
        return merged
    
    def _apply_runtime_overrides(self, config: PolicyConfig, overrides: Dict[str, Any]) -> PolicyConfig:
        """Apply runtime overrides to policy config"""
        if "default_action" in overrides:
            config.default_action = PolicyAction(overrides["default_action"])
        
        if "fail_fast" in overrides:
            config.fail_fast = bool(overrides["fail_fast"])
        
        if "max_warnings" in overrides:
            config.max_warnings = int(overrides["max_warnings"])
        
        if "max_alerts" in overrides:
            config.max_alerts = int(overrides["max_alerts"])
        
        return config
    
    def apply_policy(self, rule_results: List[RuleResult]) -> Dict[str, Any]:
        """Apply policy to rule results and return action summary"""
        
        policy_result = {
            "should_fail": False,
            "should_continue": True,
            "actions_taken": [],
            "summary": {
                "total_rules": len(rule_results),
                "failures": 0,
                "warnings": 0,
                "alerts": 0,
                "ignored": 0
            },
            "messages": []
        }
        
        for rule_result in rule_results:
            self.execution_stats["rules_processed"] += 1
            
            # Get rule_id from metadata if available
            rule_id = rule_result.metadata.get("rule_id", "unknown_rule")
            
            # Process breaking changes in this rule result
            for breaking_change in rule_result.breaking_changes:
                action = self._determine_action(rule_id, breaking_change)
                action_result = self._execute_action(action, rule_result, breaking_change)
                
                policy_result["actions_taken"].append(action_result)
                # Increment counter for action type
                action_name = action_result["action"]
                if action_name == "fail":
                    policy_result["summary"]["failures"] += 1
                elif action_name == "warn":
                    policy_result["summary"]["warnings"] += 1
                elif action_name == "alert":
                    policy_result["summary"]["alerts"] += 1
                elif action_name == "ignore":
                    policy_result["summary"]["ignored"] += 1
                
                if action_result.get("message"):
                    policy_result["messages"].append(action_result["message"])
                
                # Check for fail-fast
                if action == PolicyAction.FAIL:
                    policy_result["should_fail"] = True
                    if self.config.fail_fast:
                        policy_result["should_continue"] = False
                        break
            
            if not policy_result["should_continue"]:
                break
        
        # Check threshold limits
        if (self.execution_stats["actions_taken"]["warn"] > self.config.max_warnings or
            self.execution_stats["actions_taken"]["alert"] > self.config.max_alerts):
            policy_result["should_fail"] = True
            policy_result["messages"].append(
                f"Exceeded policy thresholds: warnings={self.execution_stats['actions_taken']['warn']}, "
                f"alerts={self.execution_stats['actions_taken']['alert']}"
            )
        
        return policy_result
    
    def _determine_action(self, rule_id: str, breaking_change: BreakingChange) -> PolicyAction:
        """Determine policy action for a specific rule and breaking change"""
        
        # Find matching policy rule
        for policy_rule in self.config.rules:
            if self._matches_pattern(rule_id, policy_rule.rule_pattern):
                if (policy_rule.context is None or policy_rule.context == self.context):
                    if breaking_change.severity.value >= policy_rule.severity_threshold.value:
                        return policy_rule.action
        
        # No specific rule found, use default
        return self.config.default_action
    
    def _matches_pattern(self, rule_id: str, pattern: str) -> bool:
        """Check if rule ID matches pattern (supports wildcards)"""
        if pattern == "*":
            return True
        
        if "*" in pattern:
            # Simple wildcard matching
            parts = pattern.split("*")
            if len(parts) == 2:
                prefix, suffix = parts
                return rule_id.startswith(prefix) and rule_id.endswith(suffix)
        
        return rule_id == pattern
    
    def _execute_action(
        self, 
        action: PolicyAction, 
        rule_result: RuleResult, 
        breaking_change: BreakingChange
    ) -> Dict[str, Any]:
        """Execute policy action and return result"""
        
        rule_id = rule_result.metadata.get("rule_id", "unknown_rule")
        action_result = {
            "action": action.value,
            "rule_id": rule_id,
            "severity": breaking_change.severity.value,
            "description": breaking_change.description,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.execution_stats["actions_taken"][action.value] += 1
        
        if action == PolicyAction.FAIL:
            message = f"POLICY FAILURE: {rule_id} - {breaking_change.description}"
            logger.error(message)
            action_result["message"] = message
            self.execution_stats["failures"].append(action_result)
        
        elif action == PolicyAction.WARN:
            message = f"POLICY WARNING: {rule_id} - {breaking_change.description}"
            logger.warning(message)
            action_result["message"] = message
            self.execution_stats["warnings"].append(action_result)
        
        elif action == PolicyAction.ALERT:
            message = f"POLICY ALERT: {rule_id} - {breaking_change.description}"
            logger.warning(message)
            action_result["message"] = message
            self.execution_stats["alerts"].append(action_result)
            
            # Send external alert if enabled
            if self.config.enable_notifications:
                self._send_alert_notification(rule_result, breaking_change)
        
        elif action == PolicyAction.IGNORE:
            logger.debug(f"POLICY IGNORE: {rule_id} - {breaking_change.description}")
        
        elif action == PolicyAction.CUSTOM:
            # Execute custom handler
            handler_name = self._find_custom_handler(rule_id)
            if handler_name and handler_name in self._custom_handlers:
                try:
                    custom_result = self._custom_handlers[handler_name](rule_result, breaking_change)
                    action_result.update(custom_result)
                except (RuntimeError, ValueError, TypeError) as e:
                    logger.error(f"Custom handler {handler_name} failed: {e}")
                    action_result["error"] = str(e)
        
        return action_result
    
    def _find_custom_handler(self, rule_id: str) -> Optional[str]:
        """Find custom handler for rule"""
        for policy_rule in self.config.rules:
            if (self._matches_pattern(rule_id, policy_rule.rule_pattern) and 
                policy_rule.action == PolicyAction.CUSTOM):
                return policy_rule.custom_handler
        return None
    
    def _send_alert_notification(self, rule_result: RuleResult, breaking_change: BreakingChange):
        """Send external alert notification"""
        # Integration with alerting system (Slack, email, etc.)
        # For now, just log
        rule_id = rule_result.metadata.get("rule_id", "unknown_rule")
        logger.info(f"EXTERNAL ALERT: {rule_id} - {breaking_change.description}")
    
    def _register_default_handlers(self):
        """Register default custom handlers"""
        
        def foundry_compliance_handler(rule_result: RuleResult, breaking_change: BreakingChange) -> Dict[str, Any]:
            """Custom handler for Foundry compliance violations"""
            return {
                "custom_action": "foundry_compliance_check",
                "compliance_status": "violation_detected",
                "remediation_required": True
            }
        
        def performance_degradation_handler(rule_result: RuleResult, breaking_change: BreakingChange) -> Dict[str, Any]:
            """Custom handler for performance issues"""
            return {
                "custom_action": "performance_analysis",
                "monitoring_enabled": True,
                "auto_scaling_triggered": True
            }
        
        self._custom_handlers.update({
            "foundry_compliance": foundry_compliance_handler,
            "performance_degradation": performance_degradation_handler
        })
    
    def register_custom_handler(self, name: str, handler: callable):
        """Register a custom policy handler"""
        self._custom_handlers[name] = handler
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            **self.execution_stats,
            "config_context": self.context.value,
            "total_actions": sum(self.execution_stats["actions_taken"].values())
        }
    
    def reset_stats(self):
        """Reset execution statistics"""
        self.execution_stats = {
            "rules_processed": 0,
            "actions_taken": {action.value: 0 for action in PolicyAction},
            "failures": [],
            "warnings": [],
            "alerts": []
        }


# Environment-based policy factory
def create_policy_engine_from_env() -> PolicyEngine:
    """Create policy engine based on environment variables"""
    
    # Determine context from environment
    context = ExecutionContext.DEVELOPMENT  # Default
    
    if os.getenv("CI") == "true":
        if os.getenv("GITHUB_EVENT_NAME") == "pull_request":
            context = ExecutionContext.CI_PR
        else:
            context = ExecutionContext.CI_BUILD
    elif os.getenv("ENVIRONMENT") == "production":
        context = ExecutionContext.PRODUCTION
    elif os.getenv("RUNTIME_MODE") == "batch":
        context = ExecutionContext.RUNTIME_BATCH
    elif os.getenv("RUNTIME_MODE") == "stream":
        context = ExecutionContext.RUNTIME_STREAM
    
    # Runtime overrides from environment
    overrides = {}
    if os.getenv("POLICY_FAIL_FAST"):
        overrides["fail_fast"] = os.getenv("POLICY_FAIL_FAST").lower() == "true"
    if os.getenv("POLICY_MAX_WARNINGS"):
        overrides["max_warnings"] = int(os.getenv("POLICY_MAX_WARNINGS"))
    if os.getenv("POLICY_MAX_ALERTS"):
        overrides["max_alerts"] = int(os.getenv("POLICY_MAX_ALERTS"))
    if os.getenv("POLICY_DEFAULT_ACTION"):
        overrides["default_action"] = os.getenv("POLICY_DEFAULT_ACTION")
    
    config_file = os.getenv("POLICY_CONFIG_FILE")
    
    return PolicyEngine(
        context=context,
        config_source=config_file,
        runtime_overrides=overrides if overrides else None
    )


# Factory functions for common use cases
def create_ci_policy_engine(fail_fast: bool = True) -> PolicyEngine:
    """Create policy engine for CI/CD environments"""
    return PolicyEngine(
        context=ExecutionContext.CI_BUILD,
        runtime_overrides={"fail_fast": fail_fast}
    )


def create_production_policy_engine(enable_notifications: bool = True) -> PolicyEngine:
    """Create policy engine for production environments"""
    config = PolicyConfig(
        context=ExecutionContext.PRODUCTION,
        enable_notifications=enable_notifications
    )
    return PolicyEngine(ExecutionContext.PRODUCTION)


def create_development_policy_engine() -> PolicyEngine:
    """Create policy engine for development environments"""
    return PolicyEngine(ExecutionContext.DEVELOPMENT)