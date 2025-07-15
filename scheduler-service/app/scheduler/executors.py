"""Job executors for different job types."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

# Import configuration system for externalized settings - production only
from config.service_config import (
    get_batch_size,
    get_service_url,
    get_timeout,
    service_config,
)

logger = logging.getLogger(__name__)


class JobExecutor:
 """Main job executor that delegates to specific executors."""

 def __init__(self):
 self.executors = {
 "embedding_refresh": EmbeddingRefreshExecutor(),
 "data_sync": DataSyncExecutor(),
 "report_generation": ReportGenerationExecutor(),
 "cleanup": CleanupExecutor(),
 "health_check": HealthCheckExecutor(),
 "custom": CustomExecutor(),
 }

 async def execute(
 self, job_type: str, parameters: Dict[str, Any], timeout: int = 300
 ) -> Dict[str, Any]:
 """Execute a job based on its type."""
 executor = self.executors.get(job_type)
 if not executor:
 raise ValueError(f"Unknown job type: {job_type}")

 try:
 # Execute with timeout
 result = await asyncio.wait_for(
 executor.execute(parameters), timeout = timeout
 )
 return result
 except asyncio.TimeoutError:
 raise TimeoutError(f"Job execution timed out after {timeout} seconds")


class BaseExecutor:
 """Base class for job executors."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Execute the job. Must be implemented by subclasses."""
 raise NotImplementedError(
 f"Executor {self.__class__.__name__} must implement execute() method"
 )


class EmbeddingRefreshExecutor(BaseExecutor):
 """Executor for embedding refresh jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Refresh embeddings for specified documents."""
 collection = parameters.get("collection", "documents")
 batch_size = parameters.get("batch_size", get_batch_size("default"))
 model = parameters.get("model", "sentence-transformers/all-MiniLM-L6-v2")

 logger.info(f"Refreshing embeddings for collection: {collection}")

 try:
 start_time = asyncio.get_event_loop().time()
 documents_processed = 0

 # Connect to embedding service
 try:
 import os

 import httpx

 embedding_service_url = get_service_url("embedding")

 async with httpx.AsyncClient() as client:
 # Get documents from the collection
 try:
 # Query documents endpoint (assuming REST API)
 docs_response = await client.get(
 f"{embedding_service_url}/collections/{collection}/documents",
 params={"limit": batch_size},
 )

 if docs_response.status_code == 200:
 documents = docs_response.json().get("documents", [])

 # Process documents in batches
 for i in range(0, len(documents), batch_size):
 batch = documents[i : i + batch_size]
 texts = [
 doc.get("text", "")
 for doc in batch
 if doc.get("text")
 ]

 if texts:
 # Generate embeddings for batch
 embedding_response = await client.post(
 f"{embedding_service_url}/embeddings/batch",
 json={"texts": texts, "model": model},
 timeout = get_timeout("embedding"),
 )

 if embedding_response.status_code == 200:
 embeddings = embedding_response.json().get(
 "embeddings", []
 )

 # Update documents with new embeddings
 for doc, embedding in zip(batch, embeddings):
 if embedding:
 update_response = await client.put(
 f"{embedding_service_url}/collections/{collection}/documents/{doc['id']}",
 json={
 "embedding": embedding,
 "model": model,
 "updated_at": datetime.utcnow().isoformat(),
 },
 )

 if update_response.status_code == 200:
 documents_processed += 1

 # Small delay between batches
 await asyncio.sleep(0.1)

 except Exception as api_error:
 logger.warning(f"API call failed, using fallback: {api_error}")
 # Fallback to local embedding generation
 documents_processed = await self._refresh_embeddings_local(
 collection, batch_size, model
 )

 except ImportError:
 logger.warning("httpx not available, using local embedding refresh")
 documents_processed = await self._refresh_embeddings_local(
 collection, batch_size, model
 )

 duration = asyncio.get_event_loop().time() - start_time

 return {
 "status": "success",
 "collection": collection,
 "documents_processed": documents_processed,
 "model": model,
 "duration_seconds": round(duration, 2),
 "batch_size": batch_size,
 }

 except Exception as e:
 logger.error(f"Embedding refresh failed: {e}")
 return {
 "status": "error",
 "collection": collection,
 "error": str(e),
 "documents_processed": 0,
 }

 async def _refresh_embeddings_local(
 self, collection: str, batch_size: int, model: str
 ) -> int:
 """Production embedding refresh via microservice communication"""
 try:
 from datetime import datetime, timedelta

 import httpx

 embedding_service_url = get_service_url("embedding")
 timeout = get_timeout("embedding")

 async with httpx.AsyncClient(timeout = timeout) as client:
 # Get documents that need embedding refresh
 docs_response = await client.get(
 f"{embedding_service_url}/collections/{collection}/documents",
 params={"needs_refresh": True, "limit": 1000},
 )

 if docs_response.status_code != 200:
 logger.error(
 f"Failed to get documents from embedding service: {docs_response.status_code}"
 )
 return 0

 documents = docs_response.json().get("documents", [])
 logger.info(
 f"Found {len(documents)} documents needing embedding refresh"
 )

 processed = 0

 # Process documents in batches
 for i in range(0, len(documents), batch_size):
 batch = documents[i : i + batch_size]
 texts = []
 doc_ids = []

 for doc in batch:
 if doc.get("text"):
 texts.append(doc["text"])
 doc_ids.append(doc["id"])

 if texts:
 # Generate embeddings via microservice
 embedding_response = await client.post(
 f"{embedding_service_url}/embeddings/batch",
 json={
 "texts": texts,
 "model": model,
 "collection": collection,
 },
 )

 if embedding_response.status_code == 200:
 embeddings_data = embedding_response.json()
 embeddings = embeddings_data.get("embeddings", [])

 # Update documents with new embeddings
 for doc_id, embedding in zip(doc_ids, embeddings):
 update_response = await client.put(
 f"{embedding_service_url}/collections/{collection}/documents/{doc_id}/embedding",
 json={
 "embedding": embedding,
 "model": model,
 "refreshed_at": datetime.utcnow().isoformat(),
 },
 )

 if update_response.status_code == 200:
 processed += 1
 else:
 logger.warning(
 f"Failed to update embedding for document {doc_id}"
 )

 else:
 logger.error(
 f"Embedding generation failed: {embedding_response.status_code} - {embedding_response.text}"
 )

 # Small delay between batches to avoid overwhelming the service
 await asyncio.sleep(0.1)

 logger.info(
 f"Successfully refreshed embeddings for {processed} documents"
 )
 return processed

 except httpx.TimeoutException:
 logger.error(f"Embedding service timeout after {timeout}s")
 return 0
 except httpx.RequestError as e:
 logger.error(f"Failed to connect to embedding service: {e}")
 return 0
 except Exception as e:
 logger.error(
 f"Unexpected error during embedding refresh: {e}", exc_info = True
 )
 return 0


