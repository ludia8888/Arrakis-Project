# Event Publisher Core Package
"""
Unified Event Publishing Interface
- Reduces duplication by providing single entry point
- Supports multiple platforms: NATS, EventBridge, Enhanced
- Uses factory pattern for appropriate publisher selection
"""

from .enhanced_event_service import EnhancedEventService
from .nats_publisher import NATSEventPublisher
from .multi_platform_router import MultiPlatformEventRouter, Platform, RoutingStrategy
import os

# 전역 통합 서비스 인스턴스 (중복 제거)
_UNIFIED_SERVICE = None

def get_event_publisher():
    """
    통합 이벤트 퍼블리셔 - 중복 제거된 단일 인터페이스
    
    우선순위:
    1. MultiPlatformRouter (다중 플랫폼 지원시)
    2. NATSEventPublisher (NATS 설정시)  
    3. EnhancedEventService (기본값)
    
    Returns:
        Unified event publisher instance
    """
    global _UNIFIED_SERVICE
    if _UNIFIED_SERVICE is None:
        # Check for multi-platform configuration
        if os.getenv("EVENT_PLATFORMS"):  # e.g., "nats,eventbridge"
            platforms = os.getenv("EVENT_PLATFORMS").split(",")
            _UNIFIED_SERVICE = MultiPlatformEventRouter(
                platforms=[Platform(p.strip()) for p in platforms],
                strategy=RoutingStrategy(os.getenv("EVENT_ROUTING_STRATEGY", "primary_only"))
            )
        # Single platform fallback
        elif os.getenv("NATS_URL"):
            _UNIFIED_SERVICE = NATSEventPublisher()
        else:
            _UNIFIED_SERVICE = EnhancedEventService()
    return _UNIFIED_SERVICE

# DEPRECATED: Use get_event_publisher() instead
def get_legacy_publisher():
    """Backward compatibility - DEPRECATED"""
    import warnings
    warnings.warn("get_legacy_publisher() is deprecated, use get_event_publisher()", 
                  DeprecationWarning, stacklevel=2)
    return get_event_publisher()

# Export unified interface (reduces confusion from multiple options)
__all__ = [
    'get_event_publisher',  # Primary interface
    'MultiPlatformEventRouter',  # Advanced usage
    # Legacy exports for backward compatibility
    'EnhancedEventService', 
    'NATSEventPublisher'
]
