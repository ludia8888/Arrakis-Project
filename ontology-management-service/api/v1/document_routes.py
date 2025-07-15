"""
Document Processing API Routes
REST endpoints for unfoldable documents and metadata frames
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from arrakis_common import get_logger
from core.auth_utils import UserContext
from core.documents import (
    MetadataFrameParser,
    SchemaDocumentationGenerator,
    UnfoldableDocument,
    UnfoldableProcessor,
    UnfoldContext,
    UnfoldLevel,
)
from core.documents.storage import get_document_storage
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from fastapi import APIRouter, Depends, HTTPException, Request, status
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel, Field

logger = get_logger(__name__)
router = APIRouter(prefix = "/documents", tags = ["Documents"])


# Request/Response Models

class UnfoldContextRequest(BaseModel):
 """Request model for unfold context"""
 level: str = Field("COLLAPSED", description = "Unfold level: COLLAPSED, SHALLOW, DEEP,
     CUSTOM")
 paths: Optional[List[str]] = Field(None, description = "Specific paths to unfold")
 max_depth: int = Field(10, ge = 1, le = 20)
 size_threshold: int = Field(10240, ge = 1024)
 array_threshold: int = Field(100, ge = 10)
 include_summaries: bool = Field(True)


class UnfoldDocumentRequest(BaseModel):
 """Request for unfolding a document"""
 content: Dict[str, Any] = Field(..., description = "Document content")
 context: UnfoldContextRequest = Field(..., description = "Unfold context")
 metadata: Optional[Dict[str, Any]] = Field(None, description = "Document metadata")


class UnfoldPathRequest(BaseModel):
 """Request for unfolding a specific path"""
 content: Dict[str, Any] = Field(..., description = "Document content")
 path: str = Field(..., description = "Path to unfold")


class PrepareUnfoldableRequest(BaseModel):
 """Request for preparing a document with unfoldable annotations"""
 content: Dict[str, Any] = Field(..., description = "Document content")
 unfoldable_paths: List[str] = Field(..., description = "Paths to mark as unfoldable")


class ParseMetadataRequest(BaseModel):
 """Request for parsing metadata frames"""
 markdown_content: str = Field(...,
     description = "Markdown content with metadata frames")


class GenerateDocumentationRequest(BaseModel):
 """Request for generating schema documentation"""
 object_type: Dict[str, Any] = Field(..., description = "Object type definition")
 include_examples: bool = Field(True, description = "Include example metadata frames")


class StoreDocumentRequest(BaseModel):
 """Request for storing a document"""
 name: str = Field(..., description = "Document name")
 content: Dict[str, Any] = Field(..., description = "Document content")
 metadata: Optional[Dict[str, Any]] = Field(None, description = "Document metadata")
 tags: Optional[List[str]] = Field(None, description = "Document tags")
 auto_optimize: bool = Field(True,
     description = "Auto-optimize with unfoldable annotations")


class UpdateDocumentRequest(BaseModel):
 """Request for updating a document"""
 content: Optional[Dict[str, Any]] = Field(None, description = "Document content")
 metadata: Optional[Dict[str, Any]] = Field(None, description = "Document metadata")
 tags: Optional[List[str]] = Field(None, description = "Document tags")
 auto_optimize: bool = Field(True,
     description = "Auto-optimize with unfoldable annotations")


class DocumentSearchRequest(BaseModel):
 """Request for searching documents"""
 query: str = Field(..., description = "Search query")
 search_content: bool = Field(True, description = "Search in document content")
 search_metadata: bool = Field(True, description = "Search in document metadata")
 limit: int = Field(50, ge = 1, le = 100, description = "Maximum number of results")


class InjectMetadataRequest(BaseModel):
 """Request for injecting metadata frames into content"""
 markdown_content: str = Field(..., description = "Base markdown content")
 metadata_frames: List[Dict[str, Any]] = Field(...,
     description = "Metadata frames to inject")


class ValidateMetadataRequest(BaseModel):
 """Request for validating metadata frames"""
 markdown_content: str = Field(...,
     description = "Markdown content with metadata frames")
 strict: bool = Field(False, description = "Enable strict validation")


class ConvertMetadataRequest(BaseModel):
 """Request for converting metadata frame formats"""
 metadata_frames: List[Dict[str, Any]] = Field(...,
     description = "Metadata frames to convert")
 target_format: str = Field(..., description = "Target format: yaml, json")


class ExportDocumentationRequest(BaseModel):
 """Request for exporting documentation in different formats"""
 schema_documentation: Dict[str, Any] = Field(...,
     description = "Schema documentation object")
 export_format: str = Field("markdown", description = "Export format: markdown, html,
     pd")
 include_metadata: bool = Field(True, description = "Include metadata frames in export")


# Endpoints

@router.post("/unfold",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def unfold_document(
 request: UnfoldDocumentRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Process a document with unfoldable content

 Returns folded document based on the provided context
 """
 try:
 # Create unfold context
 unfold_level = UnfoldLevel[request.context.level]
 context = UnfoldContext(
 level = unfold_level,
 paths = set(request.context.paths) if request.context.paths else set(),
 max_depth = request.context.max_depth,
 size_threshold = request.context.size_threshold,
 array_threshold = request.context.array_threshold,
 include_summaries = request.context.include_summaries
 )

 # Create and process document
 doc = UnfoldableDocument(request.content, request.metadata)
 folded_content = doc.fold(context)
 unfoldable_paths = doc.get_unfoldable_paths()

 return {
 "content": folded_content,
 "unfoldable_paths": unfoldable_paths,
 "metadata": request.metadata,
 "stats": {
 "total_unfoldable_fields": len(unfoldable_paths),
 "unfold_level": request.context.level
 }
 }

 except Exception as e:
 logger.error(f"Error unfolding document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to unfold document: {str(e)}"
 )


