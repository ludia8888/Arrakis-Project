"""
GraphQL Schema for Unfoldable Documents
Provides GraphQL queries and mutations for document operations
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

import strawberry
from arrakis_common import get_logger
from core.documents import (
    MetadataFrameParser,
    SchemaDocumentationGenerator,
    UnfoldableDocument,
    UnfoldableProcessor,
    UnfoldContext,
    UnfoldLevel,
)

logger = get_logger(__name__)


# GraphQL Types


@strawberry.type
class UnfoldableFieldInfo:
    """GraphQL type for unfoldable field information"""

    path: str
    display_name: str
    summary: Optional[str] = None
    size_bytes: Optional[int] = None
    item_count: Optional[int] = None
    is_large: bool = False


@strawberry.type
class DocumentStats:
    """GraphQL type for document statistics"""

    total_unfoldable_fields: int
    unfold_level: str
    processing_time_ms: Optional[float] = None


@strawberry.type
class UnfoldedDocument:
    """GraphQL type for unfolded document response"""

    content: strawberry.scalars.JSON
    unfoldable_paths: List[UnfoldableFieldInfo]
    metadata: Optional[strawberry.scalars.JSON] = None
    stats: DocumentStats


@strawberry.type
class UnfoldedPath:
    """GraphQL type for unfolded path response"""

    path: str
    content: strawberry.scalars.JSON
    type_name: str


@strawberry.type
class PreparedDocument:
    """GraphQL type for prepared document response"""

    content: strawberry.scalars.JSON
    unfoldable_paths: List[str]
    annotations_added: int


@strawberry.type
class MetadataFrameInfo:
    """GraphQL type for metadata frame information"""

    frame_type: str
    content: strawberry.scalars.JSON
    position_start: int
    position_end: int
    format: str


@strawberry.type
class ParsedDocument:
    """GraphQL type for parsed document response"""

    cleaned_content: str
    metadata_frames: List[MetadataFrameInfo]
    summary: strawberry.scalars.JSON


@strawberry.type
class GeneratedDocumentation:
    """GraphQL type for generated documentation response"""

    name: str
    title: str
    description: str
    version: str
    markdown: str
    metadata_frames: List[MetadataFrameInfo]
    stats: strawberry.scalars.JSON


# Input Types


@strawberry.input
class UnfoldContextInput:
    """GraphQL input type for unfold context"""

    level: str = "COLLAPSED"
    paths: Optional[List[str]] = None
    max_depth: int = 10
    size_threshold: int = 10240
    array_threshold: int = 100
    include_summaries: bool = True


@strawberry.input
class UnfoldDocumentInput:
    """GraphQL input type for unfolding a document"""

    content: strawberry.scalars.JSON
    context: UnfoldContextInput
    metadata: Optional[strawberry.scalars.JSON] = None


@strawberry.input
class UnfoldPathInput:
    """GraphQL input type for unfolding a specific path"""

    content: strawberry.scalars.JSON
    path: str


@strawberry.input
class PrepareUnfoldableInput:
    """GraphQL input type for preparing unfoldable document"""

    content: strawberry.scalars.JSON
    unfoldable_paths: List[str]


@strawberry.input
class ParseMetadataInput:
    """GraphQL input type for parsing metadata frames"""

    markdown_content: str


@strawberry.input
class GenerateDocumentationInput:
    """GraphQL input type for generating documentation"""

    object_type: strawberry.scalars.JSON
    include_examples: bool = True


@strawberry.input
class AutoMarkUnfoldableInput:
    """GraphQL input type for auto-marking unfoldable content"""

    content: strawberry.scalars.JSON
    size_threshold: int = 10240
    array_threshold: int = 100
    text_threshold: int = 1000


@strawberry.input
class BatchUnfoldInput:
    """GraphQL input type for batch unfolding operations"""

    documents: List[UnfoldDocumentInput]
    parallel: bool = True


# Query and Mutation Classes


@strawberry.type
class DocumentQueries:
    """GraphQL queries for unfoldable documents"""

    @strawberry.field
    async def unfold_document(self, input: UnfoldDocumentInput) -> UnfoldedDocument:
        """
        Unfold a document based on the provided context
        """
        try:
            import time

            start_time = time.time()

            # Create unfold context
            unfold_level = UnfoldLevel[input.context.level]
            context = UnfoldContext(
                level=unfold_level,
                paths=set(input.context.paths) if input.context.paths else set(),
                max_depth=input.context.max_depth,
                size_threshold=input.context.size_threshold,
                array_threshold=input.context.array_threshold,
                include_summaries=input.context.include_summaries,
            )

            # Create and process document
            doc = UnfoldableDocument(input.content, input.metadata)
            folded_content = doc.fold(context)
            unfoldable_paths_data = doc.get_unfoldable_paths()

            processing_time = (time.time() - start_time) * 1000

            # Convert unfoldable paths to GraphQL types
            unfoldable_paths = [
                UnfoldableFieldInfo(
                    path=path["path"],
                    display_name=path["display_name"],
                    summary=path["summary"],
                    size_bytes=path["size_bytes"],
                    item_count=path["item_count"],
                    is_large=path["is_large"],
                )
                for path in unfoldable_paths_data
            ]

            stats = DocumentStats(
                total_unfoldable_fields=len(unfoldable_paths),
                unfold_level=input.context.level,
                processing_time_ms=processing_time,
            )

            return UnfoldedDocument(
                content=folded_content,
                unfoldable_paths=unfoldable_paths,
                metadata=input.metadata,
                stats=stats,
            )

        except Exception as e:
            logger.error(f"Error unfolding document: {e}")
            raise

    @strawberry.field
    async def unfold_path(self, input: UnfoldPathInput) -> UnfoldedPath:
        """
        Unfold a specific path in a document
        """
        try:
            doc = UnfoldableDocument(input.content)
            content = doc.unfold_path(input.path)

            if content is None:
                raise ValueError(f"Path not found: {input.path}")

            return UnfoldedPath(
                path=input.path, content=content, type_name=type(content).__name__
            )

        except Exception as e:
            logger.error(f"Error unfolding path: {e}")
            raise

    @strawberry.field
    async def get_unfoldable_paths(
        self, content: strawberry.scalars.JSON
    ) -> List[UnfoldableFieldInfo]:
        """
        Get all unfoldable paths in a document
        """
        try:
            doc = UnfoldableDocument(content)
            paths_data = doc.get_unfoldable_paths()

            return [
                UnfoldableFieldInfo(
                    path=path["path"],
                    display_name=path["display_name"],
                    summary=path["summary"],
                    size_bytes=path["size_bytes"],
                    item_count=path["item_count"],
                    is_large=path["is_large"],
                )
                for path in paths_data
            ]

        except Exception as e:
            logger.error(f"Error getting unfoldable paths: {e}")
            raise

    @strawberry.field
    async def parse_metadata_frames(self, input: ParseMetadataInput) -> ParsedDocument:
        """
        Parse metadata frames from markdown content
        """
        try:
            parser = MetadataFrameParser()
            cleaned_content, frames = parser.parse_document(input.markdown_content)

            # Convert frames to GraphQL types
            metadata_frames = [
                MetadataFrameInfo(
                    frame_type=frame.frame_type,
                    content=frame.content,
                    position_start=frame.position[0],
                    position_end=frame.position[1],
                    format=frame.format,
                )
                for frame in frames
            ]

            # Build summary
            summary = {"total_frames": len(frames), "frame_types": {}, "metadata": {}}

            for frame in frames:
                if frame.frame_type not in summary["frame_types"]:
                    summary["frame_types"][frame.frame_type] = 0
                summary["frame_types"][frame.frame_type] += 1

                if frame.frame_type == "document":
                    summary["metadata"].update(frame.content)

            return ParsedDocument(
                cleaned_content=cleaned_content,
                metadata_frames=metadata_frames,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Error parsing metadata frames: {e}")
            raise

    @strawberry.field
    async def generate_documentation(
        self, input: GenerateDocumentationInput
    ) -> GeneratedDocumentation:
        """
        Generate schema documentation with metadata frames
        """
        try:
            generator = SchemaDocumentationGenerator()
            doc = generator.generate_object_type_doc(input.object_type)

            # Convert frames to GraphQL types
            metadata_frames = [
                MetadataFrameInfo(
                    frame_type=frame.frame_type,
                    content=frame.content,
                    position_start=frame.position[0],
                    position_end=frame.position[1],
                    format=frame.format,
                )
                for frame in doc.metadata_frames
            ]

            stats = {
                "total_frames": len(metadata_frames),
                "content_length": len(doc.to_markdown()),
            }

            return GeneratedDocumentation(
                name=doc.name,
                title=doc.title,
                description=doc.description,
                version=doc.version,
                markdown=doc.to_markdown(),
                metadata_frames=metadata_frames,
                stats=stats,
            )

        except Exception as e:
            logger.error(f"Error generating documentation: {e}")
            raise


@strawberry.type
class DocumentMutations:
    """GraphQL mutations for unfoldable documents"""

    @strawberry.mutation
    async def prepare_unfoldable(
        self, input: PrepareUnfoldableInput
    ) -> PreparedDocument:
        """
        Prepare a document with @unfoldable annotations
        """
        try:
            prepared = UnfoldableProcessor.prepare_document(
                input.content, input.unfoldable_paths
            )

            return PreparedDocument(
                content=prepared,
                unfoldable_paths=input.unfoldable_paths,
                annotations_added=len(input.unfoldable_paths),
            )

        except Exception as e:
            logger.error(f"Error preparing unfoldable document: {e}")
            raise

    @strawberry.mutation
    async def auto_mark_unfoldable(
        self, input: AutoMarkUnfoldableInput
    ) -> PreparedDocument:
        """
        Automatically mark large content as unfoldable
        """
        try:
            processed = UnfoldableProcessor.auto_mark_unfoldable(
                input.content,
                input.size_threshold,
                input.array_threshold,
                input.text_threshold,
            )

            # Count annotations added by comparing with original
            doc = UnfoldableDocument(processed)
            unfoldable_paths = [path["path"] for path in doc.get_unfoldable_paths()]

            return PreparedDocument(
                content=processed,
                unfoldable_paths=unfoldable_paths,
                annotations_added=len(unfoldable_paths),
            )

        except Exception as e:
            logger.error(f"Error auto-marking unfoldable content: {e}")
            raise

    @strawberry.mutation
    async def extract_unfoldable_content(
        self, content: strawberry.scalars.JSON
    ) -> strawberry.scalars.JSON:
        """
        Extract unfoldable content from a document
        """
        try:
            (
                main_doc,
                unfoldable_content,
            ) = UnfoldableProcessor.extract_unfoldable_content(content)

            return {
                "main_document": main_doc,
                "unfoldable_content": unfoldable_content,
                "stats": {"unfoldable_fields": len(unfoldable_content)},
            }

        except Exception as e:
            logger.error(f"Error extracting unfoldable content: {e}")
            raise

    @strawberry.mutation
    async def batch_unfold_documents(
        self, input: BatchUnfoldInput
    ) -> List[UnfoldedDocument]:
        """
        Batch unfold multiple documents
        """
        try:
            results = []

            if input.parallel:
                import asyncio

                tasks = [
                    self.unfold_document(doc_input) for doc_input in input.documents
                ]
                results = await asyncio.gather(*tasks)
            else:
                for doc_input in input.documents:
                    result = await self.unfold_document(doc_input)
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error batch unfolding documents: {e}")
            raise


# Schema combination
def get_document_schema_types():
    """Get all document-related GraphQL types for schema building"""
    return {
        "queries": DocumentQueries,
        "mutations": DocumentMutations,
        "types": [
            UnfoldableFieldInfo,
            DocumentStats,
            UnfoldedDocument,
            UnfoldedPath,
            PreparedDocument,
            MetadataFrameInfo,
            ParsedDocument,
            GeneratedDocumentation,
        ],
        "inputs": [
            UnfoldContextInput,
            UnfoldDocumentInput,
            UnfoldPathInput,
            PrepareUnfoldableInput,
            ParseMetadataInput,
            GenerateDocumentationInput,
            AutoMarkUnfoldableInput,
            BatchUnfoldInput,
        ],
    }
