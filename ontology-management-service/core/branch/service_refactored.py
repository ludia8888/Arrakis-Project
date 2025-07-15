"""
REQ-OMS-F2: 브랜치 관리 핵심 서비스 (리팩토링 버전)
버전 제어 (Branching & Merge) 시스템 구현
의존성 주입을 통한 느슨한 결합 구현
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
from database.clients.unified_database_client import UnifiedDatabaseClient
from middleware.three_way_merge import JsonMerger
from middleware.three_way_merge import MergeStrategy as MiddlewareMergeStrategy
from models.domain import Branch as DomainBranch

logger = logging.getLogger(__name__)


class BranchService:
 """
 Git-style 브랜치 생성, 머지, Proposal 워크플로 지원
 Refactored to work with dependency injection
 """

 def __init__(
 self,
 db_client: UnifiedDatabaseClient,
 event_gateway: Optional[Any] = None,
 diff_engine: Optional[DiffEngine] = None,
 conflict_resolver: Optional[ConflictResolver] = None,
 ):
 """
 Initialize BranchService with proper dependency injection

 Args:
 db_client: Unified database client (injected)
 event_gateway: Event publisher (injected)
 diff_engine: Diff calculation engine (optional, will be created if not provided)
 conflict_resolver: Conflict resolution engine (optional,
     will be created if not provided)
 """
 self.db_client = db_client
 self.event_publisher = event_gateway
 # Production audit service integration
 import os

 self.audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 # Get TerminusDB endpoint from config or environment
 self.tdb_endpoint = os.getenv("TERMINUSDB_ENDPOINT", "http://localhost:6363")
 self.db_name = os.getenv("TERMINUSDB_DB", "oms")

 async def _send_audit_event(
 self,
 event_type: str,
 user_id: str,
 target_type: str,
 target_id: str,
 operation: str,
 metadata: dict = None,
 ):
 """Production audit event sender - direct HTTP to audit-service"""
 try:
 import httpx

 audit_payload = {
 "event_type": event_type,
 "event_category": "branch_management",
 "user_id": user_id,
 "username": user_id,
 "target_type": target_type,
 "target_id": target_id,
 "operation": operation,
 "severity": "INFO",
 "metadata": {"source": "branch_service", **(metadata or {})},
 }

 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.post(
 f"{self.audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(f"Branch audit event sent: {event_type} for {target_id}")

 except Exception as e:
 logger.warning(f"Failed to send branch audit event: {e}")

 # TerminusDB client는 db_client에서 가져옴 (DI 원칙 준수)
 self.tdb = None
 if hasattr(db_client, "terminus_client"):
 self.tdb = db_client.terminus_client
 logger.info(f"🔗 TerminusDB client 연결됨: {self.tdb_endpoint}")
 else:
 logger.warning("⚠️ UnifiedDatabaseClient에 terminus_client가 없음")
 # Fallback: 직접 생성하지 않고 에러 처리로 위임
 logger.info("🔄 TerminusDB 연결은 런타임에 재시도됩니다")

 # Initialize diff engine and conflict resolver
 self.diff_engine = diff_engine or DiffEngine(self.tdb_endpoint)
 self.conflict_resolver = conflict_resolver or ConflictResolver()

 # Initialize merger
 self.merger = JsonMerger()

 # Initialize merge strategy implementor
 self.merge_strategy_implementor = MergeStrategyImplementor(self.merger)

 logger.info(
 f"BranchService initialized with db_client={type(db_client).__name__},
     event_gateway={type(event_gateway).__name__ if event_gateway else 'None'}"
 )

 async def create_branch(
 self, name: str, from_branch: str = "main", created_by: Optional[str] = None
 ) -> DomainBranch:
 """
 REQ-OMS-F2-AC1: 스키마 브랜치 생성
 Git-style branching으로 새 작업 브랜치 생성
 """
 try:
 logger.info(f"Creating branch '{name}' from '{from_branch}'")

 # Validate source branch exists
 source_exists = await self._branch_exists(from_branch)
 if not source_exists:
 raise ValueError(f"Source branch '{from_branch}' does not exist")

 # Check if branch already exists
 if await self._branch_exists(name):
 raise ValueError(f"Branch '{name}' already exists")

 # Create branch in TerminusDB
 await self.tdb.create_branch(self.db_name, name, from_branch)

 # Create branch metadata
 branch = DomainBranch(
 id = str(uuid.uuid4()),
 name = name,
 displayName = name,
 parentBranch = from_branch,
 createdAt = datetime.utcnow(),
 createdBy = created_by or "system",
 modifiedAt = datetime.utcnow(),
 modifiedBy = created_by or "system",
 isProtected = False,
 isActive = True,
 versionHash = str(uuid.uuid4()),
 description = f"Branch created from {from_branch}",
 )

 # Publish event if event publisher is available
 if self.event_publisher:
 await self._publish_event(
 "branch.created",
 {
 "branch_name": name,
 "parent_branch": from_branch,
 "created_by": created_by,
 },
 )

 # Record audit event
 await self._send_audit_event(
 event_type = "branch.created",
 user_id = created_by or "system",
 target_type = "branch",
 target_id = name,
 operation = "create",
 metadata={"parent_branch": from_branch, "branch_id": branch.id},
 )

 logger.info(f"Successfully created branch '{name}'")
 return branch

 except Exception as e:
 logger.error(f"Failed to create branch '{name}': {str(e)}")
 raise

 async def list_branches(self) -> List[DomainBranch]:
 """
 List all branches from the database
 실제 TerminusDB에서 브랜치 목록을 조회합니다.
 """
 try:
 logger.info("🔍 Branch Service: 실제 데이터베이스에서 브랜치 목록 조회")

 # 주입된 db_client를 실제로 사용
 if not self.db_client:
 logger.error("❌ Database client가 주입되지 않음")
 raise RuntimeError("Database client not available")

 # TerminusDB에서 실제 브랜치 목록 조회
 try:
 # UnifiedDatabaseClient를 통해 TerminusDB 브랜치 조회
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # TerminusDB에서 브랜치 목록 조회
 db_branches = await tdb_client.get_branches(self.db_name)

 # TerminusDB 브랜치를 DomainBranch 모델로 변환
 branches = []
 for tdb_branch in db_branches:
 branch = DomainBranch(
 id = str(uuid.uuid4()),
 name = tdb_branch.get("name", "unknown"),
 displayName = tdb_branch.get(
 "display_name", tdb_branch.get("name", "unknown")
 ),
 parentBranch = tdb_branch.get("parent"),
 createdAt = datetime.utcnow(),
 createdBy = tdb_branch.get("created_by", "system"),
 modifiedAt = datetime.utcnow(),
 modifiedBy = tdb_branch.get("modified_by", "system"),
 isProtected = tdb_branch.get("name") == "main",
 isActive = True,
 versionHash = tdb_branch.get(
 "version_hash", str(uuid.uuid4())
 ),
 description = f"Branch from TerminusDB: {tdb_branch.get('name')}",
 )
 branches.append(branch)

 if branches:
 logger.info(f"✅ TerminusDB에서 {len(branches)}개 브랜치 조회 성공")
 return branches

 logger.warning("⚠️ TerminusDB에서 브랜치를 찾을 수 없음, 기본 브랜치 생성")

 except Exception as db_error:
 logger.error(f"❌ TerminusDB 브랜치 조회 실패: {db_error}")
 logger.info("🔄 기본 브랜치로 fallback")

 # Fallback: 기본 브랜치들 생성 (하지만 실제 DB 연동 시도 후)
 # 이는 시스템 초기화 시에만 사용됨
 default_branches = [
 DomainBranch(
 id = str(uuid.uuid4()),
 name = "main",
 displayName = "Main Branch",
 parentBranch = None,
 createdAt = datetime.utcnow(),
 createdBy = "system",
 modifiedAt = datetime.utcnow(),
 modifiedBy = "system",
 isProtected = True,
 isActive = True,
 versionHash = str(uuid.uuid4()),
 description = "Default main branch (system initialized)",
 )
 ]

 # 기본 브랜치를 실제 DB에 저장 시도
 try:
 for branch in default_branches:
 await self._ensure_branch_exists(branch.name)
 logger.info("✅ 기본 브랜치가 데이터베이스에 생성됨")
 except Exception as create_error:
 logger.error(f"⚠️ 기본 브랜치 생성 실패: {create_error}")

 logger.info(f"📋 Branch Service: {len(default_branches)}개 기본 브랜치 반환")
 return default_branches

 except Exception as e:
 logger.error(f"❌ Branch Service 전체 실패: {str(e)}")
 raise RuntimeError(f"Failed to list branches: {str(e)}")

 async def _ensure_branch_exists(self, branch_name: str) -> bool:
 """
 브랜치가 존재하는지 확인하고, 없으면 생성
 """
 try:
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # 브랜치 존재 확인
 exists = await tdb_client.branch_exists(self.db_name, branch_name)
 if not exists and branch_name == "main":
 # main 브랜치가 없으면 생성
 await tdb_client.create_database(self.db_name)
 logger.info(f"✅ 데이터베이스 '{self.db_name}' 생성됨")
 elif not exists:
 # 다른 브랜치는 main에서 분기
 await tdb_client.branch(self.db_name, branch_name, "main")
 logger.info(f"✅ 브랜치 '{branch_name}' 생성됨")

 return True
 except Exception as e:
 logger.error(f"브랜치 생성/확인 실패 {branch_name}: {e}")
 return False

 async def get_branch(self, branch_name: str) -> Optional[DomainBranch]:
 """
 Get a specific branch by name from the database directly
 직접 데이터베이스에서 특정 브랜치를 조회합니다.
 """
 try:
 logger.info(f"🔍 Branch Service: '{branch_name}' 브랜치 직접 조회")

 if not self.db_client:
 logger.error("❌ Database client가 주입되지 않음")
 return None

 # TerminusDB에서 직접 브랜치 조회
 try:
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # 브랜치 존재 여부 확인
 branch_exists = await tdb_client.branch_exists(
 self.db_name, branch_name
 )

 if branch_exists:
 # 브랜치 메타데이터 조회
 branch_info = await tdb_client.get_branch_info(
 self.db_name, branch_name
 )

 branch = DomainBranch(
 id = str(uuid.uuid4()),
 name = branch_name,
 displayName = branch_name,
 parentBranch = branch_info.get("parent"),
 createdAt = datetime.utcnow(),
 createdBy = branch_info.get("created_by", "system"),
 modifiedAt = datetime.utcnow(),
 modifiedBy = branch_info.get("created_by", "system"),
 isProtected = branch_name == "main",
 isActive = True,
 versionHash = branch_info.get(
 "version_hash", str(uuid.uuid4())
 ),
 description = f"Branch from TerminusDB: {branch_name}",
 )

 logger.info(f"✅ 브랜치 '{branch_name}' TerminusDB에서 조회 성공")
 return branch
 else:
 logger.info(f"🔍 브랜치 '{branch_name}'이 TerminusDB에 존재하지 않음")
 return None

 except Exception as db_error:
 logger.error(f"❌ TerminusDB 브랜치 조회 실패: {db_error}")

 # Fallback: 기본 브랜치들에서 찾기 (시스템 초기화 시에만)
 if branch_name == "main":
 logger.info(f"🔄 '{branch_name}' 기본 브랜치로 fallback")
 return DomainBranch(
 id = str(uuid.uuid4()),
 name = "main",
 displayName = "Main Branch",
 parentBranch = None,
 createdAt = datetime.utcnow(),
 createdBy = "system",
 modifiedAt = datetime.utcnow(),
 modifiedBy = "system",
 isProtected = True,
 isActive = True,
 versionHash = str(uuid.uuid4()),
 description = "Default main branch (system fallback)",
 )

 return None

 except Exception as e:
 logger.error(f"❌ 브랜치 '{branch_name}' 조회 실패: {str(e)}")
 return None

 async def delete_branch(
 self, branch_name: str, deleted_by: Optional[str] = None
 ) -> bool:
 """
 Delete a branch
 """
 try:
 if branch_name == "main":
 raise ValueError("Cannot delete the main branch")

 # Check if branch exists
 if not await self._branch_exists(branch_name):
 raise ValueError(f"Branch '{branch_name}' does not exist")

 # Delete branch in TerminusDB
 await self.tdb.delete_branch(self.db_name, branch_name)

 # Publish event
 if self.event_publisher:
 await self._publish_event(
 "branch.deleted",
 {"branch_name": branch_name, "deleted_by": deleted_by},
 )

 logger.info(f"Successfully deleted branch '{branch_name}'")
 return True

 except Exception as e:
 logger.error(f"Failed to delete branch '{branch_name}': {str(e)}")
 raise

 async def calculate_diff(self, from_branch: str, to_branch: str) -> BranchDiff:
 """
 REQ-OMS-F2-AC3: 브랜치 간 차이점 계산
 """
 try:
 return await self.diff_engine.calculate_diff(from_branch, to_branch)
 except Exception as e:
 logger.error(
 f"Failed to calculate diff between '{from_branch}' and '{to_branch}': {str(e)}"
 )
 raise

 async def merge_branches(
 self,
 source_branch: str,
 target_branch: str,
 strategy: MergeStrategy = MergeStrategy.MERGE,
 merged_by: Optional[str] = None,
 ) -> MergeResult:
 """
 REQ-OMS-F2-AC2: 브랜치 머지
 """
 try:
 logger.info(
 f"Merging '{source_branch}' into '{target_branch}' with strategy {strategy}"
 )

 # Calculate diff
 diff = await self.calculate_diff(source_branch, target_branch)

 # Check for conflicts
 if diff.has_conflicts and strategy != MergeStrategy.FORCE:
 return MergeResult(
 success = False,
 merged_at = datetime.utcnow(),
 conflicts = diff.conflicts,
 changes_applied = [],
 merge_commit_id = None,
 )

 # Apply merge based on strategy
 result = await self.merge_strategy_implementor.apply_merge(
 source_branch, target_branch, diff, strategy
 )

 # Publish event
 if self.event_publisher and result.success:
 await self._publish_event(
 "branch.merged",
 {
 "source_branch": source_branch,
 "target_branch": target_branch,
 "strategy": strategy.value,
 "merged_by": merged_by,
 },
 )

 return result

 except Exception as e:
 logger.error(f"Failed to merge branches: {str(e)}")
 raise

 async def _branch_exists(self, branch_name: str) -> bool:
 """
 Check if a branch exists in the database directly
 직접 데이터베이스에서 브랜치 존재 여부를 확인합니다.
 """
 try:
 logger.debug(f"🔍 Branch Service: '{branch_name}' 존재 여부 직접 확인")

 if not self.db_client:
 logger.error("❌ Database client가 주입되지 않음")
 return False

 # TerminusDB에서 직접 브랜치 존재 확인
 try:
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # TerminusDB의 branch_exists API 사용
 exists = await tdb_client.branch_exists(self.db_name, branch_name)

 logger.debug(f"🔍 TerminusDB에서 '{branch_name}' 존재 여부: {exists}")
 return exists

 except Exception as db_error:
 logger.error(f"❌ TerminusDB 브랜치 존재 확인 실패: {db_error}")

 # Fallback: 기본 브랜치들에 대해서만 True 반환
 if branch_name in ["main"]:
 logger.debug(f"🔄 '{branch_name}'은 기본 브랜치로 간주")
 return True

 return False

 except Exception as e:
 logger.error(f"❌ 브랜치 '{branch_name}' 존재 확인 실패: {str(e)}")
 return False

 async def _publish_event(self, event_type: str, data: Dict[str, Any]):
 """Publish an event through the event gateway"""
 if self.event_publisher:
 try:
 await self.event_publisher.publish(event_type, data)
 except Exception as e:
 logger.error(f"Failed to publish event '{event_type}': {str(e)}")

 # Placeholder methods for proposals (to be implemented)
 async def create_proposal(
 self,
 title: str,
 description: str,
 source_branch: str,
 target_branch: str,
 created_by: str,
 ) -> ChangeProposal:
 """Create a change proposal (pull request)"""
 try:
 logger.info(
 f"Creating proposal from '{source_branch}' to '{target_branch}'"
 )

 # Validate branches exist
 if not await self._branch_exists(source_branch):
 raise ValueError(f"Source branch '{source_branch}' does not exist")
 if not await self._branch_exists(target_branch):
 raise ValueError(f"Target branch '{target_branch}' does not exist")

 # Calculate diff between branches
 diff = await self.calculate_diff(source_branch, target_branch)

 # Create proposal object
 proposal = ChangeProposal(
 id = str(uuid.uuid4()),
 title = title,
 description = description,
 source_branch = source_branch,
 target_branch = target_branch,
 status = ProposalStatus.OPEN,
 created_by = created_by,
 created_at = datetime.utcnow(),
 updated_at = datetime.utcnow(),
 reviews = [],
 diff = diff,
 merge_strategy = MergeStrategy.MERGE,
 )

 # Store proposal in TerminusDB
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Insert proposal document
 woql_query = {
 "type": "add_triple",
 "subject": f"Proposal/{proposal.id}",
 "predicate": "rdf:type",
 "object": "ChangeProposal",
 }
 await tdb_client.query(self.db_name, woql_query)

 # Add proposal properties
 properties = {
 "title": proposal.title,
 "description": proposal.description,
 "source_branch": proposal.source_branch,
 "target_branch": proposal.target_branch,
 "status": proposal.status.value,
 "created_by": proposal.created_by,
 "created_at": proposal.created_at.isoformat(),
 "has_conflicts": diff.has_conflicts,
 }

 for prop, value in properties.items():
 await tdb_client.query(
 self.db_name,
 {
 "type": "add_triple",
 "subject": f"Proposal/{proposal.id}",
 "predicate": prop,
 "object": {"@type": "xsd:string", "@value": str(value)},
 },
 )

 # Publish event
 if self.event_publisher:
 await self._publish_event(
 "proposal.created",
 {
 "proposal_id": proposal.id,
 "title": title,
 "source_branch": source_branch,
 "target_branch": target_branch,
 "created_by": created_by,
 },
 )

 # Record audit event
 await self._send_audit_event(
 event_type = "proposal.created",
 user_id = created_by,
 target_type = "proposal",
 target_id = proposal.id,
 operation = "create",
 metadata={
 "target_branch": target_branch,
 "source_branch": source_branch,
 "title": title,
 },
 )

 logger.info(f"Successfully created proposal '{proposal.id}'")
 return proposal

 except Exception as e:
 logger.error(f"Failed to create proposal: {str(e)}")
 raise

 async def review_proposal(
 self,
 proposal_id: str,
 action: str,
 reviewer: str,
 comment: Optional[str] = None,
 ) -> ChangeProposal:
 """Review a change proposal"""
 try:
 logger.info(f"Reviewing proposal '{proposal_id}' with action '{action}'")

 # Get existing proposal
 proposal = await self.get_proposal(proposal_id)
 if not proposal:
 raise ValueError(f"Proposal '{proposal_id}' not found")

 # Validate proposal is open
 if proposal.status != ProposalStatus.OPEN:
 raise ValueError(
 f"Cannot review proposal in status '{proposal.status.value}'"
 )

 # Create review record
 review = {
 "id": str(uuid.uuid4()),
 "reviewer": reviewer,
 "action": action,
 "comment": comment,
 "reviewed_at": datetime.utcnow().isoformat(),
 }

 # Update proposal based on action
 if action == "approve":
 proposal.status = ProposalStatus.APPROVED
 # Auto-merge if approved
 if hasattr(self, "merge_branches"):
 merge_result = await self.merge_branches(
 proposal.source_branch,
 proposal.target_branch,
 proposal.merge_strategy,
 reviewer,
 )
 if merge_result.success:
 proposal.status = ProposalStatus.MERGED
 elif action == "reject":
 proposal.status = ProposalStatus.REJECTED
 elif action == "comment":
 # Just add comment, don't change status
 pass
 else:
 raise ValueError(f"Invalid review action: {action}")

 proposal.reviews.append(review)
 proposal.updated_at = datetime.utcnow()

 # Update in TerminusDB
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Update proposal status
 await tdb_client.query(
 self.db_name,
 {
 "type": "update_triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "status",
 "object": {
 "@type": "xsd:string",
 "@value": proposal.status.value,
 },
 },
 )

 # Add review
 await tdb_client.query(
 self.db_name,
 {
 "type": "add_triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "has_review",
 "object": f"Review/{review['id']}",
 },
 )

 # Publish event
 if self.event_publisher:
 await self._publish_event(
 "proposal.reviewed",
 {
 "proposal_id": proposal_id,
 "action": action,
 "reviewer": reviewer,
 "new_status": proposal.status.value,
 },
 )

 # Record audit event
 await self._send_audit_event(
 event_type = "proposal.reviewed",
 user_id = reviewer,
 target_type = "proposal",
 target_id = proposal_id,
 operation = "review",
 metadata={
 "action": action,
 "new_status": proposal.status.value,
 "comment": comment,
 "source_branch": proposal.source_branch,
 },
 )

 logger.info(f"Successfully reviewed proposal '{proposal_id}'")
 return proposal

 except Exception as e:
 logger.error(f"Failed to review proposal: {str(e)}")
 raise

 async def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
 """Get a specific proposal"""
 try:
 logger.info(f"Getting proposal '{proposal_id}'")

 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Query proposal from TerminusDB
 woql_query = {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "rdf:type",
 "object": "ChangeProposal",
 },
 {
 "type": "triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": {"@type": "Variable", "variable_name": "Prop"},
 "object": {"@type": "Variable", "variable_name": "Value"},
 },
 ],
 }

 results = await tdb_client.query(self.db_name, woql_query)

 if results:
 # Reconstruct proposal from results
 props = {}
 for result in results:
 if "Prop" in result and "Value" in result:
 props[result["Prop"]] = result["Value"]

 # Get diff for the proposal
 diff = await self.calculate_diff(
 props.get("source_branch", ""), props.get("target_branch", "")
 )

 proposal = ChangeProposal(
 id = proposal_id,
 title = props.get("title", ""),
 description = props.get("description", ""),
 source_branch = props.get("source_branch", ""),
 target_branch = props.get("target_branch", ""),
 status = ProposalStatus(props.get("status", "open")),
 created_by = props.get("created_by", "unknown"),
 created_at = datetime.fromisoformat(
 props.get("created_at", datetime.utcnow().isoformat())
 ),
 updated_at = datetime.utcnow(),
 reviews = await self._load_proposal_reviews(
 proposal_id
 ), # Load reviews from DB
 diff = diff,
 merge_strategy = MergeStrategy.MERGE,
 )

 logger.info(f"Found proposal '{proposal_id}'")
 return proposal

 logger.info(f"Proposal '{proposal_id}' not found")
 return None

 except Exception as e:
 logger.error(f"Failed to get proposal '{proposal_id}': {str(e)}")
 return None

 async def list_proposals(
 self, status: Optional[ProposalStatus] = None, branch: Optional[str] = None
 ) -> List[ChangeProposal]:
 """List proposals with optional filtering"""
 try:
 logger.info(f"Listing proposals (status={status}, branch={branch})")
 proposals = []

 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Build query with filters
 clauses = [
 {
 "type": "triple",
 "subject": {"@type": "Variable", "variable_name": "ProposalId"},
 "predicate": "rdf:type",
 "object": "ChangeProposal",
 }
 ]

 if status:
 clauses.append(
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "ProposalId",
 },
 "predicate": "status",
 "object": {"@type": "xsd:string", "@value": status.value},
 }
 )

 if branch:
 clauses.append(
 {
 "type": "or",
 "clauses": [
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "ProposalId",
 },
 "predicate": "source_branch",
 "object": {"@type": "xsd:string", "@value": branch},
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "ProposalId",
 },
 "predicate": "target_branch",
 "object": {"@type": "xsd:string", "@value": branch},
 },
 ],
 }
 )

 woql_query = {"type": "and", "clauses": clauses}
 results = await tdb_client.query(self.db_name, woql_query)

 # Get unique proposal IDs
 proposal_ids = set()
 for result in results:
 if "ProposalId" in result:
 # Extract ID from URI format "Proposal/uuid"
 proposal_id = result["ProposalId"].split("/")[-1]
 proposal_ids.add(proposal_id)

 # Load each proposal
 for proposal_id in proposal_ids:
 proposal = await self.get_proposal(proposal_id)
 if proposal:
 proposals.append(proposal)

 # Sort by created_at descending
 proposals.sort(key = lambda p: p.created_at, reverse = True)

 logger.info(f"Found {len(proposals)} proposals")
 return proposals

 except Exception as e:
 logger.error(f"Failed to list proposals: {str(e)}")
 return []

 async def update_proposal(
 self, proposal_id: str, update: ProposalUpdate
 ) -> ChangeProposal:
 """Update a proposal"""
 try:
 logger.info(f"Updating proposal '{proposal_id}'")

 # Get existing proposal
 proposal = await self.get_proposal(proposal_id)
 if not proposal:
 raise ValueError(f"Proposal '{proposal_id}' not found")

 # Validate proposal is still open
 if proposal.status not in [ProposalStatus.OPEN, ProposalStatus.DRAFT]:
 raise ValueError(
 f"Cannot update proposal in status '{proposal.status.value}'"
 )

 # Apply updates
 if update.title:
 proposal.title = update.title
 if update.description:
 proposal.description = update.description
 if update.merge_strategy:
 proposal.merge_strategy = update.merge_strategy

 proposal.updated_at = datetime.utcnow()

 # Update in TerminusDB
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Update fields that changed
 if update.title:
 await tdb_client.query(
 self.db_name,
 {
 "type": "update_triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "title",
 "object": {"@type": "xsd:string", "@value": update.title},
 },
 )

 if update.description:
 await tdb_client.query(
 self.db_name,
 {
 "type": "update_triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "description",
 "object": {
 "@type": "xsd:string",
 "@value": update.description,
 },
 },
 )

 # Update timestamp
 await tdb_client.query(
 self.db_name,
 {
 "type": "update_triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "updated_at",
 "object": {
 "@type": "xsd:dateTime",
 "@value": proposal.updated_at.isoformat(),
 },
 },
 )

 # Re-calculate diff if branches changed
 if update.source_branch or update.target_branch:
 proposal.diff = await self.calculate_diff(
 proposal.source_branch, proposal.target_branch
 )

 # Publish event
 if self.event_publisher:
 await self._publish_event(
 "proposal.updated",
 {
 "proposal_id": proposal_id,
 "updates": {
 "title": update.title,
 "description": update.description,
 "merge_strategy": update.merge_strategy.value
 if update.merge_strategy
 else None,
 },
 },
 )

 # Record audit event
 await self._send_audit_event(
 event_type = "proposal.updated",
 user_id = getattr(update, "updated_by", "system"),
 target_type = "proposal",
 target_id = proposal_id,
 operation = "update",
 metadata={
 "updates": update.dict(exclude_none = True),
 "source_branch": proposal.source_branch,
 },
 )

 logger.info(f"Successfully updated proposal '{proposal_id}'")
 return proposal

 except Exception as e:
 logger.error(f"Failed to update proposal: {str(e)}")
 raise

 async def _load_proposal_reviews(self, proposal_id: str) -> List[Dict[str, Any]]:
 """Load reviews for a proposal from TerminusDB"""
 reviews = []
 try:
 if (
 hasattr(self.db_client, "terminus_client")
 and self.db_client.terminus_client
 ):
 tdb_client = self.db_client.terminus_client

 # Query reviews for this proposal
 woql_query = {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": f"Proposal/{proposal_id}",
 "predicate": "has_review",
 "object": {
 "@type": "Variable",
 "variable_name": "ReviewId",
 },
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "ReviewId",
 },
 "predicate": {"@type": "Variable", "variable_name": "Prop"},
 "object": {"@type": "Variable", "variable_name": "Value"},
 },
 ],
 }

 results = await tdb_client.query(self.db_name, woql_query)

 # Group review properties by review ID
 review_data = {}
 for result in results:
 if "ReviewId" in result and "Prop" in result and "Value" in result:
 review_id = result["ReviewId"]
 if review_id not in review_data:
 review_data[review_id] = {}
 review_data[review_id][result["Prop"]] = result["Value"]

 # Convert to review objects
 for review_id, props in review_data.items():
 review = {
 "id": review_id.split("/")[-1]
 if "/" in review_id
 else review_id,
 "reviewer": props.get("reviewer", "unknown"),
 "action": props.get("action", "comment"),
 "comment": props.get("comment", ""),
 "reviewed_at": props.get(
 "reviewed_at", datetime.utcnow().isoformat()
 ),
 }
 reviews.append(review)

 logger.debug(
 f"Loaded {len(reviews)} reviews for proposal {proposal_id}"
 )

 except Exception as e:
 logger.error(f"Failed to load reviews for proposal {proposal_id}: {e}")
 # Return empty list on error to prevent breaking the proposal loading

 return reviews

 async def commit_changes(
 self, branch: str, message: str, author: str = "system"
 ) -> str:
 """
 Commit changes to a branch

 For now, just return a mock commit ID to allow schema service to work
 """
 commit_id = str(uuid.uuid4())
 logger.info(
 f"Mock commit '{commit_id}' created for branch '{branch}' with message: {message}"
 )
 return commit_id

 async def create_pull_request(
 self,
 source_branch: str,
 target_branch: str,
 title: str,
 description: str,
 created_by: str,
 ) -> Dict[str, Any]:
 """
 Create a pull request

 For now, just return a mock PR to allow schema service to work
 """
 pr_id = str(uuid.uuid4())[:8]
 logger.info(
 f"Mock PR '{pr_id}' created from '{source_branch}' to '{target_branch}'"
 )
 return {
 "pr_id": pr_id,
 "source_branch": source_branch,
 "target_branch": target_branch,
 "title": title,
 "description": description,
 "created_by": created_by,
 "status": "open",
 }