@router.post("/unfold-path",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def unfold_path(
 request: UnfoldPathRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Unfold a specific path in a document

 Returns the content at the specified path
 """
 try:
 doc = UnfoldableDocument(request.content)
 content = doc.unfold_path(request.path)

 if content is None:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Path not found: {request.path}"
 )

 return {
 "path": request.path,
 "content": content,
 "type": type(content).__name__
 }

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Error unfolding path: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to unfold path: {str(e)}"
 )


@router.post("/prepare-unfoldable",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def prepare_unfoldable(
 request: PrepareUnfoldableRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Prepare a document with @unfoldable annotations

 Marks specified paths as unfoldable in the document
 """
 try:
 prepared = UnfoldableProcessor.prepare_document(
 request.content,
 request.unfoldable_paths
 )

 return {
 "content": prepared,
 "unfoldable_paths": request.unfoldable_paths,
 "annotations_added": len(request.unfoldable_paths)
 }

 except Exception as e:
 logger.error(f"Error preparing unfoldable document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to prepare document: {str(e)}"
 )


@router.post("/extract-unfoldable",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def extract_unfoldable(
 content: Dict[str, Any],
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Extract unfoldable content from a document

 Separates main document from unfoldable content
 """
 try:
 main_doc, unfoldable_content = UnfoldableProcessor.extract_unfoldable_content(
 content
 )

 return {
 "main_document": main_doc,
 "unfoldable_content": unfoldable_content,
 "stats": {
 "unfoldable_fields": len(unfoldable_content)
 }
 }

 except Exception as e:
 logger.error(f"Error extracting unfoldable content: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to extract content: {str(e)}"
 )


@router.post("/parse-metadata",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def parse_metadata_frames(
 request: ParseMetadataRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Parse metadata frames from markdown content

 Extracts @metadata frames and returns cleaned content
 """
 try:
 parser = MetadataFrameParser()
 cleaned_content, frames = parser.parse_document(request.markdown_content)

 # Build summary
 summary = {
 'total_frames': len(frames),
 'frame_types': {},
 'metadata': {}
 }

 frame_list = []
 for frame in frames:
 frame_list.append({
 "frame_type": frame.frame_type,
 "content": frame.content,
 "position": frame.position,
 "format": frame.format
 })

 # Update summary
 if frame.frame_type not in summary['frame_types']:
 summary['frame_types'][frame.frame_type] = 0
 summary['frame_types'][frame.frame_type] += 1

 if frame.frame_type == 'document':
 summary['metadata'].update(frame.content)

 return {
 "cleaned_content": cleaned_content,
 "metadata_frames": frame_list,
 "summary": summary
 }

 except Exception as e:
 logger.error(f"Error parsing metadata frames: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to parse metadata: {str(e)}"
 )


@router.post("/generate-documentation",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def generate_documentation(
 request: GenerateDocumentationRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Generate schema documentation with metadata frames

 Creates markdown documentation for schema objects
 """
 try:
 generator = SchemaDocumentationGenerator()
 doc = generator.generate_object_type_doc(request.object_type)

 # Extract frame information
 frames = []
 for frame in doc.metadata_frames:
 frames.append({
 "frame_type": frame.frame_type,
 "content": frame.content,
 "format": frame.format
 })

 return {
 "name": doc.name,
 "title": doc.title,
 "description": doc.description,
 "version": doc.version,
 "markdown": doc.to_markdown(),
 "metadata_frames": frames,
 "stats": {
 "total_frames": len(frames),
 "content_length": len(doc.to_markdown())
 }
 }

 except Exception as e:
 logger.error(f"Error generating documentation: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to generate documentation: {str(e)}"
 )


@router.get("/metadata-frame-types",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_metadata_frame_types(
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """Get supported metadata frame types"""
 parser = MetadataFrameParser()

 return {
 "frame_types": parser.frame_types,
 "supported_formats": parser.supported_formats,
 "description": {
 "schema": "Schema definition metadata",
 "document": "Document metadata (front matter)",
 "api": "API endpoint metadata",
 "example": "Example metadata",
 "validation": "Validation rules",
 "changelog": "Change history",
 "custom": "Custom metadata"
 }
 }


@router.get("/unfold-levels",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_unfold_levels(
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """Get supported unfold levels"""
 return {
 "levels": [
 {
 "name": "COLLAPSED",
 "value": 0,
 "description": "Only show summary/metadata"
 },
 {
 "name": "SHALLOW",
 "value": 1,
 "description": "Show immediate children"
 },
 {
 "name": "DEEP",
 "value": 2,
 "description": "Show all nested content"
 },
 {
 "name": "CUSTOM",
 "value": 3,
 "description": "Custom unfold paths"
 }
 ]
 }


@router.post("/auto-mark-unfoldable",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def auto_mark_unfoldable(
 content: Dict[str, Any],
 size_threshold: int = 10240,
 array_threshold: int = 100,
 text_threshold: int = 1000,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Automatically mark large content as unfoldable

 Analyzes document content and automatically adds @unfoldable annotations
 to large objects, arrays, and text content based on configurable thresholds
 """
 try:
 processed = UnfoldableProcessor.auto_mark_unfoldable(
 content,
 size_threshold,
 array_threshold,
 text_threshold
 )

 # Get statistics about what was marked
 doc = UnfoldableDocument(processed)
 unfoldable_paths = doc.get_unfoldable_paths()

 return {
 "content": processed,
 "unfoldable_paths": [path["path"] for path in unfoldable_paths],
 "annotations_added": len(unfoldable_paths),
 "thresholds": {
 "size_threshold": size_threshold,
 "array_threshold": array_threshold,
 "text_threshold": text_threshold
 },
 "stats": {
 "large_objects": len([p for p in unfoldable_paths if "Object with" in p["summary"]]),
 "large_arrays": len([p for p in unfoldable_paths if "Array with" in p["summary"]]),
 "large_text": len([p for p in unfoldable_paths if "Text content" in p["summary"]])
 }
 }

 except Exception as e:
 logger.error(f"Error auto-marking unfoldable content: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to auto-mark content: {str(e)}"
 )


@router.post("/batch-unfold",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def batch_unfold_documents(
 documents: List[UnfoldDocumentRequest],
 parallel: bool = True,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Batch unfold multiple documents

 Processes multiple documents with their respective unfold contexts.
 Can run in parallel or sequential mode.
 """
 try:
 import asyncio
 import time

 start_time = time.time()
 results = []

 async def process_single_document(doc_request: UnfoldDocumentRequest) -> Dict[str,
     Any]:
 # Create unfold context
 unfold_level = UnfoldLevel[doc_request.context.level]
 context = UnfoldContext(
 level = unfold_level,
 paths = set(doc_request.context.paths) if doc_request.context.paths else set(),
 max_depth = doc_request.context.max_depth,
 size_threshold = doc_request.context.size_threshold,
 array_threshold = doc_request.context.array_threshold,
 include_summaries = doc_request.context.include_summaries
 )

 # Create and process document
 doc = UnfoldableDocument(doc_request.content, doc_request.metadata)
 folded_content = doc.fold(context)
 unfoldable_paths = doc.get_unfoldable_paths()

 return {
 "content": folded_content,
 "unfoldable_paths": unfoldable_paths,
 "metadata": doc_request.metadata,
 "stats": {
 "total_unfoldable_fields": len(unfoldable_paths),
 "unfold_level": doc_request.context.level
 }
 }

 if parallel:
 tasks = [process_single_document(doc) for doc in documents]
 results = await asyncio.gather(*tasks)
 else:
 for doc in documents:
 result = await process_single_document(doc)
 results.append(result)

 processing_time = (time.time() - start_time) * 1000

 return {
 "results": results,
 "batch_stats": {
 "total_documents": len(documents),
 "processing_mode": "parallel" if parallel else "sequential",
 "processing_time_ms": processing_time,
 "average_time_per_doc_ms": processing_time / len(documents) if documents else 0
 }
 }

 except Exception as e:
 logger.error(f"Error batch processing documents: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to batch process documents: {str(e)}"
 )


@router.post("/analyze-document",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def analyze_document_structure(
 content: Dict[str, Any],
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Analyze document structure and complexity

 Provides insights into document size, structure, and potential unfoldable content
 without actually modifying the document
 """
 try:
 import json

 def analyze_structure(obj: Any, path: str = "", depth: int = 0) -> Dict[str, Any]:
 stats = {
 "total_fields": 0,
 "max_depth": depth,
 "large_objects": 0,
 "large_arrays": 0,
 "large_text_fields": 0,
 "circular_refs": 0,
 "field_types": {},
 "size_distribution": {"small": 0, "medium": 0, "large": 0}
 }

 if isinstance(obj, dict):
 stats["total_fields"] += len(obj)
 for key, value in obj.items():
 field_type = type(value).__name__
 stats["field_types"][field_type] = stats["field_types"].get(field_type, 0) + 1

 if isinstance(value, dict):
 obj_size = len(json.dumps(value))
 if obj_size > 10240:
 stats["large_objects"] += 1
 elif obj_size > 1024:
 stats["size_distribution"]["medium"] += 1
 else:
 stats["size_distribution"]["small"] += 1

 sub_stats = analyze_structure(value, f"{path}.{key}", depth + 1)
 stats["max_depth"] = max(stats["max_depth"], sub_stats["max_depth"])
 stats["total_fields"] += sub_stats["total_fields"]
 stats["large_objects"] += sub_stats["large_objects"]
 stats["large_arrays"] += sub_stats["large_arrays"]
 stats["large_text_fields"] += sub_stats["large_text_fields"]

 elif isinstance(value, list):
 if len(value) > 100:
 stats["large_arrays"] += 1
 stats["size_distribution"]["large"] += 1
 elif len(value) > 10:
 stats["size_distribution"]["medium"] += 1
 else:
 stats["size_distribution"]["small"] += 1

 elif isinstance(value, str):
 if len(value) > 1000:
 stats["large_text_fields"] += 1
 stats["size_distribution"]["large"] += 1
 elif len(value) > 100:
 stats["size_distribution"]["medium"] += 1
 else:
 stats["size_distribution"]["small"] += 1

 return stats

 # Analyze structure
 structure_stats = analyze_structure(content)

 # Calculate document size
 doc_size = len(json.dumps(content))

 # Analyze potential unfoldable content
 doc = UnfoldableDocument(content)
 unfoldable_paths = doc.get_unfoldable_paths()

 # Complexity score (0-100)
 complexity_score = min(100, (
 structure_stats["max_depth"] * 10 +
 structure_stats["large_objects"] * 5 +
 structure_stats["large_arrays"] * 3 +
 structure_stats["large_text_fields"] * 2 +
 (doc_size / 1024) * 0.1
 ))

 return {
 "document_stats": {
 "total_size_bytes": doc_size,
 "total_size_kb": round(doc_size / 1024, 2),
 "structure": structure_stats,
 "complexity_score": round(complexity_score, 1)
 },
 "unfoldable_analysis": {
 "detected_unfoldable_fields": len(unfoldable_paths),
 "fields": unfoldable_paths,
 "recommendations": {
 "should_use_unfoldable": len(unfoldable_paths) > 0,
 "auto_mark_threshold": doc_size > 50000,
 "suggested_unfold_level": "SHALLOW" if len(unfoldable_paths) < 5 else "COLLAPSED"
 }
 },
 "performance_insights": {
 "estimated_load_time_ms": max(10, doc_size / 1000),
 "memory_usage_estimate_kb": doc_size * 1.5 / 1024,
 "network_efficiency": "good" if doc_size < 100000 else "consider_optimization"
 }
 }

 except Exception as e:
 logger.error(f"Error analyzing document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to analyze document: {str(e)}"
 )


@router.post("/optimize-document",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def optimize_document_for_performance(
 content: Dict[str, Any],
 target_size_kb: int = 100,
 aggressive_optimization: bool = False,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Optimize document for performance

 Automatically applies optimizations like unfoldable annotations, compression,
 and structure improvements to reduce document size and improve loading performance
 """
 try:
 import json
 original_size = len(json.dumps(content))

 # Start with auto-marking unfoldable content
 if aggressive_optimization:
 optimized = UnfoldableProcessor.auto_mark_unfoldable(
 content,
 size_threshold = 5120, # More aggressive thresholds
 array_threshold = 50,
 text_threshold = 500
 )
 else:
 optimized = UnfoldableProcessor.auto_mark_unfoldable(content)

 # Additional optimizations
 def apply_optimizations(obj: Any) -> Any:
 if isinstance(obj, dict):
 result = {}
 for key, value in obj.items():
 # Skip null/empty values in aggressive mode
 if aggressive_optimization and (value is None or value == "" or value == []):
 continue
 result[key] = apply_optimizations(value)
 return result
 elif isinstance(obj, list):
 # Truncate very large arrays in aggressive mode
 if aggressive_optimization and len(obj) > 1000:
 return {
 "@unfoldable": True,
 "@display_name": "large_array",
 "@summary": f"Truncated array with {len(obj)} items",
 "@content": obj
 }
 return [apply_optimizations(item) for item in obj]
 else:
 return obj

 if aggressive_optimization:
 optimized = apply_optimizations(optimized)

 optimized_size = len(json.dumps(optimized))
 size_reduction = ((original_size - optimized_size) / original_size) * 100

 # Check if we met the target
 target_size_bytes = target_size_kb * 1024
 meets_target = optimized_size <= target_size_bytes

 # Get unfoldable analysis
 doc = UnfoldableDocument(optimized)
 unfoldable_paths = doc.get_unfoldable_paths()

 return {
 "optimized_content": optimized,
 "optimization_stats": {
 "original_size_bytes": original_size,
 "optimized_size_bytes": optimized_size,
 "size_reduction_percent": round(size_reduction, 2),
 "meets_target": meets_target,
 "target_size_kb": target_size_kb,
 "actual_size_kb": round(optimized_size / 1024, 2)
 },
 "applied_optimizations": {
 "unfoldable_annotations": len(unfoldable_paths),
 "aggressive_mode": aggressive_optimization,
 "empty_field_removal": aggressive_optimization,
 "large_array_truncation": aggressive_optimization
 },
 "recommendations": {
 "further_optimization_needed": not meets_target,
 "suggested_unfold_level": "COLLAPSED" if len(unfoldable_paths) > 3 else "SHALLOW",
 "caching_recommended": optimized_size > 50000
 }
 }

 except Exception as e:
 logger.error(f"Error optimizing document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to optimize document: {str(e)}"
 )


# Document Storage Endpoints

@router.post("/store",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def store_document(
 request: StoreDocumentRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Store a document with unfoldable content

 Stores the document in persistent storage with automatic unfoldable optimization
 """
 try:
 storage = get_document_storage()

 stored_doc = storage.store_document(
 name = request.name,
 content = request.content,
 metadata = request.metadata,
 tags = request.tags,
 auto_optimize = request.auto_optimize
 )

 return {
 "id": stored_doc.id,
 "name": stored_doc.name,
 "created_at": stored_doc.created_at.isoformat(),
 "version": stored_doc.version,
 "tags": stored_doc.tags,
 "stats": {
 "size_bytes": stored_doc.size_bytes,
 "unfoldable_fields_count": stored_doc.unfoldable_fields_count,
 "optimization_applied": request.auto_optimize
 }
 }

 except Exception as e:
 logger.error(f"Error storing document: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to store document: {str(e)}"
 )


@router.get("/store/{doc_id}",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_stored_document(
 doc_id: str,
 unfold_level: str = "COLLAPSED",
 unfold_paths: Optional[str] = None,
 max_depth: int = 10,
 include_summaries: bool = True,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Retrieve a stored document with optional unfolding

 Returns the document with applied unfold context
 """
 try:
 storage = get_document_storage()

 # Create unfold context
 unfold_context = None
 if unfold_level != "FULL":
 level = UnfoldLevel[unfold_level]
 paths = set(unfold_paths.split(",")) if unfold_paths else set()
 unfold_context = UnfoldContext(
 level = level,
 paths = paths,
 max_depth = max_depth,
 include_summaries = include_summaries
 )

 document = storage.get_document(doc_id, unfold_context)

 if document is None:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {doc_id}"
 )

 return document

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Error retrieving document {doc_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to retrieve document: {str(e)}"
 )


@router.put("/store/{doc_id}",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def update_stored_document(
 doc_id: str,
 request: UpdateDocumentRequest,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Update a stored document

 Updates the document content, metadata, or tags
 """
 try:
 storage = get_document_storage()

 stored_doc = storage.update_document(
 doc_id = doc_id,
 content = request.content,
 metadata = request.metadata,
 tags = request.tags,
 auto_optimize = request.auto_optimize
 )

 if stored_doc is None:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {doc_id}"
 )

 return {
 "id": stored_doc.id,
 "name": stored_doc.name,
 "updated_at": stored_doc.updated_at.isoformat(),
 "version": stored_doc.version,
 "tags": stored_doc.tags,
 "stats": {
 "size_bytes": stored_doc.size_bytes,
 "unfoldable_fields_count": stored_doc.unfoldable_fields_count
 }
 }

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Error updating document {doc_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to update document: {str(e)}"
 )


@router.delete("/store/{doc_id}",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def delete_stored_document(
 doc_id: str,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Delete a stored document
 """
 try:
 storage = get_document_storage()

 success = storage.delete_document(doc_id)

 if not success:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {doc_id}"
 )

 return {
 "message": f"Document {doc_id} deleted successfully"
 }

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Error deleting document {doc_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to delete document: {str(e)}"
 )


@router.get("/store",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def list_stored_documents(
 tags: Optional[str] = None,
 name_filter: Optional[str] = None,
 limit: int = 100,
 offset: int = 0,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 List stored documents with filtering and pagination
 """
 try:
 storage = get_document_storage()

 tag_list = tags.split(",") if tags else None

 result = storage.list_documents(
 tags = tag_list,
 name_filter = name_filter,
 limit = limit,
 offset = offset
 )

 return result

 except Exception as e:
 logger.error(f"Error listing documents: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to list documents: {str(e)}"
 )


@router.post("/search",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def search_stored_documents(
 request: DocumentSearchRequest,
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Search stored documents by content or metadata
 """
 try:
 storage = get_document_storage()

 results = storage.search_documents(
 query = request.query,
 search_content = request.search_content,
 search_metadata = request.search_metadata,
 limit = request.limit
 )

 return {
 "query": request.query,
 "results": results,
 "total_results": len(results)
 }

 except Exception as e:
 logger.error(f"Error searching documents: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to search documents: {str(e)}"
 )


@router.get("/stats",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_storage_stats(
 req: Request = None,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Get document storage statistics
 """
 try:
 storage = get_document_storage()
 stats = storage.get_document_stats()

 return {
 "storage_stats": stats,
 "timestamp": datetime.utcnow().isoformat()
 }

 except Exception as e:
 logger.error(f"Error getting storage stats: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to get storage stats: {str(e)}"
 )


@router.post("/inject-metadata",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))])
async def inject_metadata_frames(
 request: InjectMetadataRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Inject metadata frames into markdown content

 Adds metadata frames to existing markdown content at appropriate positions
 """
 try:
 parser = MetadataFrameParser()

 # Convert request frames to MetadataFrame objects
 frames = []
 for frame_data in request.metadata_frames:
 frame = MetadataFrame(
 frame_type = frame_data["frame_type"],
 content = frame_data["content"],
 position=(0, 0), # Will be positioned automatically
 format = frame_data.get("format", "yaml")
 )
 frames.append(frame)

 # Inject frames into content
 result_content = parser.inject_frames(request.markdown_content, frames)

 return {
 "markdown_content": result_content,
 "frames_injected": len(frames),
 "total_length": len(result_content)
 }

 except Exception as e:
 logger.error(f"Error injecting metadata frames: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to inject metadata frames: {str(e)}"
 )


@router.post("/validate-metadata",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def validate_metadata_frames(
 request: ValidateMetadataRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Validate metadata frames in markdown content

 Checks for syntax errors, schema compliance, and consistency
 """
 try:
 parser = MetadataFrameParser()
 generator = SchemaDocumentationGenerator()

 # Parse document
 cleaned_content, frames = parser.parse_document(request.markdown_content)

 # Validation results
 validation_results = {
 "is_valid": True,
 "total_frames": len(frames),
 "frame_validation": [],
 "warnings": [],
 "errors": []
 }

 for i, frame in enumerate(frames):
 frame_validation = {
 "frame_index": i,
 "frame_type": frame.frame_type,
 "format": frame.format,
 "is_valid": True,
 "issues": []
 }

 # Validate frame type
 if frame.frame_type not in parser.frame_types:
 frame_validation["is_valid"] = False
 frame_validation["issues"].append(f"Unknown frame type: {frame.frame_type}")
 validation_results["errors"].append(f"Frame {i}: Unknown frame type '{frame.frame_type}'")
 validation_results["is_valid"] = False

 # Validate format
 if frame.format not in parser.supported_formats:
 frame_validation["is_valid"] = False
 frame_validation["issues"].append(f"Unsupported format: {frame.format}")
 validation_results["errors"].append(f"Frame {i}: Unsupported format '{frame.format}'")
 validation_results["is_valid"] = False

 # Validate content structure based on frame type
 if request.strict:
 if frame.frame_type == "schema" and not isinstance(frame.content, dict):
 frame_validation["issues"].append("Schema frame content must be an object")
 validation_results["warnings"].append(f"Frame {i}: Schema should be an object")

 if frame.frame_type == "api" and "endpoint" not in frame.content:
 frame_validation["issues"].append("API frame missing endpoint field")
 validation_results["warnings"].append(f"Frame {i}: API frame should include endpoint")

 if frame.frame_type == "validation" and "rules" not in frame.content:
 frame_validation["issues"].append("Validation frame missing rules field")
 validation_results["warnings"].append(f"Frame {i}: Validation frame should include rules")

 validation_results["frame_validation"].append(frame_validation)

 # Generate summary for additional validation
 summary = generator.extract_metadata_summary(request.markdown_content)

 return {
 "validation": validation_results,
 "summary": summary,
 "cleaned_content_length": len(cleaned_content)
 }

 except Exception as e:
 logger.error(f"Error validating metadata frames: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to validate metadata frames: {str(e)}"
 )


@router.post("/convert-metadata",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def convert_metadata_formats(
 request: ConvertMetadataRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Convert metadata frames between different formats (YAML/JSON)

 Converts metadata frame content from one format to another
 """
 try:
 import json

 import yaml

 converted_frames = []
 conversion_stats = {
 "total_frames": len(request.metadata_frames),
 "successful_conversions": 0,
 "failed_conversions": 0,
 "errors": []
 }

 for i, frame_data in enumerate(request.metadata_frames):
 try:
 # Create MetadataFrame object
 frame = MetadataFrame(
 frame_type = frame_data["frame_type"],
 content = frame_data["content"],
 position = tuple(frame_data.get("position", [0, 0])),
 format = frame_data.get("format", "yaml")
 )

 # Change format
 frame.format = request.target_format

 # Convert to markdown to validate
 markdown = frame.to_markdown()

 converted_frames.append({
 "frame_type": frame.frame_type,
 "content": frame.content,
 "position": frame.position,
 "format": frame.format,
 "markdown": markdown
 })

 conversion_stats["successful_conversions"] += 1

 except Exception as e:
 conversion_stats["failed_conversions"] += 1
 conversion_stats["errors"].append({
 "frame_index": i,
 "error": str(e)
 })

 return {
 "converted_frames": converted_frames,
 "stats": conversion_stats,
 "target_format": request.target_format
 }

 except Exception as e:
 logger.error(f"Error converting metadata formats: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to convert metadata formats: {str(e)}"
 )


@router.post("/export-documentation",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def export_documentation(
 request: ExportDocumentationRequest,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Export schema documentation in different formats

 Converts schema documentation to various export formats (Markdown, HTML, etc.)
 """
 try:
 from datetime import datetime

 # Create SchemaDocumentation from request data
 doc_data = request.schema_documentation
 doc = SchemaDocumentation(
 name = doc_data["name"],
 title = doc_data["title"],
 description = doc_data["description"],
 version = doc_data.get("version", "1.0.0"),
 author = doc_data.get("author"),
 created_at = datetime.fromisoformat(doc_data["created_at"]) if "created_at" in doc_data else None,


 updated_at = datetime.fromisoformat(doc_data["updated_at"]) if "updated_at" in doc_data else None,


 tags = doc_data.get("tags", []),
 content = doc_data.get("content", "")
 )

 # Generate markdown
 markdown_content = doc.to_markdown()

 # Export based on format
 export_content = ""
 content_type = "text/plain"

 if request.export_format == "markdown":
 export_content = markdown_content
 content_type = "text/markdown"

 elif request.export_format == "html":
 # Convert markdown to HTML (simplified)
 html_template = """<!DOCTYPE html>
<html>
<head>
 <title>{doc.title}</title>
 <meta charset = "UTF-8">
 <style>
 body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
 h1, h2, h3 {{ color: #333; }}
 code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
 pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
 .metadata-frame {{ border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }}
 </style>
</head>
<body>
 <h1>{doc.title}</h1>
 <p><strong > Version:</strong> {doc.version}</p>
 <p><strong > Description:</strong> {doc.description}</p>
 <div>
 {markdown_content.replace(chr(10), '<br > ').replace('```',
     '</code></pre><pre><code > ').replace('# ', '<h1 > ').replace('## ',
     '<h2 > ').replace('### ', '<h3 > ')}
 </div>
</body>
</html > """
 export_content = html_template
 content_type = "text/html"

 else:
 export_content = markdown_content
 content_type = "text/markdown"

 # Generate filename
 safe_name = doc.name.replace(" ", "_").replace("/", "_")
 filename = f"{safe_name}_v{doc.version}.{request.export_format}"

 return {
 "export_content": export_content,
 "content_type": content_type,
 "filename": filename,
 "export_format": request.export_format,
 "size_bytes": len(export_content.encode('utf-8')),
 "metadata": {
 "title": doc.title,
 "version": doc.version,
 "export_timestamp": datetime.utcnow().isoformat(),
 "include_metadata": request.include_metadata
 }
 }

 except Exception as e:
 logger.error(f"Error exporting documentation: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to export documentation: {str(e)}"
 )


@router.get("/metadata-summary/{document_id}",
    dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))])
async def get_document_metadata_summary(
 document_id: str,
 req: Request,
 user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """
 Get metadata summary for a stored document

 Returns a summary of all metadata frames in a document
 """
 try:
 storage = get_document_storage()

 # Get document
 document = storage.get_document(document_id)
 if document is None:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"Document not found: {document_id}"
 )

 # Extract markdown content if available
 markdown_content = ""
 if "markdown_content" in document:
 markdown_content = document["markdown_content"]
 elif "content" in document and isinstance(document["content"], str):
 markdown_content = document["content"]
 else:
 # Generate markdown from structured content
 generator = SchemaDocumentationGenerator()
 if "object_type" in document:
 doc = generator.generate_object_type_doc(document["object_type"])
 markdown_content = doc.to_markdown()

 if not markdown_content:
 return {
 "document_id": document_id,
 "metadata_summary": {
 'total_frames': 0,
 'frame_types': {},
 'metadata': {}
 },
 "message": "No markdown content found for metadata extraction"
 }

 # Generate summary
 generator = SchemaDocumentationGenerator()
 summary = generator.extract_metadata_summary(markdown_content)

 return {
 "document_id": document_id,
 "metadata_summary": summary,
 "document_info": {
 "name": document.get("name", "Unknown"),
 "created_at": document.get("created_at"),
 "updated_at": document.get("updated_at")
 }
 }

 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Error getting metadata summary for document {document_id}: {e}")
 raise HTTPException(
 status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
 detail = f"Failed to get metadata summary: {str(e)}"
 )


@router.get("/health")
async def health_check() -> Dict[str, str]:
 """Health check for document service"""
 return {
 "status": "healthy",
 "service": "document-processor",
 "features": ["unfoldable", "metadata-frames", "batch-processing", "optimization"]
 }