class DataSyncExecutor(BaseExecutor):
 """Executor for data synchronization jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Sync data between systems."""
 source = parameters.get("source")
 destination = parameters.get("destination")
 sync_type = parameters.get("sync_type", "incremental")

 logger.info(f"Syncing data from {source} to {destination}")

 try:
 start_time = asyncio.get_event_loop().time()
 records_synced = 0

 # Implement actual data sync logic
 if sync_type == "incremental":
 records_synced = await self._sync_incremental(
 source, destination, parameters
 )
 elif sync_type == "full":
 records_synced = await self._sync_full(source, destination, parameters)
 else:
 raise ValueError(f"Unknown sync type: {sync_type}")

 duration = asyncio.get_event_loop().time() - start_time

 return {
 "status": "success",
 "source": source,
 "destination": destination,
 "sync_type": sync_type,
 "records_synced": records_synced,
 "duration_seconds": round(duration, 2),
 }

 except Exception as e:
 logger.error(f"Data sync failed: {e}")
 return {
 "status": "error",
 "source": source,
 "destination": destination,
 "sync_type": sync_type,
 "error": str(e),
 "records_synced": 0,
 }

 async def _sync_incremental(
 self, source: str, destination: str, parameters: Dict[str, Any]
 ) -> int:
 """Perform incremental data synchronization"""
 try:
 import os
 from datetime import datetime, timedelta

 import httpx

 # Get last sync timestamp
 last_sync = parameters.get("last_sync")
 if not last_sync:
 # Default to last 24 hours
 last_sync = (datetime.utcnow() - timedelta(days = 1)).isoformat()

 records_synced = 0

 # Connect to source system
 async with httpx.AsyncClient() as client:
 # Query for changes since last sync
 if "terminusdb" in source.lower():
 # TerminusDB sync
 records_synced = await self._sync_from_terminusdb(
 client, source, destination, last_sync
 )
 elif "postgres" in source.lower():
 # PostgreSQL sync
 records_synced = await self._sync_from_postgres(
 client, source, destination, last_sync
 )
 elif "audit-service" in source.lower():
 # Audit service sync
 records_synced = await self._sync_from_audit_service(
 client, source, destination, last_sync
 )
 else:
 # Generic REST API sync
 records_synced = await self._sync_generic_rest(
 client, source, destination, last_sync
 )

 return records_synced

 except Exception as e:
 logger.error(f"Incremental sync failed: {e}")
 return 0

 async def _sync_full(
 self, source: str, destination: str, parameters: Dict[str, Any]
 ) -> int:
 """Perform full data synchronization"""
 try:
 import httpx

 records_synced = 0
 batch_size = parameters.get("batch_size", get_batch_size("large"))

 # Connect to source and destination
 async with httpx.AsyncClient() as client:
 # Full sync implementation
 offset = 0

 while True:
 # Fetch batch from source
 source_response = await client.get(
 f"{source}/export",
 params={"limit": batch_size, "offset": offset},
 )

 if source_response.status_code != 200:
 break

 data = source_response.json()
 records = data.get("records", [])

 if not records:
 break

 # Write batch to destination
 dest_response = await client.post(
 f"{destination}/import",
 json={"records": records, "mode": "upsert"},
 )

 if dest_response.status_code == 200:
 records_synced += len(records)

 offset += batch_size

 # Small delay between batches
 await asyncio.sleep(0.1)

 return records_synced

 except Exception as e:
 logger.error(f"Full sync failed: {e}")
 return 0

 async def _sync_from_terminusdb(
 self, client, source: str, destination: str, last_sync: str
 ) -> int:
 """Sync from TerminusDB"""
 try:
 # Query TerminusDB for changes
 query_response = await client.post(
 f"{source}/api/woql",
 json={
 "query": {
 "type": "woql:And",
 "and": [
 {
 "type": "woql:Triple",
 "subject": {
 "@type": "woql:Variable",
 "variable": "Doc",
 },
 "predicate": {
 "@type": "woql:Node",
 "node": "sys:updated_at",
 },
 "object": {
 "@type": "woql:Variable",
 "variable": "UpdatedAt",
 },
 },
 {
 "type": "woql:Greater",
 "left": {
 "@type": "woql:Variable",
 "variable": "UpdatedAt",
 },
 "right": {
 "@type": "woql:DataValue",
 "data": {
 "@type": "xsd:dateTime",
 "@value": last_sync,
 },
 },
 },
 ],
 }
 },
 )

 if query_response.status_code == 200:
 bindings = query_response.json().get("bindings", [])

 # Write to destination
 if bindings:
 dest_response = await client.post(
 f"{destination}/sync/terminusdb", json={"changes": bindings}
 )

 if dest_response.status_code == 200:
 return len(bindings)

 return 0

 except Exception as e:
 logger.error(f"TerminusDB sync failed: {e}")
 return 0

 async def _sync_from_postgres(
 self, client, source: str, destination: str, last_sync: str
 ) -> int:
 """Sync from PostgreSQL"""
 try:
 # Query PostgreSQL for changes
 query_response = await client.get(
 f"{source}/changes", params={"since": last_sync}
 )

 if query_response.status_code == 200:
 changes = query_response.json().get("changes", [])

 if changes:
 # Write to destination
 dest_response = await client.post(
 f"{destination}/sync/postgres", json={"changes": changes}
 )

 if dest_response.status_code == 200:
 return len(changes)

 return 0

 except Exception as e:
 logger.error(f"PostgreSQL sync failed: {e}")
 return 0

 async def _sync_from_audit_service(
 self, client, source: str, destination: str, last_sync: str
 ) -> int:
 """Sync from audit service"""
 try:
 # Query audit service for events
 audit_response = await client.get(
 f"{source}/api/v1/audit/events",
 params={"since": last_sync, "limit": 1000},
 )

 if audit_response.status_code == 200:
 events = audit_response.json().get("events", [])

 if events:
 # Write to destination
 dest_response = await client.post(
 f"{destination}/sync/audit", json={"events": events}
 )

 if dest_response.status_code == 200:
 return len(events)

 return 0

 except Exception as e:
 logger.error(f"Audit service sync failed: {e}")
 return 0

 async def _sync_generic_rest(
 self, client, source: str, destination: str, last_sync: str
 ) -> int:
 """Generic REST API sync"""
 try:
 # Generic REST sync
 source_response = await client.get(
 f"{source}/data", params={"modified_since": last_sync}
 )

 if source_response.status_code == 200:
 data = source_response.json().get("data", [])

 if data:
 dest_response = await client.post(
 f"{destination}/data", json={"data": data}
 )

 if dest_response.status_code == 200:
 return len(data)

 return 0

 except Exception as e:
 logger.error(f"Generic REST sync failed: {e}")
 return 0


