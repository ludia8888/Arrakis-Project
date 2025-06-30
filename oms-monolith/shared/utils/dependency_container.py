"""
Dependency Injection Container
Manages singleton instances and dependencies without circular imports
"""
from typing import Dict, Any, Optional, TypeVar, Callable
from contextlib import asynccontextmanager
import asyncio

T = TypeVar('T')


class DependencyContainer:
    """Simple dependency injection container for managing singletons"""
    
    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
    
    def register_factory(self, name: str, factory: Callable[[], T]) -> None:
        """Register a factory function for creating instances"""
        self._factories[name] = factory
    
    async def get(self, name: str) -> Optional[Any]:
        """Get or create an instance by name"""
        async with self._lock:
            if name not in self._instances:
                if name not in self._factories:
                    return None
                
                factory = self._factories[name]
                # Check if factory is async
                if asyncio.iscoroutinefunction(factory):
                    instance = await factory()
                else:
                    instance = factory()
                
                self._instances[name] = instance
            
            return self._instances[name]
    
    async def set(self, name: str, instance: Any) -> None:
        """Set an instance directly (useful for testing)"""
        async with self._lock:
            self._instances[name] = instance
    
    def clear(self) -> None:
        """Clear all instances (useful for testing)"""
        self._instances.clear()
    
    def remove(self, name: str) -> None:
        """Remove a specific instance"""
        self._instances.pop(name, None)
    
    async def close_all(self) -> None:
        """Close all instances that have a close/shutdown method"""
        for name, instance in self._instances.items():
            if hasattr(instance, 'shutdown'):
                if asyncio.iscoroutinefunction(instance.shutdown):
                    await instance.shutdown()
                else:
                    instance.shutdown()
            elif hasattr(instance, 'close'):
                if asyncio.iscoroutinefunction(instance.close):
                    await instance.close()
                else:
                    instance.close()


# Global container instance
_container = DependencyContainer()


def get_container() -> DependencyContainer:
    """Get the global dependency container"""
    return _container


@asynccontextmanager
async def dependency_scope():
    """Context manager for dependency lifecycle"""
    container = get_container()
    try:
        yield container
    finally:
        await container.close_all()
        container.clear()