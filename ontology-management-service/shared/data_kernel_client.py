"""
TerminusGatewayClient - gRPC client wrapper for Data-Kernel Gateway
Maintains same interface as TerminusDBClient for easy migration
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import grpc
from opentelemetry import trace

# Production imports - proto stubs must be available
from shared.proto_stubs import data_kernel_pb2 as dk_pb2
from shared.proto_stubs import data_kernel_pb2_grpc as dk_pb2_grpc
from shared.terminus_context import (
    get_author,
    get_branch,
    get_commit_message,
    get_trace_id,
)

# gRPC instrumentation is handled by create_instrumented_channel



logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class TerminusGatewayClient:
 """
 gRPC client for Data-Kernel Gateway.
 Implements same interface as TerminusDBClient for drop-in replacement.
 """

 def __init__(
 self,
 endpoint: str = None,
 username: str = None,
 password: str = None,
 service_name: str = "oms-service",
 use_connection_pool: bool = True,
 ):
 """Initialize the gRPC client."""

 # Use gateway endpoint from env or default
 self.target = endpoint or os.getenv(
 "DATA_KERNEL_GRPC_ENDPOINT", "data-kernel:50051"
 )
 self.service_name = service_name

 # Create channel with interceptors
 from shared.grpc_interceptors import create_instrumented_channel

 self.channel = create_instrumented_channel(self.target)

 # Create stubs for different services
 self.doc_stub = dk_pb2_grpc.DocumentServiceStub(self.channel)
 self.query_stub = dk_pb2_grpc.QueryServiceStub(self.channel)
 self.schema_stub = dk_pb2_grpc.SchemaServiceStub(self.channel)
 self.unified_stub = dk_pb2_grpc.DataKernelServiceStub(self.channel)

 logger.info(f"TerminusGatewayClient initialized for {self.target}")

 async def __aenter__(self):
 """Async context manager entry."""
 return self

 async def __aexit__(self, exc_type, exc_val, exc_tb):
 """Async context manager exit."""
 await self.close()

 async def close(self):
 """Close the gRPC channel."""
 await self.channel.close()

 async def ping(self) -> Dict[str, Any]:
 """Check connectivity to Data-Kernel Gateway."""
 try:
 request = dk_pb2.HealthCheckRequest()
 response = await self.unified_stub.HealthCheck(request)
 return {
 "status": "healthy" if response.healthy else "unhealthy",
 "details": dict(response.details),
 }
 except grpc.RpcError as e:
 logger.error(f"Health check failed: {e}")
 return {"status": "error", "error": str(e)}

 def _get_commit_meta(self, commit_msg: Optional[str] = None):
 """Create CommitMeta from current context."""
 # Get values from context variables (set by middleware)
 author = get_author()
 branch = get_branch()
 trace_id = get_trace_id()

 # Use provided commit message or build from context
 final_commit_msg = get_commit_message(commit_msg)

 if dk_pb2:
 return dk_pb2.CommitMeta(
 author = author,
 commit_msg = final_commit_msg,
 trace_id = trace_id,
 branch = branch,
 )
 else:
 # Return dict when proto stubs aren't available
 return {
 "author": author,
 "commit_msg": final_commit_msg,
 "trace_id": trace_id,
 "branch": branch,
 }

 async def query(
 self, db_name: str, query: Dict[str, Any], commit_msg: Optional[str] = None
 ) -> Dict[str, Any]:
 """Execute a WOQL query."""
 with tracer.start_as_current_span("query") as span:
 span.set_attribute("db.name", db_name)

 request = dk_pb2.WOQL(
 query = json.dumps(query),
 database = db_name,
 meta = self._get_commit_meta(commit_msg),
 )

 # Execute query and collect streamed results
 results = []
 try:
 async for doc in self.query_stub.Execute(request):
 if doc.json:
 results.append(json.loads(doc.json.decode("utf-8")))

 # Return combined results
 if len(results) == 1:
 return results[0]
 elif results:
 return {"results": results}
 else:
 return {}
 except grpc.RpcError as e:
 logger.error(f"Query failed: {e}")
 raise

 async def get_document(
 self,
 db_name: str,
 doc_id: str,
 branch: Optional[str] = None,
 revision: Optional[str] = None,
 ) -> Optional[Dict[str, Any]]:
 """Get a document by ID."""
 with tracer.start_as_current_span("get_document") as span:
 span.set_attribute("db.name", db_name)
 span.set_attribute("doc.id", doc_id)

 # Use provided branch or get from context
 actual_branch = branch if branch is not None else get_branch()

 request = dk_pb2.DocumentId(
 id = doc_id,
 database = db_name,
 meta = dk_pb2.CommitMeta(branch = actual_branch),
 )

 try:
 response = await self.doc_stub.Get(request)
 if response.json:
 return json.loads(response.json.decode("utf-8"))
 return None
 except grpc.RpcError as e:
 if e.code() == grpc.StatusCode.NOT_FOUND:
 return None
 logger.error(f"Get document failed: {e}")
 raise

 async def insert_document(
 self,
 db_name: str,
 document: Dict[str, Any],
 commit_msg: str = "Insert document",
 ) -> Dict[str, Any]:
 """Insert a new document."""
 with tracer.start_as_current_span("insert_document") as span:
 span.set_attribute("db.name", db_name)

 request = dk_pb2.Document(
 json = json.dumps(document).encode("utf-8"),
 database = db_name,
 meta = self._get_commit_meta(commit_msg),
 )

 try:
 response = await self.doc_stub.Put(request)
 return {"id": response.id}
 except grpc.RpcError as e:
 logger.error(f"Insert document failed: {e}")
 raise

 async def update_document(
 self,
 db_name: str,
 doc_id: str,
 updates: Dict[str, Any],
 commit_msg: str = "Update document",
 ) -> Dict[str, Any]:
 """Update an existing document."""
 with tracer.start_as_current_span("update_document") as span:
 span.set_attribute("db.name", db_name)
 span.set_attribute("doc.id", doc_id)

 # Add @id to updates
 doc_data = {"@id": doc_id, **updates}

 request = dk_pb2.Document(
 json = json.dumps(doc_data).encode("utf-8"),
 database = db_name,
 meta = self._get_commit_meta(commit_msg),
 )

 try:
 response = await self.doc_stub.Patch(request)
 return {"id": response.id}
 except grpc.RpcError as e:
 logger.error(f"Update document failed: {e}")
 raise

 async def delete_document(
 self, db_name: str, doc_id: str, commit_msg: str = "Delete document"
 ) -> Dict[str, Any]:
 """Delete a document."""
 with tracer.start_as_current_span("delete_document") as span:
 span.set_attribute("db.name", db_name)
 span.set_attribute("doc.id", doc_id)

 request = dk_pb2.DocumentId(
 id = doc_id, database = db_name, meta = self._get_commit_meta(commit_msg)
 )

 try:
 await self.doc_stub.Delete(request)
 return {"deleted": True}
 except grpc.RpcError as e:
 logger.error(f"Delete document failed: {e}")
 raise

 async def get_schema(self, db_name: str) -> Dict[str, Any]:
 """Get database schema."""
 with tracer.start_as_current_span("get_schema") as span:
 span.set_attribute("db.name", db_name)

 request = dk_pb2.SchemaRequest(
 database = db_name, meta = self._get_commit_meta()
 )

 try:
 response = await self.schema_stub.Get(request)
 if response.json:
 return json.loads(response.json.decode("utf-8"))
 return {}
 except grpc.RpcError as e:
 logger.error(f"Get schema failed: {e}")
 raise

 async def update_schema(
 self, db_name: str, schema: Dict[str, Any], commit_msg: str = "Update schema"
 ) -> Dict[str, Any]:
 """Update database schema."""
 with tracer.start_as_current_span("update_schema") as span:
 span.set_attribute("db.name", db_name)

 request = dk_pb2.Schema(
 json = json.dumps(schema).encode("utf-8"),
 database = db_name,
 meta = self._get_commit_meta(commit_msg),
 )

 try:
 await self.schema_stub.Update(request)
 return {"updated": True}
 except grpc.RpcError as e:
 logger.error(f"Update schema failed: {e}")
 raise

 # Methods to maintain compatibility with TerminusDBClient
 async def create_database(
 self, db_name: str, label: Optional[str] = None
 ) -> Dict[str, Any]:
 """Create a database using unified service."""
 with tracer.start_as_current_span("create_database") as span:
 span.set_attribute("db.name", db_name)

 try:
 request = dk_pb2.CreateDatabaseRequest(
 database = db_name,
 label = label or f"{db_name} Database",
 comment = f"Created by {self.service_name}",
 )

 response = await self.unified_stub.CreateDatabase(request)
 return {
 "created": response.success,
 "database": db_name,
 "message": response.message
 if hasattr(response, "message")
 else "Database created",
 }
 except grpc.RpcError as e:
 if e.code() == grpc.StatusCode.ALREADY_EXISTS:
 logger.warning(f"Database {db_name} already exists")
 return {
 "created": False,
 "database": db_name,
 "message": "Database already exists",
 }
 logger.error(f"Create database failed: {e}")
 raise

 async def delete_database(self, db_name: str) -> Dict[str, Any]:
 """Delete a database using unified service."""
 with tracer.start_as_current_span("delete_database") as span:
 span.set_attribute("db.name", db_name)

 try:
 request = dk_pb2.DeleteDatabaseRequest(
 database = db_name, force = False # Safe delete by default
 )

 response = await self.unified_stub.DeleteDatabase(request)
 return {
 "deleted": response.success,
 "database": db_name,
 "message": response.message
 if hasattr(response, "message")
 else "Database deleted",
 }
 except grpc.RpcError as e:
 if e.code() == grpc.StatusCode.NOT_FOUND:
 logger.warning(f"Database {db_name} not found")
 return {
 "deleted": False,
 "database": db_name,
 "message": "Database not found",
 }
 logger.error(f"Delete database failed: {e}")
 raise

 async def get_databases(self) -> List[str]:
 """List databases using unified service."""
 with tracer.start_as_current_span("get_databases"):
 try:
 request = dk_pb2.ListDatabasesRequest()
 response = await self.unified_stub.ListDatabases(request)

 # Return list of database names
 databases = []
 for db in response.databases:
 databases.append(
 {
 "name": db.name,
 "label": db.label if hasattr(db, "label") else db.name,
 "created_at": db.created_at
 if hasattr(db, "created_at")
 else None,
 }
 )

 return databases
 except grpc.RpcError as e:
 logger.error(f"List databases failed: {e}")
 # Return empty list on error to allow service to continue
 return []
