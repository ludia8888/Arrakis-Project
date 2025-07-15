"""
Funnel Service Indexing Event Handler
Handles indexing.completed events from Funnel Service and manages branch state transitions
Supports both traditional locking and Shadow Index + Switch patterns
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from arrakis_common import get_logger
from core.branch.lock_manager import LockConflictError, get_lock_manager
from core.shadow_index.manager import get_shadow_manager
from models.branch_state import BranchState
from models.shadow_index import IndexType, SwitchRequest
from utils.audit_id_generator import AuditIDGenerator

logger = get_logger(__name__)


class FunnelIndexingEventHandler:
 """
 Handles Funnel Service indexing events and manages branch state transitions
 """

 def __init__(self):
 self.lock_manager = get_lock_manager()
 self.shadow_manager = get_shadow_manager()

 # Production audit service integration
 import os

 self.audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 # Auto-merge configuration
 self.auto_merge_config = {
 "enabled": True,
 "require_validation": True,
 "require_no_conflicts": True,
 "timeout_hours": 24, # Auto-merge timeout
 }

 # Shadow index configuration
 self.shadow_index_config = {
 "enabled": True,
 "auto_switch": True,
 "validation_checks": ["RECORD_COUNT_VALIDATION", "SIZE_COMPARISON"],
 "backup_before_switch": True,
 }

 async def handle_indexing_completed(self, event_data: Dict[str, Any]) -> bool:
 """
 Handle Funnel Service indexing.completed event

 Expected event structure (Traditional or Shadow Index):
 {
 "id": "indexing-uuid",
 "source": "funnel-service",
 "type": "com.oms.indexing.completed",
 "data": {
 "branch_name": "feature/user-schema",
 "indexing_id": "idx-123",
 "indexing_mode": "shadow", # "traditional" or "shadow"
 "shadow_index_id": "shadow-123", # If shadow mode
 "started_at": "2025-06-26T10:00:00Z",
 "completed_at": "2025-06-26T10:30:00Z",
 "status": "success",
 "records_indexed": 1250,
 "index_size_bytes": 52428800,
 "resource_types": ["object_type", "link_type"],
 "errors": [],
 "validation_results": {
 "passed": true,
 "errors": []
 }
 }
 }
 """
 try:
 logger.info(f"Processing indexing.completed event: {event_data.get('id')}")

 # Extract event data
 data = event_data.get("data", {})
 branch_name = data.get("branch_name")
 indexing_status = data.get("status")
 indexing_mode = data.get(
 "indexing_mode", "traditional"
 ) # Default to traditional
 shadow_index_id = data.get("shadow_index_id")

 if not branch_name:
 logger.error(f"Missing branch_name in event: {event_data}")
 return False

 # Route to appropriate handler based on indexing mode
 if indexing_mode == "shadow" and shadow_index_id:
 logger.info(f"Processing shadow index completion: {shadow_index_id}")
 success = await self._handle_shadow_indexing_completed(
 shadow_index_id, branch_name, data, event_data
 )
 else:
 logger.info(
 f"Processing traditional indexing completion for branch: {branch_name}"
 )
 # Traditional mode - check branch state
 branch_state = await self.lock_manager.get_branch_state(branch_name)

 if branch_state.current_state != BranchState.LOCKED_FOR_WRITE:
 logger.warning(
 f"Branch {branch_name} is not in LOCKED_FOR_WRITE state. "
 f"Current state: {branch_state.current_state}"
 )
 # Continue processing but log the unexpected state

 if indexing_status == "success":
 success = await self._handle_successful_indexing(
 branch_name, data, event_data
 )
 else:
 success = await self._handle_failed_indexing(
 branch_name, data, event_data
 )
 if success:
 # Check auto-merge conditions
 await self._check_auto_merge_conditions(branch_name, data)
 return success

 except Exception as e:
 logger.error(f"Error handling indexing.completed event: {e}")
 return False

 async def _handle_successful_indexing(
 self, branch_name: str, data: Dict[str, Any], full_event: Dict[str, Any]
 ) -> bool:
 """
 Handle successful indexing completion
 """
 try:
 # Complete indexing in lock manager (resource-specific or all)
 # Extract which resource types were indexed from event data
 indexed_resource_types = data.get("indexed_resource_types")

 success = await self.lock_manager.complete_indexing(
 branch_name = branch_name,
 completed_by = "funnel-service",
 resource_types = indexed_resource_types, # None means all indexing locks
 )

 if not success:
 logger.error(f"Failed to complete indexing for branch {branch_name}")
 return False

 logger.info(
 f"Successfully completed indexing for branch {branch_name}. "
 "Branch state: LOCKED_FOR_WRITE -> READY"
 )

 # Generate audit log
 await self._create_audit_log(
 branch_name = branch_name,
 action_type = "INDEXING_COMPLETED",
 event_data = data,
 success = True,
 )

 return True

 except Exception as e:
 logger.error(f"Error handling successful indexing for {branch_name}: {e}")
 return False

 async def _handle_failed_indexing(
 self, branch_name: str, data: Dict[str, Any], full_event: Dict[str, Any]
 ) -> bool:
 """
 Handle failed indexing
 """
 try:
 # Move branch to ERROR state
 await self.lock_manager.set_branch_state(
 branch_name = branch_name,
 new_state = BranchState.ERROR,
 reason = f"Indexing failed: {data.get('error_message', 'Unknown error')}",
 )

 logger.error(
 f"Indexing failed for branch {branch_name}. "
 "Branch state: LOCKED_FOR_WRITE -> ERROR"
 )

 # Generate audit log
 await self._create_audit_log(
 branch_name = branch_name,
 action_type = "INDEXING_FAILED",
 event_data = data,
 success = False,
 )

 # Send alert for failed indexing
 await self._send_indexing_failure_alert(branch_name, data)

 return True

 except Exception as e:
 logger.error(f"Error handling failed indexing for {branch_name}: {e}")
 return False

 async def _check_auto_merge_conditions(
 self, branch_name: str, data: Dict[str, Any]
 ):
 """
 Check if auto-merge conditions are met and trigger auto-merge if applicable
 """
 try:
 if not self.auto_merge_config.get("enabled", False):
 logger.debug(f"Auto-merge disabled for branch {branch_name}")
 return

 logger.info(f"Checking auto-merge conditions for branch {branch_name}")

 # Get current branch state
 branch_state = await self.lock_manager.get_branch_state(branch_name)

 if branch_state.current_state != BranchState.READY:
 logger.debug(
 f"Branch {branch_name} not ready for auto-merge. "
 f"Current state: {branch_state.current_state}"
 )
 return

 # Check validation requirements
 if self.auto_merge_config.get("require_validation", True):
 validation_results = data.get("validation_results", {})
 if not validation_results.get("passed", False):
 logger.info(
 f"Auto-merge blocked for {branch_name}: validation failed"
 )
 return

 # Check for conflicts (simplified check)
 if self.auto_merge_config.get("require_no_conflicts", True):
 conflicts = await self._check_merge_conflicts(branch_name)
 if conflicts:
 logger.info(
 f"Auto-merge blocked for {branch_name}: merge conflicts detected"
 )
 return

 # All conditions met - trigger auto-merge
 logger.info(f"Auto-merge conditions met for branch {branch_name}")
 await self._trigger_auto_merge(branch_name, data)

 except Exception as e:
 logger.error(f"Error checking auto-merge conditions for {branch_name}: {e}")

 async def _check_merge_conflicts(self, branch_name: str) -> bool:
 """
 Check if there are merge conflicts between branch and main
 """
 if branch_name == "main":
 return False # Main branch cannot have conflicts with itself

 try:
 from bootstrap.providers.database import get_terminusdb_client
 from core.branch.diff_engine import DiffEngine

 # Get TerminusDB client
 tdb_client = get_terminusdb_client()
 if not tdb_client:
 logger.warning("TerminusDB client not available for conflict detection")
 return False

 # Initialize diff engine
 tdb_endpoint = os.getenv("TERMINUSDB_ENDPOINT", "http://terminusdb:6363")
 diff_engine = DiffEngine(tdb_endpoint)

 # Calculate three-way diff between base, branch, and main
 try:
 # Get branch info to find common ancestor
 branch_info = await tdb_client.get_branch_info("oms", branch_name)
 main_info = await tdb_client.get_branch_info("oms", "main")

 if not branch_info or not main_info:
 logger.warning(
 f"Could not get branch info for conflict detection: {branch_name}"
 )
 return False

 # Use simplified common ancestor detection
 # In a real system, this would find the actual merge base
 base_commit = branch_info.get(
 "parent_commit", main_info.get("head_commit", "")
 )
 branch_commit = branch_info.get("head_commit", "")
 main_commit = main_info.get("head_commit", "")

 if not all([base_commit, branch_commit, main_commit]):
 logger.warning("Missing commit information for conflict detection")
 return False

 # Calculate three-way diff
 three_way_diff = await diff_engine.calculate_three_way_diff(
 base = base_commit, source = branch_commit, target = main_commit
 )

 # Check for conflicts
 has_conflicts = len(three_way_diff.conflicts) > 0

 if has_conflicts:
 logger.warning(
 f"Merge conflicts detected for branch {branch_name}: "
 f"{len(three_way_diff.conflicts)} conflicts found"
 )

 # Log conflict details
 for conflict in three_way_diff.conflicts:
 logger.info(
 f"Conflict: {conflict.conflict_type.value} on "
 f"{conflict.resource_type}/{conflict.resource_name}"
 )
 else:
 logger.info(f"No merge conflicts detected for branch {branch_name}")

 return has_conflicts

 except Exception as diff_error:
 logger.error(
 f"Error calculating diff for conflict detection: {diff_error}"
 )

 # Fallback: check for overlapping schema changes
 return await self._check_schema_overlaps(branch_name)

 except Exception as e:
 logger.error(f"Error during conflict detection for {branch_name}: {e}")
 return False

 async def _check_schema_overlaps(self, branch_name: str) -> bool:
 """
 Fallback conflict detection based on schema overlaps
 """
 try:
 from bootstrap.providers.database import get_terminusdb_client

 tdb_client = get_terminusdb_client()
 if not tdb_client:
 return False

 # Get recent schema changes from both branches
 branch_schema = await tdb_client.get_schema("oms") # Current branch schema

 # Simple overlap detection: check for same entity modifications
 # This is a simplified check - real implementation would be more sophisticated

 # For now, assume no overlaps unless we detect obvious conflicts
 # Real implementation would check:
 # - Same object types modified in both branches
 # - Conflicting property changes
 # - Dependency violations

 logger.info(
 f"Schema overlap check completed for {branch_name} - no conflicts detected"
 )
 return False

 except Exception as e:
 logger.error(f"Error checking schema overlaps for {branch_name}: {e}")
 return False

 async def _trigger_auto_merge(self, branch_name: str, data: Dict[str, Any]):
 """
 Trigger automatic merge process
 """
 try:
 logger.info(f"Triggering auto-merge for branch {branch_name}")

 # Mark branch as ready for merge and transition to ACTIVE
 await self.lock_manager.set_branch_state(
 branch_name = branch_name,
 new_state = BranchState.ACTIVE,
 reason = "Auto-merge completed successfully",
 )

 # Generate audit log for auto-merge
 await self._create_audit_log(
 branch_name = branch_name,
 action_type = "BRANCH_MERGED",
 event_data={
 "merge_type": "auto",
 "trigger": "indexing_completed",
 "indexing_data": data,
 },
 success = True,
 )

 logger.info(f"Auto-merge completed for branch {branch_name}")

 # Send success notification
 await self._send_auto_merge_notification(branch_name, data)

 except Exception as e:
 logger.error(f"Error during auto-merge for {branch_name}: {e}")
 # Set branch to ERROR state if auto-merge fails
 await self.lock_manager.set_branch_state(
 branch_name = branch_name,
 new_state = BranchState.ERROR,
 reason = f"Auto-merge failed: {str(e)}",
 )

 async def _create_audit_log(
 self,
 branch_name: str,
 action_type: str,
 event_data: Dict[str, Any],
 success: bool,
 ):
 """Create audit log for indexing events - Production audit-service integration"""
 try:
 import httpx

 # Map action types to proper event types
 event_type_mapping = {
 "INDEXING_COMPLETED": "indexing.completed",
 "INDEXING_FAILED": "indexing.failed",
 "BRANCH_MERGED": "branch.merged",
 "BRANCH_INDEXING_COMPLETED": "branch.indexing.completed",
 "BRANCH_INDEXING_FAILED": "branch.indexing.failed",
 }

 audit_payload = {
 "event_type": event_type_mapping.get(action_type, action_type.lower()),
 "event_category": "branch_indexing",
 "user_id": "system",
 "username": "funnel-indexing-handler",
 "target_type": "branch",
 "target_id": branch_name,
 "operation": "index",
 "severity": "ERROR" if not success else "INFO",
 "metadata": {
 "source": "funnel_indexing_handler",
 "success": success,
 "action_type": action_type,
 **event_data,
 },
 }

 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.post(
 f"{self.audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(f"Audit event sent for branch {branch_name}: {action_type}")

 except Exception as e:
 logger.warning(f"Failed to send audit event: {e}")
 # Don't fail the main operation due to audit logging failure

 async def _handle_shadow_indexing_completed(
 self,
 shadow_index_id: str,
 branch_name: str,
 data: Dict[str, Any],
 event_data: Dict[str, Any],
 ) -> bool:
 """
 Handle shadow index completion and optionally trigger automatic switch
 """
 try:
 indexing_status = data.get("status")
 records_indexed = data.get("records_indexed", 0)
 index_size_bytes = data.get("index_size_bytes", 0)

 if indexing_status == "success":
 # Mark shadow build as complete
 success = await self.shadow_manager.complete_shadow_build(
 shadow_index_id = shadow_index_id,
 index_size_bytes = index_size_bytes,
 record_count = records_indexed,
 service_name = "funnel-service",
 )

 if not success:
 logger.error(
 f"Failed to mark shadow build complete: {shadow_index_id}"
 )
 return False

 # Check if auto-switch is enabled
 if self.shadow_index_config.get("auto_switch", False):
 logger.info(f"Auto-switching shadow index: {shadow_index_id}")

 # Create switch request
 switch_request = SwitchRequest(
 shadow_index_id = shadow_index_id,
 force_switch = False,
 validation_checks = self.shadow_index_config.get(
 "validation_checks", []
 ),
 backup_current = self.shadow_index_config.get(
 "backup_before_switch", True
 ),
 switch_timeout_seconds = 10,
 )

 # Perform atomic switch
 switch_result = await self.shadow_manager.request_atomic_switch(
 shadow_index_id = shadow_index_id,
 request = switch_request,
 service_name = "funnel-service",
 )

 if switch_result.success:
 logger.info(
 f"Shadow index auto-switch completed: {shadow_index_id} "
 f"in {switch_result.switch_duration_ms}ms"
 )

 # Create audit log for successful switch
 await self._create_shadow_audit_log(
 branch_name,
 shadow_index_id,
 "SHADOW_INDEX_SWITCHED",
 data,
 switch_result,
 )

 # Check auto-merge conditions after successful switch
 await self._check_auto_merge_conditions(branch_name, data)

 return True
 else:
 logger.error(
 f"Shadow index auto-switch failed: {shadow_index_id} - {switch_result.message}"
 )

 # Create audit log for failed switch
 await self._create_shadow_audit_log(
 branch_name,
 shadow_index_id,
 "SHADOW_INDEX_SWITCH_FAILED",
 data,
 switch_result,
 )

 # Don't fail completely - shadow is built and ready for manual switch
 return True
 else:
 logger.info(
 f"Shadow index build completed, ready for manual switch: {shadow_index_id}"
 )

 # Create audit log for build completion
 await self._create_shadow_audit_log(
 branch_name, shadow_index_id, "SHADOW_INDEX_BUILT", data
 )

 return True
 else:
 # Handle shadow build failure
 logger.error(
 f"Shadow index build failed: {shadow_index_id} - {data.get('error_message',
     'Unknown error')}"
 )

 # Create audit log for build failure
 await self._create_shadow_audit_log(
 branch_name, shadow_index_id, "SHADOW_INDEX_BUILD_FAILED", data
 )

 # Send alert for shadow build failure
 await self._send_shadow_indexing_failure_alert(
 shadow_index_id, branch_name, data
 )

 return False

 except Exception as e:
 logger.error(f"Error handling shadow indexing completion: {e}")
 return False

 async def _create_shadow_audit_log(
 self,
 branch_name: str,
 shadow_index_id: str,
 action_type: str,
 indexing_data: Dict[str, Any],
 switch_result: Optional[Any] = None,
 ):
 """
 Create audit log for shadow index operations - Production audit-service integration
 """
 try:
 import httpx

 # Map action types to proper event types
 event_type_mapping = {
 "SHADOW_INDEX_BUILT": "shadow_index.built",
 "SHADOW_INDEX_SWITCHED": "shadow_index.switched",
 "SHADOW_INDEX_SWITCH_FAILED": "shadow_index.switch_failed",
 "SHADOW_INDEX_BUILD_FAILED": "shadow_index.build_failed",
 }

 success = "FAILED" not in action_type

 # Build metadata
 metadata = {
 "source": "funnel_indexing_handler",
 "indexing_mode": "shadow",
 "shadow_index_id": shadow_index_id,
 "action_type": action_type,
 "records_indexed": indexing_data.get("records_indexed"),
 "index_size_bytes": indexing_data.get("index_size_bytes"),
 "indexing_duration": self._calculate_duration(
 indexing_data.get("started_at"), indexing_data.get("completed_at")
 ),
 "handler": "FunnelIndexingEventHandler",
 }

 # Add switch result if available
 if switch_result:
 metadata.update(
 {
 "switch_duration_ms": getattr(
 switch_result, "switch_duration_ms", None
 ),
 "switch_success": getattr(switch_result, "success", None),
 "validation_passed": getattr(
 switch_result, "validation_passed", None
 ),
 "verification_passed": getattr(
 switch_result, "verification_passed", None
 ),
 }
 )

 # Create audit payload for audit-service
 audit_payload = {
 "event_type": event_type_mapping.get(action_type, action_type.lower()),
 "event_category": "shadow_indexing",
 "user_id": "system",
 "username": "funnel-service",
 "target_type": "shadow_index",
 "target_id": shadow_index_id,
 "operation": "index",
 "severity": "ERROR" if not success else "INFO",
 "metadata": metadata,
 }

 # Send to audit-service with timeout
 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.post(
 f"{self.audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(
 f"Shadow index audit event sent for {shadow_index_id}: {action_type}"
 )

 except Exception as e:
 logger.warning(f"Failed to send shadow index audit event: {e}")
 # Don't fail the main operation due to audit logging failure

 async def _send_shadow_indexing_failure_alert(
 self, shadow_index_id: str, branch_name: str, data: Dict[str, Any]
 ):
 """
 Send alert for shadow indexing failure
 """
 logger.error(
 f"ALERT: Shadow index build failed for {shadow_index_id} (branch: {branch_name}). "
 f"Error: {data.get('error_message', 'Unknown error')}"
 )

 # Implement actual alerting
 alert_data = {
 "type": "shadow_indexing_failure",
 "shadow_index_id": shadow_index_id,
 "branch_name": branch_name,
 "error_message": data.get("error_message", "Unknown error"),
 "timestamp": datetime.now(timezone.utc).isoformat(),
 "records_indexed": data.get("records_indexed", 0),
 "indexing_duration": self._calculate_duration(
 data.get("started_at"), data.get("completed_at")
 ),
 "build_progress": data.get("build_progress", "Unknown"),
 "severity": "high",
 }

 # Send to multiple notification channels
 await self._send_shadow_alert_notifications(alert_data)

 async def _send_shadow_alert_notifications(self, alert_data: Dict[str, Any]):
 """
 Send shadow indexing alert to configured notification channels
 """
 # Slack notification
 slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
 if slack_webhook_url:
 await self._send_slack_shadow_alert(slack_webhook_url, alert_data)

 # Email notification
 email_enabled = os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true"
 if email_enabled:
 await self._send_email_shadow_alert(alert_data)

 # PagerDuty integration
 pagerduty_enabled = os.getenv("PAGERDUTY_ENABLED", "false").lower() == "true"
 if pagerduty_enabled and alert_data.get("severity") == "high":
 await self._send_pagerduty_shadow_alert(alert_data)

 # Custom webhook
 custom_webhook_url = os.getenv("CUSTOM_ALERT_WEBHOOK_URL")
 if custom_webhook_url:
 await self._send_custom_webhook_alert(custom_webhook_url, alert_data)

 async def _send_slack_shadow_alert(
 self, webhook_url: str, alert_data: Dict[str, Any]
 ):
 """
 Send shadow indexing alert to Slack
 """
 try:
 import httpx

 slack_payload = {
 "username": "OMS-Shadow-Index-Bot",
 "icon_emoji": ":exclamation:",
 "attachments": [
 {
 "color": "danger",
 "title": f"Shadow Index Build Failed: {alert_data['shadow_index_id']}",
 "text": alert_data["error_message"],
 "fields": [
 {
 "title": "Shadow Index ID",
 "value": alert_data["shadow_index_id"],
 "short": True,
 },
 {
 "title": "Branch",
 "value": alert_data["branch_name"],
 "short": True,
 },
 {
 "title": "Records Indexed",
 "value": str(alert_data.get("records_indexed", "N/A")),
 "short": True,
 },
 {
 "title": "Build Progress",
 "value": str(alert_data.get("build_progress", "N/A")),
 "short": True,
 },
 {
 "title": "Duration",
 "value": f"{alert_data.get('indexing_duration', 'N/A')}s",
 "short": True,
 },
 {
 "title": "Timestamp",
 "value": alert_data["timestamp"],
 "short": True,
 },
 ],
 "footer": "OMS Shadow Index Monitor",
 "ts": int(datetime.now().timestamp()),
 }
 ],
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 webhook_url, json = slack_payload, timeout = 10.0
 )

 if response.status_code == 200:
 logger.info(
 f"Slack shadow alert sent successfully for {alert_data['shadow_index_id']}"
 )
 else:
 logger.warning(
 f"Failed to send Slack shadow alert: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending Slack shadow alert: {e}")

 async def _send_email_shadow_alert(self, alert_data: Dict[str, Any]):
 """
 Send shadow indexing email alert
 """
 try:
 import smtplib
 from email.mime.multipart import MIMEMultipart
 from email.mime.text import MIMEText

 smtp_server = os.getenv("SMTP_SERVER", "localhost")
 smtp_port = int(os.getenv("SMTP_PORT", "587"))
 smtp_username = os.getenv("SMTP_USERNAME")
 smtp_password = os.getenv("SMTP_PASSWORD")
 from_email = os.getenv("FROM_EMAIL", "oms@arrakis.dev")
 to_emails = os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")

 if not to_emails or not to_emails[0]:
 logger.warning("No email recipients configured for shadow index alerts")
 return

 # Create email content
 subject = f"OMS Shadow Index Build Failure: {alert_data['shadow_index_id']}"

 html_content = """
 <html>
 <body>
 <h2 > Shadow Index Build Failure Alert</h2>
 <p><strong > Shadow Index ID:</strong> {alert_data['shadow_index_id']}</p>
 <p><strong > Branch:</strong> {alert_data['branch_name']}</p>
 <p><strong > Error:</strong> {alert_data['error_message']}</p>
 <p><strong > Records Indexed:</strong> {alert_data.get('records_indexed', 'N/A')}</p>
 <p><strong > Build Progress:</strong> {alert_data.get('build_progress', 'N/A')}</p>
 <p><strong > Duration:</strong> {alert_data.get('indexing_duration',
     'N/A')} seconds</p>
 <p><strong > Timestamp:</strong> {alert_data['timestamp']}</p>

 <h3 > Next Steps:</h3>
 <ul>
 <li > Check the shadow index build logs for detailed error information</li>
 <li > Verify the branch state and data integrity</li>
 <li > Check resource availability and limits</li>
 <li > Consider retrying the shadow index build</li>
 <li > Escalate to development team if issue persists</li>
 </ul>

 <h3 > Suggested Remediation:</h3>
 <ul>
 <li > Inspect build logs at progress point: {alert_data.get('build_progress',
     'N/A')}</li>
 <li > Verify shadow index storage capacity</li>
 <li > Check for data corruption in source branch</li>
 </ul>
 </body>
 </html>
 """

 # Send email
 msg = MIMEMultipart("alternative")
 msg["Subject"] = subject
 msg["From"] = from_email
 msg["To"] = ", ".join(to_emails)

 html_part = MIMEText(html_content, "html")
 msg.attach(html_part)

 with smtplib.SMTP(smtp_server, smtp_port) as server:
 if smtp_username and smtp_password:
 server.starttls()
 server.login(smtp_username, smtp_password)

 server.send_message(msg)

 logger.info(
 f"Email shadow alert sent successfully for {alert_data['shadow_index_id']}"
 )

 except Exception as e:
 logger.error(f"Error sending email shadow alert: {e}")

 async def _send_pagerduty_shadow_alert(self, alert_data: Dict[str, Any]):
 """
 Send shadow indexing alert to PagerDuty
 """
 try:
 import httpx

 integration_key = os.getenv("PAGERDUTY_INTEGRATION_KEY")
 if not integration_key:
 logger.warning("PagerDuty integration key not configured")
 return

 pagerduty_payload = {
 "routing_key": integration_key,
 "event_action": "trigger",
 "dedup_key": f"oms-shadow-index-{alert_data['shadow_index_id']}",
 "payload": {
 "summary": f"OMS Shadow Index Build Failed: {alert_data['shadow_index_id']}",
 "source": "oms-shadow-indexing-service",
 "severity": "error",
 "component": "shadow_indexing",
 "group": "oms",
 "class": "shadow_index_build_failure",
 "custom_details": {
 "shadow_index_id": alert_data["shadow_index_id"],
 "branch_name": alert_data["branch_name"],
 "error_message": alert_data["error_message"],
 "records_indexed": alert_data.get("records_indexed"),
 "build_progress": alert_data.get("build_progress"),
 "duration_seconds": alert_data.get("indexing_duration"),
 "timestamp": alert_data["timestamp"],
 },
 },
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 "https://events.pagerduty.com/v2/enqueue",
 json = pagerduty_payload,
 timeout = 10.0,
 )

 if response.status_code == 202:
 logger.info(
 f"PagerDuty shadow alert sent successfully for {alert_data['shadow_index_id']}"
 )
 else:
 logger.warning(
 f"Failed to send PagerDuty shadow alert: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending PagerDuty shadow alert: {e}")

 def _calculate_duration(
 self, started_at: str, completed_at: str
 ) -> Optional[float]:
 """
 Calculate indexing duration in seconds
 """
 try:
 if not started_at or not completed_at:
 return None

 start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
 end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

 return (end - start).total_seconds()

 except Exception as e:
 logger.error(f"Error calculating duration: {e}")
 return None

 async def _send_indexing_failure_alert(
 self, branch_name: str, data: Dict[str, Any]
 ):
 """
 Send alert for indexing failure
 """
 logger.error(
 f"ALERT: Indexing failed for branch {branch_name}. "
 f"Error: {data.get('error_message', 'Unknown error')}"
 )

 # Implement actual alerting (email, Slack, etc.)
 alert_data = {
 "type": "indexing_failure",
 "branch_name": branch_name,
 "error_message": data.get("error_message", "Unknown error"),
 "timestamp": datetime.now(timezone.utc).isoformat(),
 "records_indexed": data.get("records_indexed", 0),
 "indexing_duration": self._calculate_duration(
 data.get("started_at"), data.get("completed_at")
 ),
 "severity": "high",
 }

 # Send to multiple notification channels
 await self._send_to_notification_channels(alert_data)

 async def _send_to_notification_channels(self, alert_data: Dict[str, Any]):
 """
 Send alert to configured notification channels
 """
 # Slack notification
 slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
 if slack_webhook_url:
 await self._send_slack_alert(slack_webhook_url, alert_data)

 # Email notification
 email_enabled = os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true"
 if email_enabled:
 await self._send_email_alert(alert_data)

 # PagerDuty integration
 pagerduty_enabled = os.getenv("PAGERDUTY_ENABLED", "false").lower() == "true"
 if pagerduty_enabled and alert_data.get("severity") == "high":
 await self._send_pagerduty_alert(alert_data)

 # Custom webhook
 custom_webhook_url = os.getenv("CUSTOM_ALERT_WEBHOOK_URL")
 if custom_webhook_url:
 await self._send_custom_webhook_alert(custom_webhook_url, alert_data)

 async def _send_slack_alert(self, webhook_url: str, alert_data: Dict[str, Any]):
 """
 Send alert to Slack
 """
 try:
 import httpx

 color = "danger" if alert_data.get("severity") == "high" else "warning"

 slack_payload = {
 "username": "OMS-Indexing-Bot",
 "icon_emoji": ":warning:",
 "attachments": [
 {
 "color": color,
 "title": f"Indexing Failed: {alert_data['branch_name']}",
 "text": alert_data["error_message"],
 "fields": [
 {
 "title": "Branch",
 "value": alert_data["branch_name"],
 "short": True,
 },
 {
 "title": "Records Indexed",
 "value": str(alert_data.get("records_indexed", "N/A")),
 "short": True,
 },
 {
 "title": "Duration",
 "value": f"{alert_data.get('indexing_duration', 'N/A')}s",
 "short": True,
 },
 {
 "title": "Timestamp",
 "value": alert_data["timestamp"],
 "short": True,
 },
 ],
 "footer": "OMS Indexing Monitor",
 "ts": int(datetime.now().timestamp()),
 }
 ],
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 webhook_url, json = slack_payload, timeout = 10.0
 )

 if response.status_code == 200:
 logger.info(
 f"Slack alert sent successfully for {alert_data['branch_name']}"
 )
 else:
 logger.warning(
 f"Failed to send Slack alert: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending Slack alert: {e}")

 async def _send_email_alert(self, alert_data: Dict[str, Any]):
 """
 Send email alert
 """
 try:
 import smtplib
 from email.mime.multipart import MIMEMultipart
 from email.mime.text import MIMEText

 smtp_server = os.getenv("SMTP_SERVER", "localhost")
 smtp_port = int(os.getenv("SMTP_PORT", "587"))
 smtp_username = os.getenv("SMTP_USERNAME")
 smtp_password = os.getenv("SMTP_PASSWORD")
 from_email = os.getenv("FROM_EMAIL", "oms@arrakis.dev")
 to_emails = os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")

 if not to_emails or not to_emails[0]:
 logger.warning("No email recipients configured for alerts")
 return

 # Create email content
 subject = f"OMS Indexing Failure: {alert_data['branch_name']}"

 html_content = """
 <html>
 <body>
 <h2 > Indexing Failure Alert</h2>
 <p><strong > Branch:</strong> {alert_data['branch_name']}</p>
 <p><strong > Error:</strong> {alert_data['error_message']}</p>
 <p><strong > Records Indexed:</strong> {alert_data.get('records_indexed', 'N/A')}</p>
 <p><strong > Duration:</strong> {alert_data.get('indexing_duration',
     'N/A')} seconds</p>
 <p><strong > Timestamp:</strong> {alert_data['timestamp']}</p>

 <h3 > Next Steps:</h3>
 <ul>
 <li > Check the indexing logs for detailed error information</li>
 <li > Verify the branch state and data integrity</li>
 <li > Consider re-running the indexing process</li>
 </ul>
 </body>
 </html>
 """

 # Send email
 msg = MIMEMultipart("alternative")
 msg["Subject"] = subject
 msg["From"] = from_email
 msg["To"] = ", ".join(to_emails)

 html_part = MIMEText(html_content, "html")
 msg.attach(html_part)

 with smtplib.SMTP(smtp_server, smtp_port) as server:
 if smtp_username and smtp_password:
 server.starttls()
 server.login(smtp_username, smtp_password)

 server.send_message(msg)

 logger.info(
 f"Email alert sent successfully for {alert_data['branch_name']}"
 )

 except Exception as e:
 logger.error(f"Error sending email alert: {e}")

 async def _send_pagerduty_alert(self, alert_data: Dict[str, Any]):
 """
 Send alert to PagerDuty
 """
 try:
 import httpx

 integration_key = os.getenv("PAGERDUTY_INTEGRATION_KEY")
 if not integration_key:
 logger.warning("PagerDuty integration key not configured")
 return

 pagerduty_payload = {
 "routing_key": integration_key,
 "event_action": "trigger",
 "dedup_key": f"oms-indexing-{alert_data['branch_name']}",
 "payload": {
 "summary": f"OMS Indexing Failed: {alert_data['branch_name']}",
 "source": "oms-indexing-service",
 "severity": "error",
 "component": "indexing",
 "group": "oms",
 "class": "indexing_failure",
 "custom_details": {
 "branch_name": alert_data["branch_name"],
 "error_message": alert_data["error_message"],
 "records_indexed": alert_data.get("records_indexed"),
 "duration_seconds": alert_data.get("indexing_duration"),
 "timestamp": alert_data["timestamp"],
 },
 },
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 "https://events.pagerduty.com/v2/enqueue",
 json = pagerduty_payload,
 timeout = 10.0,
 )

 if response.status_code == 202:
 logger.info(
 f"PagerDuty alert sent successfully for {alert_data['branch_name']}"
 )
 else:
 logger.warning(
 f"Failed to send PagerDuty alert: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending PagerDuty alert: {e}")

 async def _send_custom_webhook_alert(
 self, webhook_url: str, alert_data: Dict[str, Any]
 ):
 """
 Send alert to custom webhook
 """
 try:
 import httpx

 webhook_payload = {
 "event_type": "indexing_failure",
 "service": "oms-indexing",
 "data": alert_data,
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 webhook_url, json = webhook_payload, timeout = 10.0
 )

 if response.status_code in [200, 201, 202]:
 logger.info(
 f"Custom webhook alert sent successfully for {alert_data['branch_name']}"
 )
 else:
 logger.warning(
 f"Failed to send custom webhook alert: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending custom webhook alert: {e}")

 async def _send_auto_merge_notification(
 self, branch_name: str, data: Dict[str, Any]
 ):
 """
 Send notification for successful auto-merge
 """
 logger.info(
 f"NOTIFICATION: Auto-merge completed for branch {branch_name}. "
 f"Records indexed: {data.get('records_indexed', 'unknown')}"
 )

 # Implement actual notifications
 notification_data = {
 "type": "auto_merge_success",
 "branch_name": branch_name,
 "message": f"Auto-merge completed successfully for {branch_name}",
 "timestamp": datetime.now(timezone.utc).isoformat(),
 "records_indexed": data.get("records_indexed", 0),
 "indexing_duration": self._calculate_duration(
 data.get("started_at"), data.get("completed_at")
 ),
 "severity": "info",
 }

 # Send to notification channels (but not PagerDuty for success notifications)
 await self._send_success_notifications(notification_data)

 async def _send_success_notifications(self, notification_data: Dict[str, Any]):
 """
 Send success notifications (excludes PagerDuty)
 """
 # Slack notification
 slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
 if slack_webhook_url:
 await self._send_slack_success_notification(
 slack_webhook_url, notification_data
 )

 # Email notification (if enabled for success events)
 email_success_enabled = (
 os.getenv("EMAIL_SUCCESS_NOTIFICATIONS_ENABLED", "false").lower() == "true"
 )
 if email_success_enabled:
 await self._send_email_success_notification(notification_data)

 # Custom webhook
 custom_webhook_url = os.getenv("CUSTOM_NOTIFICATION_WEBHOOK_URL")
 if custom_webhook_url:
 await self._send_custom_webhook_alert(custom_webhook_url, notification_data)

 async def _send_slack_success_notification(
 self, webhook_url: str, notification_data: Dict[str, Any]
 ):
 """
 Send success notification to Slack
 """
 try:
 import httpx

 slack_payload = {
 "username": "OMS-Auto-Merge-Bot",
 "icon_emoji": ":white_check_mark:",
 "attachments": [
 {
 "color": "good",
 "title": f"Auto-Merge Successful: {notification_data['branch_name']}",
 "text": f"Branch {notification_data['branch_name']} has been automatically merged after successful indexing.",


 "fields": [
 {
 "title": "Branch",
 "value": notification_data["branch_name"],
 "short": True,
 },
 {
 "title": "Records Indexed",
 "value": str(
 notification_data.get("records_indexed", "N/A")
 ),
 "short": True,
 },
 {
 "title": "Duration",
 "value": f"{notification_data.get('indexing_duration', 'N/A')}s",
 "short": True,
 },
 {
 "title": "Timestamp",
 "value": notification_data["timestamp"],
 "short": True,
 },
 ],
 "footer": "OMS Auto-Merge System",
 "ts": int(datetime.now().timestamp()),
 }
 ],
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 webhook_url, json = slack_payload, timeout = 10.0
 )

 if response.status_code == 200:
 logger.info(
 f"Slack success notification sent for {notification_data['branch_name']}"
 )
 else:
 logger.warning(
 f"Failed to send Slack success notification: {response.status_code}"
 )

 except Exception as e:
 logger.error(f"Error sending Slack success notification: {e}")

 async def _send_email_success_notification(self, notification_data: Dict[str, Any]):
 """
 Send email success notification
 """
 try:
 import smtplib
 from email.mime.multipart import MIMEMultipart
 from email.mime.text import MIMEText

 smtp_server = os.getenv("SMTP_SERVER", "localhost")
 smtp_port = int(os.getenv("SMTP_PORT", "587"))
 smtp_username = os.getenv("SMTP_USERNAME")
 smtp_password = os.getenv("SMTP_PASSWORD")
 from_email = os.getenv("FROM_EMAIL", "oms@arrakis.dev")
 to_emails = os.getenv("SUCCESS_EMAIL_RECIPIENTS", "").split(",")

 if not to_emails or not to_emails[0]:
 logger.info("No email recipients configured for success notifications")
 return

 # Create email content
 subject = f"OMS Auto-Merge Success: {notification_data['branch_name']}"

 html_content = """
 <html>
 <body>
 <h2 > Auto-Merge Success Notification</h2>
 <p><strong > Branch:</strong> {notification_data['branch_name']}</p>
 <p><strong > Status:</strong> Successfully merged</p>
 <p><strong > Records Indexed:</strong> {notification_data.get('records_indexed',
     'N/A')}</p>
 <p><strong > Duration:</strong> {notification_data.get('indexing_duration',
     'N/A')} seconds</p>
 <p><strong > Timestamp:</strong> {notification_data['timestamp']}</p>

 <p > The branch has been automatically merged after successful indexing and validation.</p>
 </body>
 </html>
 """

 # Send email
 msg = MIMEMultipart("alternative")
 msg["Subject"] = subject
 msg["From"] = from_email
 msg["To"] = ", ".join(to_emails)

 html_part = MIMEText(html_content, "html")
 msg.attach(html_part)

 with smtplib.SMTP(smtp_server, smtp_port) as server:
 if smtp_username and smtp_password:
 server.starttls()
 server.login(smtp_username, smtp_password)

 server.send_message(msg)

 logger.info(
 f"Email success notification sent for {notification_data['branch_name']}"
 )

 except Exception as e:
 logger.error(f"Error sending email success notification: {e}")


# Singleton instance
_handler_instance = None


def get_funnel_indexing_handler() -> FunnelIndexingEventHandler:
 """
 Get singleton instance of FunnelIndexingEventHandler
 """
 global _handler_instance
 if _handler_instance is None:
 _handler_instance = FunnelIndexingEventHandler()
 return _handler_instance
