"""
Validation rule registry implementation
"""

from typing import Dict, List, Set, Optional
import threading
import logging

from ..interfaces.contracts import ValidationRuleInterface
from ..interfaces.models import ValidationCategory, ValidationLevel

logger = logging.getLogger(__name__)


class ValidationRuleRegistry:
    """
    Thread-safe registry for validation rules
    """
    
    def __init__(self):
        self._rules: Dict[str, ValidationRuleInterface] = {}
        self._rules_by_category: Dict[ValidationCategory, List[str]] = {}
        self._rules_by_level: Dict[ValidationLevel, Set[str]] = {
            ValidationLevel.MINIMAL: set(),
            ValidationLevel.STANDARD: set(),
            ValidationLevel.STRICT: set(),
            ValidationLevel.PARANOID: set()
        }
        self._lock = threading.RLock()
        self._initialize_default_rule_sets()
    
    def register(self, rule: ValidationRuleInterface) -> None:
        """Register a validation rule"""
        with self._lock:
            rule_id = rule.get_rule_id()
            
            if rule_id in self._rules:
                logger.warning(f"Replacing existing rule: {rule_id}")
            
            self._rules[rule_id] = rule
            
            # Index by category
            category = rule.get_category()
            if category not in self._rules_by_category:
                self._rules_by_category[category] = []
            if rule_id not in self._rules_by_category[category]:
                self._rules_by_category[category].append(rule_id)
            
            # Assign to validation levels based on category
            self._assign_rule_to_levels(rule_id, category)
            
            logger.info(f"Registered validation rule: {rule_id}")
    
    def unregister(self, rule_id: str) -> bool:
        """Unregister a validation rule"""
        with self._lock:
            if rule_id not in self._rules:
                return False
            
            rule = self._rules[rule_id]
            category = rule.get_category()
            
            # Remove from main registry
            del self._rules[rule_id]
            
            # Remove from category index
            if category in self._rules_by_category:
                self._rules_by_category[category].remove(rule_id)
            
            # Remove from level assignments
            for level_rules in self._rules_by_level.values():
                level_rules.discard(rule_id)
            
            logger.info(f"Unregistered validation rule: {rule_id}")
            return True
    
    def get_rule(self, rule_id: str) -> Optional[ValidationRuleInterface]:
        """Get a specific rule by ID"""
        with self._lock:
            return self._rules.get(rule_id)
    
    def get_rules_for_level(self, level: ValidationLevel) -> List[ValidationRuleInterface]:
        """Get all rules applicable for a validation level"""
        with self._lock:
            rule_ids = self._rules_by_level.get(level, set())
            return [self._rules[rule_id] for rule_id in rule_ids if rule_id in self._rules]
    
    def get_rules_by_category(self, category: ValidationCategory) -> List[ValidationRuleInterface]:
        """Get all rules in a specific category"""
        with self._lock:
            rule_ids = self._rules_by_category.get(category, [])
            return [self._rules[rule_id] for rule_id in rule_ids if rule_id in self._rules]
    
    def get_all_rules(self) -> List[ValidationRuleInterface]:
        """Get all registered rules"""
        with self._lock:
            return list(self._rules.values())
    
    def _initialize_default_rule_sets(self):
        """Initialize default rule assignments to validation levels"""
        # This would be called during initialization to set up
        # which rules apply at which validation levels
        pass
    
    def _assign_rule_to_levels(self, rule_id: str, category: ValidationCategory):
        """Assign a rule to appropriate validation levels based on its category"""
        # MINIMAL: Only critical syntax rules
        if category == ValidationCategory.SYNTAX:
            self._rules_by_level[ValidationLevel.MINIMAL].add(rule_id)
        
        # STANDARD: Syntax + Business rules
        if category in [ValidationCategory.SYNTAX, ValidationCategory.BUSINESS]:
            self._rules_by_level[ValidationLevel.STANDARD].add(rule_id)
        
        # STRICT: All except paranoid security
        if category != ValidationCategory.SECURITY:
            self._rules_by_level[ValidationLevel.STRICT].add(rule_id)
        else:
            # Only basic security for STRICT
            self._rules_by_level[ValidationLevel.STRICT].add(rule_id)
        
        # PARANOID: Everything
        self._rules_by_level[ValidationLevel.PARANOID].add(rule_id)