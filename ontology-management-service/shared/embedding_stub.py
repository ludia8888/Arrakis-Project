"""
Production Vector Embeddings Implementation with Multi-Provider Support
Integrates with the embedding-service microservice for production use
NO FALLBACKS - All dependencies must be available in production
"""
import asyncio
import hashlib
import json
import logging
import os

# Production imports - all dependencies must be available
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import grpc
import numpy as np

# Add embedding-service to path for imports
embedding_service_path = os.path.join(
 os.path.dirname(__file__), "../../embedding-service/app"
)
if embedding_service_path not in sys.path:
 sys.path.append(embedding_service_path)

import cohere
import openai
from embeddings.providers import (
 BaseEmbeddingProvider,
 EmbeddingAPIError,
 EmbeddingBatchSizeError,
 EmbeddingConfig,
 EmbeddingProvider,
 EmbeddingProviderError,
 EmbeddingProviderFactory,
 EmbeddingTokenLimitError,
)
from embeddings.service import VectorEmbeddingService

# Production ML dependencies - must be available
from sentence_transformers import SentenceTransformer

# Production gRPC proto imports - must be available
from services.embedding_service.proto import embedding_service_pb2 as pb2
from services.embedding_service.proto import embedding_service_pb2_grpc as pb2_grpc
from shared.grpc_interceptors import create_instrumented_channel

logger = logging.getLogger(__name__)


class EmbeddingProviderType(Enum):
 """Supported embedding provider types"""

 OPENAI = "openai"
 COHERE = "cohere"
 SENTENCE_TRANSFORMERS = "sentence_transformers"
 HUGGINGFACE = "huggingface"
 AZURE_OPENAI = "azure_openai"


@dataclass
class EmbeddingProviderConfig:
 """Configuration for embedding providers"""

 name: str
 provider_type: str
 model_name: str
 dimensions: int
 api_key: Optional[str] = None
 api_url: Optional[str] = None
 enabled: bool = True
 max_tokens: Optional[int] = None
 batch_size: int = 100
 timeout_seconds: int = 30
 rate_limit_rpm: Optional[int] = None
 metadata: Dict[str, Any] = None

 def __post_init__(self):
 if self.metadata is None:
 self.metadata = {}


class EmbeddingService:
 """Production embedding service with multi-provider support"""

 def __init__(self, use_microservice: bool = True):
 self.use_microservice = use_microservice
 self.providers: Dict[str, EmbeddingProvider] = {}
 self.default_provider: Optional[str] = None
 self.provider_chain: List[str] = []

 # Production-only configuration
 if not self.use_microservice:
 # Initialize local providers for production
 self._initialize_local_providers()

 self.grpc_service = None
 if self.use_microservice:
 self.grpc_service = EmbeddingMicroserviceClient()

 async def initialize(self):
 """Initialize the embedding service"""
 logger.info("Initializing production embedding service")

 if self.use_microservice:
 await self.grpc_service.initialize()
 else:
 await self._initialize_local_service()

 self._setup_provider_chain()
 logger.info(
 f"Embedding service initialized with providers: {list(self.providers.keys())}"
 )

 def _initialize_local_providers(self):
 """Initialize local embedding providers for production"""
 # OpenAI provider
 openai_config = EmbeddingProviderConfig(
 name = "openai",
 provider_type = "openai",
 model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
 dimensions = 1536,
 api_key = os.getenv("OPENAI_API_KEY"),
 enabled = bool(os.getenv("OPENAI_API_KEY")),
 )

 # Cohere provider
 cohere_config = EmbeddingProviderConfig(
 name = "cohere",
 provider_type = "cohere",
 model_name = os.getenv("COHERE_EMBEDDING_MODEL", "embed-english-v3.0"),
 dimensions = 1024,
 api_key = os.getenv("COHERE_API_KEY"),
 enabled = bool(os.getenv("COHERE_API_KEY")),
 )

 # Sentence Transformers provider (always available)
 sentence_transformers_config = EmbeddingProviderConfig(
 name = "sentence_transformers",
 provider_type = "sentence_transformers",
 model_name = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2"),
 dimensions = 384,
 enabled = True,
 )

 configs = [openai_config, cohere_config, sentence_transformers_config]

 for config in configs:
 if config.enabled:
 provider = self._create_provider(config)
 self.providers[config.name] = provider

 if self.default_provider is None:
 self.default_provider = config.name

 def _create_provider(self, config: EmbeddingProviderConfig) -> EmbeddingProvider:
 """Create a production embedding provider"""
 factory = EmbeddingProviderFactory()

 # Map config to embedding config format
 embedding_config = EmbeddingConfig(
 provider_type = config.provider_type,
 model_name = config.model_name,
 api_key = config.api_key,
 api_url = config.api_url,
 dimensions = config.dimensions,
 max_tokens = config.max_tokens,
 batch_size = config.batch_size,
 timeout_seconds = config.timeout_seconds,
 rate_limit_rpm = config.rate_limit_rpm,
 metadata = config.metadata,
 )

 return factory.create_provider(embedding_config)

 async def _initialize_local_service(self):
 """Initialize local embedding service"""
 if not self.providers:
 raise RuntimeError("No embedding providers available - check configuration")

 # Initialize each provider
 for name, provider in self.providers.items():
 await provider.initialize()
 logger.info(f"Initialized provider: {name}")

 def _setup_provider_chain(self):
 """Setup provider priority chain for production"""
 # Priority order for providers
 priority_order = ["openai", "cohere", "sentence_transformers"]
 self.provider_chain = [
 name for name in priority_order if name in self.providers
 ]

 if not self.provider_chain:
 raise RuntimeError("No enabled providers found - cannot operate")

 if self.default_provider is None:
 self.default_provider = self.provider_chain[0]

 logger.info(f"Provider chain: {self.provider_chain}")


