"""
Production Embedding Service Client - NO FALLBACKS
All embedding providers must be available in production
"""
import logging
import os
from typing import Any, Dict, List, Optional, Union

import cohere
import numpy as np
import openai

# Production imports - all must be available
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Use microservice in production
USE_EMBEDDING_MS = os.getenv("USE_EMBEDDING_MS", "true").lower() == "true"


class ProductionEmbeddingService:
 """Production embedding service with multi-provider support."""

 def __init__(self):
 self.providers = {}
 self.default_provider = None
 self._setup_providers()

 def _setup_providers(self):
 """Setup all available embedding providers"""

 # Setup sentence transformers provider (always available)
 self.providers["sentence_transformers"] = {
 "client": SentenceTransformer("all-MiniLM-L6-v2"),
 "model": "all-MiniLM-L6-v2",
 "type": "local",
 }
 if self.default_provider is None:
 self.default_provider = "sentence_transformers"
 logger.info("Sentence transformers provider initialized")

 # Setup OpenAI if API key available
 if os.getenv("OPENAI_API_KEY"):
 self.providers["openai"] = {
 "client": openai.AsyncOpenAI(api_key = os.getenv("OPENAI_API_KEY")),
 "model": "text-embedding-3-large",
 "type": "openai",
 }
 if self.default_provider is None:
 self.default_provider = "openai"
 logger.info("OpenAI embedding provider initialized")

 # Setup Cohere if API key available
 if os.getenv("COHERE_API_KEY"):
 self.providers["cohere"] = {
 "client": cohere.AsyncClient(api_key = os.getenv("COHERE_API_KEY")),
 "model": "embed-english-v3.0",
 "type": "cohere",
 }
 logger.info("Cohere embedding provider initialized")

 if not self.providers:
 raise RuntimeError("No embedding providers available - check configuration")

 logger.info(
 f"Production embedding service initialized with providers: {list(self.providers.keys())}"
 )

 async def embed_text(self, text: str, provider: str = None) -> List[float]:
 """Get embeddings for text"""
 provider_name = provider or self.default_provider

 if provider_name not in self.providers:
 raise ValueError(f"Provider {provider_name} not available")

 provider_info = self.providers[provider_name]

 if provider_info["type"] == "local":
 # Sentence transformers
 embedding = provider_info["client"].encode(text, convert_to_numpy = True)
 return embedding.tolist()

 elif provider_info["type"] == "openai":
 # OpenAI
 response = await provider_info["client"].embeddings.create(
 model = provider_info["model"], input = text
 )
 return response.data[0].embedding

 elif provider_info["type"] == "cohere":
 # Cohere
 response = await provider_info["client"].embed(
 texts = [text], model = provider_info["model"], input_type = "search_document"
 )
 return response.embeddings[0]

 else:
 raise ValueError(f"Unknown provider type: {provider_info['type']}")

 async def embed_batch(
 self, texts: List[str], provider: str = None
 ) -> List[List[float]]:
 """Get embeddings for multiple texts"""
 provider_name = provider or self.default_provider

 if provider_name not in self.providers:
 raise ValueError(f"Provider {provider_name} not available")

 provider_info = self.providers[provider_name]

 if provider_info["type"] == "local":
 # Sentence transformers
 embeddings = provider_info["client"].encode(texts, convert_to_numpy = True)
 return embeddings.tolist()

 elif provider_info["type"] == "openai":
 # OpenAI
 response = await provider_info["client"].embeddings.create(
 model = provider_info["model"], input = texts
 )
 return [data.embedding for data in response.data]

 elif provider_info["type"] == "cohere":
 # Cohere
 response = await provider_info["client"].embed(
 texts = texts, model = provider_info["model"], input_type = "search_document"
 )
 return response.embeddings

 else:
 raise ValueError(f"Unknown provider type: {provider_info['type']}")

 def get_available_providers(self) -> List[str]:
 """Get list of available providers"""
 return list(self.providers.keys())


# Global service instance
_embedding_service: Optional[ProductionEmbeddingService] = None


def get_embedding_service() -> ProductionEmbeddingService:
 """Get global embedding service instance"""
 global _embedding_service

 if _embedding_service is None:
 _embedding_service = ProductionEmbeddingService()

 return _embedding_service


async def embed_text(text: str, provider: str = None) -> List[float]:
 """Convenience function to embed single text"""
 service = get_embedding_service()
 return await service.embed_text(text, provider)


async def embed_batch(texts: List[str], provider: str = None) -> List[List[float]]:
 """Convenience function to embed multiple texts"""
 service = get_embedding_service()
 return await service.embed_batch(texts, provider)
