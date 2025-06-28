"""
Advanced Ontology Management Service
TerminusDB의 진짜 Native 기능들을 OMS에 통합
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from terminusdb_client import WOQLClient
from terminusdb_client.woqlquery import WOQLQuery as WQ

from core.advanced.terminus_advanced import TerminusAdvancedFeatures, OntologySpecificFeatures
from core.monitoring.migration_monitor import track_native_operation

logger = logging.getLogger(__name__)


class AdvancedOntologyService:
    """OMS를 위한 고급 TerminusDB 기능 서비스"""
    
    def __init__(self, client: WOQLClient):
        self.client = client
        self.advanced = TerminusAdvancedFeatures(client)
        self.ontology = OntologySpecificFeatures(client)
        
    @track_native_operation("semantic_search")
    async def semantic_search_ontology(self, query: str, filters: Optional[Dict] = None) -> List[Dict]:
        """
        온톨로지 요소를 의미적으로 검색
        
        예: "사용자 정보를 저장하는 클래스" → User, Person, Account 등 찾기
        """
        # VectorLink를 사용한 의미 검색
        similar_docs = await self.advanced.semantic_search(query, limit=20)
        
        # 필터 적용
        if filters:
            filtered = []
            for doc in similar_docs:
                if filters.get("type") and doc.get("@type") != filters["type"]:
                    continue
                if filters.get("min_score") and doc.get("score", 0) < filters["min_score"]:
                    continue
                filtered.append(doc)
            similar_docs = filtered
            
        # 추가 정보 enrichment
        for doc in similar_docs:
            # 사용 통계 추가
            doc["usage_count"] = await self._get_usage_count(doc["_id"])
            
            # 관련 엔티티 추가
            doc["related"] = await self._get_related_entities(doc["_id"], limit=5)
            
        return similar_docs
        
    @track_native_operation("impact_analysis")
    async def analyze_change_impact(self, branch: str, base_branch: str = "main") -> Dict:
        """
        브랜치의 변경사항이 미치는 영향 분석
        """
        # 1. Diff 가져오기
        diff = self.client.diff(branch, base_branch)
        
        impact_report = {
            "branch": branch,
            "base_branch": base_branch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_changes": 0,
                "breaking_changes": 0,
                "affected_entities": 0,
                "risk_level": "low"
            },
            "details": []
        }
        
        # 2. 각 변경사항 분석
        for change in diff:
            impact = await self._analyze_single_change(change)
            impact_report["details"].append(impact)
            
            # 통계 업데이트
            impact_report["summary"]["total_changes"] += 1
            if impact["is_breaking"]:
                impact_report["summary"]["breaking_changes"] += 1
            impact_report["summary"]["affected_entities"] += len(impact["affected_entities"])
            
        # 3. 위험도 계산
        if impact_report["summary"]["breaking_changes"] > 0:
            impact_report["summary"]["risk_level"] = "high"
        elif impact_report["summary"]["affected_entities"] > 100:
            impact_report["summary"]["risk_level"] = "medium"
            
        # 4. 추천사항 생성
        impact_report["recommendations"] = self._generate_recommendations(impact_report)
        
        return impact_report
        
    @track_native_operation("ontology_validation")
    async def validate_ontology_branch(self, branch: str) -> Dict:
        """
        온톨로지 일관성 및 품질 검증
        """
        validation_report = {
            "branch": branch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "valid",
            "issues": []
        }
        
        # 1. 순환 참조 검사
        circular_refs = await self._check_circular_references()
        if circular_refs:
            validation_report["issues"].append({
                "type": "circular_reference",
                "severity": "error",
                "entities": circular_refs
            })
            validation_report["status"] = "invalid"
            
        # 2. 필수 속성 검사
        missing_required = await self._check_required_properties()
        if missing_required:
            validation_report["issues"].append({
                "type": "missing_required_properties",
                "severity": "error",
                "entities": missing_required
            })
            validation_report["status"] = "invalid"
            
        # 3. 명명 규칙 검사
        naming_issues = await self._check_naming_conventions()
        if naming_issues:
            validation_report["issues"].append({
                "type": "naming_convention_violation",
                "severity": "warning",
                "entities": naming_issues
            })
            
        # 4. 문서화 수준 검사
        undocumented = await self._check_documentation_coverage()
        if undocumented:
            validation_report["issues"].append({
                "type": "missing_documentation",
                "severity": "info",
                "entities": undocumented,
                "coverage": f"{100 - len(undocumented)}%"
            })
            
        return validation_report
        
    @track_native_operation("auto_migrate_schema")
    async def auto_migrate_schema(self, target_version: str) -> Dict:
        """
        스키마를 목표 버전으로 자동 마이그레이션
        """
        current_version = await self._get_schema_version()
        
        if current_version == target_version:
            return {"status": "already_up_to_date", "version": current_version}
            
        # 마이그레이션 경로 찾기
        migration_path = await self._find_migration_path(current_version, target_version)
        
        if not migration_path:
            return {"status": "no_migration_path", "from": current_version, "to": target_version}
            
        # 마이그레이션 브랜치 생성
        migration_branch = f"auto_migration_{current_version}_to_{target_version}"
        self.client.create_branch(migration_branch)
        self.client.branch = migration_branch
        
        try:
            # 단계별 마이그레이션 실행
            for step in migration_path:
                result = await self._apply_migration_step(step)
                if not result["success"]:
                    raise Exception(f"Migration step failed: {step['name']}")
                    
            # 검증
            validation = await self.validate_ontology_branch(migration_branch)
            
            if validation["status"] == "valid":
                # 머지
                self.client.merge(
                    migration_branch,
                    "main",
                    author="Auto Migration System",
                    message=f"Auto migrate schema from {current_version} to {target_version}"
                )
                
                return {
                    "status": "success",
                    "from_version": current_version,
                    "to_version": target_version,
                    "steps_applied": len(migration_path)
                }
            else:
                return {
                    "status": "validation_failed",
                    "validation_report": validation
                }
                
        except Exception as e:
            # 롤백
            self.client.branch = "main"
            self.client.delete_branch(migration_branch)
            
            return {
                "status": "failed",
                "error": str(e)
            }
            
    @track_native_operation("generate_api_docs")
    async def generate_api_documentation(self) -> Dict:
        """
        온톨로지에서 자동으로 API 문서 생성
        """
        # GraphQL 스키마 가져오기
        graphql_schema = self.client.get_graphql_schema()
        
        # 온톨로지 문서 생성
        ontology_docs = await self.ontology.generate_ontology_documentation()
        
        # API 예제 생성
        api_examples = await self._generate_api_examples()
        
        # 통합 문서
        documentation = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "graphql_schema": graphql_schema,
            "ontology_documentation": ontology_docs,
            "api_examples": api_examples,
            "endpoints": {
                "graphql": "/api/graphql",
                "rest": "/api/rest/v1",
                "woql": "/api/woql"
            }
        }
        
        # Markdown 파일로 저장
        markdown = self._format_as_markdown(documentation)
        
        with open("docs/AUTO_GENERATED_API_DOCS.md", "w") as f:
            f.write(markdown)
            
        return {
            "status": "generated",
            "path": "docs/AUTO_GENERATED_API_DOCS.md",
            "size": len(markdown)
        }
        
    async def _analyze_single_change(self, change: Dict) -> Dict:
        """단일 변경사항 영향 분석"""
        impact = {
            "change": change,
            "is_breaking": False,
            "affected_entities": [],
            "migration_required": False
        }
        
        # 속성 제거는 breaking change
        if change.get("@type") == "DeleteProperty":
            impact["is_breaking"] = True
            
            # 해당 속성을 사용하는 모든 인스턴스 찾기
            query = WQ().triple("v:instance", change["@id"], "v:value")
            result = self.client.query(query)
            
            impact["affected_entities"] = [
                r["instance"] for r in result.get("bindings", [])
            ]
            impact["migration_required"] = len(impact["affected_entities"]) > 0
            
        return impact
        
    async def _check_circular_references(self) -> List[str]:
        """순환 참조 검사"""
        query = WQ().path(
            "v:class",
            "(scm:subClassOf|owl:equivalentClass)+",
            "v:class"
        ).select("v:class")
        
        result = self.client.query(query)
        return [r["class"] for r in result.get("bindings", [])]
        
    async def _get_usage_count(self, entity_id: str) -> int:
        """엔티티 사용 횟수 조회"""
        query = WQ().triple("v:s", "v:p", entity_id).count("v:s", "v:count")
        result = self.client.query(query)
        return result.get("bindings", [{}])[0].get("count", 0)
        
    async def _get_related_entities(self, entity_id: str, limit: int = 5) -> List[Dict]:
        """관련 엔티티 조회"""
        query = WQ().woql_or(
            WQ().triple(entity_id, "v:prop", "v:related"),
            WQ().triple("v:related", "v:prop", entity_id)
        ).triple("v:related", "rdfs:label", "v:label").limit(limit)
        
        result = self.client.query(query)
        return [
            {"id": r["related"], "label": r.get("label", "Unknown")}
            for r in result.get("bindings", [])
        ]
        
    def _format_as_markdown(self, documentation: Dict) -> str:
        """문서를 Markdown으로 포맷"""
        lines = [
            "# Auto-Generated API Documentation",
            f"Generated: {documentation['generated_at']}",
            "",
            "## Endpoints",
            ""
        ]
        
        for endpoint, url in documentation["endpoints"].items():
            lines.append(f"- **{endpoint.upper()}**: `{url}`")
            
        lines.extend([
            "",
            "## GraphQL Schema",
            "```graphql",
            documentation["graphql_schema"],
            "```",
            "",
            "## API Examples",
            ""
        ])
        
        for example in documentation["api_examples"]:
            lines.extend([
                f"### {example['title']}",
                f"{example['description']}",
                "```" + example['language'],
                example['code'],
                "```",
                ""
            ])
            
        return "\n".join(lines)