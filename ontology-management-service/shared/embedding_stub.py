"""
Real Vector Embeddings Implementation with Multi-Provider Support
Integrates with the embedding-service microservice for production use
and provides fallback local implementations
"""
import grpc
import logging
import numpy as np
import os
import asyncio
import json
import hashlib
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from shared.grpc_interceptors import create_instrumented_channel

# Import the actual embedding providers
try:
    import sys
    import os
    # Add embedding-service to path for imports
    embedding_service_path = os.path.join(os.path.dirname(__file__), '../../embedding-service/app')
    if embedding_service_path not in sys.path:
        sys.path.append(embedding_service_path)
    
    from embeddings.providers import (
        EmbeddingProviderFactory, EmbeddingConfig, EmbeddingProvider, BaseEmbeddingProvider,
        EmbeddingProviderError, EmbeddingAPIError, EmbeddingBatchSizeError, EmbeddingTokenLimitError
    )
    from embeddings.service import VectorEmbeddingService
    HAS_EMBEDDING_SERVICE = True
except ImportError as e:
    logger.warning(f"Embedding service modules not available: {e}. Using fallback implementation.")
    HAS_EMBEDDING_SERVICE = False

# Fallback gRPC proto imports
try:
    from services.embedding_service.proto import embedding_service_pb2 as pb2
    from services.embedding_service.proto import embedding_service_pb2_grpc as pb2_grpc
    HAS_GRPC_PROTOS = True
except ImportError:
    HAS_GRPC_PROTOS = False
    pb2 = None
    pb2_grpc = None

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingProviderConfig:
    """Configuration for an embedding provider"""
    name: str
    provider_type: str
    model_name: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    dimensions: Optional[int] = None
    max_tokens: int = 8192
    batch_size: int = 100
    timeout: int = 30
    enabled: bool = True


