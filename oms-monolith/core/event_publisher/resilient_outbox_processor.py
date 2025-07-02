"""
Resilient Outbox Processor - Integrates event publishing with unified resilience module

This enhances the outbox processor with unified retry patterns, circuit breakers,
and retry budgets for more reliable event publishing.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

from shared.resilience import (
    ResilienceRegistry,
    RetryConfig,
    CircuitBreakerConfig,
    RetryBudgetConfig,
    RETRY_POLICIES,
    with_retry
)
from shared.monitoring.unified_metrics import get_metrics_collector
from database.clients.terminus_db import TerminusDBClient
from shared.infrastructure.unified_nats_client import UnifiedNATSClient as NATSClient

from .outbox_processor import OutboxProcessor
from .cloudevents_enhanced import EnhancedCloudEvent
from .multi_platform_router import MultiPlatformEventRouter
from .eventbridge_publisher import EventBridgeConfig

logger = logging.getLogger(__name__)
metrics = get_metrics_collector()


class ResilientOutboxProcessor(OutboxProcessor):
    """
    Outbox processor with integrated resilience patterns.
    
    This enhances the standard outbox processor with:
    - Unified retry patterns for event publishing
    - Circuit breakers for external platform calls
    - Retry budgets to prevent retry storms
    - Per-platform resilience configuration
    """
    
    def __init__(
        self,
        tdb_client: TerminusDBClient,
        nats_client: NATSClient,
        metrics_collector: Any,
        eventbridge_config: Optional[EventBridgeConfig] = None,
        enable_multi_platform: bool = False,
        resilience_name: Optional[str] = None
    ):
        super().__init__(
            tdb_client=tdb_client,
            nats_client=nats_client,
            metrics=metrics_collector,
            eventbridge_config=eventbridge_config,
            enable_multi_platform=enable_multi_platform
        )
        
        # Initialize resilience components
        self.resilience_name = resilience_name or "outbox_processor"
        
        # Create circuit breakers for different platforms
        self._init_circuit_breakers()
        
        # Create retry budgets
        self._init_retry_budgets()
        
        # Get retry executors
        self._init_retry_executors()
        
        # Additional metrics
        self.retry_counter = metrics.Counter(
            'outbox_event_retries_total',
            'Total event publishing retry attempts',
            ['platform', 'status']
        )
    
    def _init_circuit_breakers(self):
        """Initialize circuit breakers for each platform"""
        # NATS circuit breaker
        self.nats_cb = ResilienceRegistry.get_circuit_breaker(
            name=f"{self.resilience_name}_nats_cb",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=timedelta(seconds=30),
                track_exceptions=[ConnectionError, TimeoutError]
            )
        )
        
        # EventBridge circuit breaker
        self.eventbridge_cb = ResilienceRegistry.get_circuit_breaker(
            name=f"{self.resilience_name}_eventbridge_cb",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout=timedelta(minutes=1),
                track_exceptions=[ConnectionError, TimeoutError]
            )
        )
    
    def _init_retry_budgets(self):
        """Initialize retry budgets to prevent retry storms"""
        # Shared retry budget for all event publishing
        self.retry_budget = ResilienceRegistry.get_retry_budget(
            name=f"{self.resilience_name}_budget",
            config=RetryBudgetConfig(
                budget_percent=30.0,  # Allow 30% retry rate
                window_size=timedelta(minutes=1),
                min_requests=20,
                max_tokens=100,
                tokens_per_second=10
            )
        )
    
    def _init_retry_executors(self):
        """Initialize retry executors for different scenarios"""
        # NATS retry executor
        self.nats_retry_executor = ResilienceRegistry.get_retry_executor(
            name=f"{self.resilience_name}_nats",
            circuit_breaker_name=f"{self.resilience_name}_nats_cb",
            retry_budget_name=f"{self.resilience_name}_budget"
        )
        
        # EventBridge retry executor
        self.eventbridge_retry_executor = ResilienceRegistry.get_retry_executor(
            name=f"{self.resilience_name}_eventbridge",
            circuit_breaker_name=f"{self.resilience_name}_eventbridge_cb",
            retry_budget_name=f"{self.resilience_name}_budget"
        )
    
    async def _process_batch(self) -> int:
        """Enhanced batch processing with resilience patterns"""
        # Query for pending events
        query = """
        SELECT ?event ?id ?type ?payload ?created_at ?retry_count
        WHERE {
            ?event a ont:OutboxEvent .
            ?event ont:status "pending" .
            ?event ont:id ?id .
            ?event ont:type ?type .
            ?event ont:payload ?payload .
            ?event ont:created_at ?created_at .
            OPTIONAL { ?event ont:retry_count ?retry_count }
        }
        ORDER BY ?created_at
        LIMIT $limit
        """
        
        events = await self.tdb.query(
            query,
            branch="_outbox",
            bindings={"limit": self.batch_size}
        )
        
        if not events:
            return 0
        
        # Process events concurrently with limited concurrency
        semaphore = asyncio.Semaphore(10)  # Process max 10 events concurrently
        
        async def process_event(event):
            async with semaphore:
                return await self._process_single_event(event)
        
        results = await asyncio.gather(
            *[process_event(event) for event in events],
            return_exceptions=True
        )
        
        # Count successful publishes
        processed = sum(1 for r in results if r is True)
        
        return processed
    
    async def _process_single_event(self, event: Dict) -> bool:
        """Process a single event with resilience patterns"""
        event_id = event["id"]
        retry_count = int(event.get("retry_count", 0))
        
        try:
            # Determine retry configuration based on event type and retry count
            retry_config = self._get_retry_config_for_event(event, retry_count)
            
            # Create the publish function
            async def _publish():
                return await self._publish_event(event)
            
            # Execute with retry based on platform
            if self.enable_multi_platform:
                # Multi-platform uses different executors per platform
                result = await self._publish_with_multi_platform_resilience(event)
            else:
                # Single platform (NATS) uses NATS executor
                result = await self.nats_retry_executor.aexecute(_publish, retry_config)
                
                if result.successful:
                    await self._mark_published(event_id)
                    
                    if result.attempts > 1:
                        self.retry_counter.labels(
                            platform="nats",
                            status="success"
                        ).inc(result.attempts - 1)
                    
                    return True
                else:
                    await self._handle_publish_failure(event, result.last_error, result.attempts)
                    
                    self.retry_counter.labels(
                        platform="nats",
                        status="failed"
                    ).inc(result.attempts)
                    
                    return False
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error processing event {event_id}: {e}")
            await self._mark_failed(event_id, str(e))
            return False
    
    async def _publish_with_multi_platform_resilience(self, event: Dict) -> bool:
        """Publish to multiple platforms with per-platform resilience"""
        event_id = event["id"]
        
        # Convert to CloudEvent
        payload = json.loads(event["payload"])
        cloud_event = EnhancedCloudEvent(
            type=f"com.foundry.oms.{event['type']}",
            source=f"/oms/{payload.get('branch', 'main')}",
            id=event_id,
            data=payload
        )
        
        # Publish to each platform with its own retry logic
        platform_results = {}
        
        # NATS publishing
        async def _publish_to_nats():
            return await self._publish_to_nats_directly(cloud_event, event)
        
        nats_config = RETRY_POLICIES["network"].to_config()
        nats_result = await self.nats_retry_executor.aexecute(_publish_to_nats, nats_config)
        platform_results["nats"] = nats_result
        
        # EventBridge publishing (if configured)
        if self.eventbridge_config and self.router:
            async def _publish_to_eventbridge():
                return await self.router._publish_to_eventbridge(cloud_event)
            
            eb_config = RETRY_POLICIES["webhook"].to_config()
            eb_result = await self.eventbridge_retry_executor.aexecute(
                _publish_to_eventbridge,
                eb_config
            )
            platform_results["eventbridge"] = eb_result
        
        # Check overall success
        success_count = sum(1 for r in platform_results.values() if r.successful)
        
        if success_count > 0:
            await self._mark_published(event_id)
            
            # Record retry metrics
            for platform, result in platform_results.items():
                if result.attempts > 1:
                    self.retry_counter.labels(
                        platform=platform,
                        status="success" if result.successful else "failed"
                    ).inc(result.attempts - 1)
            
            return True
        else:
            # All platforms failed
            total_attempts = sum(r.attempts for r in platform_results.values())
            last_error = next(
                (r.last_error for r in platform_results.values() if r.last_error),
                "All platforms failed"
            )
            
            await self._handle_publish_failure(event, last_error, total_attempts)
            return False
    
    def _get_retry_config_for_event(self, event: Dict, retry_count: int) -> RetryConfig:
        """Get appropriate retry config based on event type and history"""
        event_type = event["type"]
        
        # Map event types to retry policies
        type_to_policy = {
            "schema.changed": "critical",  # Schema changes are critical
            "branch.merged": "critical",   # Branch merges are critical
            "action.completed": "standard",
            "webhook": "webhook",
            "notification": "network"
        }
        
        # Find matching policy
        policy_name = "standard"
        for key, policy in type_to_policy.items():
            if key in event_type:
                policy_name = policy
                break
        
        # Get base config
        if policy_name in RETRY_POLICIES:
            config = RETRY_POLICIES[policy_name].to_config()
        else:
            config = RetryConfig()
        
        # Adjust based on previous retry count
        if retry_count > 0:
            # Reduce max attempts by previous retries
            config.max_attempts = max(1, config.max_attempts - retry_count)
            # Increase initial delay for repeated failures
            config.initial_delay = min(config.initial_delay * (2 ** retry_count), config.max_delay)
        
        return config
    
    async def _handle_publish_failure(self, event: Dict, error: Exception, attempts: int):
        """Handle publishing failure with enhanced logic"""
        event_id = event["id"]
        current_retry_count = int(event.get("retry_count", 0))
        new_retry_count = current_retry_count + attempts
        
        # Check if we should move to dead letter
        max_total_retries = 10  # Total retry limit across all attempts
        
        if new_retry_count >= max_total_retries:
            # Move to dead letter status
            await self._mark_dead_letter(event_id, str(error), new_retry_count)
            logger.error(
                f"Event {event_id} moved to dead letter after {new_retry_count} total retries"
            )
        else:
            # Update retry count and schedule for retry
            await self._update_retry_count(event_id, new_retry_count, str(error))
            logger.warning(
                f"Event {event_id} failed, will retry. Total retries: {new_retry_count}"
            )
    
    async def _mark_dead_letter(self, event_id: str, error: str, retry_count: int):
        """Mark event as dead letter"""
        update_query = """
        WOQL.and(
            WOQL.triple("v:Event", "ont:id", $event_id),
            WOQL.delete_triple("v:Event", "ont:status", "pending"),
            WOQL.add_triple("v:Event", "ont:status", "dead_letter"),
            WOQL.add_triple("v:Event", "ont:final_error", $error),
            WOQL.add_triple("v:Event", "ont:total_retries", $retry_count),
            WOQL.add_triple("v:Event", "ont:dead_letter_at", WOQL.datetime())
        )
        """
        
        await self.tdb.update(
            update_query,
            branch="_outbox",
            bindings={
                "event_id": event_id,
                "error": error,
                "retry_count": retry_count
            }
        )
    
    async def _update_retry_count(self, event_id: str, retry_count: int, error: str):
        """Update retry count for an event"""
        update_query = """
        WOQL.and(
            WOQL.triple("v:Event", "ont:id", $event_id),
            WOQL.opt(WOQL.delete_triple("v:Event", "ont:retry_count", "v:OldCount")),
            WOQL.add_triple("v:Event", "ont:retry_count", $retry_count),
            WOQL.add_triple("v:Event", "ont:last_error", $error),
            WOQL.add_triple("v:Event", "ont:last_attempt", WOQL.datetime())
        )
        """
        
        await self.tdb.update(
            update_query,
            branch="_outbox",
            bindings={
                "event_id": event_id,
                "retry_count": retry_count,
                "error": error
            }
        )
    
    def get_resilience_metrics(self) -> Dict[str, Any]:
        """Get resilience metrics for this processor"""
        return {
            "circuit_breakers": {
                "nats": self.nats_cb.get_metrics(),
                "eventbridge": self.eventbridge_cb.get_metrics()
            },
            "retry_executors": {
                "nats": self.nats_retry_executor.get_metrics().__dict__,
                "eventbridge": self.eventbridge_retry_executor.get_metrics().__dict__
            },
            "retry_budget": self.retry_budget.get_metrics()
        }
    
    async def process_dead_letter_events(self, limit: int = 100) -> int:
        """Process dead letter events for manual retry"""
        query = """
        SELECT ?event ?id ?type ?payload ?created_at ?total_retries
        WHERE {
            ?event a ont:OutboxEvent .
            ?event ont:status "dead_letter" .
            ?event ont:id ?id .
            ?event ont:type ?type .
            ?event ont:payload ?payload .
            ?event ont:created_at ?created_at .
            ?event ont:total_retries ?total_retries .
        }
        ORDER BY ?created_at
        LIMIT $limit
        """
        
        events = await self.tdb.query(
            query,
            branch="_outbox",
            bindings={"limit": limit}
        )
        
        if not events:
            return 0
        
        # Reset events to pending for retry
        processed = 0
        for event in events:
            await self._reset_dead_letter_event(event["id"])
            processed += 1
        
        logger.info(f"Reset {processed} dead letter events for retry")
        return processed
    
    async def _reset_dead_letter_event(self, event_id: str):
        """Reset a dead letter event to pending status"""
        update_query = """
        WOQL.and(
            WOQL.triple("v:Event", "ont:id", $event_id),
            WOQL.delete_triple("v:Event", "ont:status", "dead_letter"),
            WOQL.add_triple("v:Event", "ont:status", "pending"),
            WOQL.add_triple("v:Event", "ont:reset_at", WOQL.datetime())
        )
        """
        
        await self.tdb.update(
            update_query,
            branch="_outbox",
            bindings={"event_id": event_id}
        )