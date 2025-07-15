"""
REQ-OMS-F2: Branch management core service
Version control (Branching & Merge) system implementation
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from core.branch.conflict_resolver import ConflictResolver
from core.branch.diff_engine import DiffEngine
from core.branch.merge_strategies import MergeStrategyImplementor
from core.branch.models import (
    BranchDiff,
    ChangeProposal,
    DiffEntry,
    MergeResult,
    MergeStrategy,
    ProposalStatus,
    ProposalUpdate,
)
from database.clients.terminus_db import TerminusDBClient
from middleware.three_way_merge import JsonMerger
from shared.models.domain import Branch as DomainBranch

logger = logging.getLogger(__name__)


class BranchService:
    """
    Git-style branch creation, merge, and Proposal workflow support
    """

    def __init__(
            self,
            tdb_endpoint: str,
            diff_engine: DiffEngine,
            conflict_resolver: ConflictResolver,
            event_publisher: Optional[Any] = None,
        ):
            self.tdb_endpoint = tdb_endpoint
            self.tdb = TerminusDBClient(endpoint=tdb_endpoint)
            self.diff_engine = diff_engine
            self.conflict_resolver = conflict_resolver
            self.event_publisher = event_publisher
            self.db_name = os.getenv("TERMINUSDB_DB", "oms")
            self.merger = JsonMerger()

            # In-memory proposal storage (could be replaced with database storage)
            self._proposals: Dict[str, ChangeProposal] = {}
            self._proposal_counter = 0
            self.merge_strategies = MergeStrategyImplementor(self.tdb)

    async def initialize(self):
            try:
                async with self.tdb:
                    await self.tdb.create_database(self.db_name)
                    logger.info(f"Database {self.db_name} initialized")
            except Exception as e:
                logger.warning(f"Database initialization failed: {e}")

    def _generate_id(self) -> str:
            return str(uuid.uuid4())

    def _generate_proposal_id(self) -> str:
            return f"proposal_{self._generate_id()}"

    def _validate_branch_name(self, name: str) -> bool:
            import re

            pattern = r"^[a-z][a-z0-9\-/]*$"
            return bool(re.match(pattern, name))

    async def _branch_exists(self, name: str) -> bool:
            """Check if branch exists in TerminusDB"""
            try:
                branch_info = await self.tdb.get_branch_info(self.db_name, name)
                return branch_info is not None
            except Exception as e:
                logger.error(f"Failed to check branch existence for '{name}': {e}")
                raise

    async def _get_branch_info(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """Get branch information from TerminusDB"""
        try:
        return await self.tdb.get_branch_info(self.db_name, branch_name)
        except Exception as e:
        logger.error(f"Failed to get branch info for '{branch_name}': {e}")
        raise

    async def _get_branch_head(self, branch_name: str) -> Optional[str]:
        info = await self._get_branch_info(branch_name)
        return info.get("head") if info else None

    async def _is_protected_branch(self, branch_name: str) -> bool:
        if branch_name in ["main", "master", "_system", "_proposals"]:
        return True
        # Check if branch has protection metadata
        try:
        branch_doc = await self.tdb.get_document(
        self.db_name, "_system", f"Branch/{branch_name}"
        )
        if branch_doc and branch_doc.get("isProtected"):
        return True
        except Exception as e:
        logger.error(f"Failed to check branch protection for '{branch_name}': {e}")
        # In case of error, treat protected branches as protected
        if branch_name in ["main", "master", "_system", "_proposals"]:
        return True
        raise
        return False

    async def create_branch(
        self,
        name: str,
        from_branch: str = "main",
        description: Optional[str] = None,
        user_id: str = "system",
        ) -> DomainBranch:
        """
        Create a new branch and save metadata.

        1. Name validation
        2. Check for duplicates
        3. Create native branch in TerminusDB
        4. Save metadata document in _system branch
        5. Publish event
        6. Return completed branch object

        Args:
        name (str): New branch name
        from_branch (str, optional): Base branch. Defaults to "main".
        description (Optional[str], optional): Branch description. Defaults to None.
        user_id (str, optional): Creator ID. Defaults to "system".

        Raises:
        ValueError: Invalid branch name or already exists
        Exception: Database operation error

        Returns:
        DomainBranch: Created branch details
        """
        logger.info(
        f"Attempting to create branch '{name}' from '{from_branch}' by user '{user_id}'."
        )

        # 1. branch Name validation
        if not self._validate_branch_name(name):
        raise ValueError(f"Invalid branch name: {name}")

        # 2. Check for duplicates
        existing_branch = await self.get_branch(name)
        if existing_branch:
        raise ValueError(f"Branch '{name}' already exists.")

        # 3. Create native branch in TerminusDB
        created = await self.tdb.create_branch(self.db_name, name, from_branch)
        if not created:
        # create_branch가 False를 반환하는 경우는 이미 존재할 때 이지만, get_branch에서 확인했으므로
        # 여기 도달했다면 다른 생성 실패 케이스로 간주
        raise Exception(
        f"Failed to create branch '{name}' in TerminusDB for an unknown reason."
        )

        # 4. Save metadata document in _system branch
        now = datetime.utcnow()
        document_id = f"Branch/{name}"
        branch_metadata = {
        "@type": "Branch",
        "@id": document_id,
        "name": name,
        "displayName": name.replace("-", " ").replace("_", " ").title(),
        "description": description,
        "parentBranch": from_branch,
        "isProtected": False,
        "createdBy": user_id,
        "createdAt": now.isoformat() + "Z", # ISO 8601 UTC format
        "modifiedBy": user_id,
        "modifiedAt": now.isoformat() + "Z",
        "isActive": True,
        }

        try:
        await self.tdb.insert_document(
        self.db_name,
        "_system",
        branch_metadata,
        commit_msg = f"Create metadata for branch '{name}'",
        )
        logger.info(f"Metadata for branch '{name}' created in _system branch.")
        except Exception as e:
        # Rollback: attempt to delete native branch if metadata creation fails
        logger.error(
        f"Failed to insert metadata for branch '{name}'. Attempting to roll back. Error: {e}"
        )
        # await self.terminus_client.delete_branch(self.db_name, name) # Add rollback logic according to policy
        raise Exception(f"Failed to insert metadata for branch '{name}'.") from e

        # 5. Publish event (if implemented)
        if self.event_publisher:
        try:
        # Publish event에 필요한 데이터 형식에 맞춰 전달해야 함
        await self.event_publisher.publish_branch_created(
        branch_name = name,
        parent_branch = from_branch,
        author = user_id,
        description = description,
        metadata={"id": document_id},
        )
        logger.info(f"Published 'branch.created' event for branch '{name}'.")
        except Exception as e:
        # Publish event Treat failure as non-critical and only log
        logger.warning(
        f"Failed to publish branch creation event for '{name}': {e}"
        )

        # 6. Return completed branch object
        # get_branch를 호출하여 DB에서 직접 읽어와 일관성을 보장
        final_branch = await self.get_branch(name)
        if not final_branch:
        # This case should rarely occur.
        raise Exception(
        f"Could not retrieve branch '{name}' immediately after creation."
        )
        return final_branch

    async def get_branch(self, branch_name: str) -> Optional[DomainBranch]:
        """
        Get detailed information for a specific branch.

        Args:
        branch_name (str): Branch name to query

        Returns:
        Optional[DomainBranch]: Branch info object. Returns None if branch doesn't exist.

        Raises:
        Exception: Database query error
        """
        logger.info(f"Fetching details for branch: {branch_name}")
        try:
        # 1. TerminusDB Query branch basic info with native API
        branch_info = await self.tdb.get_branch_info(self.db_name, branch_name)
        if not branch_info:
        logger.warning(f"Branch '{branch_name}' does not exist in TerminusDB.")
        return None

        head_commit_id = branch_info.get("head")
        # TerminusDB는 branch 정보에 last 수정 hours을 포함할 수 있습니다.
        # 하지만 여기서는 메타데이터를 우선시하고, 없을 경우 현재 hours으로 대체합니다.
        last_modified_raw = branch_info.get("@timestamp")
        last_modified = (
        datetime.fromtimestamp(last_modified_raw)
        if last_modified_raw
        else datetime.utcnow()
        )

        # 2. _system Query branch metadata document from branch
        document_id = f"Branch/{branch_name}"
        metadata_doc = await self.tdb.get_document(
        self.db_name, "_system", document_id
        )

        if not metadata_doc:
        logger.warning(
        f"Metadata document not found for branch '{branch_name}'. "
        "Returning branch object with basic info from branch head."
        )
        return DomainBranch(
        id = branch_name,
        name = branch_name,
        displayName = branch_name.title(),
        versionHash = head_commit_id or "unknown",
        createdBy = "system",
        createdAt = last_modified, # 정확한 생성 hours을 알 수 없으므로 last 수정 hours으로 대체
        modifiedBy = "system",
        modifiedAt = last_modified,
        )

        # 3. Combine information DomainBranch Create object
        created_at_str = metadata_doc.get("createdAt")
        created_at = (
        datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        if created_at_str
        else datetime.utcnow()
        )

        modified_at_str = metadata_doc.get("modifiedAt")
        # 수정 hours이 없다면 생성 hours으로 대체
        modified_at = (
        datetime.fromisoformat(modified_at_str.replace("Z", "+00:00"))
        if modified_at_str
        else created_at
        )

        return DomainBranch(
        id = metadata_doc.get("@id", document_id),
        name = metadata_doc.get("name", branch_name),
        displayName = metadata_doc.get("displayName", branch_name.title()),
        description = metadata_doc.get("description"),
        parentBranch = metadata_doc.get("parentBranch"),
        isProtected = metadata_doc.get("isProtected", False),
        createdBy = metadata_doc.get("createdBy", "unknown"),
        createdAt = created_at,
        modifiedBy = metadata_doc.get("modifiedBy", "unknown"),
        modifiedAt = modified_at,
        versionHash = head_commit_id or "unknown",
        isActive = metadata_doc.get("isActive", True),
        )

        except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching branch '{branch_name}': {e}")
        # Specific types of errors can be handled more specifically.
        raise Exception(
        f"Failed to fetch branch '{branch_name}' due to a network issue."
        ) from e
        except Exception as e:
        logger.error(
        f"An unexpected error occurred while fetching branch '{branch_name}': {e}"
        )
        raise

    async def list_branches(
        self, include_system: bool = False, status: Optional[str] = None
        ) -> List[DomainBranch]:
        """Query all branch metadata from _system branch."""
        logger.info("Listing branches from _system branch")
        try:
        async with TerminusDBClient(self.tdb_endpoint) as tdb:
        # _system from branch type이 'Branch'get all documents of type WOQL query
        woql_query = {
        "@type": "Triple",
        "subject": {"@type": "Variable", "name": "doc_uri"},
        "predicate": {"@type": "NodeValue", "node": "rdf:type"},
        "object": {"@type": "NodeValue", "node": "Branch"},
        }

        # WOQL query를 사용하여 문서의 전체 내용을 가져오도록 수정
        full_query = {
        "@type": "Select",
        "variables": ["doc"],
        "query": {
        "@type": "And",
        "and": [
        woql_query,
        {
        "@type": "Get",
        "resource": {"@type": "Variable", "name": "doc_uri"},
        "value": {"@type": "Variable", "name": "doc"},
        },
        ],
        },
        }

        result = await tdb.query_branch(
        db_name = self.db_name,
        branch_name = "_system",
        query = json.dumps(full_query),
        )

        bindings = result.get("bindings", [])
        if not bindings:
        return []

        branches = [DomainBranch(**item["doc"]) for item in bindings]

        # Filtering logic
        if not include_system:
        branches = [
        b for b in branches if b.name not in ["_system", "_proposals"]
        ]

        if status:
        is_active = status.lower() == "active"
        branches = [b for b in branches if b.isActive == is_active]

        return branches

        except Exception as e:
        logger.error(f"Failed to list branches: {e}", exc_info = True)
        return []

    async def delete_branch(self, branch_name: str, user_id: str = "system") -> bool:
        """
        Delete branch and related metadata.

        1. Check branch existence and protection status
        2. Delete metadata document from _system branch
        3. Delete native branch from TerminusDB
        4. Publish event

        Args:
        branch_name (str): Branch name to delete
        user_id (str, optional): Deletion requester ID. Defaults to "system".

        Raises:
        ValueError: Branch not found or is protected

        Returns:
        bool: True if successfully deleted
        """
        logger.info(f"Attempting to delete branch '{branch_name}' by user '{user_id}'.")

        # 1. Check branch existence and protection status
        if not await self.get_branch(branch_name):
        raise ValueError(f"Branch '{branch_name}' not found.")

        if self._is_protected_branch(branch_name):
        raise ValueError(f"Cannot delete protected branch: {branch_name}")

        # 2. Delete metadata document from _system branch
        document_id = f"Branch/{branch_name}"
        try:
        deleted_meta = await self.tdb.delete_document(
        self.db_name,
        "_system",
        document_id,
        commit_msg = f"Delete metadata for branch '{branch_name}'",
        )
        if deleted_meta:
        logger.info(
        f"Metadata document '{document_id}' for branch '{branch_name}' deleted."
        )
        else:
        logger.warning(
        f"Metadata document for branch '{branch_name}' not found,
         continuing with branch deletion."
        )
        except Exception as e:
        logger.error(f"Failed to delete metadata for branch '{branch_name}': {e}")
        # If metadata deletion fails, do not proceed with branch deletion
        raise Exception(
        f"Failed to delete metadata for branch '{branch_name}'."
        ) from e

        # 3. Delete native branch from TerminusDB
        try:
        deleted_branch = await self.tdb.delete_branch(self.db_name, branch_name)
        if not deleted_branch:
        # If already deleted or missing, just log warning and consider success
        logger.warning(
        f"Native branch '{branch_name}' was not found during deletion, but proceeding."
        )
        logger.info(f"Native branch '{branch_name}' deleted successfully.")
        except Exception as e:
        # Native branch deletion failure is critical error. But metadata is already deleted.
        # In this case, must leave very critical log indicating manual intervention may be needed.
        logger.critical(
        f"CRITICAL: Failed to delete native branch '{branch_name}' after its metadata was removed. Manual intervention required. Error: {e}"
        )
        raise Exception(f"Failed to delete native branch '{branch_name}'.") from e

        # 4. Publish event
        if self.event_publisher:
        try:
        await self.event_publisher.publish_branch_deleted(
        branch_name = branch_name,
        author = user_id,
        )
        logger.info(
        f"Published 'branch.deleted' event for branch '{branch_name}'."
        )
        except Exception as e:
        logger.warning(
        f"Failed to publish branch deletion event for '{branch_name}': {e}"
        )

        return True

    async def create_proposal(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: Optional[str] = None,
        user_id: str = "system",
        ) -> ChangeProposal:
        """Create a new change proposal for branch merge"""
        try:
        # Validate branches exist
        if not await self._branch_exists(source_branch):
        raise ValueError(f"Source branch '{source_branch}' does not exist")
        if not await self._branch_exists(target_branch):
        raise ValueError(f"Target branch '{target_branch}' does not exist")

        # Check if target branch is protected
        if await self._is_protected_branch(target_branch):
        # Protected branches require review
        logger.info(
        f"Target branch '{target_branch}' is protected, proposal will require approval"
        )

        # Get branch information
        source_info = await self._get_branch_info(source_branch)
        target_info = await self._get_branch_info(target_branch)

        # Get diff between branches
        diff = await self.diff_engine.calculate_diff(source_branch, target_branch)

        proposal_id = self._generate_proposal_id()
        now = datetime.utcnow()

        proposal = ChangeProposal(
        id = proposal_id,
        title = title,
        description = description,
        source_branch = source_branch,
        target_branch = target_branch,
        status = ProposalStatus.OPEN,
        base_hash = diff.base_hash,
        source_hash = source_info.get("head", "") if source_info else "",
        target_hash = target_info.get("head", "") if target_info else "",
        author = user_id,
        created_at = now,
        updated_at = now,
        diff_summary={
        "total_changes": diff.total_changes,
        "additions": diff.additions,
        "modifications": diff.modifications,
        "deletions": diff.deletions,
        },
        )

        # Save proposal to database
        await self._save_proposal_to_db(proposal)

        # Cache in memory
        self._proposals[proposal_id] = proposal

        # Publish event
        if self.event_publisher:
        await self._publish_event(
        "proposal.created",
        {
        "proposal_id": proposal_id,
        "title": title,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "author": user_id,
        },
        )

        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

        except Exception as e:
        logger.error(f"Failed to create proposal: {e}")
        raise

    async def merge_branch(
        self,
        proposal_id: str,
        strategy: MergeStrategy,
        user_id: str = "system",
        conflict_resolutions: Optional[Dict[str, Any]] = None,
        ) -> MergeResult:
        """Execute branch merge based on approved proposal"""
        try:
        # Get proposal
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
        raise ValueError(f"Proposal {proposal_id} not found")

        # Verify proposal is approved
        if proposal.status != ProposalStatus.APPROVED:
        raise ValueError(
        f"Proposal {proposal_id} is not approved (status: {proposal.status})"
        )

        # Check user permissions
        if not await self._user_can_merge(user_id, proposal):
        raise PermissionError(f"User {user_id} cannot merge this proposal")

        # Get latest diff
        diff = await self.diff_engine.calculate_diff(
        proposal.source_branch, proposal.target_branch
        )

        # Check for conflicts
        conflicts = await self.conflict_resolver.detect_conflicts(diff)

        # Apply conflict resolutions if provided
        if conflicts and conflict_resolutions:
        conflicts = await self.conflict_resolver.apply_resolutions(
        conflicts, conflict_resolutions
        )

        # If unresolved conflicts remain, fail
        unresolved = [c for c in conflicts if not c.resolved]
        if unresolved:
        raise ValueError(
        f"Cannot merge: {len(unresolved)} unresolved conflicts"
        )

        # Execute merge using selected strategy
        merge_result = await self.merge_strategies.execute_merge(
        source_branch = proposal.source_branch,
        target_branch = proposal.target_branch,
        strategy = strategy,
        user_id = user_id,
        message = f"Merge {proposal.source_branch} into {proposal.target_branch} (#{proposal_id})",


        )

        # Update proposal status
        proposal.status = ProposalStatus.MERGED
        proposal.merged_at = datetime.now()
        proposal.merged_by = user_id
        await self._save_proposal_to_db(proposal)

        # Publish merge event
        if self.event_publisher:
        await self._publish_event(
        "branch.merged",
        {
        "proposal_id": proposal_id,
        "source_branch": proposal.source_branch,
        "target_branch": proposal.target_branch,
        "merge_commit": merge_result.merge_commit,
        "strategy": strategy.value,
        "user_id": user_id,
        },
        )

        logger.info(
        f"Successfully merged {proposal.source_branch} into {proposal.target_branch}"
        )
        return merge_result

        except Exception as e:
        logger.error(f"Failed to merge branches: {e}")
        raise

    async def get_branch_diff(
        self, source_branch: str, target_branch: str, format: str = "summary"
        ) -> BranchDiff:
        """Get differences between two branches"""
        try:
        # Validate branches exist
        if not await self._branch_exists(source_branch):
        raise ValueError(f"Source branch '{source_branch}' does not exist")
        if not await self._branch_exists(target_branch):
        raise ValueError(f"Target branch '{target_branch}' does not exist")

        # Calculate diff using diff engine
        diff = await self.diff_engine.calculate_diff(source_branch, target_branch)

        # Format diff based on requested format
        if format == "detailed":
        # Include full diff entries
        return diff
        else:
        # Return summary only
        return BranchDiff(
        source_branch = diff.source_branch,
        target_branch = diff.target_branch,
        base_hash = diff.base_hash,
        source_hash = diff.source_hash,
        target_hash = diff.target_hash,
        total_changes = diff.total_changes,
        additions = diff.additions,
        modifications = diff.modifications,
        deletions = diff.deletions,
        renames = diff.renames,
        entries = [] if format == "summary" else diff.entries,
        )

        except Exception as e:
        logger.error(f"Failed to get branch diff: {e}")
        raise

    async def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
        """Get a specific proposal by ID"""
        try:
        logger.info(f"Retrieving proposal: {proposal_id}")

        # Check in-memory storage first
        if proposal_id in self._proposals:
        proposal = self._proposals[proposal_id]
        logger.debug(f"Found proposal {proposal_id} in memory")
        return proposal

        # Try to load from persistent storage (TerminusDB)
        proposal = await self._load_proposal_from_db(proposal_id)
        if proposal:
        # Cache in memory
        self._proposals[proposal_id] = proposal
        logger.debug(f"Loaded proposal {proposal_id} from database")
        return proposal

        logger.warning(f"Proposal {proposal_id} not found")
        return None

        except Exception as e:
        logger.error(f"Error retrieving proposal {proposal_id}: {e}")
        return None

    async def _load_proposal_from_db(
        self, proposal_id: str
        ) -> Optional[ChangeProposal]:
        """Load proposal from TerminusDB storage"""
        try:
        async with TerminusDBClient(self.tdb_endpoint) as tdb:
        # Query for the proposal document using TerminusDB v11.1.14 JSON syntax
        query = {
        "type": "and",
        "clauses": [
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "type"},
        "object": {"@type": "Value", "value": "Proposal"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "proposal_id"},
        "object": {"@type": "Value", "value": proposal_id},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "title"},
        "object": {"@type": "Variable", "variable_name": "Title"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "status"},
        "object": {"@type": "Variable", "variable_name": "Status"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "source_branch"},
        "object": {
        "@type": "Variable",
        "variable_name": "SourceBranch",
        },
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "target_branch"},
        "object": {
        "@type": "Variable",
        "variable_name": "TargetBranch",
        },
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "author"},
        "object": {"@type": "Variable", "variable_name": "Author"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "created_at"},
        "object": {
        "@type": "Variable",
        "variable_name": "CreatedAt",
        },
        },
        ],
        }

        result = await tdb.query(query)

        if result and "bindings" in result and result["bindings"]:
        binding = result["bindings"][0]

        # Parse the result into a ChangeProposal object
        proposal = ChangeProposal(
        id = proposal_id,
        title = binding.get("Title", ""),
        source_branch = binding.get("SourceBranch", ""),
        target_branch = binding.get("TargetBranch", ""),
        status = ProposalStatus(binding.get("Status", "DRAFT")),
        author = binding.get("Author", ""),
        created_at = datetime.fromisoformat(binding.get("CreatedAt", "")),
        description = binding.get("Description", ""),
        diff = None, # Load separately if needed
        )

        return proposal

        except Exception as e:
        logger.error(f"Failed to load proposal {proposal_id} from database: {e}")

        return None

    async def list_proposals(
        self,
        branch: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        author: Optional[str] = None,
        ) -> List[ChangeProposal]:
        """List proposals with optional filtering"""
        try:
        logger.info(
        f"Listing proposals: branch={branch}, status={status}, author={author}"
        )

        # Get all proposals from memory and database
        all_proposals = list(self._proposals.values())

        # Load additional proposals from database
        db_proposals = await self._load_all_proposals_from_db()

        # Merge and deduplicate
        proposal_dict = {p.id: p for p in all_proposals}
        for p in db_proposals:
        if p.id not in proposal_dict:
        proposal_dict[p.id] = p
        # Cache in memory
        self._proposals[p.id] = p

        proposals = list(proposal_dict.values())

        # Apply filters
        filtered_proposals = []
        for proposal in proposals:
        # Filter by branch (source or target)
        if branch and branch not in [
        proposal.source_branch,
        proposal.target_branch,
        ]:
        continue

        # Filter by status
        if status and proposal.status != status:
        continue

        # Filter by author
        if author and proposal.author != author:
        continue

        filtered_proposals.append(proposal)

        # Sort by creation date (newest first)
        filtered_proposals.sort(key = lambda p: p.created_at, reverse = True)

        logger.debug(f"Found {len(filtered_proposals)} proposals matching filters")
        return filtered_proposals

        except Exception as e:
        logger.error(f"Error listing proposals: {e}")
        return []

    async def _load_all_proposals_from_db(self) -> List[ChangeProposal]:
        """Load all proposals from TerminusDB storage"""
        try:
        async with TerminusDBClient(self.tdb_endpoint) as tdb:
        # Query for all proposal documents using TerminusDB v11.1.14 JSON syntax
        query = {
        "type": "and",
        "clauses": [
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "type"},
        "object": {"@type": "Value", "value": "Proposal"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "proposal_id"},
        "object": {
        "@type": "Variable",
        "variable_name": "ProposalId",
        },
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "title"},
        "object": {"@type": "Variable", "variable_name": "Title"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "status"},
        "object": {"@type": "Variable", "variable_name": "Status"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "source_branch"},
        "object": {
        "@type": "Variable",
        "variable_name": "SourceBranch",
        },
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "target_branch"},
        "object": {
        "@type": "Variable",
        "variable_name": "TargetBranch",
        },
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "author"},
        "object": {"@type": "Variable", "variable_name": "Author"},
        },
        {
        "type": "triple",
        "subject": {
        "@type": "Variable",
        "variable_name": "Proposal",
        },
        "predicate": {"@type": "Node", "node": "created_at"},
        "object": {
        "@type": "Variable",
        "variable_name": "CreatedAt",
        },
        },
        ],
        }

        result = await tdb.query(query)
        proposals = []

        if result and "bindings" in result:
        for binding in result["bindings"]:
        try:
        proposal = ChangeProposal(
        id = binding.get("ProposalId", ""),
        title = binding.get("Title", ""),
        source_branch = binding.get("SourceBranch", ""),
        target_branch = binding.get("TargetBranch", ""),
        status = ProposalStatus(binding.get("Status", "DRAFT")),
        author = binding.get("Author", ""),
        created_at = datetime.fromisoformat(
        binding.get("CreatedAt", "")
        ),
        description = binding.get("Description", ""),
        diff = None,
        )
        proposals.append(proposal)
        except Exception as parse_error:
        logger.warning(f"Failed to parse proposal: {parse_error}")

        return proposals

        except Exception as e:
        logger.error(f"Failed to load proposals from database: {e}")
        return []

    async def update_proposal(
        self, proposal_id: str, update: ProposalUpdate, user_id: str
        ) -> ChangeProposal:
        """Update an existing proposal"""
        try:
        logger.info(f"Updating proposal {proposal_id} by user {user_id}")

        proposal = await self.get_proposal(proposal_id)
        if not proposal:
        raise ValueError(f"Proposal {proposal_id} not found")

        # Check if user can update this proposal
        if proposal.author != user_id and not await self._user_can_modify_proposal(
        user_id, proposal
        ):
        raise PermissionError(
        f"User {user_id} cannot update proposal {proposal_id}"
        )

        # Apply updates
        if update.title is not None:
        proposal.title = update.title
        if update.description is not None:
        proposal.description = update.description
        if update.status is not None:
        proposal.status = update.status

        # Update timestamp
        proposal.updated_at = datetime.now()

        # Save to storage
        await self._save_proposal_to_db(proposal)

        # Update in-memory cache
        self._proposals[proposal_id] = proposal

        # Publish event
        if self.event_publisher:
        await self.event_publisher.publish_event(
        "proposal_updated",
        {
        "proposal_id": proposal_id,
        "updated_by": user_id,
        "changes": update.__dict__,
        },
        )

        logger.info(f"Successfully updated proposal {proposal_id}")
        return proposal

        except Exception as e:
        logger.error(f"Failed to update proposal {proposal_id}: {e}")
        raise

    async def _user_can_modify_proposal(
        self, user_id: str, proposal: ChangeProposal
        ) -> bool:
        """Check if user has permission to modify the proposal"""
        # Simple permission check - could be extended with role-based access
        return (
        proposal.author == user_id
        or user_id == "admin"
        or await self._user_is_maintainer(user_id, proposal.target_branch)
        )

    async def _user_is_maintainer(self, user_id: str, branch: str) -> bool:
        """Check if user is a maintainer of the target branch"""
        # Mock implementation - would check actual permissions
        maintainers = ["admin", "maintainer", "lead"]
        return user_id in maintainers

    async def _save_proposal_to_db(self, proposal: ChangeProposal):
        """Save proposal to TerminusDB storage"""
        try:
        async with TerminusDBClient(self.tdb_endpoint) as tdb:
        # Create/update proposal document
        doc = {
        "@type": "Proposal",
        "proposal_id": proposal.id,
        "title": proposal.title,
        "description": proposal.description or "",
        "source_branch": proposal.source_branch,
        "target_branch": proposal.target_branch,
        "status": proposal.status.value,
        "author": proposal.author,
        "created_at": proposal.created_at.isoformat(),
        "updated_at": proposal.updated_at.isoformat()
        if proposal.updated_at
        else datetime.now().isoformat(),
        }

        await tdb.insert_document(
        doc, commit_msg = f"Update proposal {proposal.id}"
        )
        logger.debug(f"Saved proposal {proposal.id} to database")

        except Exception as e:
        logger.error(f"Failed to save proposal {proposal.id} to database: {e}")
        raise

    async def approve_proposal(
        self, proposal_id: str, user_id: str, comment: Optional[str] = None
        ) -> ChangeProposal:
        """Approve a proposal for merge"""
        try:
        logger.info(f"Approving proposal {proposal_id} by user {user_id}")

        proposal = await self.get_proposal(proposal_id)
        if not proposal:
        raise ValueError(f"Proposal {proposal_id} not found")

        # Check if user can approve this proposal
        if not await self._user_can_approve_proposal(user_id, proposal):
        raise PermissionError(
        f"User {user_id} cannot approve proposal {proposal_id}"
        )

        # Check proposal state
        if proposal.status not in [
        ProposalStatus.OPEN,
        ProposalStatus.READY_FOR_REVIEW,
        ]:
        raise ValueError(
        f"Proposal {proposal_id} cannot be approved in status {proposal.status}"
        )

        # Update proposal status
        proposal.status = ProposalStatus.APPROVED
        proposal.updated_at = datetime.now()

        # Add approval comment if provided
        if comment:
        if not hasattr(proposal, "comments"):
        proposal.comments = []
        proposal.comments.append(
        {
        "author": user_id,
        "comment": comment,
        "action": "approved",
        "timestamp": datetime.now().isoformat(),
        }
        )

        # Save to storage
        await self._save_proposal_to_db(proposal)

        # Update in-memory cache
        self._proposals[proposal_id] = proposal

        # Publish approval event
        if self.event_publisher:
        await self.event_publisher.publish_event(
        "proposal_approved",
        {
        "proposal_id": proposal_id,
        "approved_by": user_id,
        "comment": comment,
        "source_branch": proposal.source_branch,
        "target_branch": proposal.target_branch,
        },
        )

        # Perform auto-merge if configured
        if await self._should_auto_merge(proposal):
        logger.info(f"Auto-merging approved proposal {proposal_id}")
        try:
        await self.merge_branches(
        source_branch = proposal.source_branch,
        target_branch = proposal.target_branch,
        strategy = MergeStrategy.AUTO,
        commit_msg = f"Auto-merge approved proposal: {proposal.title}",
        )
        proposal.status = ProposalStatus.MERGED
        await self._save_proposal_to_db(proposal)
        except Exception as merge_error:
        logger.error(
        f"Auto-merge failed for proposal {proposal_id}: {merge_error}"
        )
        # Don't fail the approval, just log the merge failure

        logger.info(f"Successfully approved proposal {proposal_id}")
        return proposal

        except Exception as e:
        logger.error(f"Failed to approve proposal {proposal_id}: {e}")
        raise

    async def _user_can_merge(self, user_id: str, proposal: ChangeProposal) -> bool:
        """Check if user has permission to merge the proposal"""
        # Check if user is the author - authors cannot merge their own proposals
        if proposal.author == user_id:
        return False

        # Check if user has merge permissions for the target branch
        return await self._user_is_maintainer(user_id, proposal.target_branch)

    async def _user_can_approve_proposal(
        self, user_id: str, proposal: ChangeProposal
        ) -> bool:
        """Check if user has permission to approve the proposal"""
        # Author cannot approve their own proposal
        if proposal.author == user_id:
        return False

        # Check if user is a maintainer or admin
        return user_id == "admin" or await self._user_is_maintainer(
        user_id, proposal.target_branch
        )

    async def _should_auto_merge(self, proposal: ChangeProposal) -> bool:
        """Check if proposal should be auto-merged after approval"""
        # Simple policy - could be configured per branch/project
        return proposal.target_branch != "main" # Don't auto-merge to main branch

    async def reject_proposal(
        self, proposal_id: str, user_id: str, reason: str
        ) -> ChangeProposal:
        """Reject a proposal with a reason"""
        try:
        logger.info(f"Rejecting proposal {proposal_id} by user {user_id}")

        proposal = await self.get_proposal(proposal_id)
        if not proposal:
        raise ValueError(f"Proposal {proposal_id} not found")

        # Check if user can reject this proposal
        if not await self._user_can_approve_proposal(user_id, proposal):
        raise PermissionError(
        f"User {user_id} cannot reject proposal {proposal_id}"
        )

        # Check proposal state
        if proposal.status in [ProposalStatus.REJECTED, ProposalStatus.MERGED]:
        raise ValueError(
        f"Proposal {proposal_id} cannot be rejected in status {proposal.status}"
        )

        # Update proposal status
        proposal.status = ProposalStatus.REJECTED
        proposal.updated_at = datetime.now()

        # Add rejection comment
        if not hasattr(proposal, "comments"):
        proposal.comments = []
        proposal.comments.append(
        {
        "author": user_id,
        "comment": reason,
        "action": "rejected",
        "timestamp": datetime.now().isoformat(),
        }
        )

        # Save to storage
        await self._save_proposal_to_db(proposal)

        # Update in-memory cache
        self._proposals[proposal_id] = proposal

        # Publish rejection event
        if self.event_publisher:
        await self.event_publisher.publish_event(
        "proposal_rejected",
        {
        "proposal_id": proposal_id,
        "rejected_by": user_id,
        "reason": reason,
        "source_branch": proposal.source_branch,
        "target_branch": proposal.target_branch,
        },
        )

        # Notify proposal author
        await self._notify_proposal_author(proposal, user_id, "rejected", reason)

        logger.info(f"Successfully rejected proposal {proposal_id}")
        return proposal

        except Exception as e:
        logger.error(f"Failed to reject proposal {proposal_id}: {e}")
        raise

    async def _notify_proposal_author(
        self, proposal: ChangeProposal, reviewer_id: str, action: str, message: str
        ):
        """Notify the proposal author of status changes"""
        try:
        # This could integrate with notification service, email, etc.
        notification = {
        "recipient": proposal.author,
        "type": f"proposal_{action}",
        "subject": f"Proposal {action}: {proposal.title}",
        "message": f"Your proposal '{proposal.title}' has been {action} by {reviewer_id}.\n\nMessage: {message}",


        "proposal_id": proposal.id,
        "reviewer": reviewer_id,
        }

        # Mock notification - would integrate with actual notification service
        logger.info(
        f"Notification sent to {proposal.author}: Proposal {proposal.id} {action}"
        )

        except Exception as e:
        logger.warning(f"Failed to notify proposal author: {e}")

    async def commit_changes(
        self, branch: str, message: str, author: str = "system"
        ) -> str:
        """Commit changes to a branch and return commit ID"""
        try:
        # Validate branch exists
        if not await self._branch_exists(branch):
        raise ValueError(f"Branch '{branch}' does not exist")

        # Check if branch is protected
        if await self._is_protected_branch(branch):
        raise PermissionError(
        f"Cannot directly commit to protected branch '{branch}'"
        )

        # Create a commit using TerminusDB
        # Note: In TerminusDB, commits are created automatically when data is modified
        # This method would typically be called after data modifications

        # Get current branch head
        branch_info = await self._get_branch_info(branch)
        previous_commit = branch_info.get("head", "") if branch_info else ""

        # Generate commit metadata
        commit_metadata = {
        "author": author,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "branch": branch,
        "previous": previous_commit,
        }

        # Store commit metadata in _system branch
        commit_id = str(uuid.uuid4())
        await self.tdb.insert_document(
        self.db_name,
        "_system",
        {
        "@type": "Commit",
        "@id": f"Commit/{commit_id}",
        "commitId": commit_id,
        "branch": branch,
        "author": author,
        "message": message,
        "timestamp": commit_metadata["timestamp"],
        "previousCommit": previous_commit,
        },
        commit_msg = f"Record commit: {message}",
        )

        # Publish commit event
        if self.event_publisher:
        await self._publish_event(
        "branch.commit",
        {
        "branch": branch,
        "message": message,
        "author": author,
        "commit_id": commit_id,
        "timestamp": commit_metadata["timestamp"],
        },
        )

        logger.info(f"Created commit {commit_id} on branch '{branch}'")
        return commit_id

        except Exception as e:
        logger.error(f"Failed to commit changes: {e}")
        raise

    async def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: Optional[str] = None,
        created_by: str = "system",
        ) -> Dict[str, Any]:
        """Create a pull request and return PR info"""
        try:
        # Create a change proposal (which is our PR equivalent)
        proposal = await self.create_proposal(
        source_branch = source_branch,
        target_branch = target_branch,
        title = title,
        description = description,
        user_id = created_by,
        )

        # Convert proposal to PR format for compatibility
        pr_result = {
        "id": proposal.id,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
        "created_by": created_by,
        "status": proposal.status.value,
        "created_at": proposal.created_at.isoformat(),
        "diff_summary": proposal.diff_summary,
        "proposal_id": proposal.id, # Reference to internal proposal
        }

        # Publish PR created event
        if self.event_publisher:
        await self._publish_event("pull_request.created", pr_result)

        logger.info(f"Created pull request {proposal.id}: {title}")
        return pr_result

        except Exception as e:
        logger.error(f"Failed to create pull request: {e}")
        raise

    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        if self.event_publisher:
        try:
        await self.event_publisher.publish(event_type, data)
        except Exception as e:
        logger.error(f"Failed to publish event {event_type}: {e}")

    async def update_branch_properties(
        self, branch_name: str, updates: Dict[str, Any], user_id: str = "system"
        ) -> DomainBranch:
        """
        Update branch properties (metadata).

        Args:
        branch_name (str): Branch name to update
        updates (Dict[str, Any]): Properties dictionary to change (e.g., {"description": "new desc"})
        user_id (str, optional): Requester ID. Defaults to "system".

        Raises:
        ValueError: Branch not found or invalid properties to update
        Exception: Database operation error

        Returns:
        DomainBranch: Updated branch details
        """
        logger.info(
        f"Attempting to update properties for branch '{branch_name}' by user '{user_id}'."
        )

        document_id = f"Branch/{branch_name}"

        # 1. Query original metadata document
        original_doc = await self.tdb.get_document(self.db_name, "_system", document_id)
        if not original_doc:
        raise ValueError(
        f"Could not find metadata for branch '{branch_name}' to update."
        )

        # 2. Apply changes
        updated_doc = original_doc.copy()
        for key, value in updates.items():
        # Can restrict to update only fields defined in the model.
        # Here we assume all passed keys will be updated.
        updated_doc[key] = value

        # 수정자 및 수정 hours 업데이트
        updated_doc["modifiedBy"] = user_id
        updated_doc["modifiedAt"] = datetime.utcnow().isoformat() + "Z"

        # 3. Update document
        try:
        await self.tdb.update_document(
        self.db_name,
        "_system",
        updated_doc,
        commit_msg = f"Update properties for branch '{branch_name}'",
        )
        logger.info(f"Successfully updated properties for branch '{branch_name}'.")
        except Exception as e:
        logger.error(f"Failed to update document for branch '{branch_name}': {e}")
        raise Exception("Failed to save branch property updates.") from e

        # 4. Publish event
        if self.event_publisher:
        try:
        await self.event_publisher.publish_branch_updated(
        branch_name = branch_name,
        updates = updates,
        author = user_id,
        )
        logger.info(
        f"Published 'branch.updated' event for branch '{branch_name}'."
        )
        except Exception as e:
        logger.warning(
        f"Failed to publish branch update event for '{branch_name}': {e}"
        )

        # 5. Return latest information
        updated_branch = await self.get_branch(branch_name)
        if not updated_branch:
        raise Exception(
        f"Could not retrieve branch '{branch_name}' immediately after update."
        )

        return updated_branch
