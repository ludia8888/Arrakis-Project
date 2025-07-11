"""
Enhanced Embedding Service Provider with Multi-Provider Support
Supports dependency injection and configuration-driven provider initialization
"""
from typing import Optional, Dict, Any, List
import os
import asyncio
from .base import Provider
from shared.embedding_stub import get_embedding_stub, EmbeddingStub
from shared.embedding_config import get_embedding_config, validate_embedding_config, ProviderConfig
from common_logging.setup import get_logger

logger = get_logger(__name__)


class EnhancedEmbeddingServiceProvider(Provider[EmbeddingStub]):
    """Enhanced provider for embedding service with multi-provider support."""
    
    def __init__(self):
        super().__init__()
        self._stub = None
        self._config = None
        self._validation_results = None
        self._initialized = False
    
    async def provide(self) -> EmbeddingStub:
        """Provide embedding service stub instance with full configuration."""
        if not self._stub:
            await self.initialize()
        return self._stub
    
    async def initialize(self) -> None:
        """Initialize the provider with configuration validation."""
        if self._initialized:
            return
            
        logger.info("Initializing enhanced embedding service provider...")
        
        # Load and validate configuration
        self._config = get_embedding_config()
        self._validation_results = validate_embedding_config()
        
        # Log configuration validation results
        await self._log_configuration_status()
        
        # Initialize the embedding stub
        endpoint = self._config.service_endpoint
        self._stub = get_embedding_stub(endpoint)
        await self._stub.initialize()
        
        # Log provider status
        await self._log_provider_status()
        
        self._initialized = True
        logger.info("Enhanced embedding service provider initialization complete")
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._stub:
            await self._stub.close()
        logger.info("Enhanced embedding service provider shutdown complete")
    
    async def get_provider_stats(self) -> Dict[str, Any]:
        """Get comprehensive provider statistics."""
        if not self._initialized:
            await self.initialize()
        
        stats = {
            "configuration": {
                "use_microservice": self._config.use_microservice,
                "default_provider": self._config.default_provider,
                "fallback_enabled": self._config.fallback_enabled,
                "cache_enabled": self._config.cache_enabled,
                "enabled_providers": list(self._get_enabled_providers().keys())
            },
            "validation": self._validation_results,
            "runtime_stats": {}
        }
        
        # Get runtime stats from the stub if available
        if self._stub and hasattr(self._stub, 'get_stats'):
            try:
                runtime_stats = await self._stub.get_stats()
                stats["runtime_stats"] = runtime_stats
            except Exception as e:
                stats["runtime_stats"] = {"error": str(e)}
        
        return stats
    
    async def get_available_providers(self) -> List[str]:
        """Get list of available embedding providers."""
        if not self._initialized:
            await self.initialize()
        
        return list(self._get_enabled_providers().keys())
    
    async def test_provider(self, provider_name: str) -> Dict[str, Any]:
        """Test a specific embedding provider."""
        if not self._initialized:
            await self.initialize()
        
        test_result = {
            "provider": provider_name,
            "available": False,
            "test_passed": False,
            "error": None,
            "response_time": None
        }
        
        enabled_providers = self._get_enabled_providers()
        if provider_name not in enabled_providers:
            test_result["error"] = f"Provider {provider_name} not enabled or configured"
            return test_result
        
        test_result["available"] = True
        
        # Test embedding generation
        try:
            import time
            start_time = time.time()
            
            # Use the stub to generate a test embedding
            if hasattr(self._stub, 'generate_embedding_with_provider'):
                embedding = await self._stub.generate_embedding_with_provider(
                    "This is a test embedding.", provider_name
                )
            else:
                embedding = await self._stub.generate_embedding("This is a test embedding.")
            
            test_result["response_time"] = time.time() - start_time
            test_result["test_passed"] = len(embedding) > 0
            test_result["embedding_dimension"] = len(embedding)
            
        except Exception as e:
            test_result["error"] = str(e)
        
        return test_result
    
    async def test_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Test all available embedding providers."""
        if not self._initialized:
            await self.initialize()
        
        results = {}
        enabled_providers = self._get_enabled_providers()
        
        # Test providers concurrently
        tasks = []
        for provider_name in enabled_providers:
            task = self.test_provider(provider_name)
            tasks.append((provider_name, task))
        
        # Wait for all tests to complete
        for provider_name, task in tasks:
            try:
                results[provider_name] = await task
            except Exception as e:
                results[provider_name] = {
                    "provider": provider_name,
                    "available": False,
                    "test_passed": False,
                    "error": str(e)
                }
        
        return results
    
    def _get_enabled_providers(self) -> Dict[str, ProviderConfig]:
        """Get enabled providers from configuration."""
        if not self._config:
            return {}
        
        return {
            name: config for name, config in self._config.providers.items() 
            if config.enabled
        }
    
    async def _log_configuration_status(self):
        """Log configuration validation status."""
        if not self._validation_results["valid"]:
            logger.error("Embedding configuration validation failed:")
            for error in self._validation_results["errors"]:
                logger.error(f"  - {error}")
        
        if self._validation_results["warnings"]:
            logger.warning("Embedding configuration warnings:")
            for warning in self._validation_results["warnings"]:
                logger.warning(f"  - {warning}")
        
        # Log provider status
        enabled_count = 0
        for name, status in self._validation_results["provider_status"].items():
            if status["enabled"]:
                enabled_count += 1
                if status["issues"]:
                    logger.warning(f"Provider {name} has issues: {', '.join(status['issues'])}")
                else:
                    logger.info(f"Provider {name} configured successfully")
        
        logger.info(f"Total enabled providers: {enabled_count}")
    
    async def _log_provider_status(self):
        """Log provider runtime status."""
        try:
            if hasattr(self._stub, 'get_available_providers'):
                available_providers = await self._stub.get_available_providers()
                logger.info(f"Runtime available providers: {available_providers}")
            
            fallback_chain = [
                name for name in self._config.fallback_order 
                if name in self._get_enabled_providers()
            ]
            logger.info(f"Provider fallback chain: {fallback_chain}")
            
        except Exception as e:
            logger.warning(f"Failed to get provider status: {e}")


# Backward compatibility alias
EmbeddingServiceProvider = EnhancedEmbeddingServiceProvider


def get_embedding_service_provider() -> EnhancedEmbeddingServiceProvider:
    """Get enhanced embedding service provider instance."""
    return EnhancedEmbeddingServiceProvider()


# Additional utility functions
async def get_embedding_provider_status() -> Dict[str, Any]:
    """Get status of all embedding providers."""
    provider = get_embedding_service_provider()
    await provider.initialize()
    return await provider.get_provider_stats()


async def test_embedding_providers() -> Dict[str, Dict[str, Any]]:
    """Test all embedding providers and return results."""
    provider = get_embedding_service_provider()
    await provider.initialize()
    return await provider.test_all_providers()