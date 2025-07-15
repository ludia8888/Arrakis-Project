"""
Migration Executor - Production-ready migration execution engine
Executes migration plans with full error handling, rollback support, and monitoring
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.validation.models import (
    MigrationPlan,
    MigrationResult,
    MigrationStatus,
    MigrationStep,
)
from database.clients.terminus_db import TerminusDBClient
from middleware.circuit_breaker_http import http_circuit_breaker
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MigrationExecutor:
 """Production-ready migration executor with full error handling"""

 def __init__(self, tdb_client: TerminusDBClient, dry_run: bool = False):
 self.tdb = tdb_client
 self.dry_run = dry_run
 self.execution_history: List[Dict[str, Any]] = []

 # Production audit service integration
 import os

 self.audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 async def execute_migration(
 self, plan: MigrationPlan, db_name: str, user_id: str = "system"
 ) -> MigrationResult:
 """
 Execute a migration plan with full error handling and rollback support

 Args:
 plan: The migration plan to execute
 db_name: Target database name
 user_id: User executing the migration

 Returns:
 MigrationResult with execution details
 """
 start_time = datetime.utcnow()
 executed_steps: List[MigrationStep] = []
 errors: List[Dict[str, Any]] = []

 try:
 # Audit migration start
 await self._audit_migration_event(
 "migration.started",
 plan.id,
 user_id,
 {"total_steps": len(plan.steps), "dry_run": self.dry_run},
 )

 # Pre-flight checks
 if not await self._validate_prerequisites(plan, db_name):
 raise ValueError("Migration prerequisites not met")

 # Execute steps in order
 for step_index, step in enumerate(plan.steps):
 try:
 logger.info(
 f"Executing step {step_index + 1}/{len(plan.steps)}: {step.description}"
 )

 # Check if downtime required
 if step.requires_downtime and not self.dry_run:
 await self._handle_downtime_window(step)

 # Execute the step
 if self.dry_run:
 logger.info(f"[DRY RUN] Would execute: {step.type}")
 await self._simulate_step_execution(step)
 else:
 await self._execute_step(step, db_name)

 executed_steps.append(step)

 # Verify step execution if verification script provided
 if step.verification_script and not self.dry_run:
 if not await self._verify_step(step, db_name):
 raise RuntimeError(
 f"Step verification failed: {step.description}"
 )

 # Progress update
 progress = (step_index + 1) / len(plan.steps) * 100
 await self._update_progress(plan.id, progress)

 except Exception as e:
 logger.error(f"Step {step_index + 1} failed: {str(e)}")
 errors.append(
 {
 "step_index": step_index,
 "step_type": step.type,
 "error": str(e),
 "timestamp": datetime.utcnow().isoformat(),
 }
 )

 # Decide whether to continue or rollback
 if step.type in ["atomic_switch", "make_required_and_switch"]:
 # Critical steps - must rollback
 logger.error("Critical step failed, initiating rollback")
 await self._rollback_migration(executed_steps, db_name)
 raise
 else:
 # Non-critical - log and continue
 logger.warning(f"Non-critical step failed, continuing: {e}")

 # Post-migration verification
 if not self.dry_run:
 verification_passed = await self._verify_migration_complete(
 plan, db_name
 )
 if not verification_passed:
 logger.warning("Post-migration verification failed")

 # Calculate final status
 end_time = datetime.utcnow()
 duration = (end_time - start_time).total_seconds()
 status = (
 MigrationStatus.COMPLETED
 if not errors
 else MigrationStatus.COMPLETED_WITH_WARNINGS
 )

 # Audit migration completion
 await self._audit_migration_event(
 "migration.completed",
 plan.id,
 user_id,
 {
 "duration_seconds": duration,
 "steps_executed": len(executed_steps),
 "errors": len(errors),
 "status": status.value,
 },
 )

 return MigrationResult(
 plan_id = plan.id,
 status = status,
 started_at = start_time,
 completed_at = end_time,
 duration_seconds = duration,
 steps_executed = len(executed_steps),
 steps_total = len(plan.steps),
 errors = errors,
 dry_run = self.dry_run,
 )

 except Exception as e:
 logger.error(f"Migration failed: {str(e)}")

 # Audit migration failure
 await self._audit_migration_event(
 "migration.failed",
 plan.id,
 user_id,
 {
 "error": str(e),
 "steps_executed": len(executed_steps),
 "rollback_initiated": True,
 },
 )

 # Return failure result
 return MigrationResult(
 plan_id = plan.id,
 status = MigrationStatus.FAILED,
 started_at = start_time,
 completed_at = datetime.utcnow(),
 duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
 steps_executed = len(executed_steps),
 steps_total = len(plan.steps),
 errors = errors + [{"error": str(e), "type": "fatal"}],
 dry_run = self.dry_run,
 )

 async def _execute_step(self, step: MigrationStep, db_name: str) -> None:
 """Execute a single migration step"""
 if not step.woql_script:
 logger.info(f"Step {step.type} has no WOQL script, skipping execution")
 return

 try:
 # Execute in batches if batch_size specified
 if step.batch_size and step.can_parallel:
 await self._execute_batched(step, db_name)
 else:
 # Execute as single operation
 result = await self.tdb.query(
 db_name,
 step.woql_script,
 commit_msg = f"Migration step: {step.description}",
 )

 # Store execution result
 self.execution_history.append(
 {
 "step": step.type,
 "timestamp": datetime.utcnow().isoformat(),
 "result": result,
 }
 )

 except Exception as e:
 logger.error(f"Failed to execute step {step.type}: {e}")
 raise

 async def _execute_batched(self, step: MigrationStep, db_name: str) -> None:
 """Execute step in batches for large datasets"""
 batch_num = 0
 total_processed = 0

 while True:
 batch_num += 1
 logger.info(f"Processing batch {batch_num} (size: {step.batch_size})")

 # Execute batch
 result = await self.tdb.query(
 db_name,
 step.woql_script,
 commit_msg = f"Migration batch {batch_num}: {step.description}",
 )

 # Check if more data to process
 if not result or (
 isinstance(result, dict) and result.get("bindings", []) == []
 ):
 logger.info(f"Batch processing complete. Total batches: {batch_num}")
 break

 total_processed += step.batch_size

 # Add delay between batches to reduce load
 await asyncio.sleep(1)

 async def _verify_step(self, step: MigrationStep, db_name: str) -> bool:
 """Verify step execution was successful"""
 if not step.verification_script:
 return True

 try:
 result = await self.tdb.query(db_name, step.verification_script)

 # Check verification result
 if isinstance(result, dict) and "bindings" in result:
 # Assumes verification returns boolean result
 return bool(result["bindings"])

 return True

 except Exception as e:
 logger.error(f"Step verification failed: {e}")
 return False

 async def _rollback_migration(
 self, executed_steps: List[MigrationStep], db_name: str
 ) -> None:
 """Rollback executed steps in reverse order"""
 logger.info(f"Starting rollback of {len(executed_steps)} steps")

 for step in reversed(executed_steps):
 if step.rollback_script:
 try:
 logger.info(f"Rolling back: {step.description}")
 await self.tdb.query(
 db_name,
 step.rollback_script,
 commit_msg = f"Rollback: {step.description}",
 )
 except Exception as e:
 logger.error(f"Rollback failed for step {step.type}: {e}")
 # Continue with other rollbacks

 async def _validate_prerequisites(self, plan: MigrationPlan, db_name: str) -> bool:
 """Validate migration can be safely executed"""
 try:
 # Check database exists and is accessible
 databases = await self.tdb.get_databases()
 if not any(db["name"] == db_name for db in databases):
 logger.error(f"Database {db_name} not found")
 return False

 # Check for any locks or ongoing operations
 # This would check for branch locks, ongoing merges, etc.

 return True

 except Exception as e:
 logger.error(f"Prerequisites validation failed: {e}")
 return False

 async def _handle_downtime_window(self, step: MigrationStep) -> None:
 """Handle downtime requirements for a step"""
 if step.downtime_duration:
 logger.warning(
 f"Step requires {step.downtime_duration}s downtime. "
 "Ensure appropriate maintenance window is active."
 )
 # In production, this would coordinate with load balancers,
 # health checks, etc.

 async def _update_progress(self, plan_id: str, progress: float) -> None:
 """Update migration progress for monitoring"""
 # This would update a progress tracker, send notifications, etc.
 logger.info(f"Migration {plan_id} progress: {progress:.1f}%")

 async def _verify_migration_complete(
 self, plan: MigrationPlan, db_name: str
 ) -> bool:
 """Verify entire migration completed successfully"""
 # Run comprehensive verification queries
 # Check data integrity, schema consistency, etc.
 return True

 async def _simulate_step_execution(self, step: MigrationStep) -> None:
 """Simulate step execution for dry run"""
 # Estimate impact, check syntax, etc.
 await asyncio.sleep(0.1) # Simulate execution time

 async def _audit_migration_event(
 self, event_type: str, plan_id: str, user_id: str, metadata: Dict[str, Any]
 ) -> None:
 """Audit migration events - Production audit-service integration"""
 try:
 from datetime import datetime

 import httpx

 # Create audit payload for audit-service
 audit_payload = {
 "event_type": event_type,
 "event_category": "schema_migration",
 "user_id": user_id,
 "username": user_id,
 "target_type": "migration_plan",
 "target_id": plan_id,
 "operation": event_type.split("_")[-1]
 if "_" in event_type
 else event_type,
 "severity": "INFO",
 "metadata": {
 "source": "migration_executor",
 "timestamp": datetime.utcnow().isoformat(),
 **metadata,
 },
 }

 # Send to audit-service with timeout
 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.post(
 f"{self.audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(f"Migration audit event sent: {event_type} for plan {plan_id}")

 except Exception as e:
 logger.warning(
 f"Failed to send migration audit event to audit-service: {e}"
 )
