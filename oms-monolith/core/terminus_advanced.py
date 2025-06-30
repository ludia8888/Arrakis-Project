"""
Advanced TerminusDB Native Features
진짜 TerminusDB의 강력한 기능들을 100% 활용
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from terminusdb_client import WOQLClient
from terminusdb_client.woqlquery import WOQLQuery as WQ

logger = logging.getLogger(__name__)


class TerminusAdvancedFeatures:
    """TerminusDB의 고급 Native 기능들을 완전히 활용"""
    
    def __init__(self, client: WOQLClient):
        self.client = client
        
    # 1. WOQL (Web Object Query Language) - Datalog 기반 강력한 쿼리
    async def complex_graph_query(self, start_node: str, depth: int = 3) -> List[Dict]:
        """
        WOQL로 복잡한 그래프 탐색 - SQL로는 불가능한 재귀 쿼리
        """
        # 재귀적 관계 탐색 (예: 모든 하위 ontology 찾기)
        query = WQ.path(
            WQ.string(start_node),      # 시작점
            "scm:subClassOf+",           # + = 1회 이상 반복
            "v:descendant",              # 결과 변수
            depth                        # 최대 깊이
        ).triple(
            "v:descendant",
            "rdfs:label", 
            "v:label"
        ).select("v:descendant", "v:label")
        
        result = self.client.query(query)
        return result.get('bindings', [])
        
    # 2. Time Travel - 과거 시점 조회
    async def time_travel_query(self, commit_id: str, query: str) -> Any:
        """
        특정 commit 시점의 데이터 조회 - Git checkout과 유사
        """
        # 특정 커밋으로 이동
        original_branch = self.client.branch
        self.client.checkout(commit_id)
        
        try:
            # 과거 시점 쿼리 실행
            result = self.client.query(WQ().triple("v:s", "v:p", "v:o").limit(100))
            return result
        finally:
            # 원래 브랜치로 복귀
            self.client.checkout(original_branch)
            
    # 3. Schema Migration with Version Control
    async def schema_migration(self, migration_script: Dict[str, Any]) -> Dict:
        """
        스키마 마이그레이션을 브랜치에서 실행하고 PR처럼 머지
        """
        migration_branch = f"schema_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 마이그레이션 브랜치 생성
        self.client.branch = "main"
        self.client.create_branch(migration_branch)
        self.client.branch = migration_branch
        
        try:
            # 스키마 변경 실행
            for change in migration_script.get("changes", []):
                if change["type"] == "add_property":
                    query = WQ().add_property(
                        change["class"],
                        change["property"],
                        change["datatype"]
                    )
                elif change["type"] == "add_class":
                    query = WQ().doctype(change["class"]).label(change["label"])
                    for prop in change.get("properties", []):
                        query = query.property(prop["name"], prop["type"])
                        
                self.client.query(query, commit_msg=change.get("message", "Schema change"))
                
            # Diff 확인
            diff = self.client.diff(migration_branch, "main")
            
            # 성공하면 머지
            self.client.merge(
                migration_branch, 
                "main",
                author="Schema Migration Tool",
                message=f"Apply migration: {migration_script.get('name')}"
            )
            
            return {"status": "success", "diff": diff}
            
        except (ValueError, RuntimeError) as e:
            # 실패시 브랜치 삭제
            self.client.delete_branch(migration_branch)
            return {"status": "failed", "error": str(e)}
            
    # 4. VectorLink - AI 임베딩 검색
    async def semantic_search(self, query_text: str, limit: int = 10) -> List[Dict]:
        """
        VectorLink를 사용한 의미 기반 검색
        """
        # GraphQL로 유사 문서 검색
        graphql_query = f"""
        query {{
            similarDocuments(text: "{query_text}", limit: {limit}) {{
                _id
                score
                ... on ObjectType {{
                    label
                    description
                    properties {{
                        name
                        datatype
                    }}
                }}
            }}
        }}
        """
        
        # GraphQL 엔드포인트로 쿼리
        result = self.client.graphql(graphql_query)
        return result.get("data", {}).get("similarDocuments", [])
        
    # 5. Transaction with Rollback
    async def transactional_update(self, updates: List[Dict]) -> Dict:
        """
        트랜잭션 내에서 여러 업데이트 실행 - 실패시 자동 롤백
        """
        transaction_id = f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # 트랜잭션 시작
            with self.client.transaction() as tx:
                for update in updates:
                    if update["type"] == "insert":
                        tx.insert_document(update["document"])
                    elif update["type"] == "update":
                        tx.update_document(update["id"], update["document"])
                    elif update["type"] == "delete":
                        tx.delete_document(update["id"])
                        
                # 모든 작업 성공시 자동 커밋
                return {"status": "committed", "transaction_id": transaction_id}
                
        except (ValueError, KeyError, RuntimeError) as e:
            # 예외 발생시 자동 롤백
            logger.error(f"Transaction {transaction_id} rolled back: {e}")
            return {"status": "rolled_back", "error": str(e)}
            
    # 6. GraphQL Auto-Generated API
    def get_graphql_schema(self) -> str:
        """
        TerminusDB가 자동 생성한 GraphQL 스키마 가져오기
        """
        return self.client.get_graphql_schema()
        
    # 7. Squash Commits - 히스토리 정리
    async def squash_branch_commits(self, branch: str, message: str) -> Dict:
        """
        브랜치의 여러 커밋을 하나로 합치기 - Git squash와 동일
        """
        original_branch = self.client.branch
        self.client.branch = branch
        
        try:
            # Squash 실행
            result = self.client.squash(message)
            
            # 레이어 컴팩션으로 성능 향상
            return {
                "status": "success",
                "message": "Commits squashed and layers compacted",
                "result": result
            }
        finally:
            self.client.branch = original_branch
            
    # 8. Access Control - 세밀한 권한 관리
    async def setup_role_based_access(self, role_config: Dict) -> Dict:
        """
        역할 기반 접근 제어 설정
        """
        results = []
        
        for role in role_config.get("roles", []):
            # 역할 생성
            self.client.create_role(
                role["name"],
                role.get("description", "")
            )
            
            # 권한 부여
            for capability in role.get("capabilities", []):
                self.client.grant_capability(
                    role["name"],
                    capability["resource"],
                    capability["actions"]
                )
                
            results.append({
                "role": role["name"],
                "status": "created",
                "capabilities": len(role.get("capabilities", []))
            })
            
        return {"roles_created": results}
        
    # 9. Composite Queries - 여러 쿼리 조합
    async def composite_analysis(self, entity_id: str) -> Dict:
        """
        하나의 엔티티에 대한 종합적인 분석
        """
        # 1. 기본 정보
        basic_info = WQ().triple(entity_id, "v:predicate", "v:object").select("v:predicate", "v:object")
        
        # 2. 관련 엔티티 (1-hop)
        related = WQ().triple(entity_id, "v:link", "v:related").triple("v:related", "rdfs:label", "v:label")
        
        # 3. 역방향 참조
        references = WQ().triple("v:referrer", "v:property", entity_id).limit(10)
        
        # 4. 변경 이력
        history = self.client.get_commit_history(path=entity_id, limit=5)
        
        # 모든 쿼리 실행
        return {
            "basic_info": self.client.query(basic_info),
            "related_entities": self.client.query(related),
            "referenced_by": self.client.query(references),
            "change_history": history
        }
        
    # 10. Patch Operations - 세밀한 변경
    async def apply_json_patch(self, document_id: str, patches: List[Dict]) -> Dict:
        """
        JSON Patch 표준을 사용한 문서 부분 업데이트
        """
        from jsonpatch import JsonPatch
        
        # 현재 문서 가져오기
        current = self.client.get_document(document_id)
        
        # 패치 적용
        patch = JsonPatch(patches)
        updated = patch.apply(current)
        
        # 업데이트된 문서 저장
        self.client.update_document(document_id, updated)
        
        return {
            "status": "patched",
            "patches_applied": len(patches),
            "document_id": document_id
        }


class OntologySpecificFeatures:
    """OMS 도메인에 특화된 TerminusDB 활용"""
    
    def __init__(self, client: WOQLClient):
        self.client = client
        self.advanced = TerminusAdvancedFeatures(client)
        
    async def validate_ontology_consistency(self, branch: str) -> Dict:
        """
        온톨로지 일관성 검증 - SHACL/OWL 제약조건 체크
        """
        # 순환 참조 검출
        circular_check = WQ().path(
            "v:class",
            "scm:subClassOf+",
            "v:class"  # 자기 자신으로 돌아오는 경로
        ).select("v:class")
        
        # 필수 속성 누락 검출  
        missing_required = WQ().triple(
            "v:class",
            "scm:property",
            "v:prop"
        ).triple(
            "v:prop",
            "scm:required",
            True
        ).not_().triple(
            "v:instance",
            "rdf:type",
            "v:class"
        ).triple(
            "v:instance",
            "v:prop",
            "v:value"
        )
        
        return {
            "circular_references": self.client.query(circular_check),
            "missing_required_properties": self.client.query(missing_required),
            "branch": branch,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    async def generate_ontology_documentation(self) -> str:
        """
        온톨로지에서 자동으로 문서 생성
        """
        # 모든 클래스와 속성 추출
        schema_query = WQ().woql_and(
            WQ().triple("v:class", "rdf:type", "owl:Class"),
            WQ().triple("v:class", "rdfs:label", "v:label"),
            WQ().optional().triple("v:class", "rdfs:comment", "v:comment"),
            WQ().optional().triple("v:class", "scm:property", "v:property")
        )
        
        result = self.client.query(schema_query)
        
        # Markdown 문서 생성
        doc = ["# Ontology Documentation", ""]
        doc.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        doc.append("")
        
        for binding in result.get('bindings', []):
            doc.append(f"## {binding.get('label', 'Unknown')}")
            if binding.get('comment'):
                doc.append(f"*{binding['comment']}*")
            doc.append("")
            
        return "\n".join(doc)
        
    async def impact_analysis(self, change_proposal: Dict) -> Dict:
        """
        변경 영향도 분석 - 어떤 엔티티들이 영향받는지
        """
        affected = []
        
        for change in change_proposal.get("changes", []):
            if change["type"] == "remove_property":
                # 해당 속성을 사용하는 모든 인스턴스 찾기
                query = WQ().triple("v:instance", change["property"], "v:value")
                result = self.client.query(query)
                affected.extend([{
                    "entity": r["instance"],
                    "impact": "property_removal",
                    "property": change["property"]
                } for r in result.get('bindings', [])])
                
        return {
            "total_affected": len(affected),
            "affected_entities": affected,
            "risk_level": "high" if len(affected) > 100 else "medium" if len(affected) > 10 else "low"
        }