class EmbeddingMicroserviceClient:
 """Production gRPC client for embedding microservice"""

 def __init__(self):
 self.channel = None
 self.stub = None
 self.service_url = os.getenv("EMBEDDING_SERVICE_URL", "embedding-service:50051")

 async def initialize(self):
 """Initialize gRPC connection"""
 self.channel = create_instrumented_channel(self.service_url)
 self.stub = pb2_grpc.EmbeddingServiceStub(self.channel)

 # Health check
 await self._health_check()
 logger.info(f"Connected to embedding microservice at {self.service_url}")

 async def _health_check(self):
 """Perform health check on the microservice"""
 request = pb2.HealthCheckRequest()
 response = await self.stub.HealthCheck(request)

 if response.status != pb2.HealthCheckResponse.SERVING:
 raise RuntimeError(f"Embedding service not healthy: {response.status}")

 async def embed_text(self, text: str, provider: str = None) -> List[float]:
 """Get embeddings for text"""
 request = pb2.EmbedTextRequest(text = text, provider = provider or "default")

 response = await self.stub.EmbedText(request)

 if response.error:
 raise EmbeddingAPIError(f"Microservice error: {response.error}")

 return list(response.embedding)

 async def embed_batch(
 self, texts: List[str], provider: str = None
 ) -> List[List[float]]:
 """Get embeddings for multiple texts"""
 request = pb2.EmbedBatchRequest(texts = texts, provider = provider or "default")

 response = await self.stub.EmbedBatch(request)

 if response.error:
 raise EmbeddingAPIError(f"Microservice error: {response.error}")

 return [list(embedding) for embedding in response.embeddings]

 async def get_providers(self) -> List[Dict[str, Any]]:
 """Get available providers from microservice"""
 request = pb2.GetProvidersRequest()
 response = await self.stub.GetProviders(request)

 providers = []
 for provider in response.providers:
 providers.append(
 {
 "name": provider.name,
 "type": provider.type,
 "model": provider.model,
 "dimensions": provider.dimensions,
 "enabled": provider.enabled,
 }
 )

 return providers

 async def close(self):
 """Close gRPC connection"""
 if self.channel:
 await self.channel.close()


class LocalEmbeddingProvider(BaseEmbeddingProvider):
 """Production local embedding provider using sentence transformers"""

 def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
 self.model_name = model_name
 self.model = None
 self.dimensions = None

 async def initialize(self):
 """Initialize the model"""
 self.model = SentenceTransformer(self.model_name)
 self.dimensions = self.model.get_sentence_embedding_dimension()
 logger.info(
 f"Loaded local model: {self.model_name} (dimensions: {self.dimensions})"
 )

 async def embed_text(self, text: str) -> List[float]:
 """Get embedding for single text"""
 if not self.model:
 await self.initialize()

 embedding = self.model.encode(text, convert_to_numpy = True)
 return embedding.tolist()

 async def embed_batch(self, texts: List[str]) -> List[List[float]]:
 """Get embeddings for multiple texts"""
 if not self.model:
 await self.initialize()

 embeddings = self.model.encode(texts, convert_to_numpy = True)
 return embeddings.tolist()

 def get_dimensions(self) -> int:
 """Get embedding dimensions"""
 return self.dimensions or 384


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
 """Production OpenAI embedding provider"""

 def __init__(self, api_key: str, model_name: str = "text-embedding-ada-002"):
 self.api_key = api_key
 self.model_name = model_name
 self.client = None
 self.dimensions = 1536 # Ada-002 dimensions

 async def initialize(self):
 """Initialize OpenAI client"""
 self.client = openai.AsyncOpenAI(api_key = self.api_key)
 logger.info(f"Initialized OpenAI embedding provider: {self.model_name}")

 async def embed_text(self, text: str) -> List[float]:
 """Get embedding for single text"""
 if not self.client:
 await self.initialize()

 response = await self.client.embeddings.create(
 model = self.model_name, input = text
 )

 return response.data[0].embedding

 async def embed_batch(self, texts: List[str]) -> List[List[float]]:
 """Get embeddings for multiple texts"""
 if not self.client:
 await self.initialize()

 response = await self.client.embeddings.create(
 model = self.model_name, input = texts
 )

 return [data.embedding for data in response.data]

 def get_dimensions(self) -> int:
 """Get embedding dimensions"""
 return self.dimensions


