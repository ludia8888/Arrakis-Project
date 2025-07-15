"""
Configuration management for Vector Embedding Providers
Handles loading and parsing of embedding provider configurations
"""
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EmbeddingProviderType(Enum):
 """Supported embedding provider types"""
 OPENAI = "openai"
 ANTHROPIC = "anthropic"
 COHERE = "cohere"
 HUGGINGFACE = "huggingface"
 AZURE_OPENAI = "azure_openai"
 GOOGLE_VERTEX = "google_vertex"
 LOCAL_SENTENCE_TRANSFORMERS = "local_sentence_transformers"


@dataclass
class ProviderConfig:
 """Configuration for a single embedding provider"""
 name: str
 provider_type: EmbeddingProviderType
 enabled: bool
 api_key: Optional[str] = None
 api_base: Optional[str] = None
 model_name: str = ""
 dimensions: Optional[int] = None
 max_batch_size: int = 100
 max_tokens_per_request: Optional[int] = None
 rate_limit_rpm: Optional[int] = None
 timeout: int = 30
 extra_config: Dict[str, Any] = None

 def __post_init__(self):
 if self.extra_config is None:
 self.extra_config = {}


@dataclass
class EmbeddingServiceConfig:
 """Overall embedding service configuration"""
 use_microservice: bool
 service_endpoint: str
 default_provider: str
 fallback_enabled: bool
 fallback_order: List[str]
 cache_ttl: int
 cache_enabled: bool
 cache_backend: str
 request_timeout: int
 max_retries: int
 concurrent_requests: int
 enable_metrics: bool
 providers: Dict[str, ProviderConfig]


