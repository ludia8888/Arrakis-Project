"""
Middleware Coordinator - Facade pattern implementation for coordinating middleware components
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MiddlewareContext:
    """Middleware execution context"""

    request_id: str
    user_id: Optional[str]
    ip_address: str
    endpoint: str
    method: str
    timestamp: datetime
    metadata: Dict[str, Any]

    def add_metadata(self, key: str, value: Any):
        """Add metadata"""
        self.metadata[key] = value


class MiddlewareCoordinator:
    """
    Facade for coordinating middleware components
    Pipeline execution, error handling, and inter-component data sharing management
    """

    def __init__(self):
        # Lazy import to avoid circular dependencies
        self._health = None
        self._discovery = None
        self._rate_limiter = None
        self._dlq = None
        self._circuit_breaker = None

        self._middleware_pipeline: List[Callable] = []
        self._context_store: Dict[str, MiddlewareContext] = {}

    @property
    def health(self):
        """Health coordinator lazy loading"""
        if self._health is None:
            from .health.coordinator import HealthCoordinator

            self._health = HealthCoordinator()
        return self._health

    @property
    def discovery(self):
        """Discovery coordinator lazy loading"""
        if self._discovery is None:
            from .discovery.coordinator import DiscoveryCoordinator

            self._discovery = DiscoveryCoordinator()
        return self._discovery

    @property
    def rate_limiter(self):
        """Rate limiter coordinator lazy loading"""
        if self._rate_limiter is None:
            from .rate_limiting.coordinator import RateLimitCoordinator

            self._rate_limiter = RateLimitCoordinator()
        return self._rate_limiter

    @property
    def dlq(self):
        """DLQ coordinator lazy loading"""
        if self._dlq is None:
            from .dlq.coordinator import DLQCoordinator

            self._dlq = DLQCoordinator()
        return self._dlq

    @property
    def circuit_breaker(self):
        """Circuit breaker lazy loading"""
        if self._circuit_breaker is None:
            from .circuit_breaker import CircuitBreaker

            self._circuit_breaker = CircuitBreaker()
        return self._circuit_breaker

    async def process_request(
        self,
        request_id: str,
        user_id: Optional[str],
        ip_address: str,
        endpoint: str,
        method: str,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute request processing pipeline
        Execute all middleware sequentially and integrate results
        """
        # Create context
        context = MiddlewareContext(
            request_id=request_id,
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            method=method,
            timestamp=datetime.utcnow(),
            metadata={},
        )

        self._context_store[request_id] = context

        try:
            # 1. Health check
            health_status = await self._check_health(context)
            if not health_status["healthy"]:
                return {"error": "Service unavailable", "details": health_status}

            # 2. Rate limiting
            rate_limit_result = await self._apply_rate_limiting(context)
            if not rate_limit_result["allowed"]:
                return {"error": "Rate limit exceeded", "details": rate_limit_result}

            # 3. Service discovery
            service_endpoint = await self._discover_service(context, endpoint)
            if not service_endpoint:
                return {"error": "Service not found", "endpoint": endpoint}

            # 4. Circuit breaker
            if not await self._check_circuit(context, service_endpoint):
                # Send request to DLQ
                await self._send_to_dlq(context, request_data, "Circuit open")
                return {"error": "Service temporarily unavailable", "retry_after": 60}

            # 5. Process actual request (simulation here)
            result = {
                "success": True,
                "request_id": request_id,
                "service_endpoint": service_endpoint,
                "metadata": context.metadata,
            }

            return result

        except Exception as e:
            logger.error(f"Error processing request {request_id}: {str(e)}")
            # Send failed request to DLQ
            await self._send_to_dlq(context, request_data, str(e))
            raise
        finally:
            # Clean up context
            self._context_store.pop(request_id, None)

    async def _check_health(self, context: MiddlewareContext) -> Dict[str, Any]:
        """Perform health check"""
        try:
            health_status = await self.health.check_system_health()
            context.add_metadata("health_status", health_status)
            return health_status
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"healthy": False, "error": str(e)}

    async def _apply_rate_limiting(self, context: MiddlewareContext) -> Dict[str, Any]:
        """Apply rate limiting"""
        try:
            result = await self.rate_limiter.check_rate_limit(
                user_id=context.user_id,
                ip_address=context.ip_address,
                endpoint=context.endpoint,
            )
            context.add_metadata("rate_limit", result)
            return result
        except Exception as e:
            logger.error(f"Rate limiting failed: {str(e)}")
            # Allow request if rate limiting fails
            return {"allowed": True, "error": str(e)}

    async def _discover_service(
        self, context: MiddlewareContext, endpoint: str
    ) -> Optional[str]:
        """Service discovery"""
        try:
            service = await self.discovery.discover_service(endpoint)
            context.add_metadata("discovered_service", service)
            return service
        except Exception as e:
            logger.error(f"Service discovery failed: {str(e)}")
            return None

    async def _check_circuit(
        self, context: MiddlewareContext, service_endpoint: str
    ) -> bool:
        """Check circuit breaker"""
        try:
            is_open = await self.circuit_breaker.is_open(service_endpoint)
            context.add_metadata("circuit_status", "open" if is_open else "closed")
            return not is_open
        except Exception as e:
            logger.error(f"Circuit breaker check failed: {str(e)}")
            return True  # Allow request on failure

    async def _send_to_dlq(
        self, context: MiddlewareContext, request_data: Dict[str, Any], reason: str
    ):
        """Send failed request to DLQ"""
        try:
            await self.dlq.send_message(
                message_id=context.request_id,
                content=request_data,
                reason=reason,
                metadata=context.metadata,
            )
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {str(e)}")

    async def get_middleware_stats(self) -> Dict[str, Any]:
        """Get middleware statistics"""
        stats = {}

        # Collect statistics from each component
        if self._health:
            stats["health"] = await self.health.get_stats()
        if self._rate_limiter:
            stats["rate_limiter"] = await self.rate_limiter.get_stats()
        if self._discovery:
            stats["discovery"] = await self.discovery.get_stats()
        if self._dlq:
            stats["dlq"] = await self.dlq.get_stats()
        if self._circuit_breaker:
            stats["circuit_breaker"] = await self.circuit_breaker.get_stats()

        stats["active_contexts"] = len(self._context_store)

        return stats

    def register_middleware(self, middleware: Callable):
        """Register custom middleware"""
        self._middleware_pipeline.append(middleware)

    async def execute_pipeline(
        self, context: MiddlewareContext, handler: Callable
    ) -> Any:
        """Execute middleware pipeline"""

        async def execute_next(index: int):
            if index >= len(self._middleware_pipeline):
                return await handler(context)

            middleware = self._middleware_pipeline[index]
            return await middleware(context, lambda: execute_next(index + 1))

        return await execute_next(0)
