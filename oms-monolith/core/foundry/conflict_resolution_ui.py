"""
Foundry-style Conflict Resolution UI Backend
3-way diff와 시각적 충돌 해결 지원
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from terminusdb_client import WOQLClient
from core.branch.models import Conflict, MergeResult
from core.monitoring.migration_monitor import track_native_operation

logger = logging.getLogger(__name__)


class ConflictResolutionStrategy(Enum):
    """충돌 해결 전략"""
    TAKE_SOURCE = "take_source"      # source 브랜치 것을 선택
    TAKE_TARGET = "take_target"      # target 브랜치 것을 선택
    TAKE_BOTH = "take_both"          # 둘 다 유지 (가능한 경우)
    MANUAL = "manual"                # 수동으로 새 값 입력
    SEMANTIC_MERGE = "semantic_merge" # AI 기반 의미적 병합


@dataclass
class ConflictContext:
    """충돌 컨텍스트 정보"""
    conflict: Conflict
    base_value: Any          # 공통 조상의 값
    source_value: Any        # source 브랜치의 값
    target_value: Any        # target 브랜치의 값
    semantic_analysis: Dict  # AI 분석 결과
    affected_entities: List[str]  # 영향받는 엔티티들
    resolution_hints: List[str]   # 해결 힌트


class FoundryStyleConflictResolver:
    """Foundry처럼 시각적이고 지능적인 충돌 해결"""
    
    def __init__(self, client: WOQLClient):
        self.client = client
        
    @track_native_operation("prepare_conflict_resolution")
    async def prepare_conflict_resolution(
        self, 
        source_branch: str, 
        target_branch: str
    ) -> Dict[str, Any]:
        """
        충돌 해결을 위한 모든 정보 준비
        Foundry의 3-way diff view를 위한 데이터
        """
        # 1. 공통 조상 찾기
        common_ancestor = await self._find_common_ancestor(source_branch, target_branch)
        
        # 2. 3-way diff 생성
        three_way_diff = {
            "base_to_source": self.client.diff(common_ancestor, source_branch),
            "base_to_target": self.client.diff(common_ancestor, target_branch),
            "source_to_target": self.client.diff(source_branch, target_branch)
        }
        
        # 3. 충돌 분석
        conflicts = await self._analyze_conflicts(three_way_diff)
        
        # 4. 각 충돌에 대한 컨텍스트 생성
        conflict_contexts = []
        for conflict in conflicts:
            context = await self._create_conflict_context(
                conflict, 
                common_ancestor, 
                source_branch, 
                target_branch
            )
            conflict_contexts.append(context)
            
        # 5. 자동 해결 가능한 충돌 식별
        auto_resolvable = await self._identify_auto_resolvable(conflict_contexts)
        
        return {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "common_ancestor": common_ancestor,
            "conflicts": conflict_contexts,
            "auto_resolvable": auto_resolvable,
            "three_way_diff": three_way_diff,
            "resolution_session_id": f"resolution_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
    @track_native_operation("apply_conflict_resolution")
    async def apply_conflict_resolution(
        self,
        session_id: str,
        resolutions: List[Dict[str, Any]],
        author: str
    ) -> MergeResult:
        """
        사용자가 선택한 충돌 해결 방법 적용
        """
        resolution_branch = f"conflict_resolution_{session_id}"
        
        try:
            # 1. 해결 브랜치 생성
            self.client.create_branch(resolution_branch)
            self.client.branch = resolution_branch
            
            # 2. 각 충돌 해결 적용
            for resolution in resolutions:
                await self._apply_single_resolution(resolution)
                
            # 3. 해결 결과 검증
            validation = await self._validate_resolution(resolution_branch)
            
            if validation["is_valid"]:
                # 4. 타겟 브랜치로 머지
                merge_result = self.client.merge(
                    resolution_branch,
                    resolutions[0]["target_branch"],
                    author=author,
                    message=f"Resolved conflicts via session {session_id}"
                )
                
                # 5. 임시 브랜치 삭제
                self.client.delete_branch(resolution_branch)
                
                return MergeResult(
                    merge_commit=merge_result.get("commit"),
                    conflicts=[],
                    resolution_summary={
                        "total_conflicts": len(resolutions),
                        "auto_resolved": len([r for r in resolutions if r["strategy"] != "manual"]),
                        "manual_resolved": len([r for r in resolutions if r["strategy"] == "manual"])
                    }
                )
            else:
                return MergeResult(
                    merge_commit=None,
                    conflicts=validation["errors"],
                    error="Resolution validation failed"
                )
                
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            # 정리
            try:
                self.client.delete_branch(resolution_branch)
            except:
                pass
                
            return MergeResult(
                merge_commit=None,
                conflicts=[],
                error=str(e)
            )
            
    async def _create_conflict_context(
        self,
        conflict: Conflict,
        base: str,
        source: str,
        target: str
    ) -> ConflictContext:
        """충돌에 대한 풍부한 컨텍스트 생성"""
        # 각 브랜치에서 값 가져오기
        base_value = await self._get_value_at_branch(conflict.resource_id, base)
        source_value = await self._get_value_at_branch(conflict.resource_id, source)
        target_value = await self._get_value_at_branch(conflict.resource_id, target)
        
        # 의미적 분석 (VectorLink 활용)
        semantic_analysis = await self._semantic_conflict_analysis(
            conflict, base_value, source_value, target_value
        )
        
        # 영향받는 엔티티 찾기
        affected = await self._find_affected_entities(conflict.resource_id)
        
        # 해결 힌트 생성
        hints = self._generate_resolution_hints(
            conflict, semantic_analysis, affected
        )
        
        return ConflictContext(
            conflict=conflict,
            base_value=base_value,
            source_value=source_value,
            target_value=target_value,
            semantic_analysis=semantic_analysis,
            affected_entities=affected,
            resolution_hints=hints
        )
        
    async def _semantic_conflict_analysis(
        self,
        conflict: Conflict,
        base: Any,
        source: Any,
        target: Any
    ) -> Dict:
        """AI를 활용한 충돌 의미 분석"""
        # VectorLink로 유사성 분석
        if isinstance(source, str) and isinstance(target, str):
            # 두 값의 의미적 유사도 계산
            similarity = await self._calculate_semantic_similarity(source, target)
            
            # 자동 병합 가능 여부 판단
            if similarity > 0.9:
                return {
                    "similarity": similarity,
                    "auto_mergeable": True,
                    "suggested_value": source,  # 거의 같으므로 하나 선택
                    "reason": "Values are semantically identical"
                }
            elif similarity > 0.7:
                return {
                    "similarity": similarity,
                    "auto_mergeable": False,
                    "suggestion": "Manual review recommended - similar but not identical",
                    "combined_value": f"{source} / {target}"  # 둘 다 보존 제안
                }
            else:
                return {
                    "similarity": similarity,
                    "auto_mergeable": False,
                    "suggestion": "Significant semantic difference - manual resolution required"
                }
        
        return {"auto_mergeable": False}
        
    def _generate_resolution_hints(
        self,
        conflict: Conflict,
        semantic: Dict,
        affected: List[str]
    ) -> List[str]:
        """지능적인 해결 힌트 생성"""
        hints = []
        
        # 영향도 기반 힌트
        if len(affected) > 10:
            hints.append(f"⚠️ High impact: {len(affected)} entities will be affected")
        
        # 충돌 타입 기반 힌트
        if conflict.conflict_type == "cardinality_change":
            hints.append("💡 Consider data migration for existing relationships")
        elif conflict.conflict_type == "type_change":
            hints.append("💡 Type conversion may be needed for existing data")
            
        # 의미적 분석 기반 힌트
        if semantic.get("auto_mergeable"):
            hints.append("✅ Values are semantically equivalent - safe to auto-merge")
        elif semantic.get("similarity", 0) > 0.5:
            hints.append("🤔 Values are partially similar - review carefully")
            
        return hints
        
    async def _apply_single_resolution(self, resolution: Dict):
        """단일 충돌 해결 적용"""
        strategy = resolution["strategy"]
        conflict = resolution["conflict"]
        
        if strategy == ConflictResolutionStrategy.TAKE_SOURCE.value:
            # Source 값으로 업데이트
            await self._update_value(
                conflict["resource_id"],
                resolution["source_value"]
            )
        elif strategy == ConflictResolutionStrategy.TAKE_TARGET.value:
            # Target 값 유지 (아무것도 안함)
            pass
        elif strategy == ConflictResolutionStrategy.MANUAL.value:
            # 사용자가 입력한 값으로 업데이트
            await self._update_value(
                conflict["resource_id"],
                resolution["manual_value"]
            )
        elif strategy == ConflictResolutionStrategy.SEMANTIC_MERGE.value:
            # AI가 제안한 병합 값 사용
            await self._update_value(
                conflict["resource_id"],
                resolution["semantic_value"]
            )


class ConflictVisualizationService:
    """충돌을 시각화하기 위한 데이터 준비"""
    
    def __init__(self, resolver: FoundryStyleConflictResolver):
        self.resolver = resolver
        
    async def prepare_visualization_data(
        self,
        conflict_context: ConflictContext
    ) -> Dict:
        """
        프론트엔드 3-way diff 뷰를 위한 데이터 준비
        """
        return {
            "conflict_id": conflict_context.conflict.id,
            "resource_type": conflict_context.conflict.resource_type,
            "resource_name": conflict_context.conflict.resource_name,
            "panels": {
                "base": {
                    "title": "Common Ancestor",
                    "value": conflict_context.base_value,
                    "timestamp": "base"
                },
                "source": {
                    "title": "Your Changes",
                    "value": conflict_context.source_value,
                    "timestamp": "current",
                    "diff_from_base": self._calculate_diff(
                        conflict_context.base_value,
                        conflict_context.source_value
                    )
                },
                "target": {
                    "title": "Target Branch",
                    "value": conflict_context.target_value,
                    "timestamp": "target",
                    "diff_from_base": self._calculate_diff(
                        conflict_context.base_value,
                        conflict_context.target_value
                    )
                }
            },
            "resolution_options": [
                {
                    "strategy": ConflictResolutionStrategy.TAKE_SOURCE.value,
                    "label": "Keep Your Changes",
                    "preview": conflict_context.source_value
                },
                {
                    "strategy": ConflictResolutionStrategy.TAKE_TARGET.value,
                    "label": "Keep Target Branch",
                    "preview": conflict_context.target_value
                },
                {
                    "strategy": ConflictResolutionStrategy.MANUAL.value,
                    "label": "Edit Manually",
                    "preview": None
                }
            ],
            "hints": conflict_context.resolution_hints,
            "impact": {
                "affected_count": len(conflict_context.affected_entities),
                "affected_preview": conflict_context.affected_entities[:5]
            }
        }
        
    def _calculate_diff(self, base: Any, current: Any) -> Dict:
        """두 값 사이의 diff 계산"""
        if isinstance(base, dict) and isinstance(current, dict):
            added = {k: v for k, v in current.items() if k not in base}
            removed = {k: v for k, v in base.items() if k not in current}
            modified = {
                k: {"old": base[k], "new": current[k]}
                for k in set(base.keys()) & set(current.keys())
                if base[k] != current[k]
            }
            
            return {
                "added": added,
                "removed": removed,
                "modified": modified
            }
        else:
            return {
                "old": base,
                "new": current,
                "changed": base != current
            }