"""
Unified Merge Engine
Consolidates multiple merge implementations into one, using TerminusDB native merge
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from core.branch.models import MergeResult, MergeStrategy, Conflict
from shared.exceptions import ConflictError, ValidationError

logger = logging.getLogger(__name__)


class ConflictSeverity(Enum):
    """Conflict severity levels for domain validation"""
    INFO = "INFO"      # Safe, can be auto-resolved
    WARN = "WARN"      # Needs attention but can proceed
    ERROR = "ERROR"    # Must be manually resolved
    BLOCK = "BLOCK"    # Cannot proceed, violates critical rules


@dataclass
class DomainConflict:
    """Domain-specific conflict that TerminusDB wouldn't catch"""
    rule_name: str
    severity: ConflictSeverity
    description: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    resolution_hint: Optional[str] = None


class UnifiedMergeEngine:
    """
    Unified merge engine that:
    1. Uses TerminusDB native merge for structural conflicts
    2. Adds OMS domain-specific validation on top
    3. Replaces the 3 existing merge implementations
    """
    
    def __init__(self, terminus_client=None):
        """
        Initialize unified merge engine
        
        Args:
            terminus_client: TerminusDB client instance (will be injected)
        """
        self.terminus = terminus_client
        self.domain_rules = self._initialize_domain_rules()
        
    def _initialize_domain_rules(self) -> List[callable]:
        """Initialize OMS-specific domain validation rules"""
        return [
            self._check_cardinality_narrowing,
            self._check_required_field_removal,
            self._check_unique_constraint_conflicts,
            self._check_pii_field_exposure,
            self._check_breaking_interface_changes,
        ]
    
    async def merge(
        self,
        source_branch: str,
        target_branch: str,
        author: str,
        message: Optional[str] = None,
        strategy: MergeStrategy = MergeStrategy.MERGE
    ) -> MergeResult:
        """
        Perform merge using TerminusDB native merge + domain validation
        
        Args:
            source_branch: Source branch name
            target_branch: Target branch name
            author: Author of the merge
            message: Merge commit message
            strategy: Merge strategy to use
            
        Returns:
            MergeResult with status and any conflicts
        """
        logger.info(f"Unified merge: {source_branch} -> {target_branch} (strategy: {strategy})")
        
        try:
            # Step 1: Get diff to analyze changes
            diff = await self._get_terminus_diff(source_branch, target_branch)
            
            if not diff or not diff.get('changes'):
                return MergeResult(
                    conflicts=[],
                    merge_commit="no_changes"
                )
            
            # Step 2: Check domain-specific rules BEFORE attempting merge
            domain_conflicts = await self._validate_domain_rules(diff)
            
            # Block if critical domain violations
            blocking_conflicts = [c for c in domain_conflicts if c.severity == ConflictSeverity.BLOCK]
            if blocking_conflicts:
                return MergeResult(
                    conflicts=self._convert_domain_conflicts(blocking_conflicts),
                    merge_commit=None  # Indicates blocked
                )
            
            # Step 3: Apply merge strategy
            if strategy == MergeStrategy.SQUASH:
                return await self._squash_merge(source_branch, target_branch, author, message, domain_conflicts)
            elif strategy == MergeStrategy.REBASE:
                return await self._rebase_merge(source_branch, target_branch, author, message, domain_conflicts)
            else:
                # Standard merge using TerminusDB native
                return await self._standard_merge(source_branch, target_branch, author, message, domain_conflicts)
                
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return MergeResult(
                conflicts=[Conflict(
                    conflict_type="error",
                    resource_id="merge",
                    description=f"Merge failed: {str(e)}"
                )],
                merge_commit=None
            )
    
    async def _standard_merge(
        self,
        source: str,
        target: str,
        author: str,
        message: Optional[str],
        domain_conflicts: List[DomainConflict]
    ) -> MergeResult:
        """Standard merge using TerminusDB native merge"""
        try:
            # Let TerminusDB handle the actual merge
            merge_call = self.terminus.merge(
                source, 
                target,
                author=author,
                message=message or f"Merge {source} into {target}"
            )
            
            # Handle both sync and async
            if asyncio.iscoroutine(merge_call):
                result = await merge_call
            else:
                result = merge_call
            
            # Add any warnings from domain validation as non-blocking conflicts
            warnings = [c for c in domain_conflicts if c.severity == ConflictSeverity.WARN]
            
            return MergeResult(
                merge_commit=result.get("commit"),
                conflicts=self._convert_domain_conflicts(warnings) if warnings else []
            )
            
        except Exception as e:
            if "conflict" in str(e).lower():
                # TerminusDB detected structural conflicts
                return MergeResult(
                    conflicts=self._parse_terminus_conflicts(str(e)),
                    merge_commit=None
                )
            raise
    
    async def _squash_merge(
        self,
        source: str,
        target: str,
        author: str,
        message: Optional[str],
        domain_conflicts: List[DomainConflict]
    ) -> MergeResult:
        """Squash merge - combine all commits into one"""
        # Get all changes from source branch
        diff = await self._get_terminus_diff(target, source)
        
        # Apply all changes as a single commit on target
        # This is simplified - in practice would use TerminusDB operations
        squash_message = message or f"Squash merge {source} into {target}"
        
        # For now, use standard merge (TerminusDB doesn't have native squash)
        # In future, could implement by creating new commit with all changes
        return await self._standard_merge(source, target, author, squash_message, domain_conflicts)
    
    async def _rebase_merge(
        self,
        source: str,
        target: str,
        author: str,
        message: Optional[str],
        domain_conflicts: List[DomainConflict]
    ) -> MergeResult:
        """Rebase merge - replay source commits on top of target"""
        # TerminusDB has rebase functionality
        try:
            await self.terminus.rebase(source, target)
            
            # After rebase, do a fast-forward merge
            result = await self.terminus.merge(
                source,
                target,
                author=author,
                message=message or f"Rebase merge {source} into {target}"
            )
            
            warnings = [c for c in domain_conflicts if c.severity == ConflictSeverity.WARN]
            
            return MergeResult(
                status="success",
                commit_id=result.get("commit"),
                message="Rebased and merged successfully",
                warnings=[self._format_warning(w) for w in warnings] if warnings else None
            )
            
        except Exception as e:
            return MergeResult(
                status="error",
                message=f"Rebase failed: {str(e)}"
            )
    
    async def _get_terminus_diff(self, from_ref: str, to_ref: str) -> Dict[str, Any]:
        """Get diff using TerminusDB native diff"""
        if self.terminus:
            # Check if it's a coroutine
            result = self.terminus.diff(from_ref, to_ref)
            if asyncio.iscoroutine(result):
                return await result
            return result
        else:
            # Mock for testing
            return {"changes": []}
    
    async def _validate_domain_rules(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Apply OMS-specific domain validation rules"""
        conflicts = []
        
        for rule in self.domain_rules:
            rule_conflicts = await rule(diff)
            if rule_conflicts:
                conflicts.extend(rule_conflicts)
        
        return conflicts
    
    # Domain validation rules
    
    async def _check_cardinality_narrowing(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Check for cardinality narrowing (e.g., ONE_TO_MANY -> ONE_TO_ONE)"""
        conflicts = []
        
        for change in diff.get('changes', []):
            if change.get('@type') == 'Cardinality':
                old_card = change.get('@before', {}).get('cardinality')
                new_card = change.get('@after', {}).get('cardinality')
                
                if self._is_narrowing_cardinality(old_card, new_card):
                    conflicts.append(DomainConflict(
                        rule_name="prevent_cardinality_narrowing",
                        severity=ConflictSeverity.BLOCK,
                        description=f"Cannot narrow cardinality from {old_card} to {new_card}",
                        entity_id=change.get('@id'),
                        resolution_hint="Cardinality can only be widened, not narrowed"
                    ))
        
        return conflicts
    
    async def _check_required_field_removal(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Check for removal of required fields"""
        conflicts = []
        
        for change in diff.get('changes', []):
            if change.get('@type') == 'Property' and not change.get('@after'):
                # Property was removed
                before = change.get('@before', {})
                if before.get('required'):
                    conflicts.append(DomainConflict(
                        rule_name="prevent_required_field_removal",
                        severity=ConflictSeverity.ERROR,
                        description=f"Cannot remove required field: {before.get('name')}",
                        entity_type="Property",
                        entity_id=change.get('@id'),
                        resolution_hint="Make field optional before removing"
                    ))
        
        return conflicts
    
    async def _check_unique_constraint_conflicts(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Check for unique constraint modifications"""
        conflicts = []
        
        for change in diff.get('changes', []):
            if change.get('@type') == 'Property':
                before = change.get('@before', {})
                after = change.get('@after', {})
                
                # Removing unique constraint
                if before.get('unique') and not after.get('unique'):
                    conflicts.append(DomainConflict(
                        rule_name="unique_constraint_removal",
                        severity=ConflictSeverity.WARN,
                        description=f"Removing unique constraint from {after.get('name')}",
                        entity_type="Property",
                        entity_id=change.get('@id'),
                        resolution_hint="Ensure no duplicate data exists"
                    ))
        
        return conflicts
    
    async def _check_pii_field_exposure(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Check for PII field exposure changes"""
        conflicts = []
        
        # This would check for PII-related metadata changes
        # Simplified for now
        
        return conflicts
    
    async def _check_breaking_interface_changes(self, diff: Dict[str, Any]) -> List[DomainConflict]:
        """Check for breaking changes in interfaces"""
        conflicts = []
        
        # Check for interface removals or incompatible changes
        # Simplified for now
        
        return conflicts
    
    def _is_narrowing_cardinality(self, old_card: str, new_card: str) -> bool:
        """Check if cardinality change is narrowing"""
        if not old_card or not new_card:
            return False
            
        widening_map = {
            "ONE_TO_ONE": ["ONE_TO_MANY", "MANY_TO_MANY"],
            "ONE_TO_MANY": ["MANY_TO_MANY"],
            "MANY_TO_ONE": ["MANY_TO_MANY"],
            "MANY_TO_MANY": []
        }
        
        # If new cardinality is not in the widening options, it's narrowing
        return new_card not in widening_map.get(old_card, []) and old_card != new_card
    
    def _convert_domain_conflicts(self, domain_conflicts: List[DomainConflict]) -> List[Conflict]:
        """Convert domain conflicts to standard Conflict format"""
        return [
            Conflict(
                conflict_type=c.rule_name,
                resource_type=c.entity_type,
                resource_id=c.entity_id or "unknown",
                description=f"{c.description} (Severity: {c.severity.value})"
            )
            for c in domain_conflicts
        ]
    
    def _parse_terminus_conflicts(self, error_message: str) -> List[Conflict]:
        """Parse TerminusDB conflict errors"""
        # Simplified parser - would need more sophisticated parsing in production
        return [
            Conflict(
                conflict_type="structural_conflict",
                resource_id="unknown",
                description=error_message
            )
        ]
    
    def _format_warning(self, warning: DomainConflict) -> str:
        """Format domain conflict as warning message"""
        return f"[{warning.rule_name}] {warning.description}"


# Singleton instance
_unified_merge_engine = None


def get_unified_merge_engine(terminus_client=None) -> UnifiedMergeEngine:
    """Get or create unified merge engine instance"""
    global _unified_merge_engine
    if _unified_merge_engine is None:
        _unified_merge_engine = UnifiedMergeEngine(terminus_client)
    return _unified_merge_engine