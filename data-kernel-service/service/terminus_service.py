import os
import time
from typing import Any, Dict, Optional, List, Tuple
from contextlib import asynccontextmanager
import logging
from functools import wraps
from contextvars import ContextVar

from database.clients.terminus_db import TerminusDBClient
from core.observability.tracing import trace_method
from data_kernel.hook import CommitHookPipeline
from data_kernel.hook.base import CommitMeta, ValidationError

logger = logging.getLogger(__name__)

# Context variables for author and commit message
CURRENT_AUTHOR = ContextVar("author", default="system")
CURRENT_COMMIT_MSG = ContextVar("commit_msg", default="")


class TerminusService:
    """Singleton service wrapper for TerminusDB operations with enhanced tracing and commit metadata."""
    
    _instance = None
    _client: Optional[TerminusDBClient] = None
    _health_cache: Optional[Tuple[Dict[str, Any], float]] = None
    _health_cache_ttl: int = 60  # 60 seconds cache TTL
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = TerminusDBClient(
                endpoint=os.getenv("TERMINUSDB_ENDPOINT", "http://terminusdb:6363"),
                username=os.getenv("TERMINUSDB_USER", "admin"),
                password=os.getenv("TERMINUSDB_PASS", "changeme-admin-pass"),
                service_name="data-kernel-gateway",
                use_connection_pool=True
            )
    
    async def initialize(self):
        """Initialize the service and verify connection."""
        if self._client:
            await self._client.__aenter__()
            health = await self._client.ping()
            logger.info(f"TerminusDB connection established: {health}")
            return health
    
    async def close(self):
        """Close the service and cleanup connections."""
        if self._client:
            await self._client.__aexit__(None, None, None)
    
    @staticmethod
    def commit_author(author: str = None):
        """Decorator to inject author information into commits using context variables."""
        def decorator(func):
            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                # Extract author from kwargs or use default
                provided_author = kwargs.get('author', author)
                if provided_author:
                    # Set context variable for this operation
                    CURRENT_AUTHOR.set(provided_author)
                else:
                    # Use existing context or default
                    provided_author = CURRENT_AUTHOR.get()
                
                # Add author to commit metadata if method uses commit_msg
                if 'commit_msg' in kwargs:
                    original_msg = kwargs.get('commit_msg', '')
                    kwargs['commit_msg'] = f"[{provided_author}] {original_msg}"
                    # Also set commit message context
                    CURRENT_COMMIT_MSG.set(kwargs['commit_msg'])
                
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator
    
    @trace_method
    async def get_document(self, db_name: str, doc_id: str, branch: str = "main", revision: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve a document from TerminusDB with full branch/revision support."""
        try:
            # Implement proper branch support using TerminusDB's context system
            query_context = {
                "schema": f"{db_name}",
                "type": "instance",
                "branch": branch
            }
            
            # Add revision support if specified
            if revision:
                query_context["commit"] = revision
            
            # Construct query with proper TerminusDB Get operation
            query = {
                "@type": "woql:Get",
                "@context": query_context,
                "document": {
                    "@type": "woql:Node",
                    "node": doc_id
                },
                "result": {
                    "@type": "woql:Variable", 
                    "variable": "Document"
                }
            }
            
            # Alternative: use TerminusDB's direct document access
            if hasattr(self._client, 'get_document'):
                try:
                    # Use native TerminusDB client method if available
                    result = await self._client.get_document(
                        database=db_name,
                        doc_id=doc_id,
                        branch=branch,
                        revision=revision
                    )
                    if result is not None:
                        return result
                except Exception as native_error:
                    logger.warning(f"Native get_document failed: {native_error}, falling back to query")
            
            # Execute query with branch context
            try:
                result = await self._client.query(db_name, query, branch=branch)
                
                # Extract document from bindings
                if result and "bindings" in result:
                    bindings = result["bindings"]
                    if bindings and len(bindings) > 0:
                        document = bindings[0].get("Document", {})
                        if isinstance(document, dict) and "@value" in document:
                            return document["@value"]
                        return document
                
                return None
                
            except Exception as query_error:
                logger.warning(f"Branch-aware query failed: {query_error}, trying simple query")
                
                # Fallback: simple query without branch context
                simple_query = {
                    "@type": "woql:Triple",
                    "subject": {"@type": "woql:Node", "node": doc_id},
                    "predicate": {"@type": "woql:Variable", "variable": "Predicate"},
                    "object": {"@type": "woql:Variable", "variable": "Object"}
                }
                
                result = await self._client.query(db_name, simple_query)
                
                # Reconstruct document from triples
                if result and "bindings" in result:
                    doc_data = {}
                    for binding in result["bindings"]:
                        pred = binding.get("Predicate", {})
                        obj = binding.get("Object", {})
                        
                        if pred and obj:
                            pred_name = pred.get("@value", pred.get("node", ""))
                            obj_value = obj.get("@value", obj.get("node", ""))
                            
                            if pred_name and obj_value:
                                doc_data[pred_name] = obj_value
                    
                    if doc_data:
                        doc_data["@id"] = doc_id
                        return doc_data
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get document {doc_id} from branch {branch}: {e}")
            return None
    
    @trace_method
    @TerminusService.commit_author()
    async def insert_document(self, db_name: str, document: Dict[str, Any], commit_msg: str = "Insert document", author: str = None) -> Dict[str, Any]:
        """Insert a new document into TerminusDB."""
        query = {
            "@type": "InsertDocument",
            "document": document
        }
        
        # Execute query
        result = await self._client.query(db_name, query, commit_msg=commit_msg)
        
        # Validate result
        if result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"Insert document failed: {error_msg}")
            raise Exception(f"Failed to insert document: {error_msg}")
        
        # Run commit hooks with validation
        try:
            await self._run_commit_hooks(
                db_name=db_name,
                diff={"after": document},
                commit_msg=commit_msg,
                author=author
            )
        except ValidationError as e:
            # Rollback on validation failure
            logger.error(f"Validation failed, attempting rollback: {e}")
            await self._rollback_commit(db_name, result)
            raise
        
        return result
    
    @trace_method
    @TerminusService.commit_author()
    async def update_document(self, db_name: str, doc_id: str, updates: Dict[str, Any], commit_msg: str = "Update document", author: str = None) -> Dict[str, Any]:
        """Update an existing document in TerminusDB."""
        # Get current document for before state
        before = await self.get_document(db_name, doc_id)
        
        query = {
            "@type": "UpdateDocument",
            "document": {
                "@id": doc_id,
                **updates
            }
        }
        
        # Execute query
        result = await self._client.query(db_name, query, commit_msg=commit_msg)
        
        # Validate result
        if result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"Update document failed: {error_msg}")
            raise Exception(f"Failed to update document: {error_msg}")
        
        # Run commit hooks
        await self._run_commit_hooks(
            db_name=db_name,
            diff={"before": before, "after": {"@id": doc_id, **updates}},
            commit_msg=commit_msg,
            author=author
        )
        
        return result
    
    @trace_method
    @TerminusService.commit_author()
    async def delete_document(self, db_name: str, doc_id: str, commit_msg: str = "Delete document", author: str = None) -> Dict[str, Any]:
        """Delete a document from TerminusDB."""
        # Get document before deletion
        before = await self.get_document(db_name, doc_id)
        
        query = {
            "@type": "DeleteDocument",
            "document": doc_id
        }
        
        # Execute query
        result = await self._client.query(db_name, query, commit_msg=commit_msg)
        
        # Validate result
        if result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"Delete document failed: {error_msg}")
            raise Exception(f"Failed to delete document: {error_msg}")
        
        # Run commit hooks
        await self._run_commit_hooks(
            db_name=db_name,
            diff={"before": before, "after": None},
            commit_msg=commit_msg,
            author=author
        )
        
        return result
    
    @trace_method
    async def query(self, db_name: str, query: Dict[str, Any], commit_msg: Optional[str] = None) -> Dict[str, Any]:
        """Execute a raw WOQL query."""
        return await self._client.query(db_name, query, commit_msg=commit_msg)
    
    @trace_method
    async def branch_switch(self, db_name: str, branch_name: str) -> bool:
        """Switch to a different branch (placeholder - needs TerminusDB branch API)."""
        # This would need to be implemented based on TerminusDB's branch API
        logger.info(f"Switching to branch {branch_name} in database {db_name}")
        return True
    
    @trace_method
    async def get_schema(self, db_name: str) -> Dict[str, Any]:
        """Get the schema for a database."""
        return await self._client.get_schema(db_name)
    
    @trace_method
    @TerminusService.commit_author()
    async def update_schema(self, db_name: str, schema: Dict[str, Any], commit_msg: str = "Update schema", author: str = None) -> Dict[str, Any]:
        """Update the schema for a database."""
        return await self._client.update_schema(db_name, schema, commit_msg=commit_msg)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the TerminusDB connection with caching."""
        current_time = time.time()
        
        # Check if we have a valid cache
        if self._health_cache is not None:
            cached_result, cache_time = self._health_cache
            if current_time - cache_time < self._health_cache_ttl:
                logger.debug(f"Returning cached health check (age: {current_time - cache_time:.1f}s)")
                return cached_result
        
        # Perform actual health check
        try:
            result = await self._client.ping()
            # Cache successful result
            self._health_cache = (result, current_time)
            return result
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            # Don't cache failures
            self._health_cache = None
            raise
    
    async def _run_commit_hooks(self, db_name: str, diff: Dict[str, Any], commit_msg: str, author: str = None):
        """Run commit hooks after successful operations"""
        try:
            # Get context information
            from shared.terminus_context import get_branch, get_trace_id
            
            # Use context variables for author and commit message
            final_author = author or CURRENT_AUTHOR.get()
            final_commit_msg = commit_msg or CURRENT_COMMIT_MSG.get() or "No commit message"
            
            # Build commit metadata
            meta = CommitMeta(
                author=final_author,
                branch=get_branch(),
                trace_id=get_trace_id(),
                commit_msg=final_commit_msg,
                database=db_name
            )
            
            # Run pipeline
            result = await CommitHookPipeline.run(meta, diff)
            logger.debug(f"Commit hooks completed: {result}")
            
        except Exception as e:
            logger.error(f"Error running commit hooks: {e}")
            # Don't fail the operation if hooks fail
            # This could be configurable
            if isinstance(e, ValidationError):
                raise  # Re-raise validation errors for rollback
    
    async def _rollback_commit(self, db_name: str, commit_result: Dict[str, Any]):
        """Rollback a commit using TerminusDB API"""
        try:
            # Extract commit ID from result
            commit_id = commit_result.get("commit_id") or commit_result.get("head")
            if not commit_id:
                logger.error("Cannot rollback: no commit ID found")
                return
            
            # Get current branch
            from shared.terminus_context import get_branch
            branch = get_branch()
            
            logger.info(f"Performing rollback: database={db_name}, branch={branch}, commit={commit_id}")
            
            # Implement actual rollback using TerminusDB API
            try:
                # Use the client's reset method if available
                if hasattr(self._client, 'reset'):
                    reset_result = await self._client.reset(db_name, branch, commit_id)
                    logger.info(f"Reset successful: {reset_result}")
                else:
                    # Fallback to direct API call
                    import httpx
                    import os
                    
                    terminus_endpoint = os.getenv("TERMINUSDB_ENDPOINT", "http://terminusdb:6363")
                    reset_url = f"{terminus_endpoint}/api/branch/{db_name}/local/branch/{branch}/reset/{commit_id}"
                    
                    # Get auth from client if available
                    auth_header = None
                    if hasattr(self._client, 'api_token') and self._client.api_token:
                        auth_header = {"Authorization": f"Basic {self._client.api_token}"}
                    elif hasattr(self._client, 'key') and self._client.key:
                        auth_header = {"Authorization": f"Basic {self._client.key}"}
                    
                    async with httpx.AsyncClient() as http_client:
                        headers = auth_header or {}
                        headers["Content-Type"] = "application/json"
                        
                        response = await http_client.post(reset_url, headers=headers, json={})
                        
                        if response.status_code == 200:
                            logger.info(f"Successfully rolled back branch '{branch}' to before commit '{commit_id}'")
                        else:
                            logger.error(f"Rollback API call failed: {response.status_code} - {response.text}")
                            
                # Audit the rollback operation
                await self._audit_rollback_operation(db_name, branch, commit_id)
                
            except Exception as api_error:
                logger.error(f"Rollback API operation failed: {api_error}")
                # Try alternative rollback method - query previous commit and restore
                await self._fallback_rollback(db_name, branch, commit_id)
            
        except Exception as e:
            logger.error(f"Failed to rollback commit: {e}")
    
    async def _audit_rollback_operation(self, db_name: str, branch: str, commit_id: str):
        """Audit the rollback operation"""
        try:
            import httpx
            import os
            import time
            
            audit_url = os.getenv("AUDIT_SERVICE_URL", "http://audit-service:8000")
            
            audit_event = {
                "action": "ROLLBACK_COMMIT",
                "resource": f"terminusdb.{db_name}.{branch}",
                "user_id": "system",
                "details": {
                    "database": db_name,
                    "branch": branch,
                    "rolled_back_commit": commit_id,
                    "timestamp": time.time(),
                    "service": "data-kernel-service",
                    "reason": "commit_hook_validation_failed"
                }
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(f"{audit_url}/audit/log", json=audit_event, timeout=5.0)
                logger.debug(f"Rollback operation audited for commit {commit_id}")
                
        except Exception as e:
            logger.warning(f"Failed to audit rollback operation: {e}")
    
    async def _fallback_rollback(self, db_name: str, branch: str, commit_id: str):
        """Fallback rollback method using commit history"""
        try:
            logger.info(f"Attempting fallback rollback for commit {commit_id}")
            
            # Get commit log to find the previous commit
            if hasattr(self._client, 'get_commit_history'):
                history = await self._client.get_commit_history(db_name, branch)
                
                # Find the commit before the one we want to rollback
                commit_index = next((i for i, c in enumerate(history) if c.get("id") == commit_id), -1)
                if commit_index > 0:
                    previous_commit = history[commit_index - 1]
                    logger.info(f"Found previous commit: {previous_commit.get('id')}")
                    
                    # Create a new commit that restores the previous state
                    await self._restore_to_commit(db_name, branch, previous_commit.get("id"))
                    
        except Exception as e:
            logger.error(f"Fallback rollback failed: {e}")
    
    async def _restore_to_commit(self, db_name: str, branch: str, target_commit_id: str):
        """Restore database state to a specific commit"""
        try:
            logger.info(f"Restoring {db_name}:{branch} to commit {target_commit_id}")
            
            # Query the target commit's snapshot
            snapshot_query = {
                "@type": "woql:Using",
                "collection": db_name,
                "query": {
                    "@type": "woql:At",
                    "commit": target_commit_id,
                    "query": {
                        "@type": "woql:Triple",
                        "subject": {"@type": "woql:Variable", "variable": "Subject"},
                        "predicate": {"@type": "woql:Variable", "variable": "Predicate"},
                        "object": {"@type": "woql:Variable", "variable": "Object"}
                    }
                }
            }
            
            # Get all triples at the target commit
            snapshot_result = await self._client.query(db_name, snapshot_query)
            
            if not snapshot_result or "bindings" not in snapshot_result:
                logger.error(f"Failed to get snapshot at commit {target_commit_id}")
                return
            
            # Clear current state and restore from snapshot
            restore_query = {
                "@type": "woql:And",
                "and": [
                    # First, delete all current documents
                    {
                        "@type": "woql:DeleteObject",
                        "document": {"@type": "woql:Variable", "variable": "Doc"}
                    }
                ]
            }
            
            # Group triples by subject to reconstruct documents
            documents = {}
            for binding in snapshot_result["bindings"]:
                subject = binding.get("Subject", {}).get("node")
                predicate = binding.get("Predicate", {}).get("node")
                obj = binding.get("Object", {})
                
                if subject and predicate:
                    if subject not in documents:
                        documents[subject] = {"@id": subject}
                    
                    # Extract object value
                    obj_value = obj.get("@value") or obj.get("node")
                    if obj_value:
                        documents[subject][predicate] = obj_value
            
            # Insert all documents from snapshot
            for doc in documents.values():
                insert_query = {
                    "@type": "InsertDocument",
                    "document": doc
                }
                restore_query["and"].append(insert_query)
            
            # Execute restore with a descriptive commit message
            commit_msg = f"Restore to commit {target_commit_id} - rollback operation"
            result = await self._client.query(db_name, restore_query, commit_msg=commit_msg)
            
            if result and result.get("status") != "error":
                logger.info(f"Successfully restored {db_name}:{branch} to commit {target_commit_id}")
                
                # Audit the successful restore
                await self._audit_rollback_operation(db_name, branch, target_commit_id)
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result"
                logger.error(f"Restore operation failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Failed to restore to commit {target_commit_id}: {e}")


# Global singleton instance
_service_instance: Optional[TerminusService] = None


async def get_service() -> TerminusService:
    """Get or create the singleton TerminusService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TerminusService()
        await _service_instance.initialize()
    return _service_instance


# Context utilities
def set_commit_context(author: str = None, commit_msg: str = None):
    """Set commit context for subsequent operations."""
    if author:
        CURRENT_AUTHOR.set(author)
    if commit_msg:
        CURRENT_COMMIT_MSG.set(commit_msg)


def get_commit_context() -> Dict[str, str]:
    """Get current commit context."""
    return {
        "author": CURRENT_AUTHOR.get(),
        "commit_msg": CURRENT_COMMIT_MSG.get()
    }


@asynccontextmanager
async def commit_context(author: str = None, commit_msg: str = None):
    """Context manager for commit operations."""
    # Save current context
    old_author = CURRENT_AUTHOR.get()
    old_msg = CURRENT_COMMIT_MSG.get()
    
    try:
        # Set new context
        if author:
            CURRENT_AUTHOR.set(author)
        if commit_msg:
            CURRENT_COMMIT_MSG.set(commit_msg)
        yield
    finally:
        # Restore original context
        CURRENT_AUTHOR.set(old_author)
        CURRENT_COMMIT_MSG.set(old_msg)