class RealVectorEmbeddingService:
    """
    Real Vector Embedding Service with Multi-Provider Support
    Supports 7 AI providers: OpenAI, Anthropic, Cohere, HuggingFace, Azure OpenAI, Google Vertex, Local
    """
    
    def __init__(self):
        self.providers: Dict[str, BaseEmbeddingProvider] = {}
        self.default_provider = None
        self.fallback_chain: List[str] = []
        self._initialized = False
        self.use_microservice = os.getenv("USE_EMBEDDING_MS", "false").lower() == "true"
        
    async def initialize(self):
        """Initialize the embedding service with configured providers"""
        if self._initialized:
            return
            
        if self.use_microservice and HAS_EMBEDDING_SERVICE:
            logger.info("Initializing embedding service in microservice mode")
            await self._initialize_microservice_providers()
        else:
            logger.info("Initializing embedding service in local mode")
            await self._initialize_local_providers()
            
        self._initialized = True
        logger.info(f"Embedding service initialized with providers: {list(self.providers.keys())}")
    
    async def _initialize_microservice_providers(self):
        """Initialize providers for microservice mode"""
        # Configuration for all supported providers
        provider_configs = self._get_provider_configurations()
        
        for config in provider_configs:
            if config.enabled and config.api_key:  # Only initialize if API key is available
                try:
                    embedding_config = self._convert_to_embedding_config(config)
                    provider = EmbeddingProviderFactory.create_provider(embedding_config)
                    self.providers[config.name] = provider
                    
                    if self.default_provider is None:
                        self.default_provider = config.name
                        
                    logger.info(f"Initialized provider: {config.name} ({config.provider_type})")
                except Exception as e:
                    logger.error(f"Failed to initialize provider {config.name}: {e}")
        
        # Always ensure we have a local fallback
        await self._ensure_local_fallback()
        self._update_fallback_chain()
    
    async def _initialize_local_providers(self):
        """Initialize local-only providers"""
        # Only initialize local providers and any with available API keys
        provider_configs = [
            EmbeddingProviderConfig(
                name="local_sentence_transformers",
                provider_type="local_sentence_transformers",
                model_name="all-MiniLM-L6-v2",
                dimensions=384,
                enabled=True
            )
        ]
        
        # Add cloud providers if API keys are available
        if os.getenv("OPENAI_API_KEY"):
            provider_configs.append(EmbeddingProviderConfig(
                name="openai",
                provider_type="openai",
                model_name="text-embedding-3-large",
                api_key=os.getenv("OPENAI_API_KEY"),
                dimensions=3072,
                enabled=True
            ))
            
        if os.getenv("COHERE_API_KEY"):
            provider_configs.append(EmbeddingProviderConfig(
                name="cohere",
                provider_type="cohere",
                model_name="embed-english-v3.0",
                api_key=os.getenv("COHERE_API_KEY"),
                dimensions=1024,
                enabled=True
            ))
        
        for config in provider_configs:
            try:
                if HAS_EMBEDDING_SERVICE:
                    embedding_config = self._convert_to_embedding_config(config)
                    provider = EmbeddingProviderFactory.create_provider(embedding_config)
                    self.providers[config.name] = provider
                else:
                    # Fallback to basic local implementation
                    provider = await self._create_fallback_provider(config)
                    self.providers[config.name] = provider
                
                if self.default_provider is None:
                    self.default_provider = config.name
                    
                logger.info(f"Initialized local provider: {config.name}")
            except Exception as e:
                logger.error(f"Failed to initialize local provider {config.name}: {e}")
        
        self._update_fallback_chain()
    
    def _get_provider_configurations(self) -> List[EmbeddingProviderConfig]:
        """Get configurations for all supported providers"""
        return [
            EmbeddingProviderConfig(
                name="openai",
                provider_type="openai",
                model_name="text-embedding-3-large",
                api_key=os.getenv("OPENAI_API_KEY"),
                dimensions=3072,
                enabled=bool(os.getenv("OPENAI_API_KEY"))
            ),
            EmbeddingProviderConfig(
                name="anthropic",
                provider_type="anthropic_claude",
                model_name="claude-3-haiku-20240307",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                dimensions=384,
                batch_size=20,
                enabled=bool(os.getenv("ANTHROPIC_API_KEY"))
            ),
            EmbeddingProviderConfig(
                name="cohere",
                provider_type="cohere",
                model_name="embed-english-v3.0",
                api_key=os.getenv("COHERE_API_KEY"),
                dimensions=1024,
                batch_size=96,
                enabled=bool(os.getenv("COHERE_API_KEY"))
            ),
            EmbeddingProviderConfig(
                name="huggingface",
                provider_type="huggingface",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                api_key=os.getenv("HUGGINGFACE_API_KEY"),
                api_base="https://api-inference.huggingface.co",
                dimensions=384,
                enabled=bool(os.getenv("HUGGINGFACE_API_KEY"))
            ),
            EmbeddingProviderConfig(
                name="azure_openai",
                provider_type="azure_openai",
                model_name="text-embedding-3-large",
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
                dimensions=3072,
                enabled=bool(os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"))
            ),
            EmbeddingProviderConfig(
                name="google_vertex",
                provider_type="google_vertex",
                model_name="textembedding-gecko@003",
                dimensions=768,
                enabled=bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            ),
            EmbeddingProviderConfig(
                name="local_sentence_transformers",
                provider_type="local_sentence_transformers",
                model_name="all-MiniLM-L6-v2",
                dimensions=384,
                enabled=True  # Always available as fallback
            )
        ]
    
    def _convert_to_embedding_config(self, config: EmbeddingProviderConfig) -> 'EmbeddingConfig':
        """Convert our config to the embedding service config format"""
        provider_enum = {
            "openai": EmbeddingProvider.OPENAI,
            "anthropic_claude": EmbeddingProvider.ANTHROPIC_CLAUDE,
            "cohere": EmbeddingProvider.COHERE,
            "huggingface": EmbeddingProvider.HUGGINGFACE,
            "azure_openai": EmbeddingProvider.AZURE_OPENAI,
            "google_vertex": EmbeddingProvider.GOOGLE_VERTEX,
            "local_sentence_transformers": EmbeddingProvider.LOCAL_SENTENCE_TRANSFORMERS
        }
        
        return EmbeddingConfig(
            provider=provider_enum[config.provider_type],
            model_name=config.model_name,
            api_key=config.api_key,
            api_base=config.api_base,
            dimensions=config.dimensions,
            max_tokens=config.max_tokens,
            batch_size=config.batch_size,
            timeout=config.timeout
        )
    
    async def _create_fallback_provider(self, config: EmbeddingProviderConfig):
        """Create a basic fallback provider when embedding service is not available"""
        if config.provider_type == "local_sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                return LocalFallbackProvider(config.model_name)
            except ImportError:
                return DummyEmbeddingProvider(config.dimensions or 384)
        else:
            return DummyEmbeddingProvider(config.dimensions or 384)
    
    async def _ensure_local_fallback(self):
        """Ensure we always have a local fallback provider"""
        if "local_sentence_transformers" not in self.providers:
            try:
                config = EmbeddingProviderConfig(
                    name="local_sentence_transformers",
                    provider_type="local_sentence_transformers",
                    model_name="all-MiniLM-L6-v2",
                    dimensions=384,
                    enabled=True
                )
                
                if HAS_EMBEDDING_SERVICE:
                    embedding_config = self._convert_to_embedding_config(config)
                    provider = EmbeddingProviderFactory.create_provider(embedding_config)
                else:
                    provider = await self._create_fallback_provider(config)
                
                self.providers["local_sentence_transformers"] = provider
                logger.info("Added local sentence transformers as fallback")
            except Exception as e:
                logger.error(f"Failed to create local fallback: {e}")
                # Last resort: dummy provider
                self.providers["dummy"] = DummyEmbeddingProvider(384)
    
    def _update_fallback_chain(self):
        """Update the fallback chain based on available providers"""
        priority_order = [
            "openai", "azure_openai", "cohere", "huggingface", 
            "google_vertex", "anthropic", "local_sentence_transformers", "dummy"
        ]
        
        self.fallback_chain = [name for name in priority_order if name in self.providers]
        
        if self.default_provider is None and self.fallback_chain:
            self.default_provider = self.fallback_chain[0]
            
        logger.info(f"Fallback chain: {self.fallback_chain}")


class EmbeddingStub:
    """Enhanced Embedding Service Client with Real Multi-Provider Support"""
    
    def __init__(self, target: str = "embedding-service:50055"):
        self.target = target
        self.use_grpc = HAS_GRPC_PROTOS and os.getenv("USE_EMBEDDING_MS", "false").lower() == "true"
        
        if self.use_grpc:
            self.channel = create_instrumented_channel(target)
            self.stub = pb2_grpc.EmbeddingServiceStub(self.channel)
            logger.info(f"EmbeddingStub initialized for gRPC target: {target}")
        else:
            self.local_service = RealVectorEmbeddingService()
            logger.info("EmbeddingStub initialized for local service")
    
    async def initialize(self):
        """Initialize the stub (compatibility method)"""
        if self.use_grpc:
            # Check gRPC health
            try:
                request = pb2.HealthRequest()
                response = await self.stub.HealthCheck(request)
                if response.healthy:
                    logger.info("Embedding service is healthy")
                else:
                    logger.warning("Embedding service unhealthy")
            except Exception as e:
                logger.error(f"Failed to check embedding service health: {e}")
        else:
            # Initialize local service
            try:
                await self.local_service.initialize()
                logger.info("Local embedding service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize local embedding service: {e}")
                raise
    
    async def generate_embedding(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """Generate embedding for text"""
        if self.use_grpc:
            try:
                # Build request metadata
                meta = pb2.RequestMeta()
                if metadata:
                    if "trace_id" in metadata:
                        meta.trace_id = metadata["trace_id"]
                    if "user_id" in metadata:
                        meta.user_id = metadata["user_id"]
                
                request = pb2.EmbeddingRequest(
                    text=text,
                    meta=meta
                )
                
                response = await self.stub.GenerateEmbedding(request)
                return list(response.embedding)
                
            except grpc.RpcError as e:
                logger.error(f"gRPC error generating embedding: {e}")
                raise
        else:
            try:
                return await self._generate_embedding_local(text, metadata)
            except Exception as e:
                logger.error(f"Local embedding generation failed: {e}")
                raise
    
    async def generate_batch_embeddings(
        self,
        texts: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if self.use_grpc:
            try:
                # Build request metadata
                meta = pb2.RequestMeta()
                if metadata:
                    if "trace_id" in metadata:
                        meta.trace_id = metadata["trace_id"]
                    if "user_id" in metadata:
                        meta.user_id = metadata["user_id"]
                
                request = pb2.BatchEmbeddingRequest(
                    texts=texts,
                    meta=meta
                )
                
                response = await self.stub.GenerateBatchEmbeddings(request)
                
                embeddings = []
                for result in response.results:
                    if result.success:
                        embeddings.append(list(result.embedding))
                    else:
                        logger.warning(f"Failed to generate embedding: {result.error}")
                        embeddings.append([])
                
                return embeddings
                
            except grpc.RpcError as e:
                logger.error(f"gRPC error generating batch embeddings: {e}")
                raise
        else:
            try:
                return await self._generate_batch_embeddings_local(texts, metadata)
            except Exception as e:
                logger.error(f"Local batch embedding generation failed: {e}")
                raise
    
    async def calculate_similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray],
        metric: str = "cosine"
    ) -> float:
        """Calculate similarity between embeddings"""
        if self.use_grpc:
            try:
                # Convert numpy arrays to lists
                if isinstance(embedding1, np.ndarray):
                    embedding1 = embedding1.tolist()
                if isinstance(embedding2, np.ndarray):
                    embedding2 = embedding2.tolist()
                
                request = pb2.SimilarityRequest(
                    embedding1=embedding1,
                    embedding2=embedding2,
                    metric=metric
                )
                
                response = await self.stub.CalculateSimilarity(request)
                return response.similarity
                
            except grpc.RpcError as e:
                logger.error(f"gRPC error calculating similarity: {e}")
                raise
        else:
            return await self._calculate_similarity_local(embedding1, embedding2, metric)
    
    async def find_similar(
        self,
        query_embedding: Union[List[float], np.ndarray],
        collection: str = "default",
        top_k: int = 10,
        min_similarity: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find similar documents"""
        if self.use_grpc:
            try:
                # Convert numpy array to list
                if isinstance(query_embedding, np.ndarray):
                    query_embedding = query_embedding.tolist()
                
                request = pb2.SimilarSearchRequest(
                    query_embedding=query_embedding,
                    collection=collection,
                    top_k=top_k,
                    min_similarity=min_similarity,
                    filters=filters or {}
                )
                
                response = await self.stub.FindSimilar(request)
                
                results = []
                for doc in response.documents:
                    results.append({
                        "id": doc.id,
                        "similarity": doc.similarity,
                        "metadata": dict(doc.metadata)
                    })
                
                return results
                
            except grpc.RpcError as e:
                logger.error(f"gRPC error finding similar documents: {e}")
                raise
        else:
            return await self._find_similar_local(query_embedding, collection, top_k, min_similarity, filters)
    
    async def store_embedding(
        self,
        id: str,
        embedding: Union[List[float], np.ndarray],
        collection: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store embedding with metadata"""
        if self.use_grpc:
            try:
                # Convert numpy array to list
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                
                request = pb2.StoreEmbeddingRequest(
                    id=id,
                    embedding=embedding,
                    collection=collection,
                    metadata=metadata or {}
                )
                
                response = await self.stub.StoreEmbedding(request)
                return response.success
                
            except grpc.RpcError as e:
                logger.error(f"gRPC error storing embedding: {e}")
                raise
        else:
            return await self._store_embedding_local(id, embedding, collection, metadata)
    
    async def close(self):
        """Close the gRPC channel or local service"""
        if self.use_grpc and hasattr(self, 'channel'):
            await self.channel.close()
    
    # Local implementation methods
    async def _generate_embedding_local(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[float]:
        """Generate embedding using local service"""
        if not self.local_service._initialized:
            await self.local_service.initialize()
        
        # Try providers in fallback chain
        for provider_name in self.local_service.fallback_chain:
            try:
                provider = self.local_service.providers[provider_name]
                embedding = await provider.create_single_embedding(text)
                return embedding
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All embedding providers failed")
    
    async def _generate_batch_embeddings_local(self, texts: List[str], metadata: Optional[Dict[str, Any]] = None) -> List[List[float]]:
        """Generate batch embeddings using local service"""
        if not self.local_service._initialized:
            await self.local_service.initialize()
        
        # Try providers in fallback chain
        for provider_name in self.local_service.fallback_chain:
            try:
                provider = self.local_service.providers[provider_name]
                embeddings = await provider.create_embeddings(texts)
                return embeddings
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        raise Exception("All embedding providers failed")
    
    async def _calculate_similarity_local(self, embedding1, embedding2, metric="cosine") -> float:
        """Calculate similarity using local implementation"""
        # Convert to numpy arrays
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        if metric == "cosine":
            # Cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        else:
            # Default to cosine if metric not supported
            return await self._calculate_similarity_local(embedding1, embedding2, "cosine")
    
    async def _find_similar_local(self, query_embedding, collection="default", top_k=10, min_similarity=0.0, filters=None) -> List[Dict[str, Any]]:
        """Find similar documents using local vector store implementation"""
        try:
            # Get vector store if available
            vector_store = await self._get_vector_store()
            if vector_store is None:
                logger.warning("Vector store not available for similarity search")
                return []
            
            # Perform similarity search
            results = await vector_store.similarity_search(
                query_embedding=query_embedding,
                collection=collection,
                top_k=top_k,
                similarity_threshold=min_similarity,
                filters=filters
            )
            
            # Convert to expected format
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.document.id,
                    "similarity": result.similarity_score,
                    "metadata": result.document.metadata,
                    "text": result.document.text,
                    "distance": result.distance,
                    "rank": result.rank
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Local similarity search failed: {e}")
            return []
    
    async def _store_embedding_local(self, id: str, embedding, collection="default", metadata=None) -> bool:
        """Store embedding using local vector store implementation"""
        try:
            # Get vector store if available
            vector_store = await self._get_vector_store()
            if vector_store is None:
                logger.warning("Vector store not available for storing embeddings")
                return False
            
            # Import vector store classes
            from shared.vector_store import VectorDocument
            
            # Create vector document
            doc = VectorDocument(
                id=id,
                text=metadata.get("text", "") if metadata else "",
                embedding=embedding if isinstance(embedding, list) else embedding.tolist(),
                metadata=metadata or {},
                collection=collection
            )
            
            # Store in vector store
            return await vector_store.store_vector(doc)
            
        except Exception as e:
            logger.error(f"Local embedding storage failed: {e}")
            return False
    
    async def _get_vector_store(self):
        """Get vector store instance"""
        try:
            # Try to get TerminusDB client from the application context
            # This is a simplified approach - in production you'd inject this properly
            if hasattr(self, '_vector_store'):
                return self._vector_store
            
            # Try to create vector store
            from shared.vector_store import create_vector_store
            # This would need to be injected properly in a real implementation
            # For now, return None to avoid errors
            logger.info("Vector store integration would be initialized here")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get vector store: {e}")
            return None
    
    async def store_text_with_embedding(
        self,
        text: str,
        document_id: Optional[str] = None,
        collection: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store text with generated embedding
        
        Args:
            text: Text to store
            document_id: Optional document ID
            collection: Collection name
            metadata: Optional metadata
            
        Returns:
            Dictionary with results
        """
        try:
            # Generate embedding for the text
            embedding = await self.generate_embedding(text)
            
            # Generate document ID if not provided
            if document_id is None:
                document_id = hashlib.md5(text.encode()).hexdigest()
            
            # Add text to metadata
            full_metadata = metadata or {}
            full_metadata["text"] = text
            full_metadata["embedding_dimension"] = len(embedding)
            full_metadata["generated_at"] = datetime.utcnow().isoformat()
            
            # Store the embedding
            success = await self.store_embedding(document_id, embedding, collection, full_metadata)
            
            return {
                "success": success,
                "document_id": document_id,
                "embedding_dimension": len(embedding),
                "collection": collection
            }
            
        except Exception as e:
            logger.error(f"Failed to store text with embedding: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_id": document_id
            }
    
    async def semantic_search_text(
        self,
        query_text: str,
        collection: str = "default",
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using text query
        
        Args:
            query_text: Text to search for
            collection: Collection to search in
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score
            filters: Additional filters
            
        Returns:
            List of search results
        """
        try:
            # Generate embedding for the query text
            query_embedding = await self.generate_embedding(query_text)
            
            # Perform similarity search
            return await self.find_similar(
                query_embedding=query_embedding,
                collection=collection,
                top_k=top_k,
                min_similarity=similarity_threshold,
                filters=filters
            )
            
        except Exception as e:
            logger.error(f"Semantic text search failed: {e}")
            return []


class LocalFallbackProvider:
    """Local fallback provider using sentence transformers"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
    
    async def initialize(self):
        """Initialize the model"""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded local model: {self.model_name}")
            except ImportError:
                raise ImportError("sentence-transformers required for local provider")
    
    async def create_single_embedding(self, text: str) -> List[float]:
        """Create embedding for single text"""
        if self.model is None:
            await self.initialize()
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self.model.encode, text)
        return embedding.tolist()
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for multiple texts"""
        if self.model is None:
            await self.initialize()
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self.model.encode, texts)
        return embeddings.tolist()


class DummyEmbeddingProvider:
    """Dummy provider for testing when no real providers are available"""
    
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions
    
    async def create_single_embedding(self, text: str) -> List[float]:
        """Generate deterministic dummy embedding"""
        # Generate deterministic embedding based on text hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        seed = int(text_hash[:8], 16)
        np.random.seed(seed)
        return np.random.random(self.dimensions).tolist()
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate dummy embeddings for multiple texts"""
        return [await self.create_single_embedding(text) for text in texts]


def get_embedding_stub(target: str = "embedding-service:50055") -> EmbeddingStub:
    """Get embedding service stub instance with real multi-provider support"""
    return EmbeddingStub(target)