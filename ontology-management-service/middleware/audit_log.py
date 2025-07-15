"""
Audit Log Middleware - Production-ready HTTP access audit integration
Sends all API request audit events to audit-service
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
 """
 Production HTTP access audit middleware - sends events to audit-service
 """

 async def dispatch(self, request: Request, call_next):
 # Start timing
 start_time = time.time()

 # Get request info
 request_info = {
 "timestamp": datetime.utcnow().isoformat(),
 "method": request.method,
 "path": request.url.path,
 "query_params": dict(request.query_params),
 "client_host": request.client.host if request.client else None,
 "user_agent": request.headers.get("user-agent", ""),
 }

 # Get user info if available
 if hasattr(request.state, "user_context"):
 request_info["user_id"] = request.state.user_context.user_id
 request_info["username"] = request.state.user_context.username

 # Get request ID if available
 if hasattr(request.state, "request_id"):
 request_info["request_id"] = request.state.request_id

 # Process request
 response = await call_next(request)

 # Calculate duration
 duration = time.time() - start_time

 # Send audit entry to audit-service
 audit_entry = {
 **request_info,
 "status_code": response.status_code,
 "duration_ms": round(duration * 1000, 2),
 }

 # Send to audit-service asynchronously (don't block response)
 asyncio.create_task(self._send_http_audit_event(audit_entry))

 # Also log locally for immediate debugging
 if response.status_code >= 500:
 logger.error(f"HTTP Access Audit: {json.dumps(audit_entry)}")
 elif response.status_code >= 400:
 logger.warning(f"HTTP Access Audit: {json.dumps(audit_entry)}")
 else:
 logger.debug(f"HTTP Access Audit: {json.dumps(audit_entry)}")

 return response

 async def _send_http_audit_event(self, audit_entry: dict):
 """Send HTTP access audit event to audit-service"""
 try:
 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8001"
 )

 # Map HTTP audit data to audit-service format
 audit_payload = {
 "event_type": "http.request",
 "event_category": "http_access",
 "user_id": audit_entry.get("user_id", "anonymous"),
 "username": audit_entry.get("username", "anonymous"),
 "target_type": "http_endpoint",
 "target_id": audit_entry["path"],
 "operation": audit_entry["method"],
 "severity": self._get_severity_from_status(audit_entry["status_code"]),
 "metadata": {
 "source": "oms_http_middleware",
 "method": audit_entry["method"],
 "path": audit_entry["path"],
 "query_params": audit_entry.get("query_params", {}),
 "status_code": audit_entry["status_code"],
 "duration_ms": audit_entry["duration_ms"],
 "client_host": audit_entry.get("client_host"),
 "user_agent": audit_entry.get("user_agent", ""),
 "request_id": audit_entry.get("request_id"),
 "timestamp": audit_entry["timestamp"],
 },
 }

 # Send to audit-service with timeout and error handling
 async with httpx.AsyncClient(timeout = 3.0) as client:
 response = await client.post(
 f"{audit_service_url}/api/v2/events/direct", json = audit_payload
 )
 response.raise_for_status()

 logger.debug(
 f"HTTP audit event sent to audit-service: {audit_entry['method']} {audit_entry['path']}"
 )

 except Exception as e:
 logger.warning(f"Failed to send HTTP audit event to audit-service: {e}")
 # Don't fail the HTTP request due to audit logging failure

 def _get_severity_from_status(self, status_code: int) -> str:
 """Map HTTP status code to audit severity"""
 if status_code >= 500:
 return "ERROR"
 elif status_code >= 400:
 return "WARNING"
 else:
 return "INFO"
