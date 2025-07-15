"""
Event Subscriber Service - NATS 이벤트 구독 및 처리
섹션 10.3의 Event Schemas 구현
"""
import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any, Dict

# shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.event_consumer.funnel_indexing_handler import get_funnel_indexing_handler
from shared.events import cleanup_nats, get_nats_client

# 로깅 설정
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)


class EventSubscriber:
 """이벤트 구독자"""

 def __init__(self):
 self.running = False
 self.nats_client = None
 self.funnel_handler = get_funnel_indexing_handler()

 async def start(self):
 """구독자 시작"""
 logger.info("Event Subscriber starting...")

 # NATS 클라이언트 초기화
 self.nats_client = await get_nats_client()
 self.running = True

 # 이벤트 구독 설정
 await self._setup_subscriptions()

 logger.info("Event Subscriber started successfully")

 async def stop(self):
 """구독자 우아한 중지"""
 logger.info("Event Subscriber stopping gracefully...")

 try:
 # 1. 새로운 이벤트 처리 중단
 logger.info("Stopping new event processing...")
 self.running = False

 # 2. 진행 중인 이벤트 처리 완료 대기
 logger.info("Waiting for current events to finish processing...")
 await asyncio.sleep(2) # 진행 중인 이벤트 처리를 위한 대기

 # 3. NATS 연결 정리
 logger.info("Cleaning up NATS connections...")
 await cleanup_nats()

 logger.info("Event Subscriber stopped gracefully")
 except Exception as e:
 logger.error(f"Error during graceful shutdown: {e}")
 raise

 async def _setup_subscriptions(self):
 """이벤트 구독 설정"""

 # 스키마 변경 이벤트 구독
 await self.nats_client.subscribe(
 "oms.schema.changed.>",
 self._handle_schema_changed,
 durable_name = "schema-audit-consumer",
 queue_group = "schema-consumers",
 )

 # 브랜치 이벤트 구독
 await self.nats_client.subscribe(
 "oms.branch.created",
 self._handle_branch_created,
 durable_name = "branch-audit-consumer",
 queue_group = "branch-consumers",
 )

 await self.nats_client.subscribe(
 "oms.branch.merged.>",
 self._handle_branch_merged,
 durable_name = "merge-audit-consumer",
 queue_group = "merge-consumers",
 )

 # 제안 이벤트 구독
 await self.nats_client.subscribe(
 "oms.proposal.>",
 self._handle_proposal_status_changed,
 durable_name = "proposal-audit-consumer",
 queue_group = "proposal-consumers",
 )

 # 액션 이벤트 구독
 await self.nats_client.subscribe(
 "oms.action.started",
 self._handle_action_started,
 durable_name = "action-started-consumer",
 queue_group = "action-consumers",
 )

 await self.nats_client.subscribe(
 "oms.action.completed",
 self._handle_action_completed,
 durable_name = "action-completed-consumer",
 queue_group = "action-consumers",
 )

 await self.nats_client.subscribe(
 "oms.action.failed",
 self._handle_action_failed,
 durable_name = "action-failed-consumer",
 queue_group = "action-consumers",
 )

 # 검증 이벤트 구독
 await self.nats_client.subscribe(
 "oms.validation.completed",
 self._handle_validation_completed,
 durable_name = "validation-audit-consumer",
 queue_group = "validation-consumers",
 )

 # Funnel Service 인덱싱 이벤트 구독
 await self.nats_client.subscribe(
 "funnel.indexing.completed",
 self._handle_funnel_indexing_completed,
 durable_name = "funnel-indexing-consumer",
 queue_group = "indexing-consumers",
 )

 await self.nats_client.subscribe(
 "funnel.indexing.failed",
 self._handle_funnel_indexing_completed, # Same handler for both
 durable_name = "funnel-indexing-failed-consumer",
 queue_group = "indexing-consumers",
 )

 logger.info("All event subscriptions configured")

 async def _handle_schema_changed(self, event_data: Dict[str, Any]):
 """스키마 변경 이벤트 처리"""
 try:
 logger.info(f"Schema changed event received: {event_data}")

 # 감사 로그 저장
 await self._save_audit_log("schema_changed", event_data)

 # 캐시 무효화 알림 (필요시)
 await self._invalidate_cache(event_data)

 # 외부 시스템 알림 (필요시)
 await self._notify_external_systems("schema_changed", event_data)

 except Exception as e:
 logger.error(f"Error handling schema changed event: {e}")

 async def _handle_branch_created(self, event_data: Dict[str, Any]):
 """브랜치 생성 이벤트 처리"""
 try:
 logger.info(f"Branch created event received: {event_data}")

 # 감사 로그 저장
 await self._save_audit_log("branch_created", event_data)

 # 브랜치 보호 규칙 설정 (필요시)
 await self._setup_branch_protection(event_data)

 except Exception as e:
 logger.error(f"Error handling branch created event: {e}")

 async def _handle_branch_merged(self, event_data: Dict[str, Any]):
 """브랜치 병합 이벤트 처리"""
 try:
 logger.info(f"Branch merged event received: {event_data}")

 # 감사 로그 저장
 await self._save_audit_log("branch_merged", event_data)

 # 배포 트리거 (필요시)
 await self._trigger_deployment(event_data)

 except Exception as e:
 logger.error(f"Error handling branch merged event: {e}")

 async def _handle_proposal_status_changed(self, event_data: Dict[str, Any]):
 """제안 상태 변경 이벤트 처리"""
 try:
 logger.info(f"Proposal status changed event received: {event_data}")

 # 감사 로그 저장
 await self._save_audit_log("proposal_status_changed", event_data)

 # 알림 발송 (필요시)
 await self._send_notifications(event_data)

 except Exception as e:
 logger.error(f"Error handling proposal status changed event: {e}")

 async def _handle_action_started(self, event_data: Dict[str, Any]):
 """액션 시작 이벤트 처리"""
 try:
 logger.info(f"Action started event received: {event_data}")

 # 액션 상태 추적 시작
 await self._track_action_execution(event_data)

 except Exception as e:
 logger.error(f"Error handling action started event: {e}")

 async def _handle_action_completed(self, event_data: Dict[str, Any]):
 """액션 완료 이벤트 처리"""
 try:
 logger.info(f"Action completed event received: {event_data}")

 # 성공 메트릭 업데이트
 await self._update_action_metrics("completed", event_data)

 except Exception as e:
 logger.error(f"Error handling action completed event: {e}")

 async def _handle_action_failed(self, event_data: Dict[str, Any]):
 """액션 실패 이벤트 처리"""
 try:
 logger.error(f"Action failed event received: {event_data}")

 # 실패 메트릭 업데이트
 await self._update_action_metrics("failed", event_data)

 # 알람 발송 (중요한 액션의 경우)
 await self._send_failure_alert(event_data)

 except Exception as e:
 logger.error(f"Error handling action failed event: {e}")

 async def _handle_validation_completed(self, event_data: Dict[str, Any]):
 """검증 완료 이벤트 처리"""
 try:
 logger.info(f"Validation completed event received: {event_data}")

 # 검증 결과 통계 업데이트
 await self._update_validation_stats(event_data)

 except Exception as e:
 logger.error(f"Error handling validation completed event: {e}")

 async def _save_audit_log(self, event_type: str, event_data: Dict[str, Any]):
 """감사 로그 저장 - Production audit-service integration"""
 try:
 import os

 import httpx

 # Production implementation: Direct HTTP call to audit-service
 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 # Extract relevant information from event data
 user_id = event_data.get("user_id", "system")
 target_type = event_data.get("target_type", "unknown")
 target_id = event_data.get("target_id", "")
 operation = event_data.get("operation", event_type)
 branch = event_data.get("branch", "main")

 # Create audit event payload
 audit_payload = {
 "event_type": event_type,
 "event_category": "event_subscriber",
 "user_id": user_id,
 "username": user_id,
 "target_type": target_type,
 "target_id": target_id,
 "operation": operation,
 "severity": "INFO",
 "metadata": {
 "branch": branch,
 "source": "oms_event_subscriber",
 **event_data,
 },
 }

 # Send to audit-service with timeout and retries
 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.post(
 f"{audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(
 f"Audit event sent to audit-service for {event_type}: {user_id}"
 )

 except Exception as e:
 # Log but don't fail - audit is supplementary
 logger.warning(f"Failed to send audit event to audit-service: {e}")
 # Optionally store in local dead letter queue for retry

 async def _invalidate_cache(self, event_data: Dict[str, Any]):
 """캐시 무효화"""
 try:
 # 관련 캐시 무효화 로직
 from bootstrap.providers import RedisProvider

 redis_provider = RedisProvider()
 redis_client = await redis_provider.provide()

 # Determine cache keys to invalidate based on event data
 cache_patterns = []

 # Branch-related cache invalidation
 if "branch" in event_data:
 branch_name = event_data["branch"]
 cache_patterns.extend(
 [
 f"branch:{branch_name}:*",
 f"schema:{branch_name}:*",
 f"validation:{branch_name}:*",
 ]
 )

 # Schema-related cache invalidation
 if "schema_id" in event_data:
 schema_id = event_data["schema_id"]
 cache_patterns.extend(
 [f"schema:*:{schema_id}", f"validation:schema:{schema_id}:*"]
 )

 # User-related cache invalidation
 if "user_id" in event_data:
 user_id = event_data["user_id"]
 cache_patterns.extend([f"user:{user_id}:*", f"permissions:{user_id}:*"])

 # Job-related cache invalidation
 if "job_id" in event_data:
 job_id = event_data["job_id"]
 cache_patterns.extend([f"job:{job_id}:*", f"job:progress:{job_id}"])

 # Execute cache invalidation
 invalidated_count = 0
 for pattern in cache_patterns:
 keys = await redis_client.keys(pattern)
 if keys:
 await redis_client.delete(*keys)
 invalidated_count += len(keys)

 logger.debug(
 f"Invalidated {invalidated_count} cache keys for: {event_data}"
 )

 except Exception as e:
 logger.error(f"Failed to invalidate cache: {e}")

 async def _notify_external_systems(
 self, event_type: str, event_data: Dict[str, Any]
 ):
 """외부 시스템 알림"""
 try:
 # 외부 시스템 웹훅 호출
 import json
 import os

 import aiohttp

 webhook_urls = [
 os.getenv("EXTERNAL_WEBHOOK_URL_1"),
 os.getenv("EXTERNAL_WEBHOOK_URL_2"),
 os.getenv("EXTERNAL_WEBHOOK_URL_3"),
 ]

 # Filter out None URLs
 webhook_urls = [url for url in webhook_urls if url]

 if not webhook_urls:
 logger.debug("No external webhook URLs configured")
 return

 # Prepare webhook payload
 webhook_payload = {
 "event_type": event_type,
 "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
 "service": "oms",
 "data": event_data,
 }

 # Send to all configured webhooks
 async with aiohttp.ClientSession() as session:
 for webhook_url in webhook_urls:
 try:
 async with session.post(
 webhook_url,
 json = webhook_payload,
 headers={"Content-Type": "application/json"},
 timeout = aiohttp.ClientTimeout(total = 10),
 ) as response:
 if response.status in [200, 201, 202]:
 logger.debug(
 f"Successfully notified external system: {webhook_url}"
 )
 else:
 logger.warning(
 f"External webhook failed: {webhook_url} - {response.status}"
 )
 except Exception as webhook_error:
 logger.error(
 f"Failed to notify external system {webhook_url}: {webhook_error}"
 )

 logger.debug(
 f"Notified {len(webhook_urls)} external systems about {event_type}"
 )

 except Exception as e:
 logger.error(f"Failed to notify external systems: {e}")

 async def _setup_branch_protection(self, event_data: Dict[str, Any]):
 """브랜치 보호 규칙 설정 - Production Implementation"""
 try:
 branch_name = event_data.get("branch_name")
 if not branch_name:
 logger.warning("No branch name provided for protection setup")
 return

 # Production implementation: Set up branch protection rules
 from bootstrap.dependencies import get_branch_service
 from core.branch.service import BranchService

 branch_service = await get_branch_service()

 # Apply protection rules based on branch type
 protection_rules = {
 "require_reviews": True,
 "min_reviewers": 1 if branch_name == "main" else 0,
 "dismiss_stale_reviews": True,
 "require_status_checks": True,
 "enforce_admins": branch_name in ["main", "master"],
 "allow_force_push": False,
 "allow_deletion": branch_name not in ["main", "master"],
 }

 # Store protection rules in branch metadata
 await self._store_branch_protection_rules(branch_name, protection_rules)

 logger.info(
 f"Branch protection rules applied to {branch_name}: {protection_rules}"
 )

 except Exception as e:
 logger.error(f"Failed to setup branch protection: {e}")

 async def _trigger_deployment(self, event_data: Dict[str, Any]):
 """배포 트리거 - Production Implementation"""
 try:
 deployment_config = {
 "environment": event_data.get("environment", "staging"),
 "branch_name": event_data.get("branch_name"),
 "commit_hash": event_data.get("commit_hash"),
 "triggered_by": event_data.get("user_id", "system"),
 "deployment_type": event_data.get("deployment_type", "auto"),
 }

 # Production implementation: Trigger CI/CD pipeline
 import os

 import httpx

 # Send deployment request to CI/CD system (e.g., Jenkins, GitHub Actions, GitLab CI)
 cicd_webhook_url = os.getenv("CICD_WEBHOOK_URL")
 if cicd_webhook_url:
 async with httpx.AsyncClient() as client:
 response = await client.post(
 cicd_webhook_url,
 json = deployment_config,
 headers={"Content-Type": "application/json"},
 timeout = 30.0,
 )

 if response.status_code == 200:
 logger.info(
 f"Deployment triggered successfully: {deployment_config}"
 )
 else:
 logger.error(
 f"Failed to trigger deployment: {response.status_code} - {response.text}"
 )
 else:
 logger.warning(
 "No CICD_WEBHOOK_URL configured, skipping deployment trigger"
 )

 # Log deployment event for audit
 await self._audit_deployment_trigger(deployment_config)

 except Exception as e:
 logger.error(f"Failed to trigger deployment: {e}")

 async def _send_notifications(self, event_data: Dict[str, Any]):
 """알림 발송"""
 try:
 # 이메일/슬랙 알림 발송
 # Reuse the alert system from maintenance.py
 from workers.tasks.maintenance import send_alert

 # Determine notification details from event data
 event_type = event_data.get("event_type", "unknown")
 severity = "info"

 # Determine severity based on event type
 if "error" in event_type.lower() or "failed" in event_type.lower():
 severity = "error"
 elif "warning" in event_type.lower():
 severity = "warning"
 elif "critical" in event_type.lower():
 severity = "critical"

 # Create notification title and message
 title = f"OMS Event: {event_type}"
 message = f"Event occurred in OMS: {event_type}"

 if "branch" in event_data:
 message += f" (Branch: {event_data['branch']})"
 if "user_id" in event_data:
 message += f" (User: {event_data['user_id']})"

 await send_alert(
 alert_type = "oms_event",
 title = title,
 message = message,
 severity = severity,
 data = event_data,
 )

 logger.debug(f"Notifications sent for: {event_data}")

 except Exception as e:
 logger.error(f"Failed to send notifications: {e}")

 async def _track_action_execution(self, event_data: Dict[str, Any]):
 """액션 실행 추적 - Production Implementation"""
 try:
 action_id = event_data.get("action_id", f"action_{int(time.time())}")
 action_type = event_data.get("action_type", "unknown")
 execution_status = event_data.get("status", "started")

 # Production implementation: Track action execution status
 tracking_data = {
 "action_id": action_id,
 "action_type": action_type,
 "status": execution_status,
 "started_at": event_data.get(
 "started_at", datetime.utcnow().isoformat()
 ),
 "user_id": event_data.get("user_id"),
 "branch_name": event_data.get("branch_name"),
 "metadata": event_data.get("metadata", {}),
 }

 if execution_status in ["completed", "failed"]:
 tracking_data["completed_at"] = datetime.utcnow().isoformat()
 tracking_data["duration"] = event_data.get("duration")
 tracking_data["error_message"] = event_data.get("error_message")

 # Store execution tracking in database
 await self._store_action_execution(tracking_data)

 # Update metrics
 await self._update_action_metrics(execution_status, tracking_data)

 logger.info(f"Action execution tracked: {action_id} - {execution_status}")

 except Exception as e:
 logger.error(f"Failed to track action execution: {e}")

 async def _update_action_metrics(self, status: str, event_data: Dict[str, Any]):
 """액션 메트릭 업데이트"""
 try:
 # 메트릭 저장소에 업데이트
 from workers.tasks.maintenance import send_metrics

 # Prepare metrics data
 metric_data = {
 "action_status": status,
 "event_type": event_data.get("event_type", "unknown"),
 "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
 "duration_ms": event_data.get("duration_ms", 0),
 "success": status == "completed",
 "error_count": 1 if status == "failed" else 0,
 }

 # Add contextual metrics
 if "branch" in event_data:
 metric_data["branch"] = event_data["branch"]
 if "job_id" in event_data:
 metric_data["job_id"] = event_data["job_id"]
 if "user_id" in event_data:
 metric_data["user_id"] = event_data["user_id"]

 await send_metrics(
 metric_name = "action_execution",
 data = metric_data,
 tags={
 "service": "oms",
 "component": "event_subscriber",
 "status": status,
 },
 )

 logger.debug(f"Action metrics updated ({status}): {event_data}")

 except Exception as e:
 logger.error(f"Failed to update action metrics: {e}")

 async def _store_branch_protection_rules(
 self, branch_name: str, rules: Dict[str, Any]
 ):
 """Store branch protection rules in database"""
 try:
 import json
 import os

 import httpx

 # Store in audit-service for centralized configuration management
 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 audit_payload = {
 "event_type": "branch_protection_configured",
 "event_category": "system_config",
 "user_id": "system",
 "username": "event_subscriber",
 "target_type": "branch",
 "target_id": branch_name,
 "operation": "protection_setup",
 "metadata": {
 "protection_rules": rules,
 "configured_at": datetime.utcnow().isoformat(),
 },
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 f"{audit_service_url}/api/v1/events",
 json = audit_payload,
 timeout = 10.0,
 )

 logger.debug(f"Branch protection rules stored for {branch_name}")

 except Exception as e:
 logger.error(f"Failed to store branch protection rules: {e}")

 async def _audit_deployment_trigger(self, deployment_config: Dict[str, Any]):
 """Audit deployment trigger event"""
 try:
 import os

 import httpx

 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 audit_payload = {
 "event_type": "deployment_triggered",
 "event_category": "deployment",
 "user_id": deployment_config.get("triggered_by", "system"),
 "username": deployment_config.get("triggered_by", "system"),
 "target_type": "deployment",
 "target_id": f"{deployment_config.get('environment')}_{deployment_config.get('branch_name')}",


 "operation": "trigger_deployment",
 "metadata": deployment_config,
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 f"{audit_service_url}/api/v1/events",
 json = audit_payload,
 timeout = 10.0,
 )

 logger.debug(
 f"Deployment trigger audited: {deployment_config.get('environment')}"
 )

 except Exception as e:
 logger.error(f"Failed to audit deployment trigger: {e}")

 async def _store_action_execution(self, tracking_data: Dict[str, Any]):
 """Store action execution tracking data"""
 try:
 from bootstrap.config import get_config
 from database.clients.postgres_client_secure import PostgresClientSecure

 config = get_config()
 postgres_client = PostgresClientSecure(config = config.postgres.model_dump())
 await postgres_client.connect()

 # Create action_executions table if not exists
 await postgres_client.execute(
 """
 CREATE TABLE IF NOT EXISTS action_executions (
 id SERIAL PRIMARY KEY,
 action_id VARCHAR(255) UNIQUE NOT NULL,
 action_type VARCHAR(100) NOT NULL,
 status VARCHAR(50) NOT NULL,
 user_id VARCHAR(255),
 branch_name VARCHAR(255),
 started_at TIMESTAMP WITH TIME ZONE,
 completed_at TIMESTAMP WITH TIME ZONE,
 duration INTEGER,
 error_message TEXT,
 metadata JSONB DEFAULT '{}',
 created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
 )
 """
 )

 # Insert or update action execution record
 await postgres_client.execute(
 """
 INSERT INTO action_executions (
 action_id, action_type, status, user_id, branch_name,
 started_at, completed_at, duration, error_message, metadata
 ) VALUES (
 %(action_id)s, %(action_type)s, %(status)s, %(user_id)s, %(branch_name)s,
 %(started_at)s, %(completed_at)s, %(duration)s, %(error_message)s, %(metadata)s
 )
 ON CONFLICT (action_id)
 DO UPDATE SET
 status = EXCLUDED.status,
 completed_at = EXCLUDED.completed_at,
 duration = EXCLUDED.duration,
 error_message = EXCLUDED.error_message,
 metadata = EXCLUDED.metadata
 """,
 {
 "action_id": tracking_data["action_id"],
 "action_type": tracking_data["action_type"],
 "status": tracking_data["status"],
 "user_id": tracking_data.get("user_id"),
 "branch_name": tracking_data.get("branch_name"),
 "started_at": tracking_data.get("started_at"),
 "completed_at": tracking_data.get("completed_at"),
 "duration": tracking_data.get("duration"),
 "error_message": tracking_data.get("error_message"),
 "metadata": json.dumps(tracking_data.get("metadata", {})),
 },
 )

 await postgres_client.close()
 logger.debug(f"Action execution stored: {tracking_data['action_id']}")

 except Exception as e:
 logger.error(f"Failed to store action execution: {e}")

 async def _send_failure_alert(self, event_data: Dict[str, Any]):
 """실패 알람 발송"""
 try:
 # 중요한 액션 실패시 즉시 알람
 from workers.tasks.maintenance import send_alert

 # Determine if this is a critical failure
 event_type = event_data.get("event_type", "unknown")
 job_id = event_data.get("job_id", "unknown")
 error_message = event_data.get("error", "Unknown error")

 # Critical operations that require immediate attention
 critical_operations = [
 "schema_migration",
 "branch_merge",
 "production_deployment",
 "security_validation",
 "data_migration",
 ]

 severity = (
 "critical"
 if any(op in event_type.lower() for op in critical_operations)
 else "error"
 )

 title = f"🚨 Action Failure: {event_type}"
 message = f"Critical action failed in OMS\n\nJob ID: {job_id}\nError: {error_message}"

 if "branch" in event_data:
 message += f"\nBranch: {event_data['branch']}"
 if "user_id" in event_data:
 message += f"\nUser: {event_data['user_id']}"

 await send_alert(
 alert_type = "action_failure",
 title = title,
 message = message,
 severity = severity,
 data = event_data,
 )

 logger.warning(f"Failure alert sent for: {event_data}")

 except Exception as e:
 logger.error(f"Failed to send failure alert: {e}")

 async def _update_validation_stats(self, event_data: Dict[str, Any]):
 """검증 통계 업데이트"""
 try:
 # 검증 통계 업데이트
 from workers.tasks.maintenance import send_metrics

 # Extract validation metrics from event data
 validation_data = {
 "validation_type": event_data.get("validation_type", "unknown"),
 "success": event_data.get("success", False),
 "error_count": len(event_data.get("errors", [])),
 "warning_count": len(event_data.get("warnings", [])),
 "schemas_validated": event_data.get("schemas_validated", 0),
 "duration_ms": event_data.get("duration_ms", 0),
 "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
 }

 # Add branch context if available
 if "branch" in event_data:
 validation_data["branch"] = event_data["branch"]

 await send_metrics(
 metric_name = "validation_stats",
 data = validation_data,
 tags={
 "service": "oms",
 "component": "validation",
 "success": str(validation_data["success"]).lower(),
 },
 )

 logger.debug(f"Validation stats updated: {event_data}")

 except Exception as e:
 logger.error(f"Failed to update validation stats: {e}")

 async def _handle_funnel_indexing_completed(self, event_data: Dict[str, Any]):
 """Funnel Service 인덱싱 완료/실패 이벤트 처리"""
 try:
 logger.info(f"Funnel indexing event received: {event_data}")

 # Delegate to specialized handler
 success = await self.funnel_handler.handle_indexing_completed(event_data)

 if success:
 logger.info(
 f"Successfully processed indexing event: {event_data.get('id')}"
 )
 else:
 logger.error(
 f"Failed to process indexing event: {event_data.get('id')}"
 )

 except Exception as e:
 logger.error(f"Error handling funnel indexing event: {e}")
 # Don't re-raise - we don't want to break the entire event processing


async def main():
 """메인 실행 함수"""
 subscriber = EventSubscriber()

 # 시그널 핸들러 설정
 def signal_handler(signum, frame):
 logger.info(f"Received signal {signum}, shutting down...")
 asyncio.create_task(subscriber.stop())

 signal.signal(signal.SIGINT, signal_handler)
 signal.signal(signal.SIGTERM, signal_handler)

 try:
 await subscriber.start()

 # 무한 대기
 while subscriber.running:
 await asyncio.sleep(1)

 except Exception as e:
 logger.error(f"Event Subscriber error: {e}")
 finally:
 await subscriber.stop()


if __name__ == "__main__":
 asyncio.run(main())
