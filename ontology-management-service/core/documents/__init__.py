"""
Document Processing Module
Provides advanced document features including unfoldable content and metadata frames
"""

from .metadata_frames import (
    MetadataFrame,
    MetadataFrameParser,
    SchemaDocumentation,
    SchemaDocumentationGenerator,
)
from .storage import DocumentStorage, StoredDocument, get_document_storage
from .unfoldable import (
    UnfoldableDocument,
    UnfoldableField,
    UnfoldableProcessor,
    UnfoldContext,
    UnfoldLevel,
)

__all__ = [
    # Unfoldable
    "UnfoldLevel",
    "UnfoldableField",
    "UnfoldContext",
    "UnfoldableDocument",
    "UnfoldableProcessor",
    # Metadata Frames
    "MetadataFrame",
    "MetadataFrameParser",
    "SchemaDocumentation",
    "SchemaDocumentationGenerator",
    # Storage
    "StoredDocument",
    "DocumentStorage",
    "get_document_storage",
]
