"""
Document Storage for Unfoldable Documents
Provides persistent storage and retrieval for documents with unfoldable content
"""
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from arrakis_common import get_logger

from .metadata_frames import MetadataFrameParser
from .unfoldable import (
    UnfoldableDocument,
    UnfoldableProcessor,
    UnfoldContext,
    UnfoldLevel,
)

logger = get_logger(__name__)


@dataclass
class StoredDocument:
 """Represents a stored document with metadata"""
 id: str
 name: str
 content: Dict[str, Any]
 unfoldable_content: Dict[str, Any]
 metadata: Dict[str, Any]
 content_hash: str
 created_at: datetime
 updated_at: datetime
 version: int = 1
 tags: List[str] = None
 size_bytes: int = 0
 unfoldable_fields_count: int = 0

 def __post_init__(self):
 if self.tags is None:
 self.tags = []


class DocumentStorage:
 """
 In-memory storage for unfoldable documents
 In production, this would be backed by a database
 """

 def __init__(self):
 self._documents: Dict[str, StoredDocument] = {}
 self._indices = {
 "by_name": {},
 "by_hash": {},
 "by_tags": {},
 "by_created_date": []
 }

 def store_document(
 self,
 name: str,
 content: Dict[str, Any],
 metadata: Optional[Dict[str, Any]] = None,
 tags: Optional[List[str]] = None,
 auto_optimize: bool = True
 ) -> StoredDocument:
 """
 Store a document with unfoldable content
 """
 try:
 # Generate document ID
 doc_id = str(uuid.uuid4())

 # Process content for unfoldable features
 if auto_optimize:
 processed_content = UnfoldableProcessor.auto_mark_unfoldable(content)
 else:
 processed_content = content

 # Extract unfoldable content
 main_content, unfoldable_content = UnfoldableProcessor.extract_unfoldable_content(
 processed_content
 )

 # Calculate content hash
 content_str = json.dumps(content, sort_keys = True)
 content_hash = hashlib.sha256(content_str.encode()).hexdigest()

 # Create stored document
 now = datetime.utcnow()
 stored_doc = StoredDocument(
 id = doc_id,
 name = name,
 content = main_content,
 unfoldable_content = unfoldable_content,
 metadata = metadata or {},
 content_hash = content_hash,
 created_at = now,
 updated_at = now,
 tags = tags or [],
 size_bytes = len(content_str),
 unfoldable_fields_count = len(unfoldable_content)
 )

 # Store document
 self._documents[doc_id] = stored_doc

 # Update indices
 self._update_indices(stored_doc)

 logger.info(f"Stored document {doc_id} with {len(unfoldable_content)} unfoldable fields")
 return stored_doc

 except Exception as e:
 logger.error(f"Error storing document: {e}")
 raise

 def get_document(
 self,
 doc_id: str,
 unfold_context: Optional[UnfoldContext] = None
 ) -> Optional[Dict[str, Any]]:
 """
 Retrieve a document with optional unfolding
 """
 try:
 if doc_id not in self._documents:
 return None

 stored_doc = self._documents[doc_id]

 # Reconstruct full document
 full_content = self._reconstruct_document(stored_doc)

 if unfold_context:
 # Apply unfolding
 doc = UnfoldableDocument(full_content, stored_doc.metadata)
 content = doc.fold(unfold_context)
 else:
 content = full_content

 return {
 "id": stored_doc.id,
 "name": stored_doc.name,
 "content": content,
 "metadata": stored_doc.metadata,
 "created_at": stored_doc.created_at.isoformat(),
 "updated_at": stored_doc.updated_at.isoformat(),
 "version": stored_doc.version,
 "tags": stored_doc.tags,
 "stats": {
 "size_bytes": stored_doc.size_bytes,
 "unfoldable_fields_count": stored_doc.unfoldable_fields_count
 }
 }

 except Exception as e:
 logger.error(f"Error retrieving document {doc_id}: {e}")
 raise

 def update_document(
 self,
 doc_id: str,
 content: Optional[Dict[str, Any]] = None,
 metadata: Optional[Dict[str, Any]] = None,
 tags: Optional[List[str]] = None,
 auto_optimize: bool = True
 ) -> Optional[StoredDocument]:
 """
 Update an existing document
 """
 try:
 if doc_id not in self._documents:
 return None

 stored_doc = self._documents[doc_id]

 # Update content if provided
 if content is not None:
 if auto_optimize:
 processed_content = UnfoldableProcessor.auto_mark_unfoldable(content)
 else:
 processed_content = content

 main_content, unfoldable_content = UnfoldableProcessor.extract_unfoldable_content(
 processed_content
 )

 # Update content hash
 content_str = json.dumps(content, sort_keys = True)
 content_hash = hashlib.sha256(content_str.encode()).hexdigest()

 stored_doc.content = main_content
 stored_doc.unfoldable_content = unfoldable_content
 stored_doc.content_hash = content_hash
 stored_doc.size_bytes = len(content_str)
 stored_doc.unfoldable_fields_count = len(unfoldable_content)
 stored_doc.version += 1

 # Update metadata if provided
 if metadata is not None:
 stored_doc.metadata.update(metadata)

 # Update tags if provided
 if tags is not None:
 stored_doc.tags = tags

 stored_doc.updated_at = datetime.utcnow()

 # Update indices
 self._update_indices(stored_doc)

 logger.info(f"Updated document {doc_id} to version {stored_doc.version}")
 return stored_doc

 except Exception as e:
 logger.error(f"Error updating document {doc_id}: {e}")
 raise

 def delete_document(self, doc_id: str) -> bool:
 """
 Delete a document
 """
 try:
 if doc_id not in self._documents:
 return False

 stored_doc = self._documents[doc_id]

 # Remove from storage
 del self._documents[doc_id]

 # Remove from indices
 self._remove_from_indices(stored_doc)

 logger.info(f"Deleted document {doc_id}")
 return True

 except Exception as e:
 logger.error(f"Error deleting document {doc_id}: {e}")
 raise

 def list_documents(
 self,
 tags: Optional[List[str]] = None,
 name_filter: Optional[str] = None,
 limit: int = 100,
 offset: int = 0
 ) -> List[Dict[str, Any]]:
 """
 List documents with filtering
 """
 try:
 documents = list(self._documents.values())

 # Apply filters
 if tags:
 documents = [
 doc for doc in documents
 if any(tag in doc.tags for tag in tags)
 ]

 if name_filter:
 documents = [
 doc for doc in documents
 if name_filter.lower() in doc.name.lower()
 ]

 # Sort by creation date (newest first)
 documents.sort(key = lambda d: d.created_at, reverse = True)

 # Apply pagination
 total = len(documents)
 documents = documents[offset:offset + limit]

 # Convert to response format
 result = []
 for doc in documents:
 result.append({
 "id": doc.id,
 "name": doc.name,
 "created_at": doc.created_at.isoformat(),
 "updated_at": doc.updated_at.isoformat(),
 "version": doc.version,
 "tags": doc.tags,
 "stats": {
 "size_bytes": doc.size_bytes,
 "unfoldable_fields_count": doc.unfoldable_fields_count
 }
 })

 return {
 "documents": result,
 "pagination": {
 "total": total,
 "limit": limit,
 "offset": offset,
 "has_more": offset + limit < total
 }
 }

 except Exception as e:
 logger.error(f"Error listing documents: {e}")
 raise

 def search_documents(
 self,
 query: str,
 search_content: bool = True,
 search_metadata: bool = True,
 limit: int = 50
 ) -> List[Dict[str, Any]]:
 """
 Search documents by content or metadata
 """
 try:
 results = []
 query_lower = query.lower()

 for doc_id, stored_doc in self._documents.items():
 score = 0
 matches = []

 # Search in name
 if query_lower in stored_doc.name.lower():
 score += 10
 matches.append("name")

 # Search in tags
 for tag in stored_doc.tags:
 if query_lower in tag.lower():
 score += 5
 matches.append("tags")

 # Search in metadata
 if search_metadata:
 metadata_str = json.dumps(stored_doc.metadata).lower()
 if query_lower in metadata_str:
 score += 3
 matches.append("metadata")

 # Search in content
 if search_content:
 full_content = self._reconstruct_document(stored_doc)
 content_str = json.dumps(full_content).lower()
 if query_lower in content_str:
 score += 2
 matches.append("content")

 if score > 0:
 results.append({
 "id": stored_doc.id,
 "name": stored_doc.name,
 "created_at": stored_doc.created_at.isoformat(),
 "updated_at": stored_doc.updated_at.isoformat(),
 "tags": stored_doc.tags,
 "score": score,
 "matches": matches,
 "stats": {
 "size_bytes": stored_doc.size_bytes,
 "unfoldable_fields_count": stored_doc.unfoldable_fields_count
 }
 })

 # Sort by score (highest first)
 results.sort(key = lambda r: r["score"], reverse = True)

 return results[:limit]

 except Exception as e:
 logger.error(f"Error searching documents: {e}")
 raise

 def get_document_stats(self) -> Dict[str, Any]:
 """
 Get storage statistics
 """
 try:
 total_docs = len(self._documents)
 total_size = sum(doc.size_bytes for doc in self._documents.values())
 total_unfoldable_fields = sum(doc.unfoldable_fields_count for doc in self._documents.values())

 # Tag statistics
 tag_counts = {}
 for doc in self._documents.values():
 for tag in doc.tags:
 tag_counts[tag] = tag_counts.get(tag, 0) + 1

 return {
 "total_documents": total_docs,
 "total_size_bytes": total_size,
 "total_size_mb": round(total_size / (1024 * 1024), 2),
 "total_unfoldable_fields": total_unfoldable_fields,
 "average_size_bytes": total_size // total_docs if total_docs > 0 else 0,
 "average_unfoldable_fields": total_unfoldable_fields // total_docs if total_docs > 0 else 0,


 "tag_statistics": tag_counts,
 "storage_efficiency": {
 "compression_ratio": 0.8, # Placeholder for compression stats
 "unfoldable_space_saved": total_unfoldable_fields * 1000 # Estimated space saved
 }
 }

 except Exception as e:
 logger.error(f"Error getting storage stats: {e}")
 raise

 def _reconstruct_document(self, stored_doc: StoredDocument) -> Dict[str, Any]:
 """
 Reconstruct the full document from stored parts
 """
 # Start with main content
 full_content = json.loads(json.dumps(stored_doc.content))

 # Merge in unfoldable content
 def merge_unfoldable(obj: Any, path: str = "") -> Any:
 if isinstance(obj, dict):
 if "@unfoldable" in obj and "path" in obj:
 # This is a placeholder - replace with actual content
 unfoldable_path = obj["path"]
 if unfoldable_path in stored_doc.unfoldable_content:
 return stored_doc.unfoldable_content[unfoldable_path]

 # Process nested objects
 result = {}
 for key, value in obj.items():
 new_path = f"{path}.{key}" if path else key
 result[key] = merge_unfoldable(value, new_path)
 return result
 elif isinstance(obj, list):
 return [merge_unfoldable(item, f"{path}[{i}]") for i, item in enumerate(obj)]
 else:
 return obj

 return merge_unfoldable(full_content)

 def _update_indices(self, stored_doc: StoredDocument):
 """
 Update search indices for a document
 """
 # Update name index
 self._indices["by_name"][stored_doc.name] = stored_doc.id

 # Update hash index
 self._indices["by_hash"][stored_doc.content_hash] = stored_doc.id

 # Update tags index
 for tag in stored_doc.tags:
 if tag not in self._indices["by_tags"]:
 self._indices["by_tags"][tag] = []
 if stored_doc.id not in self._indices["by_tags"][tag]:
 self._indices["by_tags"][tag].append(stored_doc.id)

 # Update date index (keep sorted)
 date_entry = (stored_doc.created_at, stored_doc.id)
 if date_entry not in self._indices["by_created_date"]:
 self._indices["by_created_date"].append(date_entry)
 self._indices["by_created_date"].sort(reverse = True)

 def _remove_from_indices(self, stored_doc: StoredDocument):
 """
 Remove document from search indices
 """
 # Remove from name index
 if stored_doc.name in self._indices["by_name"]:
 del self._indices["by_name"][stored_doc.name]

 # Remove from hash index
 if stored_doc.content_hash in self._indices["by_hash"]:
 del self._indices["by_hash"][stored_doc.content_hash]

 # Remove from tags index
 for tag in stored_doc.tags:
 if tag in self._indices["by_tags"]:
 if stored_doc.id in self._indices["by_tags"][tag]:
 self._indices["by_tags"][tag].remove(stored_doc.id)
 if not self._indices["by_tags"][tag]:
 del self._indices["by_tags"][tag]

 # Remove from date index
 self._indices["by_created_date"] = [
 entry for entry in self._indices["by_created_date"]
 if entry[1] != stored_doc.id
 ]


# Global storage instance
_storage_instance = None

def get_document_storage() -> DocumentStorage:
 """
 Get the global document storage instance
 """
 global _storage_instance
 if _storage_instance is None:
 _storage_instance = DocumentStorage()
 return _storage_instance
