"""
REQ-OMS-F2: 브랜치 관리 핵심 서비스 (리팩토링 버전)
버전 제어 (Branching & Merge) 시스템 구현
의존성 주입을 통한 느슨한 결합 구현
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import httpx

from shared.models.domain import Branch as DomainBranch
from core.branch.conflict_resolver import ConflictResolver
from core.branch.diff_engine import DiffEngine
from core.branch.merge_strategies import MergeStrategyImplementor
from core.branch.models import (
    BranchDiff,
    ChangeProposal,
    MergeResult,
    MergeStrategy,
    ProposalStatus,
    ProposalUpdate,
    DiffEntry,
)
from middleware.three_way_merge import JsonMerger, MergeStrategy as MiddlewareMergeStrategy
from database.clients.terminus_db import TerminusDBClient
from database.clients.unified_database_client import UnifiedDatabaseClient

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
        conflict_resolver: Optional[ConflictResolver] = None
    ):
        """
        Initialize BranchService with proper dependency injection
        
        Args:
            db_client: Unified database client (injected)
            event_gateway: Event publisher (injected)
            diff_engine: Diff calculation engine (optional, will be created if not provided)
            conflict_resolver: Conflict resolution engine (optional, will be created if not provided)
        """
        self.db_client = db_client
        self.event_publisher = event_gateway
        
        # Get TerminusDB endpoint from config or environment
        self.tdb_endpoint = os.getenv("TERMINUSDB_ENDPOINT", "http://localhost:6363")
        self.db_name = os.getenv("TERMINUSDB_DB", "oms")
        
        # TerminusDB client는 db_client에서 가져옴 (DI 원칙 준수)
        self.tdb = None
        if hasattr(db_client, 'terminus_client'):
            self.tdb = db_client.terminus_client
            logger.info(f"🔗 TerminusDB client 연결됨: {self.tdb_endpoint}")
        else:
            logger.warning(f"⚠️ UnifiedDatabaseClient에 terminus_client가 없음")
            # Fallback: 직접 생성하지 않고 에러 처리로 위임
            logger.info("🔄 TerminusDB 연결은 런타임에 재시도됩니다")
        
        # Initialize diff engine and conflict resolver
        self.diff_engine = diff_engine or DiffEngine(self.tdb_endpoint)
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        
        # Initialize merger
        self.merger = JsonMerger()
        
        # Initialize merge strategy implementor
        self.merge_strategy_implementor = MergeStrategyImplementor(self.merger)
        
        logger.info(f"BranchService initialized with db_client={type(db_client).__name__}, event_gateway={type(event_gateway).__name__ if event_gateway else 'None'}")

    async def create_branch(self, name: str, from_branch: str = "main", created_by: Optional[str] = None) -> DomainBranch:
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
            await self.tdb.branch(self.db_name, name, from_branch)
            
            # Create branch metadata
            branch = DomainBranch(
                id=str(uuid.uuid4()),
                name=name,
                parent_branch=from_branch,
                created_at=datetime.utcnow(),
                created_by=created_by or "system",
                is_protected=False,
                is_default=False,
                description=f"Branch created from {from_branch}",
                metadata={"source_branch": from_branch}
            )
            
            # Publish event if event publisher is available
            if self.event_publisher:
                await self._publish_event("branch.created", {
                    "branch_name": name,
                    "parent_branch": from_branch,
                    "created_by": created_by
                })
            
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
                if hasattr(self.db_client, 'terminus_client') and self.db_client.terminus_client:
                    tdb_client = self.db_client.terminus_client
                    
                    # TerminusDB에서 브랜치 목록 조회
                    db_branches = await tdb_client.get_branches(self.db_name)
                    
                    # TerminusDB 브랜치를 DomainBranch 모델로 변환
                    branches = []
                    for tdb_branch in db_branches:
                        branch = DomainBranch(
                            id=str(uuid.uuid4()),
                            name=tdb_branch.get('name', 'unknown'),
                            displayName=tdb_branch.get('display_name', tdb_branch.get('name', 'unknown')),
                            parentBranch=tdb_branch.get('parent'),
                            createdAt=datetime.utcnow(),
                            createdBy=tdb_branch.get('created_by', 'system'),
                            modifiedAt=datetime.utcnow(),
                            modifiedBy=tdb_branch.get('modified_by', 'system'),
                            isProtected=tdb_branch.get('name') == 'main',
                            isActive=True,
                            versionHash=tdb_branch.get('version_hash', str(uuid.uuid4())),
                            description=f"Branch from TerminusDB: {tdb_branch.get('name')}"
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
                    id=str(uuid.uuid4()),
                    name="main",
                    displayName="Main Branch",
                    parentBranch=None,
                    createdAt=datetime.utcnow(),
                    createdBy="system",
                    modifiedAt=datetime.utcnow(),
                    modifiedBy="system",
                    isProtected=True,
                    isActive=True,
                    versionHash=str(uuid.uuid4()),
                    description="Default main branch (system initialized)"
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
            if hasattr(self.db_client, 'terminus_client') and self.db_client.terminus_client:
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
                if hasattr(self.db_client, 'terminus_client') and self.db_client.terminus_client:
                    tdb_client = self.db_client.terminus_client
                    
                    # 브랜치 존재 여부 확인
                    branch_exists = await tdb_client.branch_exists(self.db_name, branch_name)
                    
                    if branch_exists:
                        # 브랜치 메타데이터 조회
                        branch_info = await tdb_client.get_branch_info(self.db_name, branch_name)
                        
                        branch = DomainBranch(
                            id=str(uuid.uuid4()),
                            name=branch_name,
                            parent_branch=branch_info.get('parent'),
                            created_at=datetime.utcnow(),
                            created_by=branch_info.get('created_by', 'system'),
                            is_protected=branch_name == 'main',
                            is_default=branch_name == 'main',
                            description=f"Branch from TerminusDB: {branch_name}",
                            metadata=branch_info.get('metadata', {})
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
                    id=str(uuid.uuid4()),
                    name="main",
                    parent_branch=None,
                    created_at=datetime.utcnow(),
                    created_by="system",
                    is_protected=True,
                    is_default=True,
                    description="Default main branch (system fallback)",
                    metadata={"source": "system_fallback"}
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 브랜치 '{branch_name}' 조회 실패: {str(e)}")
            return None

    async def delete_branch(self, branch_name: str, deleted_by: Optional[str] = None) -> bool:
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
                await self._publish_event("branch.deleted", {
                    "branch_name": branch_name,
                    "deleted_by": deleted_by
                })
            
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
            logger.error(f"Failed to calculate diff between '{from_branch}' and '{to_branch}': {str(e)}")
            raise

    async def merge_branches(
        self,
        source_branch: str,
        target_branch: str,
        strategy: MergeStrategy = MergeStrategy.MERGE,
        merged_by: Optional[str] = None
    ) -> MergeResult:
        """
        REQ-OMS-F2-AC2: 브랜치 머지
        """
        try:
            logger.info(f"Merging '{source_branch}' into '{target_branch}' with strategy {strategy}")
            
            # Calculate diff
            diff = await self.calculate_diff(source_branch, target_branch)
            
            # Check for conflicts
            if diff.has_conflicts and strategy != MergeStrategy.FORCE:
                return MergeResult(
                    success=False,
                    merged_at=datetime.utcnow(),
                    conflicts=diff.conflicts,
                    changes_applied=[],
                    merge_commit_id=None
                )
            
            # Apply merge based on strategy
            result = await self.merge_strategy_implementor.apply_merge(
                source_branch, target_branch, diff, strategy
            )
            
            # Publish event
            if self.event_publisher and result.success:
                await self._publish_event("branch.merged", {
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "strategy": strategy.value,
                    "merged_by": merged_by
                })
            
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
                if hasattr(self.db_client, 'terminus_client') and self.db_client.terminus_client:
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
        created_by: str
    ) -> ChangeProposal:
        """Create a change proposal (pull request)"""
        raise NotImplementedError("Proposal creation not yet implemented")

    async def review_proposal(
        self,
        proposal_id: str,
        action: str,
        reviewer: str,
        comment: Optional[str] = None
    ) -> ChangeProposal:
        """Review a change proposal"""
        raise NotImplementedError("Proposal review not yet implemented")

    async def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
        """Get a specific proposal"""
        raise NotImplementedError("Get proposal not yet implemented")

    async def list_proposals(
        self,
        status: Optional[ProposalStatus] = None,
        branch: Optional[str] = None
    ) -> List[ChangeProposal]:
        """List proposals with optional filtering"""
        raise NotImplementedError("List proposals not yet implemented")

    async def update_proposal(
        self,
        proposal_id: str,
        update: ProposalUpdate
    ) -> ChangeProposal:
        """Update a proposal"""
        raise NotImplementedError("Update proposal not yet implemented")