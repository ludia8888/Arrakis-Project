"""
Embedding Service Client - Supports both local and remote modes
"""
import os
import logging
from typing import List, Dict, Any, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)

# Check if we should use the microservice
USE_EMBEDDING_MS = os.getenv("USE_EMBEDDING_MS", "false").lower() == "true"


class EnhancedLocalEmbeddingService:
    """Enhanced local embedding service with multi-provider support."""
    
    def __init__(self):
        self.providers = {}
        self.default_provider = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the local embedding providers."""
        if self._initialized:
            return
            
        # Try to initialize providers based on available API keys
        await self._setup_providers()
        self._initialized = True
        logger.info(f"Local embedding service initialized with providers: {list(self.providers.keys())}")
    
    async def _setup_providers(self):
        """Setup available embedding providers"""
        # Always try to setup local sentence transformers
        try:
            from sentence_transformers import SentenceTransformer
            self.providers["local"] = {
                "model": SentenceTransformer('all-MiniLM-L6-v2'),
                "type": "local"
            }
            if self.default_provider is None:
                self.default_provider = "local"
            logger.info("Local sentence transformers provider initialized")
        except ImportError:
            logger.warning("sentence-transformers not available")
        
        # Setup OpenAI if API key available
        if os.getenv("OPENAI_API_KEY"):
            try:
                import openai
                self.providers["openai"] = {
                    "client": openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")),
                    "model": "text-embedding-3-large",
                    "type": "openai"
                }
                if self.default_provider is None:
                    self.default_provider = "openai"
                logger.info("OpenAI embedding provider initialized")
            except ImportError:
                logger.warning("openai package not available")
        
        # Setup Cohere if API key available
        if os.getenv("COHERE_API_KEY"):
            try:
                import cohere
                self.providers["cohere"] = {
                    "client": cohere.AsyncClient(api_key=os.getenv("COHERE_API_KEY")),
                    "model": "embed-english-v3.0",
                    "type": "cohere"
                }
                if self.default_provider is None:
                    self.default_provider = "cohere"
                logger.info("Cohere embedding provider initialized")
            except ImportError:
                logger.warning("cohere package not available")
        
        # Fallback to dummy if no providers available
        if not self.providers:
            logger.warning("No embedding providers available, using dummy provider")
            self.providers["dummy"] = {"type": "dummy"}
            self.default_provider = "dummy"
    
    async def generate_embedding(self, text: str, metadata=None, provider=None):
        """Generate embedding for text using specified or default provider."""
        provider_name = provider or self.default_provider
        
        if provider_name not in self.providers:
            raise ValueError(f"Provider {provider_name} not available")
        
        provider_info = self.providers[provider_name]
        
        try:
            if provider_info["type"] == "local":
                embedding = provider_info["model"].encode(text)
                return embedding.tolist()
            elif provider_info["type"] == "openai":
                response = await provider_info["client"].embeddings.create(
                    input=text,
                    model=provider_info["model"]
                )
                return response.data[0].embedding
            elif provider_info["type"] == "cohere":
                response = await provider_info["client"].embed(
                    texts=[text],
                    model=provider_info["model"],
                    input_type="search_document"
                )
                return response.embeddings[0]
            elif provider_info["type"] == "dummy":
                return await self._generate_dummy_embedding(text)
        except Exception as e:
            logger.error(f"Failed to generate embedding with {provider_name}: {e}")
            # Try fallback providers
            return await self._generate_with_fallback(text, exclude=provider_name)
    
    async def _generate_with_fallback(self, text: str, exclude: str = None):
        """Generate embedding with fallback providers"""
        fallback_order = ["openai", "cohere", "local", "dummy"]
        
        for provider_name in fallback_order:
            if provider_name == exclude or provider_name not in self.providers:
                continue
            try:
                return await self.generate_embedding(text, provider=provider_name)
            except Exception as e:
                logger.warning(f"Fallback provider {provider_name} failed: {e}")
        
        raise Exception("All embedding providers failed")
    
    async def _generate_dummy_embedding(self, text: str):
        """Generate deterministic dummy embedding."""
        import hashlib
        import numpy as np
        
        hash_obj = hashlib.md5(text.encode())
        seed = int(hash_obj.hexdigest()[:8], 16)
        np.random.seed(seed)
        return np.random.random(384).tolist()
    
    async def generate_batch_embeddings(self, texts: List[str], metadata=None, provider=None):
        """Generate embeddings for multiple texts."""
        provider_name = provider or self.default_provider
        
        if provider_name not in self.providers:
            raise ValueError(f"Provider {provider_name} not available")
        
        provider_info = self.providers[provider_name]
        
        try:
            if provider_info["type"] == "local":
                embeddings = provider_info["model"].encode(texts)
                return embeddings.tolist()
            elif provider_info["type"] == "openai":
                response = await provider_info["client"].embeddings.create(
                    input=texts,
                    model=provider_info["model"]
                )
                return [embedding.embedding for embedding in response.data]
            elif provider_info["type"] == "cohere":
                response = await provider_info["client"].embed(
                    texts=texts,
                    model=provider_info["model"],
                    input_type="search_document"
                )
                return response.embeddings
            elif provider_info["type"] == "dummy":
                return [await self._generate_dummy_embedding(text) for text in texts]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings with {provider_name}: {e}")
            # Fallback to individual embeddings
            return [await self.generate_embedding(text) for text in texts]
    
    async def calculate_similarity(self, embedding1, embedding2, metric="cosine"):
        """Calculate similarity between embeddings."""
        import numpy as np
        
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        if metric == "cosine":
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        else:
            return 0.0
    
    async def find_similar(self, query_embedding, collection="default", top_k=10, 
                          min_similarity=0.0, filters=None):
        """Find similar documents (enhanced implementation)."""
        # This would integrate with your vector database
        # For now, return empty list as placeholder
        logger.info(f"Similarity search in collection '{collection}' (placeholder)")
        return []
    
    async def get_provider_stats(self):
        """Get statistics about available providers"""
        return {
            "available_providers": list(self.providers.keys()),
            "default_provider": self.default_provider,
            "provider_details": {
                name: {"type": info["type"], "model": info.get("model", "N/A")}
                for name, info in self.providers.items()
            }
        }


class EmbeddingClient:
    """
    Unified client for embedding operations.
    Automatically uses local or remote service based on configuration.
    """
    
    def __init__(self, endpoint: Optional[str] = None):
        self.use_microservice = USE_EMBEDDING_MS
        self.endpoint = endpoint or os.getenv("EMBEDDING_SERVICE_ENDPOINT", "embedding-service:50055")
        self._client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the appropriate client"""
        if self._initialized:
            return
        
        if self.use_microservice:
            logger.info("Using remote embedding microservice")
            from shared.embedding_stub import EmbeddingStub
            self._client = EmbeddingStub(self.endpoint)
            await self._client.initialize()
        else:
            logger.info("Using enhanced local embedding service")
            # Use enhanced local service with multi-provider support
            self._client = EnhancedLocalEmbeddingService()
            await self._client.initialize()
        
        self._initialized = True
    
    async def generate_embedding(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Union[List[float], np.ndarray]:
        """Generate embedding for text"""
        if not self._initialized:
            await self.initialize()
        
        if self.use_microservice:
            return await self._client.generate_embedding(text, metadata)
        else:
            return await self._client.generate_embedding(text, metadata)
    
    async def generate_batch_embeddings(
        self,
        texts: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Union[List[float], np.ndarray]]:
        """Generate embeddings for multiple texts"""
        if not self._initialized:
            await self.initialize()
        
        if self.use_microservice:
            return await self._client.generate_batch_embeddings(texts, metadata)
        else:
            return await self._client.generate_batch_embeddings(texts, metadata)
    
    async def calculate_similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray],
        metric: str = "cosine"
    ) -> float:
        """Calculate similarity between embeddings"""
        if not self._initialized:
            await self.initialize()
        
        return await self._client.calculate_similarity(embedding1, embedding2, metric)
    
    async def find_similar(
        self,
        query_embedding: Union[List[float], np.ndarray],
        collection: str = "default",
        top_k: int = 10,
        min_similarity: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find similar documents"""
        if not self._initialized:
            await self.initialize()
        
        return await self._client.find_similar(
            query_embedding, collection, top_k, min_similarity, filters
        )
    
    async def store_embedding(
        self,
        id: str,
        embedding: Union[List[float], np.ndarray],
        collection: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store embedding with metadata"""
        if not self._initialized:
            await self.initialize()
        
        if self.use_microservice:
            return await self._client.store_embedding(id, embedding, collection, metadata)
        else:
            # Local service might not have store method
            logger.warning("Store embedding not implemented in local service")
            return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        if not self._initialized:
            await self.initialize()
        
        if hasattr(self._client, 'get_stats'):
            return await self._client.get_stats()
        elif hasattr(self._client, 'get_provider_stats'):
            return await self._client.get_provider_stats()
        else:
            return {"status": "unknown"}
    
    async def get_available_providers(self) -> List[str]:
        """Get list of available embedding providers"""
        if not self._initialized:
            await self.initialize()
        
        if hasattr(self._client, 'get_provider_stats'):
            stats = await self._client.get_provider_stats()
            return stats.get("available_providers", [])
        else:
            return ["default"]
    
    async def generate_embedding_with_provider(
        self,
        text: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Union[List[float], np.ndarray]:
        """Generate embedding using a specific provider"""
        if not self._initialized:
            await self.initialize()
        
        if hasattr(self._client, 'generate_embedding') and hasattr(self._client, 'providers'):
            # Enhanced local service
            return await self._client.generate_embedding(text, metadata, provider)
        else:
            # Fall back to regular generation
            return await self.generate_embedding(text, metadata)
    
    async def close(self):
        """Close the client"""
        if self._client and hasattr(self._client, 'close'):
            await self._client.close()
        self._initialized = False


# Global singleton instance
_embedding_client: Optional[EmbeddingClient] = None


async def get_embedding_client() -> EmbeddingClient:
    """Get or create the singleton embedding client"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
        await _embedding_client.initialize()
    return _embedding_client