"""
TerminusDB Native Branch Service Adapter
Implements branch operations using TerminusDB native functionality
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from terminusdb_client import WOQLClient
from terminusdb_client.woqlquery import WOQLQuery as WQ

from core.branch.interfaces import IBranchService
from core.branch.models import ChangeProposal, BranchDiff, MergeResult, ProposalStatus, DiffEntry, Conflict
from shared.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError
)
from core.monitoring.migration_monitor import track_native_operation
from core.validation.config import get_validation_config

logger = logging.getLogger(__name__)


class TerminusNativeBranchService(IBranchService):
    """
    Branch service implementation using TerminusDB native features
    
    This adapter directly uses TerminusDB's built-in branch, merge, and diff
    capabilities instead of reimplementing them.
    """
    
    def __init__(
        self, 
        terminus_url: str = None,
        database: str = None,
        organization: str = "admin"
    ):
        """Initialize TerminusDB native branch service"""
        # Use ValidationConfig if not provided
        config = get_validation_config()
        self.terminus_url = terminus_url or config.terminus_db_url
        self.database = database or config.terminus_default_db
        self.organization = organization
        
        # Initialize TerminusDB client
        self.client = WOQLClient(self.terminus_url)
        self.client.connect(
            user="admin",
            key="admin123",
            db=self.database,
            team=self.organization,
            use_token=False
        )
        
        logger.info(
            f"TerminusDB Native Branch Service initialized - "
            f"URL: {self.terminus_url}, DB: {self.database}"
        )
    
    @track_native_operation("create_branch")
    async def create_branch(
        self, 
        parent: str, 
        name: str, 
        description: Optional[str] = None
    ) -> str:
        """
        Create a new branch using TerminusDB native branch
        
        Args:
            parent: Parent branch name (e.g., "main")
            name: New branch name
            description: Optional branch description
            
        Returns:
            Full branch name
        """
        try:
            # Create branch name following OMS convention (but TerminusDB safe)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            # TerminusDB doesn't allow slashes in branch names
            branch_name = f"proposal_{name}_{timestamp}"
            
            # Use TerminusDB native branch creation
            # First switch to parent branch
            self.client.branch = parent
            self.client.create_branch(branch_name)
            
            logger.info(f"Created TerminusDB native branch: {branch_name}")
            
            # Store branch metadata as a document (if schema exists)
            # For now, skip metadata storage as it requires schema setup
            
            return branch_name
            
        except Exception as e:
            logger.error(f"Failed to create branch {name}: {e}")
            raise ValidationError(f"Branch creation failed: {str(e)}")
    
    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch using TerminusDB native delete"""
        try:
            self.client.delete_branch(branch_name)
            logger.info(f"Deleted branch: {branch_name}")
            
            # Clean up metadata
            try:
                self.client.delete_document(f"metadata:{branch_name}")
            except:
                pass  # Metadata might not exist
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name}: {e}")
            return False
    
    async def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches using TerminusDB native API"""
        try:
            branches = []
            
            # Method 1: Try to get branches via TerminusDB API first
            try:
                # Use the correct API method for listing branches
                if hasattr(self.client, 'list_branches'):
                    api_branches = self.client.list_branches()
                    for branch_info in api_branches:
                        branch_name = branch_info if isinstance(branch_info, str) else branch_info.get('name', str(branch_info))
                        branches.append({
                            "name": branch_name,
                            "head": None,
                            "timestamp": None
                        })
                        
                elif hasattr(self.client, 'get_all_branches'):
                    api_branches = self.client.get_all_branches()
                    for branch_info in api_branches:
                        branch_name = branch_info if isinstance(branch_info, str) else branch_info.get('name', str(branch_info))
                        branches.append({
                            "name": branch_name,
                            "head": None,
                            "timestamp": None
                        })
                        
            except Exception as api_error:
                logger.debug(f"Could not get branches via API: {api_error}")
            
            # Method 2: Try WOQL query for branch metadata (if API failed)
            if not branches:
                try:
                    # Use correct WOQL instance syntax
                    query = WQ().select("v:Branch", "v:Name").triple("v:Branch", "rdf:type", "@schema:Branch").triple("v:Branch", "@schema:name", "v:Name")
                    
                    # Execute query
                    result = self.client.query(query)
                    
                    if isinstance(result, dict) and 'bindings' in result:
                        for binding in result['bindings']:
                            branch_name = binding.get('Name', {}).get('@value') if isinstance(binding.get('Name'), dict) else binding.get('Name')
                            if branch_name:
                                branches.append({
                                    "name": branch_name,
                                    "head": None,
                                    "timestamp": None
                                })
                                
                except Exception as query_error:
                    logger.debug(f"WOQL query failed: {query_error}")
            
            # Method 3: Fallback to at least include main branch
            if not branches:
                logger.info("No branches found via API or query, using fallback")
                branches.append({
                    "name": "main",
                    "head": None,
                    "timestamp": None
                })
            
            # Remove duplicates
            seen_names = set()
            unique_branches = []
            for branch in branches:
                if branch['name'] not in seen_names:
                    seen_names.add(branch['name'])
                    unique_branches.append(branch)
            
            logger.info(f"Listed {len(unique_branches)} branches")
            return unique_branches
            
        except Exception as e:
            logger.error(f"Failed to list branches: {e}")
            # Return minimal fallback even on complete failure
            return [{"name": "main", "head": None, "timestamp": None}]
    
    async def get_branch_info(self, branch_name: str) -> Dict[str, Any]:
        """Get branch information"""
        try:
            # Get basic branch info
            branches = await self.list_branches()
            branch_info = next((b for b in branches if b['name'] == branch_name), None)
            
            if not branch_info:
                raise NotFoundError(f"Branch {branch_name} not found")
            
            # Try to get metadata
            try:
                metadata = self.client.get_document(f"metadata:{branch_name}")
                branch_info.update(metadata)
            except:
                pass  # Metadata might not exist
            
            return branch_info
            
        except Exception as e:
            logger.error(f"Failed to get branch info for {branch_name}: {e}")
            raise
    
    @track_native_operation("merge_branches")
    async def merge_branches(
        self, 
        source: str, 
        target: str, 
        author: str,
        message: Optional[str] = None
    ) -> MergeResult:
        """
        Merge branches using TerminusDB native merge
        
        This leverages TerminusDB's built-in 3-way merge algorithm
        """
        try:
            # Default message if not provided
            if not message:
                message = f"Merge {source} into {target}"
            
            # First check if fast-forward is possible
            diff = await self.get_diff(source, target)
            
            if not diff.changes:
                # No changes, nothing to merge
                return MergeResult(
                    status="no_changes",
                    message="No changes to merge"
                )
            
            # Attempt TerminusDB native merge
            try:
                # TerminusDB merge API
                result = self.client.merge(
                    source, 
                    target,
                    author=author,
                    message=message
                )
                
                logger.info(f"Successfully merged {source} into {target}")
                
                # Delete source branch after successful merge
                await self.delete_branch(source)
                
                return MergeResult(
                    status="success",
                    commit_id=result.get("commit"),
                    message=f"Merged successfully: {message}"
                )
                
            except Exception as merge_error:
                # Parse TerminusDB conflict information
                if "conflict" in str(merge_error).lower():
                    conflicts = self._parse_terminus_conflicts(str(merge_error))
                    
                    return MergeResult(
                        status="conflict",
                        conflicts=conflicts,
                        message="Merge conflicts detected"
                    )
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return MergeResult(
                status="error",
                message=f"Merge failed: {str(e)}"
            )
    
    @track_native_operation("get_diff")
    async def get_diff(self, from_ref: str, to_ref: str) -> BranchDiff:
        """Get diff using TerminusDB native diff"""
        try:
            # Use TerminusDB native diff
            diff_result = self.client.diff(from_ref, to_ref)
            
            # Convert to OMS BranchDiff format
            entries = []
            
            # Handle different return types from TerminusDB
            changes = []
            if hasattr(diff_result, 'to_dict'):
                changes = diff_result.to_dict().get("changes", [])
            elif isinstance(diff_result, dict):
                changes = diff_result.get("changes", [])
            elif hasattr(diff_result, '__iter__'):
                changes = list(diff_result)
            
            # Parse TerminusDB diff format
            for change in changes:
                operation = self._get_operation_type(change)
                entries.append(DiffEntry(
                    operation=operation,
                    resource_type=change.get("@type", "unknown"),
                    resource_id=change.get("@id", "unknown"),
                    resource_name=change.get("@id", "unknown").split("/")[-1],
                    path=change.get("@id", ""),
                    old_value=change.get("@before"),
                    new_value=change.get("@after")
                ))
            
            # Count operations
            additions = sum(1 for e in entries if e.operation == "added")
            modifications = sum(1 for e in entries if e.operation == "modified")
            deletions = sum(1 for e in entries if e.operation == "deleted")
            renames = sum(1 for e in entries if e.operation == "renamed")
            
            branch_diff = BranchDiff(
                source_branch=from_ref,
                target_branch=to_ref,
                base_hash="",  # TerminusDB doesn't expose this directly
                source_hash="",  # Would need to query commit info
                target_hash="",  # Would need to query commit info
                total_changes=len(entries),
                additions=additions,
                modifications=modifications,
                deletions=deletions,
                renames=renames,
                entries=entries,
                has_conflicts=False,
                conflicts=[]
            )
            
            logger.info(
                f"Generated diff from {from_ref} to {to_ref}: "
                f"{branch_diff.total_changes} changes"
            )
            
            return branch_diff
            
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            raise
    
    def _parse_terminus_conflicts(self, error_message: str) -> List[Conflict]:
        """Parse TerminusDB conflict information from error message"""
        # This is a simplified parser - in production would need more robust parsing
        conflicts = []
        
        if "conflict" in error_message.lower():
            conflicts.append(Conflict(
                conflict_type="merge-conflict",
                resource_type="unknown",
                resource_id="unknown",
                description=error_message
            ))
        
        return conflicts
    
    def _get_operation_type(self, change: Dict[str, Any]) -> str:
        """Determine operation type from TerminusDB change object"""
        if "@before" in change and "@after" in change:
            return "modified"
        elif "@after" in change:
            return "added"
        elif "@before" in change:
            return "deleted"
        else:
            return "unknown"