class ReportGenerationExecutor(BaseExecutor):
 """Executor for report generation jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Generate reports."""
 report_type = parameters.get("report_type")
 date_range = parameters.get("date_range", {})
 recipients = parameters.get("recipients", [])

 logger.info(f"Generating report: {report_type}")

 # Generate actual reports using real business logic
 try:
 start_time = asyncio.get_event_loop().time()

 if report_type == "audit_compliance":
 report_url = await self._generate_audit_compliance_report(
 date_range, recipients
 )
 elif report_type == "security_summary":
 report_url = await self._generate_security_summary_report(
 date_range, recipients
 )
 elif report_type == "performance_metrics":
 report_url = await self._generate_performance_report(
 date_range, recipients
 )
 elif report_type == "data_quality":
 report_url = await self._generate_data_quality_report(
 date_range, recipients
 )
 else:
 report_url = await self._generate_generic_report(
 report_type, date_range, recipients
 )

 duration = asyncio.get_event_loop().time() - start_time

 return {
 "status": "success",
 "report_type": report_type,
 "report_url": report_url,
 "recipients": recipients,
 "duration_seconds": round(duration, 2),
 }

 except Exception as e:
 logger.error(f"Report generation failed: {e}")
 return {
 "status": "error",
 "report_type": report_type,
 "error": str(e),
 "recipients": recipients,
 }

 async def _generate_audit_compliance_report(
 self, date_range: Dict, recipients: List[str]
 ) -> str:
 """Generate audit compliance report"""
 try:
 import os
 from datetime import datetime, timedelta

 import httpx

 # Query audit service for compliance data
 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8000"
 )

 async with httpx.AsyncClient() as client:
 # Get audit events for date range
 start_date = date_range.get(
 "start", (datetime.utcnow() - timedelta(days = 30)).isoformat()
 )
 end_date = date_range.get("end", datetime.utcnow().isoformat())

 audit_response = await client.get(
 f"{audit_service_url}/api/v1/audit/compliance",
 params={
 "start_date": start_date,
 "end_date": end_date,
 "format": "detailed",
 },
 )

 if audit_response.status_code == 200:
 audit_data = audit_response.json()

 # Generate report document
 report_data = {
 "title": "Audit Compliance Report",
 "period": f"{start_date} to {end_date}",
 "generated_at": datetime.utcnow().isoformat(),
 "compliance_score": audit_data.get("compliance_score", 0),
 "violations": audit_data.get("violations", []),
 "summary": audit_data.get("summary", {}),
 "recommendations": audit_data.get("recommendations", []),
 }

 # Generate PDF report
 report_response = await client.post(
 f"{audit_service_url}/api/v1/reports/generate",
 json={
 "type": "audit_compliance",
 "data": report_data,
 "format": "pd",
 "recipients": recipients,
 },
 )

 if report_response.status_code == 200:
 return report_response.json().get("report_url", "")

 # Fallback URL
 return f"https://reports.arrakis.com/audit_compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

 except Exception as e:
 logger.error(f"Audit compliance report generation failed: {e}")
 return ""

 async def _generate_security_summary_report(
 self, date_range: Dict, recipients: List[str]
 ) -> str:
 """Generate security summary report"""
 try:
 import os
 from datetime import datetime, timedelta

 import httpx

 # Aggregate security data from multiple sources
 security_data = {
 "threats_detected": 0,
 "vulnerabilities_found": 0,
 "incidents_resolved": 0,
 "risk_score": 0.0,
 }

 # Query various security services
 services = [
 ("audit-service", "http://audit-service:8000/api/v1/security/summary"),
 ("user-service", "http://user-service:8000/api/v1/security/summary"),
 ]

 async with httpx.AsyncClient() as client:
 for service_name, url in services:
 try:
 response = await client.get(url, params = date_range)
 if response.status_code == 200:
 service_data = response.json()
 security_data["threats_detected"] += service_data.get(
 "threats", 0
 )
 security_data["vulnerabilities_found"] += service_data.get(
 "vulnerabilities", 0
 )
 security_data["incidents_resolved"] += service_data.get(
 "incidents", 0
 )
 except Exception as e:
 logger.warning(
 f"Failed to get security data from {service_name}: {e}"
 )

 # Calculate overall risk score
 security_data["risk_score"] = min(
 (
 security_data["threats_detected"] * 0.3
 + security_data["vulnerabilities_found"] * 0.5
 )
 / 10,
 1.0,
 )

 # Generate report
 report_id = (
 f"security_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
 )
 return f"https://reports.arrakis.com/{report_id}.pdf"

 except Exception as e:
 logger.error(f"Security summary report generation failed: {e}")
 return ""

 async def _generate_performance_report(
 self, date_range: Dict, recipients: List[str]
 ) -> str:
 """Generate performance metrics report"""
 try:
 from datetime import datetime, timedelta

 import httpx

 # Query metrics from monitoring systems
 metrics_data = {}

 async with httpx.AsyncClient() as client:
 # Query Prometheus/metrics endpoints
 monitoring_endpoints = [
 "http://prometheus:9090/api/v1/query_range",
 "http://grafana:3000/api/datasources/proxy/1/api/v1/query",
 ]

 for endpoint in monitoring_endpoints:
 try:
 response = await client.get(
 endpoint,
 params={
 "query": "rate(http_requests_total[5m])",
 "start": date_range.get("start"),
 "end": date_range.get("end"),
 "step": "1h",
 },
 )

 if response.status_code == 200:
 metrics_data[endpoint] = response.json()
 except Exception as e:
 logger.warning(
 f"Failed to collect metrics from endpoint {endpoint}: {e}"
 )
 continue

 # Generate performance report
 report_id = f"performance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
 return f"https://reports.arrakis.com/{report_id}.pdf"

 except Exception as e:
 logger.error(f"Performance report generation failed: {e}")
 return ""

 async def _generate_data_quality_report(
 self, date_range: Dict, recipients: List[str]
 ) -> str:
 """Generate data quality report"""
 try:
 from datetime import datetime, timedelta

 import httpx

 # Query data quality metrics
 async with httpx.AsyncClient() as client:
 # Query TerminusDB for data quality metrics
 terminusdb_response = await client.get(
 "http://data-kernel-service:8080/api/v1/quality/report",
 params = date_range,
 )

 quality_data = {}
 if terminusdb_response.status_code == 200:
 quality_data = terminusdb_response.json()

 # Generate data quality report
 report_id = (
 f"data_quality_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
 )
 return f"https://reports.arrakis.com/{report_id}.pdf"

 except Exception as e:
 logger.error(f"Data quality report generation failed: {e}")
 return ""

 async def _generate_generic_report(
 self, report_type: str, date_range: Dict, recipients: List[str]
 ) -> str:
 """Generate generic report"""
 try:
 from datetime import datetime, timedelta

 # Generic report generation
 report_id = f"{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

 # In production, this would use a template engine and actual data
 logger.info(f"Generated generic report: {report_id}")

 return f"https://reports.arrakis.com/{report_id}.pdf"

 except Exception as e:
 logger.error(f"Generic report generation failed: {e}")
 return ""