class EmbeddingConfigManager:
 """Manages embedding provider configurations"""

 def __init__(self, env_file: Optional[str] = None):
 self.env_file = env_file
 self._config: Optional[EmbeddingServiceConfig] = None

 def load_config(self) -> EmbeddingServiceConfig:
 """Load configuration from environment variables"""
 if self._config is not None:
 return self._config

 # Load environment file if specified
 if self.env_file and os.path.exists(self.env_file):
 self._load_env_file(self.env_file)

 # Build provider configurations
 providers = {}

 # OpenAI Provider
 if self._get_bool("OPENAI_API_KEY"):
 providers["openai"] = ProviderConfig(
 name = "openai",
 provider_type = EmbeddingProviderType.OPENAI,
 enabled = bool(os.getenv("OPENAI_API_KEY")),
 api_key = os.getenv("OPENAI_API_KEY"),
 model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
 dimensions = self._get_int("OPENAI_EMBEDDING_DIMENSIONS", 3072),
 max_batch_size = self._get_int("OPENAI_MAX_BATCH_SIZE", 2048),
 max_tokens_per_request = self._get_int("OPENAI_MAX_TOKENS_PER_REQUEST", 8191),
 rate_limit_rpm = self._get_int("OPENAI_RATE_LIMIT_RPM", 10000)
 )

 # Anthropic Provider
 if os.getenv("ANTHROPIC_API_KEY"):
 providers["anthropic"] = ProviderConfig(
 name = "anthropic",
 provider_type = EmbeddingProviderType.ANTHROPIC,
 enabled = bool(os.getenv("ANTHROPIC_API_KEY")),
 api_key = os.getenv("ANTHROPIC_API_KEY"),
 model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
 dimensions = self._get_int("ANTHROPIC_EMBEDDING_DIMENSIONS", 384),
 max_batch_size = self._get_int("ANTHROPIC_MAX_BATCH_SIZE", 20)
 )

 # Cohere Provider
 if os.getenv("COHERE_API_KEY"):
 providers["cohere"] = ProviderConfig(
 name = "cohere",
 provider_type = EmbeddingProviderType.COHERE,
 enabled = bool(os.getenv("COHERE_API_KEY")),
 api_key = os.getenv("COHERE_API_KEY"),
 model_name = os.getenv("COHERE_EMBEDDING_MODEL", "embed-english-v3.0"),
 dimensions = self._get_int("COHERE_EMBEDDING_DIMENSIONS", 1024),
 max_batch_size = self._get_int("COHERE_MAX_BATCH_SIZE", 96),
 rate_limit_rpm = self._get_int("COHERE_RATE_LIMIT_RPM", 10000),
 extra_config={
 "input_type": os.getenv("COHERE_INPUT_TYPE", "search_document")
 }
 )

 # HuggingFace Provider
 if os.getenv("HUGGINGFACE_API_KEY"):
 providers["huggingface"] = ProviderConfig(
 name = "huggingface",
 provider_type = EmbeddingProviderType.HUGGINGFACE,
 enabled = bool(os.getenv("HUGGINGFACE_API_KEY")),
 api_key = os.getenv("HUGGINGFACE_API_KEY"),
 api_base = os.getenv("HUGGINGFACE_API_BASE", "https://api-inference.huggingface.co"),
 model_name = os.getenv("HUGGINGFACE_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
 dimensions = self._get_int("HUGGINGFACE_EMBEDDING_DIMENSIONS", 384),
 max_batch_size = self._get_int("HUGGINGFACE_MAX_BATCH_SIZE", 100)
 )

 # Azure OpenAI Provider
 if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
 providers["azure_openai"] = ProviderConfig(
 name = "azure_openai",
 provider_type = EmbeddingProviderType.AZURE_OPENAI,
 enabled = bool(os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT")),
 api_key = os.getenv("AZURE_OPENAI_API_KEY"),
 api_base = os.getenv("AZURE_OPENAI_ENDPOINT"),
 model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "text-embedding-3-large"),
 dimensions = self._get_int("AZURE_OPENAI_EMBEDDING_DIMENSIONS", 3072),
 max_batch_size = self._get_int("AZURE_OPENAI_MAX_BATCH_SIZE", 2048),
 extra_config={
 "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
 }
 )

 # Google Vertex AI Provider
 if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
 providers["google_vertex"] = ProviderConfig(
 name = "google_vertex",
 provider_type = EmbeddingProviderType.GOOGLE_VERTEX,
 enabled = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
 model_name = os.getenv("GOOGLE_VERTEX_MODEL", "textembedding-gecko@003"),
 dimensions = self._get_int("GOOGLE_VERTEX_EMBEDDING_DIMENSIONS", 768),
 extra_config={
 "project_id": os.getenv("GOOGLE_PROJECT_ID"),
 "location": os.getenv("GOOGLE_VERTEX_LOCATION", "us-central1")
 }
 )

 # Local Sentence Transformers Provider (always available)
 providers["local_sentence_transformers"] = ProviderConfig(
 name = "local_sentence_transformers",
 provider_type = EmbeddingProviderType.LOCAL_SENTENCE_TRANSFORMERS,
 enabled = True,
 model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
 dimensions = self._get_int("LOCAL_EMBEDDING_DIMENSIONS", 384),
 extra_config={
 "device": os.getenv("LOCAL_DEVICE", "auto"),
 "cache_dir": os.getenv("LOCAL_CACHE_DIR", "./.cache/sentence_transformers")
 }
 )

 # Parse fallback order
 fallback_order_str = os.getenv(
 "EMBEDDING_PROVIDER_FALLBACK_ORDER",
 "openai,azure_openai,cohere,huggingface,google_vertex,anthropic,local_sentence_transformers"
 )
 fallback_order = [name.strip() for name in fallback_order_str.split(",")]

 # Build main configuration
 self._config = EmbeddingServiceConfig(
 use_microservice = self._get_bool("USE_EMBEDDING_MS", False),
 service_endpoint = os.getenv("EMBEDDING_SERVICE_ENDPOINT", "embedding-service:50055"),
 default_provider = os.getenv("DEFAULT_EMBEDDING_PROVIDER", "local_sentence_transformers"),
 fallback_enabled = self._get_bool("EMBEDDING_FALLBACK_ENABLED", True),
 fallback_order = fallback_order,
 cache_ttl = self._get_int("EMBEDDING_CACHE_TTL", 3600),
 cache_enabled = self._get_bool("EMBEDDING_CACHE_ENABLED", True),
 cache_backend = os.getenv("EMBEDDING_CACHE_BACKEND", "redis"),
 request_timeout = self._get_int("EMBEDDING_REQUEST_TIMEOUT", 30),
 max_retries = self._get_int("EMBEDDING_MAX_RETRIES", 3),
 concurrent_requests = self._get_int("EMBEDDING_CONCURRENT_REQUESTS", 10),
 enable_metrics = self._get_bool("EMBEDDING_ENABLE_METRICS", True),
 providers = providers
 )

 logger.info(f"Loaded embedding configuration with {len(providers)} providers")
 return self._config

 def get_enabled_providers(self) -> List[str]:
 """Get list of enabled provider names"""
 config = self.load_config()
 return [name for name, provider in config.providers.items() if provider.enabled]

 def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
 """Get configuration for a specific provider"""
 config = self.load_config()
 return config.providers.get(provider_name)

 def get_fallback_chain(self) -> List[str]:
 """Get the fallback provider chain in priority order"""
 config = self.load_config()
 enabled_providers = set(self.get_enabled_providers())

 # Filter fallback order to only include enabled providers
 return [name for name in config.fallback_order if name in enabled_providers]

 def validate_configuration(self) -> Dict[str, Any]:
 """Validate the current configuration"""
 config = self.load_config()
 validation_results = {
 "valid": True,
 "errors": [],
 "warnings": [],
 "provider_status": {}
 }

 enabled_providers = self.get_enabled_providers()

 # Check if at least one provider is available
 if not enabled_providers:
 validation_results["errors"].append("No embedding providers are enabled")
 validation_results["valid"] = False

 # Check if default provider is available
 if config.default_provider not in enabled_providers:
 validation_results["warnings"].append(
 f"Default provider '{config.default_provider}' is not enabled"
 )

 # Validate each provider
 for name, provider in config.providers.items():
 status = {"enabled": provider.enabled, "issues": []}

 if provider.enabled:
 # Check API key for cloud providers
 if provider.provider_type != EmbeddingProviderType.LOCAL_SENTENCE_TRANSFORMERS:
 if not provider.api_key:
 status["issues"].append("Missing API key")

 # Check specific requirements
 if provider.provider_type == EmbeddingProviderType.AZURE_OPENAI:
 if not provider.api_base:
 status["issues"].append("Missing Azure endpoint")
 elif provider.provider_type == EmbeddingProviderType.GOOGLE_VERTEX:
 if not provider.extra_config.get("project_id"):
 status["issues"].append("Missing Google project ID")

 validation_results["provider_status"][name] = status

 return validation_results

 def _load_env_file(self, env_file: str):
 """Load environment variables from file"""
 try:
 with open(env_file, 'r') as f:
 for line in f:
 line = line.strip()
 if line and not line.startswith('#') and '=' in line:
 key, value = line.split('=', 1)
 os.environ.setdefault(key.strip(), value.strip())
 except Exception as e:
 logger.warning(f"Failed to load environment file {env_file}: {e}")

 def _get_bool(self, key: str, default: bool = False) -> bool:
 """Get boolean value from environment"""
 value = os.getenv(key, "").lower()
 if value in ("true", "1", "yes", "on"):
 return True
 elif value in ("false", "0", "no", "off"):
 return False
 else:
 return default

 def _get_int(self, key: str, default: int = 0) -> int:
 """Get integer value from environment"""
 try:
 return int(os.getenv(key, str(default)))
 except ValueError:
 return default


# Global configuration manager instance
_config_manager: Optional[EmbeddingConfigManager] = None


def get_embedding_config() -> EmbeddingServiceConfig:
 """Get the global embedding configuration"""
 global _config_manager
 if _config_manager is None:
 _config_manager = EmbeddingConfigManager()
 return _config_manager.load_config()


def get_provider_config(provider_name: str) -> Optional[ProviderConfig]:
 """Get configuration for a specific provider"""
 global _config_manager
 if _config_manager is None:
 _config_manager = EmbeddingConfigManager()
 return _config_manager.get_provider_config(provider_name)


def validate_embedding_config() -> Dict[str, Any]:
 """Validate the current embedding configuration"""
 global _config_manager
 if _config_manager is None:
 _config_manager = EmbeddingConfigManager()
 return _config_manager.validate_configuration()
