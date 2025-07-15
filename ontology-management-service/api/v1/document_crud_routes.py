"""
Document CRUD API Routes
문서 생성, 조회, 수정, 삭제를 위한 REST 엔드포인트
"""
from typing import Any, Dict, List, Optional

from arrakis_common import get_logger
from bootstrap.dependencies import get_db_client, get_event_gateway
from core.auth_utils import UserContext
from core.document.service import DocumentService
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from middleware.auth_middleware import get_current_user
from middleware.etag_middleware import enable_etag
from pydantic import BaseModel
from shared.models.domain import Document, DocumentCreate, DocumentUpdate

logger = get_logger(__name__)
router = APIRouter(prefix = "/documents/crud", tags = ["Document CRUD"])


async def get_document_service(
 db_client = Depends(get_db_client),
 event_gateway = Depends(get_event_gateway)
) -> DocumentService:
 """문서 서비스 인스턴스를 반환합니다."""
 return DocumentService(db_client = db_client, event_publisher = event_gateway)


@router.post("/", response_model = Document, status_code = status.HTTP_201_CREATED,
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def create_document(
 document_data: DocumentCreate,
 branch: str = Query("main", description = "Target branch"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Document:
 """
 새 문서를 생성합니다.

 - **name**: 문서 이름
 - **object_type**: 문서가 속한 객체 타입
 - **content**: 문서 내용 (JSON)
 - **metadata**: 추가 메타데이터 (선택)
 - **tags**: 태그 목록 (선택)
 - **status**: 문서 상태 (기본: draft)
 """
 try:
 document = await document_service.create_document(
 document_data = document_data,
 branch = branch,
 created_by = user.user_id
 )

 logger.info(f"Created document: {document.id} by user: {user.user_id}")
 return document

 except ValueError as e:
 raise HTTPException(
 status_code = status.HTTP_400_BAD_REQUEST,
 detail = str(e)
 )
 except Exception as e:
 logger.error(f"Failed to create document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to create document: {str(e)}"
 )


@router.get("/{document_id}", response_model = Document,
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
@enable_etag(
 resource_type_func = lambda params: "document",
 resource_id_func = lambda params: params['document_id'],
 branch_func = lambda params: params.get('branch', 'main')
)
async def get_document(
 document_id: str,
 branch: str = Query("main", description = "Branch name"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Document:
 """
 문서를 ID로 조회합니다.
 """
 try:
 document = await document_service.get_document(
 document_id = document_id,
 branch = branch
 )

 if not document:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {document_id}"
 )

 return document

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Failed to get document {document_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to get document: {str(e)}"
 )


@router.put("/{document_id}", response_model = Document,
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def update_document(
 document_id: str,
 update_data: DocumentUpdate,
 branch: str = Query("main", description = "Branch name"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Document:
 """
 문서를 업데이트합니다.

 모든 필드는 선택적이며, 제공된 필드만 업데이트됩니다.
 """
 try:
 document = await document_service.update_document(
 document_id = document_id,
 update_data = update_data,
 branch = branch,
 updated_by = user.user_id
 )

 if not document:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {document_id}"
 )

 logger.info(f"Updated document: {document_id} by user: {user.user_id}")
 return document

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Failed to update document {document_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to update document: {str(e)}"
 )


@router.delete("/{document_id}", status_code = status.HTTP_204_NO_CONTENT,
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def delete_document(
 document_id: str,
 branch: str = Query("main", description = "Branch name"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> None:
 """
 문서를 삭제합니다.
 """
 try:
 success = await document_service.delete_document(
 document_id = document_id,
 branch = branch,
 deleted_by = user.user_id
 )

 if not success:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {document_id}"
 )

 logger.info(f"Deleted document: {document_id} by user: {user.user_id}")

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Failed to delete document {document_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to delete document: {str(e)}"
 )


@router.get("/", response_model = Dict[str, Any],
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def list_documents(
 branch: str = Query("main", description = "Branch name"),
 object_type: Optional[str] = Query(None, description = "Filter by object type"),
 status: Optional[str] = Query(None, description = "Filter by status"),
 tags: Optional[List[str]] = Query(None, description = "Filter by tags"),
 offset: int = Query(0, ge = 0, description = "Pagination offset"),
 limit: int = Query(100, ge = 1, le = 1000, description = "Pagination limit"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Dict[str, Any]:
 """
 문서 목록을 조회합니다.

 필터 옵션:
 - **object_type**: 특정 객체 타입의 문서만 조회
 - **status**: 특정 상태의 문서만 조회 (draft, published, archived)
 - **tags**: 특정 태그를 가진 문서만 조회
 """
 try:
 result = await document_service.list_documents(
 branch = branch,
 object_type = object_type,
 status = status,
 tags = tags,
 offset = offset,
 limit = limit
 )

 return result

 except Exception as e:
 logger.error(f"Failed to list documents: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to list documents: {str(e)}"
 )


@router.get("/search/", response_model = Dict[str, Any],
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def search_documents(
 q: str = Query(..., description = "Search query"),
 branch: str = Query("main", description = "Branch name"),
 object_type: Optional[str] = Query(None, description = "Filter by object type"),
 offset: int = Query(0, ge = 0, description = "Pagination offset"),
 limit: int = Query(100, ge = 1, le = 1000, description = "Pagination limit"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Dict[str, Any]:
 """
 문서를 검색합니다.

 검색 대상:
 - 문서 이름
 - 문서 내용
 - 태그
 """
 try:
 result = await document_service.search_documents(
 query = q,
 branch = branch,
 object_type = object_type,
 offset = offset,
 limit = limit
 )

 return result

 except Exception as e:
 logger.error(f"Failed to search documents: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to search documents: {str(e)}"
 )


@router.get("/stats/summary", response_model = Dict[str, Any],
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_document_stats(
 branch: str = Query("main", description = "Branch name"),
 request: Request = None,
 user: UserContext = Depends(get_current_user),
 document_service = Depends(get_document_service)
) -> Dict[str, Any]:
 """
 문서 통계를 조회합니다.
 """
 try:
 # 전체 문서 조회 (통계를 위해)
 result = await document_service.list_documents(
 branch = branch,
 limit = 1000 # 통계를 위해 더 많은 문서 조회
 )

 # 통계 계산
 documents = result.get("items", [])
 stats = {
 "total_documents": len(documents),
 "by_object_type": {},
 "by_status": {},
 "by_tags": {},
 "recent_documents": []
 }

 # 객체 타입별 통계
 for doc in documents:
 obj_type = doc.object_type
 if obj_type not in stats["by_object_type"]:
 stats["by_object_type"][obj_type] = 0
 stats["by_object_type"][obj_type] += 1

 # 상태별 통계
 status = doc.status
 if status not in stats["by_status"]:
 stats["by_status"][status] = 0
 stats["by_status"][status] += 1

 # 태그별 통계
 for tag in doc.tags:
 if tag not in stats["by_tags"]:
 stats["by_tags"][tag] = 0
 stats["by_tags"][tag] += 1

 # 최근 문서 5개
 sorted_docs = sorted(documents, key = lambda x: x.modified_at, reverse = True)
 stats["recent_documents"] = [
 {
 "id": doc.id,
 "name": doc.name,
 "object_type": doc.object_type,
 "modified_at": doc.modified_at.isoformat()
 }
 for doc in sorted_docs[:5]
 ]

 return stats

 except Exception as e:
 logger.error(f"Failed to get document stats: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to get document stats: {str(e)}"
 )
