"""
TerminusDB Native Branch Service Adapter
Implements branch operations using TerminusDB native functionality
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from terminusdb_client import WOQLClient
from terminusdb_client.woqlquery import WOQLQuery as WQ

from core.branch.interfaces import IBranchService
from models.branch import ChangeProposal, BranchDiff, MergeResult, ProposalStatus
from shared.exceptions import (
    BranchNotFoundError, 
    MergeConflictError,
    ValidationError
)

logger = logging.getLogger(__name__)


class TerminusNativeBranchService(IBranchService):
    """
    Branch service implementation using TerminusDB native features
    
    This adapter directly uses TerminusDB's built-in branch, merge, and diff
    capabilities instead of reimplementing them.
    """
    
    def __init__(
        self, 
        terminus_url: str = "http://localhost:6363",
        database: str = "ontology_db",
        organization: str = "admin"
    ):
        """Initialize TerminusDB native branch service"""
        self.terminus_url = terminus_url
        self.database = database
        self.organization = organization
        
        # Initialize TerminusDB client
        self.client = WOQLClient(terminus_url)
        self.client.connect(
            db=database,
            team=organization,
            use_token=True
        )
        
        logger.info(
            f"TerminusDB Native Branch Service initialized - "
            f"URL: {terminus_url}, DB: {database}"
        )
    
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
            # Create branch name following OMS convention
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            branch_name = f"proposal/{name}/{timestamp}"
            
            # Use TerminusDB native branch creation
            self.client.branch(branch_name, empty=False)
            
            logger.info(f"Created TerminusDB native branch: {branch_name}")
            
            # Store branch metadata as a document
            if description:
                metadata = {
                    "@type": "BranchMetadata",
                    "@id": f"metadata:{branch_name}",
                    "branch": branch_name,
                    "parent": parent,
                    "description": description,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
                self.client.insert_document(metadata, graph_type="instance")
            
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
            # Get branch information from TerminusDB
            branches = []
            
            # TerminusDB stores branch info in system graph
            query = WQ.select("v:Branch", "v:Head", "v:Time").woql_and(
                WQ.triple("v:Branch", "ref:branch_name", "v:Name"),
                WQ.triple("v:Branch", "ref:head", "v:Head"),
                WQ.triple("v:Head", "ref:timestamp", "v:Time")
            )
            
            # Execute query
            result = self.client.query(query)
            
            for binding in result.get('bindings', []):
                branches.append({
                    "name": binding.get('Name', {}).get('@value'),
                    "head": binding.get('Head', {}).get('@value'),
                    "timestamp": binding.get('Time', {}).get('@value')
                })
            
            # Also get branches via API if available
            try:
                api_branches = self.client.list_branches()
                for branch in api_branches:
                    if not any(b['name'] == branch for b in branches):
                        branches.append({
                            "name": branch,
                            "head": None,
                            "timestamp": None
                        })
            except:
                pass  # API method might not be available
            
            logger.info(f"Listed {len(branches)} branches")
            return branches
            
        except Exception as e:
            logger.error(f"Failed to list branches: {e}")
            return []
    
    async def get_branch_info(self, branch_name: str) -> Dict[str, Any]:
        """Get branch information"""
        try:
            # Get basic branch info
            branches = await self.list_branches()
            branch_info = next((b for b in branches if b['name'] == branch_name), None)
            
            if not branch_info:
                raise BranchNotFoundError(f"Branch {branch_name} not found")
            
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
    
    async def get_diff(self, from_ref: str, to_ref: str) -> BranchDiff:
        """Get diff using TerminusDB native diff"""
        try:
            # Use TerminusDB native diff
            diff_result = self.client.diff(from_ref, to_ref)
            
            # Convert to OMS BranchDiff format
            branch_diff = BranchDiff(
                from_branch=from_ref,
                to_branch=to_ref,
                changes=[]
            )
            
            # Parse TerminusDB diff format
            for change in diff_result.get("changes", []):
                branch_diff.changes.append({
                    "type": change.get("@type", "unknown"),
                    "operation": self._get_operation_type(change),
                    "path": change.get("@id"),
                    "old_value": change.get("@before"),
                    "new_value": change.get("@after")
                })
            
            logger.info(
                f"Generated diff from {from_ref} to {to_ref}: "
                f"{len(branch_diff.changes)} changes"
            )
            
            return branch_diff
            
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            raise
    
    def _parse_terminus_conflicts(self, error_message: str) -> List[Dict[str, Any]]:
        """Parse TerminusDB conflict information from error message"""
        # This is a simplified parser - in production would need more robust parsing
        conflicts = []
        
        if "conflict" in error_message.lower():
            conflicts.append({
                "type": "merge_conflict",
                "description": error_message,
                "severity": "error"
            })
        
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