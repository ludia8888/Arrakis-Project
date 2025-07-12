"""
Event sink implementations for commit hook pipeline
"""
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseSink, DiffContext

# Import existing event publishers
from core.event_publisher.unified_publisher import UnifiedPublisher
from core.event_publisher.nats_backend import NATSBackend
from shared.audit_client import get_audit_client, AuditEvent

logger = logging.getLogger(__name__)


class NATSSink(BaseSink):
    """Publish events to NATS"""
    
    def __init__(self):
        self.publisher = None
        self.topic_prefix = os.getenv("NATS_TOPIC_PREFIX", "terminus.commit")
    
    @property
    def name(self) -> str:
        return "NATSSink"
    
    @property
    def enabled(self) -> bool:
        return os.getenv("ENABLE_NATS_EVENTS", "true").lower() == "true"
    
    async def initialize(self):
        """Initialize NATS connection via UnifiedPublisher"""
        try:
            # Use UnifiedPublisher for proper event publishing
            self.publisher = UnifiedPublisher()
            
            # Configure NATS backend
            nats_config = {
                "url": os.getenv("NATS_URL", "nats://nats:4222"),
                "max_reconnect_attempts": int(os.getenv("NATS_MAX_RECONNECT", "10")),
                "reconnect_time_wait": float(os.getenv("NATS_RECONNECT_WAIT", "2.0")),
                "connect_timeout": float(os.getenv("NATS_CONNECT_TIMEOUT", "10.0"))
            }
            
            # Initialize with fallback support
            try:
                await self.publisher.initialize(backend_type="nats", config=nats_config)
                logger.info(f"UnifiedPublisher initialized with NATS backend: {nats_config['url']}")
            except Exception as nats_error:
                logger.warning(f"NATS initialization failed: {nats_error}, falling back to in-memory")
                # Fallback to in-memory backend for development/testing
                await self.publisher.initialize(backend_type="memory", config={})
                logger.info("UnifiedPublisher initialized with in-memory backend")
                
        except Exception as e:
            logger.error(f"Failed to initialize UnifiedPublisher: {e}")
            # Final fallback: direct NATS backend
            try:
                self.publisher = NATSBackend(
                    url=os.getenv("NATS_URL", "nats://nats:4222")
                )
                await self.publisher.connect()
                logger.info("Fallback NATS backend initialized")
            except Exception as fallback_error:
                logger.error(f"All publisher initialization failed: {fallback_error}")
                self.publisher = None
    
    async def publish(self, context: DiffContext) -> None:
        """Publish commit event to NATS"""
        if not self.publisher:
            logger.warning("NATS publisher not initialized, skipping event")
            return
        
        try:
            # Build event payload
            event = {
                "type": "commit",
                "database": context.meta.database,
                "branch": context.meta.branch,
                "commit_id": context.meta.commit_id,
                "author": context.meta.author,
                "message": context.meta.commit_msg,
                "trace_id": context.meta.trace_id,
                "timestamp": datetime.utcnow().isoformat(),
                "diff": context.diff,
                "affected_types": context.affected_types or [],
                "affected_ids": context.affected_ids or []
            }
            
            # Determine topic based on branch
            env, service, purpose = context.meta.branch.split("/", 2)
            topic = f"{self.topic_prefix}.{env}.{service}"
            
            # Publish with headers
            headers = {
                "trace-id": context.meta.trace_id,
                "author": context.meta.author,
                "branch": context.meta.branch
            }
            
            await self.publisher.publish(
                topic=topic,
                message=event,
                headers=headers
            )
            
            logger.debug(f"Published commit event to {topic}")
            
        except Exception as e:
            logger.error(f"Failed to publish to NATS: {e}")
            # Don't raise - sinks should not fail commits


