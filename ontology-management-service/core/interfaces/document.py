"""
Document Service Protocol
문서 서비스를 위한 인터페이스 정의
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from shared.models.domain import Document, DocumentCreate, DocumentUpdate


class DocumentServiceProtocol(ABC):
 """문서 서비스 프로토콜"""

 @abstractmethod
 async def create_document(
 self,
 document_data: DocumentCreate,
 branch: str = "main",
 created_by: str = "system"
 ) -> Document:
 """새 문서를 생성합니다."""
 pass

 @abstractmethod
 async def get_document(
 self,
 document_id: str,
 branch: str = "main"
 ) -> Optional[Document]:
 """문서를 조회합니다."""
 pass

 @abstractmethod
 async def update_document(
 self,
 document_id: str,
 update_data: DocumentUpdate,
 branch: str = "main",
 updated_by: str = "system"
 ) -> Optional[Document]:
 """문서를 업데이트합니다."""
 pass

 @abstractmethod
 async def delete_document(
 self,
 document_id: str,
 branch: str = "main",
 deleted_by: str = "system"
 ) -> bool:
 """문서를 삭제합니다."""
 pass

 @abstractmethod
 async def list_documents(
 self,
 branch: str = "main",
 object_type: Optional[str] = None,
 status: Optional[str] = None,
 tags: Optional[List[str]] = None,
 offset: int = 0,
 limit: int = 100
 ) -> Dict[str, Any]:
 """문서 목록을 조회합니다."""
 pass

 @abstractmethod
 async def search_documents(
 self,
 query: str,
 branch: str = "main",
 object_type: Optional[str] = None,
 offset: int = 0,
 limit: int = 100
 ) -> Dict[str, Any]:
 """문서를 검색합니다."""
 pass
