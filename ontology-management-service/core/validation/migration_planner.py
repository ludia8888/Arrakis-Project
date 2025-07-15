"""
마이그레이션 계획 생성
섹션 8.3.3의 Migration Planner 구현
"""
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Set

from core.validation.models import (
 BreakingChange,
 MigrationOptions,
 MigrationPlan,
 MigrationStep,
 MigrationStrategy,
)
from database.clients.terminus_db import TerminusDBClient

logger = logging.getLogger(__name__)


class MigrationPlanner:
 """마이그레이션 계획 생성"""

 def __init__(self, tdb_client: TerminusDBClient):
 self.tdb = tdb_client
 self.strategies = self._initialize_strategies()

 async def create_migration_plan(
 self,
 breaking_changes: List[BreakingChange],
 target_branch: str,
 options: MigrationOptions,
 ) -> MigrationPlan:
 """Breaking changes에 대한 마이그레이션 계획 생성"""

 if not breaking_changes:
 return self._create_empty_plan(target_branch)

 # 1. 변경사항 그룹화
 grouped_changes = self._group_changes_by_object(breaking_changes)

 # 2. 의존성 분석
 dependency_graph = await self._analyze_dependencies(
 grouped_changes, target_branch
 )

 # 3. 실행 순서 결정
 execution_order = self._topological_sort(dependency_graph)

 # 4. 단계별 마이그레이션 스텝 생성
 steps = []
 for object_type in execution_order:
 changes = grouped_changes.get(object_type, [])
 if changes:
 object_steps = await self._create_steps_for_object(
 object_type, changes, options
 )
 steps.extend(object_steps)

 # 5. 롤백 계획
 rollback_steps = self._create_rollback_plan(steps)

 # 6. 시간 추정 및 다운타임 계산
 total_duration = sum(s.estimated_duration for s in steps)
 requires_downtime = any(s.requires_downtime for s in steps)

 # 7. 다운타임 윈도우 계산
 downtime_windows = self._calculate_downtime_windows(steps)

 return MigrationPlan(
 id = self._generate_plan_id(),
 breaking_changes = breaking_changes,
 target_branch = target_branch,
 steps = steps,
 rollback_steps = rollback_steps,
 execution_order = execution_order,
 estimated_duration = total_duration,
 requires_downtime = requires_downtime,
 downtime_windows = downtime_windows,
 created_at = datetime.utcnow(),
 status = "draft",
 )

 def _group_changes_by_object(
 self, breaking_changes: List[BreakingChange]
 ) -> Dict[str, List[BreakingChange]]:
 """ObjectType별로 변경사항 그룹화"""
 grouped = defaultdict(list)

 for change in breaking_changes:
 if change.resource_type == "ObjectType":
 grouped[change.resource_name].append(change)
 elif change.resource_type == "Property":
 # Property 변경은 해당 ObjectType으로 그룹화
 object_type = change.metadata.get("object_type", "Unknown")
 grouped[object_type].append(change)

 return dict(grouped)

 async def _analyze_dependencies(
 self, grouped_changes: Dict[str, List[BreakingChange]], target_branch: str
 ) -> Dict[str, Set[str]]:
 """ObjectType 간 의존성 분석"""
 dependencies = defaultdict(set)

 for object_type in grouped_changes:
 # LinkType을 통한 의존성 확인
 query = f"""
 SELECT ?linkType ?targetType
 WHERE {{
 ?linkType a LinkType .
 ?linkType sourceType <{object_type}> .
 ?linkType targetType ?targetType .
 }}
 """

 try:
 results = await self.tdb.query(query, db = "oms", branch = target_branch)

 for result in results:
 target = result.get("targetType", "").split("/")[-1]
 if target in grouped_changes:
 dependencies[object_type].add(target)

 except Exception as e:
 logger.error(f"Error analyzing dependencies for {object_type}: {e}")

 return dict(dependencies)

 def _topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
 """위상 정렬로 실행 순서 결정"""
 # Kahn's algorithm
 in_degree = defaultdict(int)
 all_nodes = set(graph.keys())

 # 모든 노드의 진입 차수 계산
 for node in graph:
 for neighbor in graph[node]:
 in_degree[neighbor] += 1
 all_nodes.add(neighbor)

 # 진입 차수가 0인 노드들로 시작
 queue = [node for node in all_nodes if in_degree[node] == 0]
 result = []

 while queue:
 node = queue.pop(0)
 result.append(node)

 # 이웃 노드들의 진입 차수 감소
 for neighbor in graph.get(node, []):
 in_degree[neighbor] -= 1
 if in_degree[neighbor] == 0:
 queue.append(neighbor)

 # 순환 의존성 체크
 if len(result) != len(all_nodes):
 logger.warning("Circular dependency detected in migration plan")
 # 순환 의존성이 있는 경우 남은 노드들을 임의로 추가
 for node in all_nodes:
 if node not in result:
 result.append(node)

 return result

 async def _create_steps_for_object(
 self, object_type: str, changes: List[BreakingChange], options: MigrationOptions
 ) -> List[MigrationStep]:
 """특정 ObjectType에 대한 마이그레이션 스텝 생성"""
 steps = []

 # Primary Key 변경이 있는 경우
 pk_changes = [c for c in changes if c.rule_id == "primary_key_change"]
 if pk_changes:
 pk_steps = await self._create_primary_key_migration_steps(
 object_type, pk_changes[0], options
 )
 steps.extend(pk_steps)

 # 필수 필드 제거
 required_removals = [
 c for c in changes if c.rule_id == "required_field_removal"
 ]
 if required_removals:
 removal_steps = await self._create_required_field_removal_steps(
 object_type, required_removals[0], options
 )
 steps.extend(removal_steps)

 # 데이터 타입 변경
 type_changes = [c for c in changes if c.rule_id == "data_type_change"]
 if type_changes:
 type_steps = await self._create_data_type_change_steps(
 object_type, type_changes[0], options
 )
 steps.extend(type_steps)

 return steps

 async def _create_primary_key_migration_steps(
 self, object_type: str, change: BreakingChange, options: MigrationOptions
 ) -> List[MigrationStep]:
 """Primary Key 변경 마이그레이션 스텝"""

 if options.strategy == MigrationStrategy.COPY_THEN_DROP:
 return [
 MigrationStep(
 type = "create_temp_collection",
 description = f"Create temporary collection for {object_type}",
 woql_script = self._generate_create_temp_script(object_type),
 estimated_duration = 5,
 can_parallel = False,
 requires_downtime = False,
 ),
 MigrationStep(
 type = "copy_with_transformation",
 description = "Copy data with new primary key",
 woql_script = self._generate_copy_script(object_type, change),
 estimated_duration = change.impact_estimate.estimated_duration_seconds
 if change.impact_estimate
 else 3600,
 can_parallel = True,
 batch_size = options.batch_size,
 ),
 MigrationStep(
 type = "verify_data_integrity",
 description = "Verify copied data integrity",
 woql_script = self._generate_verification_script(object_type),
 estimated_duration = 30,
 can_parallel = False,
 ),
 MigrationStep(
 type = "atomic_switch",
 description = "Switch to new collection",
 woql_script = self._generate_switch_script(object_type),
 estimated_duration = 5,
 requires_downtime = True,
 downtime_duration = 10,
 ),
 ]
 else:
 # BACKFILL_NULLABLE strategy
 return [
 MigrationStep(
 type = "add_nullable_column",
 description = "Add new primary key column as nullable",
 woql_script = self._generate_add_column_script(object_type, change),
 estimated_duration = 10,
 can_parallel = False,
 requires_downtime = False,
 ),
 MigrationStep(
 type = "backfill_data",
 description = "Backfill new primary key values",
 woql_script = self._generate_backfill_script(object_type, change),
 estimated_duration = change.impact_estimate.estimated_duration_seconds
 if change.impact_estimate
 else 3600,
 can_parallel = True,
 batch_size = options.batch_size,
 ),
 MigrationStep(
 type = "make_required_and_switch",
 description = "Make new column required and switch primary key",
 woql_script = self._generate_pk_switch_script(object_type, change),
 estimated_duration = 30,
 requires_downtime = True,
 downtime_duration = 60,
 ),
 ]

 async def _create_required_field_removal_steps(
 self, object_type: str, change: BreakingChange, options: MigrationOptions
 ) -> List[MigrationStep]:
 """필수 필드 제거 마이그레이션 스텝"""

 removed_fields = change.metadata.get("removed_fields", [])

 if options.strategy == MigrationStrategy.MAKE_NULLABLE_FIRST:
 return [
 MigrationStep(
 type = "make_fields_nullable",
 description = f"Make fields nullable: {', '.join(removed_fields)}",
 woql_script = self._generate_make_nullable_script(
 object_type, removed_fields
 ),
 estimated_duration = 10,
 can_parallel = False,
 requires_downtime = False,
 ),
 MigrationStep(
 type = "deprecation_period",
 description = "Wait for deprecation period (manual step)",
 woql_script = None,
 estimated_duration = 0,
 can_parallel = False,
 requires_downtime = False,
 metadata={"manual": True, "wait_days": 30},
 ),
 MigrationStep(
 type = "remove_fields",
 description = "Remove deprecated fields",
 woql_script = self._generate_remove_fields_script(
 object_type, removed_fields
 ),
 estimated_duration = 30,
 can_parallel = False,
 requires_downtime = False,
 ),
 ]
 else:
 # SET_DEFAULT_VALUES strategy
 return [
 MigrationStep(
 type = "set_default_values",
 description = "Set default values for fields to be removed",
 woql_script = self._generate_set_defaults_script(
 object_type, removed_fields
 ),
 estimated_duration = change.impact_estimate.estimated_duration_seconds
 if change.impact_estimate
 else 1800,
 can_parallel = True,
 batch_size = options.batch_size,
 ),
 MigrationStep(
 type = "remove_fields",
 description = "Remove fields with defaults set",
 woql_script = self._generate_remove_fields_script(
 object_type, removed_fields
 ),
 estimated_duration = 30,
 can_parallel = False,
 requires_downtime = True,
 downtime_duration = 30,
 ),
 ]

 async def _create_data_type_change_steps(
 self, object_type: str, change: BreakingChange, options: MigrationOptions
 ) -> List[MigrationStep]:
 """데이터 타입 변경 마이그레이션 스텝"""

 return [
 MigrationStep(
 type = "create_conversion_function",
 description = "Create data type conversion function",
 woql_script = self._generate_conversion_function(object_type, change),
 estimated_duration = 5,
 can_parallel = False,
 requires_downtime = False,
 ),
 MigrationStep(
 type = "progressive_conversion",
 description = "Convert data types progressively",
 woql_script = self._generate_progressive_conversion_script(
 object_type, change
 ),
 estimated_duration = change.impact_estimate.estimated_duration_seconds
 if change.impact_estimate
 else 3600,
 can_parallel = True,
 batch_size = options.batch_size,
 metadata={"can_resume": True},
 ),
 MigrationStep(
 type = "verify_conversion",
 description = "Verify all data converted successfully",
 woql_script = self._generate_conversion_verification_script(
 object_type, change
 ),
 estimated_duration = 60,
 can_parallel = False,
 requires_downtime = False,
 ),
 ]

 def _create_rollback_plan(self, steps: List[MigrationStep]) -> List[MigrationStep]:
 """롤백 계획 생성"""
 rollback_steps = []

 # 역순으로 롤백 스텝 생성
 for step in reversed(steps):
 if step.rollback_script:
 rollback_step = MigrationStep(
 type = f"rollback_{step.type}",
 description = f"Rollback: {step.description}",
 woql_script = step.rollback_script,
 estimated_duration = step.estimated_duration * 0.5, # 롤백은 일반적으로 더 빠름
 can_parallel = step.can_parallel,
 requires_downtime = step.requires_downtime,
 batch_size = step.batch_size,
 )
 rollback_steps.append(rollback_step)

 return rollback_steps

 def _calculate_downtime_windows(
 self, steps: List[MigrationStep]
 ) -> List[Dict[str, Any]]:
 """다운타임 윈도우 계산"""
 windows = []
 current_window = None

 for i, step in enumerate(steps):
 if step.requires_downtime:
 if current_window is None:
 current_window = {
 "start_step": i,
 "end_step": i,
 "duration": step.downtime_duration or step.estimated_duration,
 "steps": [step.description],
 }
 else:
 current_window["end_step"] = i
 current_window["duration"] += (
 step.downtime_duration or step.estimated_duration
 )
 current_window["steps"].append(step.description)
 else:
 if current_window is not None:
 windows.append(current_window)
 current_window = None

 if current_window is not None:
 windows.append(current_window)

 return windows

 def _generate_plan_id(self) -> str:
 """고유한 플랜 ID 생성"""
 return f"migration_plan_{uuid.uuid4().hex[:8]}"

 def _create_empty_plan(self, target_branch: str) -> MigrationPlan:
 """빈 마이그레이션 플랜 생성"""
 return MigrationPlan(
 id = self._generate_plan_id(),
 breaking_changes = [],
 target_branch = target_branch,
 steps = [],
 rollback_steps = [],
 execution_order = [],
 estimated_duration = 0,
 requires_downtime = False,
 created_at = datetime.utcnow(),
 status = "completed",
 )

 # WOQL 스크립트 생성 메서드들
 def _generate_create_temp_script(self, object_type: str) -> Dict[str, Any]:
 """임시 컬렉션 생성 스크립트"""
 return {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": f"{object_type}_temp"},
 {
 "type": "label",
 "class_name": f"{object_type}_temp",
 "label": f"{object_type} Temporary",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": f"{object_type}_temp",
 "description": "Temporary collection for migration",
 "language": "en",
 },
 ],
 }

 def _generate_copy_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """데이터 복사 스크립트 생성"""
 old_pk = change.metadata.get("old_pk_name", "id")
 new_pk = change.metadata.get("new_pk_name", "id")

 return {
 "type": "and",
 "clauses": [
 {
 "type": "limit",
 "limit": 1000,
 "query": {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": old_pk},
 "object": {
 "@type": "Variable",
 "variable_name": "OldPK",
 },
 },
 {
 "type": "read_object",
 "document": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "object": {
 "@type": "Variable",
 "variable_name": "Document",
 },
 },
 ],
 },
 },
 {
 "type": "and",
 "clauses": [
 {
 "type": "delete_quad",
 "subject": {
 "@type": "Variable",
 "variable_name": "Document",
 },
 "predicate": {"@type": "Node", "node": old_pk},
 "object": {"@type": "Variable", "variable_name": "OldPK"},
 "graph": "instance",
 },
 {
 "type": "add_quad",
 "subject": {
 "@type": "Variable",
 "variable_name": "Document",
 },
 "predicate": {"@type": "Node", "node": new_pk},
 "object": {"@type": "Variable", "variable_name": "OldPK"},
 "graph": "instance",
 },
 {
 "type": "insert_object",
 "document": {
 "@type": "Variable",
 "variable_name": "Document",
 },
 "class_name": f"{object_type}_temp",
 },
 ],
 },
 ],
 }

 def _generate_verification_script(self, object_type: str) -> Dict[str, Any]:
 """데이터 검증 스크립트"""
 return {
 "type": "and",
 "clauses": [
 {
 "type": "count",
 "query": {
 "type": "triple",
 "subject": {"@type": "Variable", "variable_name": "Original"},
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 "count": {"@type": "Variable", "variable_name": "OriginalCount"},
 },
 {
 "type": "count",
 "query": {
 "type": "triple",
 "subject": {"@type": "Variable", "variable_name": "Temp"},
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": f"{object_type}_temp"},
 },
 "count": {"@type": "Variable", "variable_name": "TempCount"},
 },
 {
 "type": "equals",
 "left": {"@type": "Variable", "variable_name": "OriginalCount"},
 "right": {"@type": "Variable", "variable_name": "TempCount"},
 },
 ],
 }

 def _generate_switch_script(self, object_type: str) -> Dict[str, Any]:
 """컬렉션 전환 스크립트"""
 return {
 "type": "and",
 "clauses": [
 {"type": "delete_class", "class_name": object_type},
 {
 "type": "rename_class",
 "old_name": f"{object_type}_temp",
 "new_name": object_type,
 },
 ],
 }

 def _generate_make_nullable_script(
 self, object_type: str, fields: List[str]
 ) -> Dict[str, Any]:
 """필드를 nullable로 변경하는 스크립트"""
 clauses = [{"type": "get_class", "class_name": object_type}]

 for field in fields:
 clauses.append(
 {
 "type": "update_property",
 "property_name": field,
 "updates": {"cardinality": {"min": 0, "max": 1}},
 }
 )

 return {"type": "and", "clauses": clauses}

 def _generate_set_defaults_script(
 self, object_type: str, fields: List[str]
 ) -> Dict[str, Any]:
 """기본값 설정 스크립트"""
 return {
 "type": "update_object",
 "query": {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": {"@type": "Variable", "variable_name": "Instance"},
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 {
 "type": "not",
 "query": {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {
 "@type": "Node",
 "node": fields[0] if fields else "field",
 },
 "object": {"@type": "Variable", "variable_name": "Value"},
 },
 },
 ],
 },
 "update": {fields[0] if fields else "field": "default_value"},
 }

 def _generate_remove_fields_script(
 self, object_type: str, fields: List[str]
 ) -> Dict[str, Any]:
 """필드 제거 스크립트"""
 clauses = []
 for field in fields:
 clauses.append(
 {
 "type": "delete_property",
 "class_name": object_type,
 "property_name": field,
 }
 )

 return {"type": "and", "clauses": clauses}

 def _initialize_strategies(self) -> Dict[str, Any]:
 """마이그레이션 전략 초기화"""
 return {
 "copy_then_drop": self._create_primary_key_migration_steps,
 "backfill_nullable": self._create_primary_key_migration_steps,
 "set_default_values": self._create_required_field_removal_steps,
 "make_nullable_first": self._create_required_field_removal_steps,
 "progressive_rollout": self._create_data_type_change_steps,
 }

 def _generate_add_column_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """컬럼 추가 스크립트"""
 new_pk = change.metadata.get("new_pk_name", "new_id")
 new_type = change.metadata.get("new_pk_type", "xsd:string")

 return {
 "type": "and",
 "clauses": [
 {
 "type": "add_property",
 "property_name": new_pk,
 "class_name": object_type,
 },
 {"type": "set_domain", "property_name": new_pk, "domain": object_type},
 {"type": "set_range", "property_name": new_pk, "range": new_type},
 {
 "type": "set_cardinality",
 "property_name": new_pk,
 "min": 0,
 "max": 1,
 },
 ],
 }

 def _generate_backfill_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """데이터 백필 스크립트"""
 old_pk = change.metadata.get("old_pk_name", "id")
 new_pk = change.metadata.get("new_pk_name", "new_id")

 return {
 "type": "and",
 "clauses": [
 {
 "type": "limit",
 "limit": 1000,
 "query": {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": old_pk},
 "object": {
 "@type": "Variable",
 "variable_name": "OldValue",
 },
 },
 {
 "type": "not",
 "query": {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": new_pk},
 "object": {
 "@type": "Variable",
 "variable_name": "Any",
 },
 },
 },
 ],
 },
 },
 {
 "type": "and",
 "clauses": [
 {
 "type": "concat",
 "strings": [
 {"@type": "Value", "value": "new_"},
 {"@type": "Variable", "variable_name": "OldValue"},
 ],
 "result": {
 "@type": "Variable",
 "variable_name": "NewValue",
 },
 },
 {
 "type": "add_triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": new_pk},
 "object": {
 "@type": "Variable",
 "variable_name": "NewValue",
 },
 },
 ],
 },
 ],
 }

 def _generate_pk_switch_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """Primary Key 전환 스크립트"""
 old_pk = change.metadata.get("old_pk_name", "id")
 new_pk = change.metadata.get("new_pk_name", "new_id")

 return {
 "type": "and",
 "clauses": [
 {
 "type": "set_cardinality",
 "property_name": new_pk,
 "min": 1,
 "max": 1,
 },
 {"type": "set_key", "class_name": object_type, "key_property": new_pk},
 {
 "type": "delete_property",
 "class_name": object_type,
 "property_name": old_pk,
 },
 ],
 }

 def _generate_conversion_function(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """타입 변환 함수 생성"""
 type_changes = change.old_value.get("type_changes", [])
 if not type_changes:
 return {"type": "true"}

 first_change = type_changes[0]
 return {
 "type": "typecast",
 "value": {"@type": "Variable", "variable_name": "OldValue"},
 "from_type": first_change.get("old_type", "xsd:string"),
 "result": {"@type": "Variable", "variable_name": "NewValue"},
 "to_type": first_change.get("new_type", "xsd:string"),
 }

 def _generate_progressive_conversion_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """점진적 타입 변환 스크립트"""
 type_changes = change.old_value.get("type_changes", [])
 if not type_changes:
 return {"type": "true"}

 first_change = type_changes[0]
 prop_name = first_change["property"]

 return {
 "type": "and",
 "clauses": [
 {
 "type": "limit",
 "limit": 1000,
 "query": {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": prop_name},
 "object": {
 "@type": "Variable",
 "variable_name": "OldValue",
 },
 },
 {
 "type": "not",
 "query": {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {
 "@type": "Node",
 "node": f"_converted_{prop_name}",
 },
 "object": {"@type": "Value", "value": True},
 },
 },
 ],
 },
 },
 {
 "type": "and",
 "clauses": [
 {
 "type": "typecast",
 "value": {"@type": "Variable", "variable_name": "OldValue"},
 "from_type": first_change.get("old_type", "xsd:string"),
 "result": {
 "@type": "Variable",
 "variable_name": "NewValue",
 },
 "to_type": first_change.get("new_type", "xsd:string"),
 },
 {
 "type": "delete_triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": prop_name},
 "object": {
 "@type": "Variable",
 "variable_name": "OldValue",
 },
 },
 {
 "type": "add_triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": prop_name},
 "object": {
 "@type": "Variable",
 "variable_name": "NewValue",
 },
 },
 {
 "type": "add_triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {
 "@type": "Node",
 "node": f"_converted_{prop_name}",
 },
 "object": {"@type": "Value", "value": True},
 },
 ],
 },
 ],
 }

 def _generate_conversion_verification_script(
 self, object_type: str, change: BreakingChange
 ) -> Dict[str, Any]:
 """타입 변환 검증 스크립트"""
 type_changes = change.old_value.get("type_changes", [])
 if not type_changes:
 return {"type": "true"}

 first_change = type_changes[0]
 prop_name = first_change["property"]

 return {
 "type": "and",
 "clauses": [
 {
 "type": "count",
 "query": {
 "type": "and",
 "clauses": [
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 {
 "type": "triple",
 "subject": {
 "@type": "Variable",
 "variable_name": "Instance",
 },
 "predicate": {
 "@type": "Node",
 "node": f"_converted_{prop_name}",
 },
 "object": {"@type": "Value", "value": True},
 },
 ],
 },
 "count": {"@type": "Variable", "variable_name": "ConvertedCount"},
 },
 {
 "type": "count",
 "query": {
 "type": "triple",
 "subject": {"@type": "Variable", "variable_name": "Instance"},
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": object_type},
 },
 "count": {"@type": "Variable", "variable_name": "TotalCount"},
 },
 {
 "type": "equals",
 "left": {"@type": "Variable", "variable_name": "ConvertedCount"},
 "right": {"@type": "Variable", "variable_name": "TotalCount"},
 },
 ],
 }
