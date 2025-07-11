"""
Vector Embeddings API Routes
Provides REST API endpoints for the enhanced embedding functionality
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from bootstrap.providers.embedding import (
    get_embedding_service_provider,
    get_embedding_provider_status,
    test_embedding_providers
)
from shared.embedding_config import get_embedding_config, validate_embedding_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["Vector Embeddings"])


# Request/Response Models
class EmbeddingRequest(BaseModel):
    text: str = Field(..., description="Text to generate embedding for")
    provider: Optional[str] = Field(None, description="Specific provider to use")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BatchEmbeddingRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to generate embeddings for")
    provider: Optional[str] = Field(None, description="Specific provider to use")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SimilarityRequest(BaseModel):
    embedding1: List[float] = Field(..., description="First embedding vector")
    embedding2: List[float] = Field(..., description="Second embedding vector")
    metric: str = Field("cosine", description="Similarity metric to use")


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    collection: str = Field("default", description="Collection to search in")
    top_k: int = Field(10, description="Number of results to return")
    similarity_threshold: float = Field(0.7, description="Minimum similarity score")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


class StoreTextRequest(BaseModel):
    text: str = Field(..., description="Text to store")
    document_id: Optional[str] = Field(None, description="Document ID (auto-generated if not provided)")
    collection: str = Field("default", description="Collection to store in")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Document metadata")


# API Endpoints
@router.get("/status")
async def get_embedding_status():
    """Get status of all embedding providers"""
    try:
        status = await get_embedding_provider_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_embedding_configuration():
    """Get embedding service configuration"""
    try:
        config = get_embedding_config()
        validation = validate_embedding_config()
        
        return {
            "success": True,
            "data": {
                "configuration": {
                    "use_microservice": config.use_microservice,
                    "service_endpoint": config.service_endpoint,
                    "default_provider": config.default_provider,
                    "fallback_enabled": config.fallback_enabled,
                    "cache_enabled": config.cache_enabled,
                    "enabled_providers": list(config.providers.keys())
                },
                "validation": validation
            }
        }
    except Exception as e:
        logger.error(f"Failed to get embedding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def list_embedding_providers():
    """List all available embedding providers"""
    try:
        provider = get_embedding_service_provider()
        await provider.initialize()
        
        providers = await provider.get_available_providers()
        stats = await provider.get_provider_stats()
        
        return {
            "success": True,
            "data": {
                "available_providers": providers,
                "provider_details": stats.get("configuration", {}).get("enabled_providers", []),
                "default_provider": stats.get("configuration", {}).get("default_provider")
            }
        }
    except Exception as e:
        logger.error(f"Failed to list embedding providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_all_embedding_providers(background_tasks: BackgroundTasks):
    """Test all embedding providers"""
    try:
        # Run tests in background to avoid timeout
        results = await test_embedding_providers()
        
        return {
            "success": True,
            "data": results
        }
    except Exception as e:
        logger.error(f"Failed to test embedding providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/{provider_name}")
async def test_specific_provider(provider_name: str):
    """Test a specific embedding provider"""
    try:
        provider = get_embedding_service_provider()
        await provider.initialize()
        
        result = await provider.test_provider(provider_name)
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to test provider {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_embedding(request: EmbeddingRequest):
    """Generate embedding for text"""
    try:
        provider = get_embedding_service_provider()
        stub = await provider.provide()
        
        if request.provider:
            # Use specific provider if requested
            if hasattr(stub, 'generate_embedding_with_provider'):
                embedding = await stub.generate_embedding_with_provider(
                    request.text, request.provider, request.metadata
                )
            else:
                embedding = await stub.generate_embedding(request.text, request.metadata)
        else:
            embedding = await stub.generate_embedding(request.text, request.metadata)
        
        return {
            "success": True,
            "data": {
                "embedding": embedding,
                "dimension": len(embedding),
                "text_length": len(request.text),
                "provider_used": request.provider or "default"
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def generate_batch_embeddings(request: BatchEmbeddingRequest):
    """Generate embeddings for multiple texts"""
    try:
        provider = get_embedding_service_provider()
        stub = await provider.provide()
        
        embeddings = await stub.generate_batch_embeddings(request.texts, request.metadata)
        
        return {
            "success": True,
            "data": {
                "embeddings": embeddings,
                "count": len(embeddings),
                "dimensions": [len(emb) for emb in embeddings],
                "provider_used": request.provider or "default"
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similarity")
async def calculate_similarity(request: SimilarityRequest):
    """Calculate similarity between two embeddings"""
    try:
        provider = get_embedding_service_provider()
        stub = await provider.provide()
        
        similarity = await stub.calculate_similarity(
            request.embedding1, request.embedding2, request.metric
        )
        
        return {
            "success": True,
            "data": {
                "similarity": similarity,
                "metric": request.metric,
                "embedding1_dimension": len(request.embedding1),
                "embedding2_dimension": len(request.embedding2)
            }
        }
    except Exception as e:
        logger.error(f"Failed to calculate similarity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store")
async def store_text_with_embedding(request: StoreTextRequest):
    """Store text with generated embedding"""
    try:
        provider = get_embedding_service_provider()
        stub = await provider.provide()
        
        if hasattr(stub, 'store_text_with_embedding'):
            result = await stub.store_text_with_embedding(
                text=request.text,
                document_id=request.document_id,
                collection=request.collection,
                metadata=request.metadata
            )
        else:
            # Fallback: generate embedding and store separately
            embedding = await stub.generate_embedding(request.text)
            
            import hashlib
            doc_id = request.document_id or hashlib.md5(request.text.encode()).hexdigest()
            
            full_metadata = request.metadata or {}
            full_metadata["text"] = request.text
            
            success = await stub.store_embedding(
                doc_id, embedding, request.collection, full_metadata
            )
            
            result = {
                "success": success,
                "document_id": doc_id,
                "embedding_dimension": len(embedding),
                "collection": request.collection
            }
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to store text with embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def semantic_search(request: SemanticSearchRequest):
    """Perform semantic search"""
    try:
        provider = get_embedding_service_provider()
        stub = await provider.provide()
        
        if hasattr(stub, 'semantic_search_text'):
            results = await stub.semantic_search_text(
                query_text=request.query,
                collection=request.collection,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
                filters=request.filters
            )
        else:
            # Fallback: generate embedding and search
            query_embedding = await stub.generate_embedding(request.query)
            results = await stub.find_similar(
                query_embedding=query_embedding,
                collection=request.collection,
                top_k=request.top_k,
                min_similarity=request.similarity_threshold,
                filters=request.filters
            )
        
        return {
            "success": True,
            "data": {
                "results": results,
                "query": request.query,
                "collection": request.collection,
                "results_count": len(results)
            }
        }
    except Exception as e:
        logger.error(f"Failed to perform semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def list_collections():
    """List all available collections"""
    try:
        # This would integrate with the vector store
        # For now, return a placeholder response
        return {
            "success": True,
            "data": {
                "collections": ["default"],
                "note": "Vector store integration required for full functionality"
            }
        }
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str):
    """Get statistics for a specific collection"""
    try:
        # This would integrate with the vector store
        # For now, return a placeholder response
        return {
            "success": True,
            "data": {
                "collection": collection_name,
                "document_count": 0,
                "note": "Vector store integration required for full functionality"
            }
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))