class CohereEmbeddingProvider(BaseEmbeddingProvider):
 """Production Cohere embedding provider"""

 def __init__(self, api_key: str, model_name: str = "embed-english-v3.0"):
 self.api_key = api_key
 self.model_name = model_name
 self.client = None
 self.dimensions = 1024 # Cohere v3 dimensions

 async def initialize(self):
 """Initialize Cohere client"""
 self.client = cohere.AsyncClient(api_key = self.api_key)
 logger.info(f"Initialized Cohere embedding provider: {self.model_name}")

 async def embed_text(self, text: str) -> List[float]:
 """Get embedding for single text"""
 if not self.client:
 await self.initialize()

 response = await self.client.embed(
 texts = [text], model = self.model_name, input_type = "search_document"
 )

 return response.embeddings[0]

 async def embed_batch(self, texts: List[str]) -> List[List[float]]:
 """Get embeddings for multiple texts"""
 if not self.client:
 await self.initialize()

 response = await self.client.embed(
 texts = texts, model = self.model_name, input_type = "search_document"
 )

 return response.embeddings

 def get_dimensions(self) -> int:
 """Get embedding dimensions"""
 return self.dimensions


# Factory functions for creating embedding service
def create_embedding_service(use_microservice: bool = None) -> EmbeddingService:
 """Create production embedding service"""
 if use_microservice is None:
 use_microservice = (
 os.getenv("USE_EMBEDDING_MICROSERVICE", "true").lower() == "true"
 )

 return EmbeddingService(use_microservice = use_microservice)


def create_local_embedding_service() -> EmbeddingService:
 """Create local embedding service for development"""
 return EmbeddingService(use_microservice = False)


def create_microservice_client() -> EmbeddingMicroserviceClient:
 """Create microservice client"""
 return EmbeddingMicroserviceClient()


# Global service instance
_embedding_service: Optional[EmbeddingService] = None


async def get_embedding_service() -> EmbeddingService:
 """Get global embedding service instance"""
 global _embedding_service

 if _embedding_service is None:
 _embedding_service = create_embedding_service()
 await _embedding_service.initialize()

 return _embedding_service


async def embed_text(text: str, provider: str = None) -> List[float]:
 """Convenience function to embed single text"""
 service = await get_embedding_service()

 if service.use_microservice:
 return await service.grpc_service.embed_text(text, provider)
 else:
 provider_name = provider or service.default_provider
 if provider_name not in service.providers:
 raise ValueError(f"Provider {provider_name} not available")

 provider_obj = service.providers[provider_name]
 return await provider_obj.embed_text(text)


async def embed_batch(texts: List[str], provider: str = None) -> List[List[float]]:
 """Convenience function to embed multiple texts"""
 service = await get_embedding_service()

 if service.use_microservice:
 return await service.grpc_service.embed_batch(texts, provider)
 else:
 provider_name = provider or service.default_provider
 if provider_name not in service.providers:
 raise ValueError(f"Provider {provider_name} not available")

 provider_obj = service.providers[provider_name]
 return await provider_obj.embed_batch(texts)


async def get_available_providers() -> List[Dict[str, Any]]:
 """Get list of available embedding providers"""
 service = await get_embedding_service()

 if service.use_microservice:
 return await service.grpc_service.get_providers()
 else:
 providers = []
 for name, provider in service.providers.items():
 providers.append(
 {
 "name": name,
 "type": provider.__class__.__name__,
 "dimensions": provider.get_dimensions(),
 "enabled": True,
 }
 )
 return providers


# Cleanup function
async def cleanup_embedding_service():
 """Cleanup embedding service resources"""
 global _embedding_service

 if _embedding_service and _embedding_service.grpc_service:
 await _embedding_service.grpc_service.close()

 _embedding_service = None