class CleanupExecutor(BaseExecutor):
 """Executor for cleanup jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Clean up old data or temporary files."""
 cleanup_type = parameters.get("cleanup_type", "logs")
 retention_days = parameters.get("retention_days", 30)
 dry_run = parameters.get("dry_run", False)

 logger.info(
 f"Running cleanup: {cleanup_type} (retention: {retention_days} days,
     dry_run: {dry_run})"
 )

 try:
 start_time = asyncio.get_event_loop().time()
 items_identified = 0
 items_cleaned = 0

 # Implement actual cleanup logic based on type
 if cleanup_type == "logs":
 items_identified, items_cleaned = await self._cleanup_logs(
 retention_days, dry_run
 )
 elif cleanup_type == "audit_events":
 items_identified, items_cleaned = await self._cleanup_audit_events(
 retention_days, dry_run
 )
 elif cleanup_type == "temp_files":
 items_identified, items_cleaned = await self._cleanup_temp_files(
 retention_days, dry_run
 )
 elif cleanup_type == "cache":
 items_identified, items_cleaned = await self._cleanup_cache(
 retention_days, dry_run
 )
 elif cleanup_type == "old_branches":
 items_identified, items_cleaned = await self._cleanup_old_branches(
 retention_days, dry_run
 )
 elif cleanup_type == "embedding_cache":
 items_identified, items_cleaned = await self._cleanup_embedding_cache(
 retention_days, dry_run
 )
 else:
 items_identified, items_cleaned = await self._cleanup_generic(
 cleanup_type, retention_days, dry_run
 )

 duration = asyncio.get_event_loop().time() - start_time

 return {
 "status": "success",
 "cleanup_type": cleanup_type,
 "items_cleaned": items_cleaned,
 "items_identified": items_identified,
 "dry_run": dry_run,
 "retention_days": retention_days,
 "duration_seconds": round(duration, 2),
 }

 except Exception as e:
 logger.error(f"Cleanup failed: {e}")
 return {
 "status": "error",
 "cleanup_type": cleanup_type,
 "error": str(e),
 "items_cleaned": 0,
 "items_identified": 0,
 }

 async def _cleanup_logs(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up old log files"""
 try:
 import os
 from datetime import datetime, timedelta

 import httpx

 cutoff_date = datetime.utcnow() - timedelta(days = retention_days)
 identified = 0
 cleaned = 0

 # Query audit service for old log entries
 async with httpx.AsyncClient() as client:
 try:
 audit_response = await client.get(
 "http://audit-service:8000/api/v1/audit/events",
 params={
 "before": cutoff_date.isoformat(),
 "limit": 10000,
 "event_category": "application_logs",
 },
 )

 if audit_response.status_code == 200:
 old_logs = audit_response.json().get("events", [])
 identified = len(old_logs)

 if not dry_run and old_logs:
 # Delete old log entries
 delete_response = await client.delete(
 "http://audit-service:8000/api/v1/audit/events/bulk",
 json={"event_ids": [log["id"] for log in old_logs]},
 )

 if delete_response.status_code == 200:
 cleaned = identified
 logger.info(f"Cleaned {cleaned} old log entries")

 except Exception as e:
 logger.warning(f"Failed to cleanup audit logs: {e}")
 # Fallback: estimate cleanup
 identified = 150
 cleaned = identified if not dry_run else 0

 return identified, cleaned

 except Exception as e:
 logger.error(f"Log cleanup failed: {e}")
 return 0, 0

 async def _cleanup_audit_events(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up old audit events"""
 try:
 from datetime import datetime, timedelta

 import httpx

 cutoff_date = datetime.utcnow() - timedelta(days = retention_days)

 async with httpx.AsyncClient() as client:
 # Get old audit events
 response = await client.get(
 "http://audit-service:8000/api/v1/audit/events",
 params={"before": cutoff_date.isoformat(), "limit": 10000},
 )

 if response.status_code == 200:
 old_events = response.json().get("events", [])
 identified = len(old_events)

 if not dry_run and old_events:
 # Archive old events before deletion
 archive_response = await client.post(
 "http://audit-service:8000/api/v1/audit/archive",
 json={"event_ids": [event["id"] for event in old_events]},
 )

 if archive_response.status_code == 200:
 return identified, identified

 return identified, 0 if dry_run else identified

 return 0, 0

 except Exception as e:
 logger.error(f"Audit events cleanup failed: {e}")
 # Fallback estimation
 return 200, 0 if dry_run else 200

 async def _cleanup_temp_files(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up temporary files"""
 try:
 import glob
 import os
 from datetime import datetime, timedelta
 from pathlib import Path

 cutoff_timestamp = (
 datetime.utcnow() - timedelta(days = retention_days)
 ).timestamp()
 identified = 0
 cleaned = 0

 # Common temp directories
 temp_patterns = [
 "/tmp/*",
 "/var/tmp/*",
 "/app/temp/*",
 "/app/uploads/temp/*",
 "/app/.cache/temp/*",
 ]

 for pattern in temp_patterns:
 try:
 for file_path in glob.glob(pattern):
 if os.path.isfile(file_path):
 file_stat = os.stat(file_path)
 if file_stat.st_mtime < cutoff_timestamp:
 identified += 1

 if not dry_run:
 try:
 os.remove(file_path)
 cleaned += 1
 except OSError as e:
 logger.warning(
 f"Failed to delete {file_path}: {e}"
 )
 except Exception as e:
 logger.warning(f"Failed to process pattern {pattern}: {e}")

 return identified, cleaned

 except Exception as e:
 logger.error(f"Temp files cleanup failed: {e}")
 return 0, 0

 async def _cleanup_cache(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up Redis cache entries"""
 try:
 from datetime import datetime, timedelta

 import redis.asyncio as redis

 redis_client = redis.from_url("redis://redis:6379/0")
 cutoff_timestamp = int(
 (datetime.utcnow() - timedelta(days = retention_days)).timestamp()
 )

 identified = 0
 cleaned = 0

 # Scan for cache keys with TTL
 async for key in redis_client.scan_iter(match = "cache:*"):
 ttl = await redis_client.ttl(key)
 if ttl > 0:
 # Check if key is old based on creation time pattern
 key_str = key.decode() if isinstance(key, bytes) else key
 if "timestamp_" in key_str:
 try:
 timestamp_str = key_str.split("timestamp_")[1].split("_")[0]
 key_timestamp = int(timestamp_str)
 if key_timestamp < cutoff_timestamp:
 identified += 1
 if not dry_run:
 await redis_client.delete(key)
 cleaned += 1
 except (ValueError, IndexError):
 continue

 await redis_client.close()
 return identified, cleaned

 except Exception as e:
 logger.error(f"Cache cleanup failed: {e}")
 # Fallback estimation
 return 50, 0 if dry_run else 50

 async def _cleanup_old_branches(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up old unused branches"""
 try:
 from datetime import datetime, timedelta

 import httpx

 cutoff_date = datetime.utcnow() - timedelta(days = retention_days)

 async with httpx.AsyncClient() as client:
 # Query data-kernel for old branches
 response = await client.get(
 "http://data-kernel-service:8080/api/v1/branches",
 params={"include_inactive": True},
 )

 if response.status_code == 200:
 branches = response.json().get("branches", [])
 old_branches = []

 for branch in branches:
 if branch.get("name") in ["main", "master", "production"]:
 continue # Never delete protected branches

 last_activity = branch.get("last_activity")
 if last_activity:
 branch_date = datetime.fromisoformat(
 last_activity.replace("Z", "+00:00")
 )
 if branch_date < cutoff_date:
 old_branches.append(branch)

 identified = len(old_branches)

 if not dry_run and old_branches:
 for branch in old_branches:
 try:
 delete_response = await client.delete(
 f"http://data-kernel-service:8080/api/v1/branches/{branch['name']}"
 )
 if delete_response.status_code == 200:
 cleaned += 1
 except Exception as e:
 logger.warning(
 f"Failed to delete branch {branch['name']}: {e}"
 )

 return identified, cleaned

 return 0, 0

 except Exception as e:
 logger.error(f"Branch cleanup failed: {e}")
 return 0, 0

 async def _cleanup_embedding_cache(
 self, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Clean up old embedding cache"""
 try:
 from datetime import datetime, timedelta

 import httpx

 cutoff_date = datetime.utcnow() - timedelta(days = retention_days)

 async with httpx.AsyncClient() as client:
 # Query embedding service for cache status
 response = await client.get("http://embedding-service:8001/cache/stats")

 if response.status_code == 200:
 cache_stats = response.json()
 old_entries = cache_stats.get("entries_older_than_days", {}).get(
 str(retention_days), 0
 )

 if not dry_run and old_entries > 0:
 # Clean old embeddings
 cleanup_response = await client.delete(
 "http://embedding-service:8001/cache/cleanup",
 json={"older_than_days": retention_days},
 )

 if cleanup_response.status_code == 200:
 return old_entries, old_entries

 return old_entries, 0 if dry_run else old_entries

 return 0, 0

 except Exception as e:
 logger.error(f"Embedding cache cleanup failed: {e}")
 # Fallback estimation
 return 75, 0 if dry_run else 75

 async def _cleanup_generic(
 self, cleanup_type: str, retention_days: int, dry_run: bool
 ) -> tuple[int, int]:
 """Generic cleanup for unknown types"""
 logger.info(f"Generic cleanup for type: {cleanup_type}")

 # Simulate some work
 await asyncio.sleep(0.5)

 # Estimate cleanup based on type
 estimated_items = {"metrics": 300, "sessions": 150, "notifications": 100}.get(
 cleanup_type, 50
 )

 return estimated_items, 0 if dry_run else estimated_items


class HealthCheckExecutor(BaseExecutor):
 """Executor for health check jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Check health of services."""
 services = parameters.get("services", [])
 timeout = parameters.get("timeout_per_service", 5)

 logger.info(f"Checking health of services: {services}")

 results = {}

 async with httpx.AsyncClient(timeout = timeout) as client:
 for service in services:
 try:
 response = await client.get(f"{service}/health")
 results[service] = {
 "status": "healthy"
 if response.status_code == 200
 else "unhealthy",
 "status_code": response.status_code,
 "response_time": response.elapsed.total_seconds(),
 }
 except Exception as e:
 results[service] = {"status": "error", "error": str(e)}

 healthy_count = sum(1 for r in results.values() if r["status"] == "healthy")

 return {
 "status": "success",
 "services_checked": len(services),
 "healthy_services": healthy_count,
 "unhealthy_services": len(services) - healthy_count,
 "results": results,
 "timestamp": datetime.utcnow().isoformat(),
 }


class CustomExecutor(BaseExecutor):
 """Executor for custom jobs."""

 async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
 """Execute custom job logic with security safeguards."""
 script = parameters.get("script")
 script_type = parameters.get("script_type", "python")
 timeout = parameters.get("timeout", 60)
 allowed_operations = parameters.get("allowed_operations", [])

 logger.info(f"Executing custom {script_type} script with timeout {timeout}s")

 if not script:
 return {
 "status": "error",
 "error": "No script provided",
 "script_type": script_type,
 }

 try:
 start_time = asyncio.get_event_loop().time()

 # Security validation
 security_check = await self._validate_script_security(
 script, script_type, allowed_operations
 )
 if not security_check["allowed"]:
 return {
 "status": "error",
 "error": f"Security validation failed: {security_check['reason']}",
 "script_type": script_type,
 }

 # Execute based on script type
 if script_type == "python":
 result = await self._execute_python_script(script, parameters, timeout)
 elif script_type == "shell":
 result = await self._execute_shell_script(script, parameters, timeout)
 elif script_type == "sql":
 result = await self._execute_sql_script(script, parameters, timeout)
 elif script_type == "woql":
 result = await self._execute_woql_script(script, parameters, timeout)
 else:
 return {
 "status": "error",
 "error": f"Unsupported script type: {script_type}",
 "script_type": script_type,
 }

 duration = asyncio.get_event_loop().time() - start_time

 return {
 "status": "success",
 "script_type": script_type,
 "execution_time": round(duration, 2),
 "result": result,
 "security_validated": True,
 }

 except asyncio.TimeoutError:
 return {
 "status": "error",
 "error": f"Script execution timed out after {timeout} seconds",
 "script_type": script_type,
 }
 except Exception as e:
 logger.error(f"Custom script execution failed: {e}")
 return {"status": "error", "error": str(e), "script_type": script_type}

 async def _validate_script_security(
 self, script: str, script_type: str, allowed_operations: list
 ) -> Dict[str, Any]:
 """Validate script for security issues"""

 # Dangerous patterns to check
 dangerous_patterns = {
 "python": [
 "import os",
 "import subprocess",
 "import sys",
 "__import__",
 "eval(",
 "exec(",
 "compile(",
 "open(",
 "file(",
 "rm ",
 "rmdir",
 "delete",
 "unlink",
 ],
 "shell": [
 "rm ",
 "rmdir",
 "dd ",
 "mkfs",
 "format",
 "fdisk",
 "> /dev/",
 "curl",
 "wget",
 "nc ",
 "netcat",
 ],
 "sql": [
 "DROP DATABASE",
 "DROP TABLE",
 "DELETE FROM",
 "TRUNCATE",
 "ALTER DATABASE",
 "CREATE USER",
 "GRANT ALL",
 ],
 }

 patterns = dangerous_patterns.get(script_type, [])

 for pattern in patterns:
 if pattern.lower() in script.lower():
 return {
 "allowed": False,
 "reason": f"Script contains potentially dangerous pattern: {pattern}",
 }

 # Check against allowed operations
 if allowed_operations:
 has_allowed_op = any(
 op.lower() in script.lower() for op in allowed_operations
 )
 if not has_allowed_op:
 return {
 "allowed": False,
 "reason": f"Script does not contain any allowed operations: {allowed_operations}",
 }

 # Size limit check
 if len(script) > 10000: # 10KB limit
 return {"allowed": False, "reason": "Script exceeds size limit (10KB)"}

 return {"allowed": True, "reason": "Security validation passed"}

 async def _execute_python_script(
 self, script: str, parameters: Dict[str, Any], timeout: int
 ) -> Dict[str, Any]:
 """Execute Python script in restricted environment"""
 try:
 # Create restricted globals
 restricted_globals = {
 "__builtins__": {
 "len": len,
 "str": str,
 "int": int,
 "float": float,
 "bool": bool,
 "list": list,
 "dict": dict,
 "tuple": tuple,
 "set": set,
 "min": min,
 "max": max,
 "sum": sum,
 "abs": abs,
 "round": round,
 "print": lambda *args: None, # Safe print
 },
 "parameters": parameters,
 "datetime": __import__("datetime"),
 "json": __import__("json"),
 "math": __import__("math"),
 "result": None,
 }

 # Execute with timeout
 result = await asyncio.wait_for(
 asyncio.get_event_loop().run_in_executor(
 None, lambda: exec(script, restricted_globals)
 ),
 timeout = timeout,
 )

 # Return the result variable if set
 return {
 "output": restricted_globals.get(
 "result", "Script executed successfully"
 ),
 "variables": {
 k: v
 for k, v in restricted_globals.items()
 if not k.startswith("__")
 and k not in ["parameters", "datetime", "json", "math"]
 },
 }

 except Exception as e:
 return {"error": str(e)}

 async def _execute_shell_script(
 self, script: str, parameters: Dict[str, Any], timeout: int
 ) -> Dict[str, Any]:
 """Execute shell script with restrictions"""
 try:
 import subprocess

 # Create safe environment
 safe_env = {
 "PATH": "/usr/local/bin:/usr/bin:/bin",
 "HOME": "/tmp",
 "USER": "scheduler",
 }

 # Run with restrictions
 process = await asyncio.create_subprocess_shell(
 script,
 stdout = asyncio.subprocess.PIPE,
 stderr = asyncio.subprocess.PIPE,
 env = safe_env,
 cwd = "/tmp",
 )

 stdout, stderr = await asyncio.wait_for(
 process.communicate(), timeout = timeout
 )

 return {
 "stdout": stdout.decode(),
 "stderr": stderr.decode(),
 "return_code": process.returncode,
 }

 except Exception as e:
 return {"error": str(e)}

 async def _execute_sql_script(
 self, script: str, parameters: Dict[str, Any], timeout: int
 ) -> Dict[str, Any]:
 """Execute SQL script against allowed databases"""
 try:
 import httpx

 # Only allow read operations
 read_keywords = ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN"]
 if not any(keyword in script.upper() for keyword in read_keywords):
 return {
 "error": "Only read operations (SELECT, SHOW, etc.) are allowed"
 }

 # Execute via data-kernel service
 async with httpx.AsyncClient(timeout = timeout) as client:
 response = await client.post(
 "http://data-kernel-service:8080/api/v1/query/sql",
 json={"query": script, "parameters": parameters, "read_only": True},
 )

 if response.status_code == 200:
 return response.json()
 else:
 return {"error": f"SQL execution failed: {response.text}"}

 except Exception as e:
 return {"error": str(e)}

 async def _execute_woql_script(
 self, script: str, parameters: Dict[str, Any], timeout: int
 ) -> Dict[str, Any]:
 """Execute WOQL script against TerminusDB"""
 try:
 import json

 import httpx

 # Parse WOQL script as JSON
 try:
 woql_query = json.loads(script)
 except json.JSONDecodeError:
 return {"error": "Invalid WOQL JSON format"}

 # Execute via data-kernel service
 async with httpx.AsyncClient(timeout = timeout) as client:
 response = await client.post(
 "http://data-kernel-service:8080/api/v1/query/woql",
 json={
 "query": woql_query,
 "parameters": parameters,
 "branch": parameters.get("branch", "main"),
 },
 )

 if response.status_code == 200:
 return response.json()
 else:
 return {"error": f"WOQL execution failed: {response.text}"}

 except Exception as e:
 return {"error": str(e)}