class AuditSink(BaseSink):
    """Record audit events for commits"""
    
    def __init__(self):
        self.audit_db = os.getenv("AUDIT_DATABASE", "audit_logs.db")
    
    @property
    def name(self) -> str:
        return "AuditSink"
    
    @property
    def enabled(self) -> bool:
        return os.getenv("ENABLE_AUDIT", "true").lower() == "true"
    
    async def publish(self, context: DiffContext) -> None:
        """Record audit event"""
        try:
            # Map commit operation to audit action
            action = "WRITE"
            if context.before and not context.after:
                action = "DELETE"
            elif not context.before and context.after:
                action = "CREATE"
            elif context.before and context.after:
                action = "UPDATE"
            
            # Build audit event using new audit client
            author_parts = context.meta.author.split("@")
            user_id = author_parts[0]
            username = author_parts[0] if len(author_parts) == 1 else f"{author_parts[0]}@{author_parts[1]}"
            
            audit_event = AuditEvent(
                event_type="DATA_COMMIT",
                event_category="DATA_MANAGEMENT",
                user_id=user_id,
                username=username,
                target_type="DOCUMENT",
                target_id=context.meta.commit_id or "unknown",
                operation=action,
                severity="INFO",
                branch=context.meta.branch,
                commit_id=context.meta.commit_id,
                terminus_db=context.meta.database,
                request_id=context.meta.trace_id,
                metadata={
                    "commit_message": context.meta.commit_msg,
                    "affected_types": context.affected_types,
                    "affected_ids": context.affected_ids,
                    "source": "data_kernel_hook"
                }
            )
            
            # Use audit service client
            client = await get_audit_client()
            await client.record_event(audit_event)
            
            logger.debug(f"Recorded audit event for {action} by {context.meta.author}")
            
        except Exception as e:
            logger.error(f"Failed to record audit event: {e}")


class WebhookSink(BaseSink):
    """Send webhooks for commits"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("COMMIT_WEBHOOK_URL")
        self.timeout = int(os.getenv("WEBHOOK_TIMEOUT", "5"))
    
    @property
    def name(self) -> str:
        return "WebhookSink"
    
    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)
    
    async def publish(self, context: DiffContext) -> None:
        """Send webhook notification"""
        if not self.webhook_url:
            return
        
        try:
            import httpx
            
            payload = {
                "event": "terminus.commit",
                "database": context.meta.database,
                "branch": context.meta.branch,
                "commit": {
                    "id": context.meta.commit_id,
                    "author": context.meta.author,
                    "message": context.meta.commit_msg,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "summary": {
                    "affected_types": context.affected_types or [],
                    "affected_ids": context.affected_ids or [],
                    "changes": len(context.diff) if isinstance(context.diff, dict) else 0
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "X-Trace-ID": context.meta.trace_id,
                        "X-Event-Type": "terminus.commit"
                    },
                    timeout=self.timeout
                )
                
                if response.status_code >= 400:
                    logger.warning(f"Webhook returned {response.status_code}")
                else:
                    logger.debug(f"Webhook sent successfully to {self.webhook_url}")
                    
        except asyncio.TimeoutError:
            logger.warning(f"Webhook timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")


class MetricsSink(BaseSink):
    """Record metrics for commits"""
    
    def __init__(self):
        self.metrics_enabled = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    @property
    def name(self) -> str:
        return "MetricsSink"
    
    @property
    def enabled(self) -> bool:
        return self.metrics_enabled
    
    async def publish(self, context: DiffContext) -> None:
        """Record commit metrics"""
        try:
            from prometheus_client import Counter, Histogram
            
            # Define metrics
            commit_counter = Counter(
                'terminus_commits_total',
                'Total number of commits',
                ['database', 'branch', 'author']
            )
            
            commit_size = Histogram(
                'terminus_commit_size_bytes',
                'Size of commit diffs in bytes',
                ['database', 'branch']
            )
            
            # Record metrics
            env, service, _ = context.meta.branch.split("/", 2)
            
            commit_counter.labels(
                database=context.meta.database or "unknown",
                branch=f"{env}/{service}",
                author=context.meta.author.split("@")[1] if "@" in context.meta.author else "unknown"
            ).inc()
            
            # Estimate diff size
            diff_size = len(json.dumps(context.diff))
            commit_size.labels(
                database=context.meta.database or "unknown",
                branch=f"{env}/{service}"
            ).observe(diff_size)
            
            logger.debug(f"Recorded metrics for commit {context.meta.commit_id}")
            
        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")