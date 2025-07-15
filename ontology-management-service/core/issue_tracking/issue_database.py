"""
Issue Tracking Database Service - PostgreSQL Production Implementation
Manages persistence of change-issue links and issue metadata
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from arrakis_common import get_logger
from bootstrap.config import get_config
from database.clients.postgres_client_secure import PostgresClientSecure
from models.issue_tracking import ChangeIssueLink, IssueProvider, IssueReference

logger = get_logger(__name__)


class IssueTrackingDatabase:
 """
 PostgreSQL database for issue tracking persistence - Production Ready
 """

 def __init__(self, postgres_client: Optional[PostgresClientSecure] = None):
 self._client = postgres_client
 self._initialized = False

 async def initialize(self):
 """Initialize database and create tables"""
 if self._initialized:
 return

 # Get PostgreSQL client if not provided
 if not self._client:
 config = get_config()
 self._client = PostgresClientSecure(config = config.postgres.model_dump())
 await self._client.connect()

 # Create issue tracking tables using PostgreSQL DDL
 await self._create_tables()
 self._initialized = True
 logger.info("Issue tracking database initialized with PostgreSQL")

 async def _ensure_initialized(self):
 """Ensure database is initialized"""
 if not self._initialized:
 await self.initialize()

 async def _create_tables(self):
 """Create issue tracking tables"""
 # Create change_issue_links table
 await self._client.execute(
 """
 CREATE TABLE IF NOT EXISTS change_issue_links (
 id SERIAL PRIMARY KEY,
 change_id VARCHAR(255) NOT NULL,
 change_type VARCHAR(50) NOT NULL,
 branch_name VARCHAR(255) NOT NULL,
 primary_issue_provider VARCHAR(50) NOT NULL,
 primary_issue_id VARCHAR(255) NOT NULL,
 emergency_override BOOLEAN DEFAULT FALSE,
 override_justification TEXT,
 override_approver VARCHAR(255),
 linked_by VARCHAR(255) NOT NULL,
 linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
 validation_result JSONB,
 created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
 updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
 )
 """
 )

 # Create change_related_issues table
 await self._client.execute(
 """
 CREATE TABLE IF NOT EXISTS change_related_issues (
 id SERIAL PRIMARY KEY,
 link_id INTEGER REFERENCES change_issue_links(id) ON DELETE CASCADE,
 issue_provider VARCHAR(50) NOT NULL,
 issue_id VARCHAR(255) NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
 )
 """
 )

 # Create issue_metadata_cache table
 await self._client.execute(
 """
 CREATE TABLE IF NOT EXISTS issue_metadata_cache (
 id SERIAL PRIMARY KEY,
 issue_provider VARCHAR(50) NOT NULL,
 issue_id VARCHAR(255) NOT NULL,
 title TEXT,
 status VARCHAR(50),
 issue_type VARCHAR(50),
 priority VARCHAR(50),
 assignee VARCHAR(255),
 issue_url TEXT,
 metadata JSONB,
 cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
 expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
 UNIQUE(issue_provider, issue_id)
 )
 """
 )

 # Create internal_issues table for production internal issue tracking
 await self._client.execute(
 """
 CREATE TABLE IF NOT EXISTS internal_issues (
 id SERIAL PRIMARY KEY,
 issue_id VARCHAR(255) UNIQUE NOT NULL,
 title TEXT NOT NULL,
 description TEXT,
 status VARCHAR(50) NOT NULL DEFAULT 'open',
 issue_type VARCHAR(50) NOT NULL DEFAULT 'task',
 priority VARCHAR(50) DEFAULT 'medium',
 assignee VARCHAR(255),
 reporter VARCHAR(255),
 project VARCHAR(100),
 labels JSONB DEFAULT '[]',
 metadata JSONB DEFAULT '{}',
 created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
 updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
 resolved_at TIMESTAMP WITH TIME ZONE
 )
 """
 )

 # Create indexes for performance
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_change_issue_links_change_id ON change_issue_links(change_id)"
 )
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_change_issue_links_branch ON change_issue_links(branch_name)"
 )
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_change_issue_links_primary_issue ON change_issue_links(primary_issue_provider,

     primary_issue_id)"
 )
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_issue_metadata_cache_expires ON issue_metadata_cache(expires_at)"
 )
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_internal_issues_status ON internal_issues(status)"
 )
 await self._client.execute(
 "CREATE INDEX IF NOT EXISTS idx_internal_issues_assignee ON internal_issues(assignee)"
 )

 async def store_change_issue_link(self, link: ChangeIssueLink) -> int:
 """Store a change-issue link"""
 await self._ensure_initialized()

 # Insert main link record and return the ID
 result = await self._client.fetch_one(
 """
 INSERT INTO change_issue_links (
 change_id, change_type, branch_name,
 primary_issue_provider, primary_issue_id,
 emergency_override, override_justification, override_approver,
 linked_by, linked_at, validation_result
 ) VALUES (
 %(change_id)s, %(change_type)s, %(branch_name)s,
 %(primary_issue_provider)s, %(primary_issue_id)s,
 %(emergency_override)s, %(override_justification)s, %(override_approver)s,
 %(linked_by)s, %(linked_at)s, %(validation_result)s
 ) RETURNING id
 """,
 {
 "change_id": link.change_id,
 "change_type": link.change_type,
 "branch_name": link.branch_name,
 "primary_issue_provider": link.primary_issue.provider.value,
 "primary_issue_id": link.primary_issue.issue_id,
 "emergency_override": link.emergency_override,
 "override_justification": link.override_justification,
 "override_approver": link.override_approver,
 "linked_by": link.linked_by,
 "linked_at": link.linked_at,
 "validation_result": json.dumps(link.validation_result)
 if link.validation_result
 else None,
 },
 )

 link_id = result["id"]

 # Insert related issues
 if link.related_issues:
 for related_issue in link.related_issues:
 await self._client.execute(
 """
 INSERT INTO change_related_issues (
 link_id, issue_provider, issue_id
 ) VALUES (%(link_id)s, %(issue_provider)s, %(issue_id)s)
 """,
 {
 "link_id": link_id,
 "issue_provider": related_issue.provider.value,
 "issue_id": related_issue.issue_id,
 },
 )

 logger.info(
 f"Stored change-issue link: {link.change_id} -> "
 f"{link.primary_issue.get_display_name()}"
 )

 return link_id

 async def get_issues_for_change(self, change_id: str) -> Optional[ChangeIssueLink]:
 """Get issues linked to a change"""
 await self._ensure_initialized()

 # Get main link
 row = await self._client.fetch_one(
 """
 SELECT * FROM change_issue_links
 WHERE change_id = %(change_id)s
 ORDER BY linked_at DESC
 LIMIT 1
 """,
 {"change_id": change_id},
 )

 if not row:
 return None

 # Get related issues
 related_rows = await self._client.fetch_all(
 """
 SELECT issue_provider, issue_id
 FROM change_related_issues
 WHERE link_id = %(link_id)s
 """,
 {"link_id": row["id"]},
 )

 # Reconstruct link
 primary_issue = IssueReference(
 provider = IssueProvider(row["primary_issue_provider"]),
 issue_id = row["primary_issue_id"],
 )

 related_issues = [
 IssueReference(
 provider = IssueProvider(rel["issue_provider"]), issue_id = rel["issue_id"]
 )
 for rel in related_rows
 ]

 return ChangeIssueLink(
 change_id = row["change_id"],
 change_type = row["change_type"],
 branch_name = row["branch_name"],
 primary_issue = primary_issue,
 related_issues = related_issues,
 emergency_override = bool(row["emergency_override"]),
 override_justification = row["override_justification"],
 override_approver = row["override_approver"],
 linked_by = row["linked_by"],
 linked_at = row["linked_at"]
 if isinstance(row["linked_at"], datetime)
 else datetime.fromisoformat(row["linked_at"]),
 validation_result = json.loads(row["validation_result"])
 if row["validation_result"]
 else None,
 )

 async def get_changes_for_issue(
 self, issue_provider: IssueProvider, issue_id: str
 ) -> List[Dict[str, Any]]:
 """Get all changes linked to an issue"""
 await self._ensure_initialized()

 # Check primary issues
 primary_changes = await self._client.fetch_all(
 """
 SELECT * FROM change_issue_links
 WHERE primary_issue_provider = %(provider)s AND primary_issue_id = %(issue_id)s
 ORDER BY linked_at DESC
 """,
 {"provider": issue_provider.value, "issue_id": issue_id},
 )

 # Check related issues
 related_changes = await self._client.fetch_all(
 """
 SELECT l.* FROM change_issue_links l
 JOIN change_related_issues r ON l.id = r.link_id
 WHERE r.issue_provider = %(provider)s AND r.issue_id = %(issue_id)s
 ORDER BY l.linked_at DESC
 """,
 {"provider": issue_provider.value, "issue_id": issue_id},
 )

 # Combine and deduplicate
 all_changes = []
 seen_ids = set()

 for row in primary_changes + related_changes:
 if row["change_id"] not in seen_ids:
 seen_ids.add(row["change_id"])
 all_changes.append(
 {
 "change_id": row["change_id"],
 "change_type": row["change_type"],
 "branch_name": row["branch_name"],
 "linked_by": row["linked_by"],
 "linked_at": row["linked_at"],
 "is_primary": row in primary_changes,
 "emergency_override": bool(row["emergency_override"]),
 }
 )

 return all_changes

 async def get_compliance_stats(
 self,
 start_date: Optional[datetime] = None,
 end_date: Optional[datetime] = None,
 branch_name: Optional[str] = None,
 change_type: Optional[str] = None,
 ) -> Dict[str, Any]:
 """Get compliance statistics"""
 await self._ensure_initialized()

 # Build query with named parameters
 query = """
 SELECT
 COUNT(*) as total_changes,
 COUNT(DISTINCT primary_issue_id) as unique_issues,
 SUM(CASE WHEN emergency_override = true THEN 1 ELSE 0 END) as emergency_overrides,
 COUNT(DISTINCT linked_by) as unique_users,
 COUNT(DISTINCT branch_name) as unique_branches
 FROM change_issue_links
 WHERE 1 = 1
 """
 params = {}

 if start_date:
 query += " AND linked_at >= %(start_date)s"
 params["start_date"] = start_date

 if end_date:
 query += " AND linked_at <= %(end_date)s"
 params["end_date"] = end_date

 if branch_name:
 query += " AND branch_name = %(branch_name)s"
 params["branch_name"] = branch_name

 if change_type:
 query += " AND change_type = %(change_type)s"
 params["change_type"] = change_type

 row = await self._client.fetch_one(query, params)

 return {
 "total_changes": row["total_changes"],
 "unique_issues": row["unique_issues"],
 "emergency_overrides": row["emergency_overrides"],
 "emergency_override_rate": (
 row["emergency_overrides"] / row["total_changes"] * 100
 if row["total_changes"] > 0
 else 0
 ),
 "unique_users": row["unique_users"],
 "unique_branches": row["unique_branches"],
 }

 async def get_user_compliance_stats(
 self, user: str, start_date: Optional[datetime] = None
 ) -> Dict[str, Any]:
 """Get compliance statistics for a specific user"""
 await self._ensure_initialized()

 query = """
 SELECT
 COUNT(*) as total_changes,
 COUNT(DISTINCT primary_issue_id) as unique_issues,
 SUM(CASE WHEN emergency_override = true THEN 1 ELSE 0 END) as emergency_overrides,
 MIN(linked_at) as first_change,
 MAX(linked_at) as last_change
 FROM change_issue_links
 WHERE linked_by = %(user)s
 """
 params = {"user": user}

 if start_date:
 query += " AND linked_at >= %(start_date)s"
 params["start_date"] = start_date

 row = await self._client.fetch_one(query, params)

 # Get breakdown by change type
 type_rows = await self._client.fetch_all(
 """
 SELECT
 change_type,
 COUNT(*) as count
 FROM change_issue_links
 WHERE linked_by = %(user)s
 GROUP BY change_type
 """,
 {"user": user},
 )

 type_breakdown = {row["change_type"]: row["count"] for row in type_rows}

 return {
 "user": user,
 "total_changes": row["total_changes"],
 "unique_issues": row["unique_issues"],
 "emergency_overrides": row["emergency_overrides"],
 "emergency_override_rate": (
 row["emergency_overrides"] / row["total_changes"] * 100
 if row["total_changes"] > 0
 else 0
 ),
 "first_change": row["first_change"],
 "last_change": row["last_change"],
 "change_type_breakdown": type_breakdown,
 }

 async def cache_issue_metadata(
 self,
 provider: IssueProvider,
 issue_id: str,
 metadata: Dict[str, Any],
 ttl_seconds: int = 300,
 ):
 """Cache issue metadata"""
 expires_at = datetime.now(timezone.utc) + timedelta(seconds = ttl_seconds)

 await self._ensure_initialized()

 # Use PostgreSQL UPSERT (INSERT ... ON CONFLICT)
 await self._client.execute(
 """
 INSERT INTO issue_metadata_cache (
 issue_provider, issue_id, title, status, issue_type,
 priority, assignee, issue_url, metadata, cached_at, expires_at
 ) VALUES (
 %(provider)s, %(issue_id)s, %(title)s, %(status)s, %(issue_type)s,
 %(priority)s, %(assignee)s, %(issue_url)s, %(metadata)s, %(cached_at)s, %(expires_at)s
 )
 ON CONFLICT (issue_provider, issue_id)
 DO UPDATE SET
 title = EXCLUDED.title,
 status = EXCLUDED.status,
 issue_type = EXCLUDED.issue_type,
 priority = EXCLUDED.priority,
 assignee = EXCLUDED.assignee,
 issue_url = EXCLUDED.issue_url,
 metadata = EXCLUDED.metadata,
 cached_at = EXCLUDED.cached_at,
 expires_at = EXCLUDED.expires_at
 """,
 {
 "provider": provider.value,
 "issue_id": issue_id,
 "title": metadata.get("title"),
 "status": metadata.get("status"),
 "issue_type": metadata.get("issue_type"),
 "priority": metadata.get("priority"),
 "assignee": metadata.get("assignee"),
 "issue_url": metadata.get("issue_url"),
 "metadata": json.dumps(metadata),
 "cached_at": datetime.now(timezone.utc),
 "expires_at": expires_at,
 },
 )

 async def get_cached_issue_metadata(
 self, provider: IssueProvider, issue_id: str
 ) -> Optional[Dict[str, Any]]:
 """Get cached issue metadata"""
 await self._ensure_initialized()

 row = await self._client.fetch_one(
 """
 SELECT * FROM issue_metadata_cache
 WHERE issue_provider = %(provider)s AND issue_id = %(issue_id)s
 AND expires_at > %(now)s
 """,
 {
 "provider": provider.value,
 "issue_id": issue_id,
 "now": datetime.now(timezone.utc),
 },
 )

 if row:
 return json.loads(row["metadata"])

 return None

 async def cleanup_expired_cache(self):
 """Clean up expired cache entries"""
 await self._ensure_initialized()

 await self._client.execute(
 """
 DELETE FROM issue_metadata_cache
 WHERE expires_at < %(now)s
 """,
 {"now": datetime.now(timezone.utc)},
 )

 # Internal Issues Management - Production Implementation

 async def create_internal_issue(
 self,
 issue_id: str,
 title: str,
 description: Optional[str] = None,
 status: str = "open",
 issue_type: str = "task",
 priority: str = "medium",
 assignee: Optional[str] = None,
 reporter: Optional[str] = None,
 project: Optional[str] = None,
 labels: Optional[List[str]] = None,
 metadata: Optional[Dict[str, Any]] = None,
 ) -> Dict[str, Any]:
 """Create a new internal issue"""
 await self._ensure_initialized()

 result = await self._client.fetch_one(
 """
 INSERT INTO internal_issues (
 issue_id, title, description, status, issue_type, priority,
 assignee, reporter, project, labels, metadata
 ) VALUES (
 %(issue_id)s, %(title)s, %(description)s, %(status)s, %(issue_type)s, %(priority)s,
 %(assignee)s, %(reporter)s, %(project)s, %(labels)s, %(metadata)s
 ) RETURNING *
 """,
 {
 "issue_id": issue_id,
 "title": title,
 "description": description,
 "status": status,
 "issue_type": issue_type,
 "priority": priority,
 "assignee": assignee,
 "reporter": reporter,
 "project": project,
 "labels": json.dumps(labels or []),
 "metadata": json.dumps(metadata or {}),
 },
 )

 return dict(result)

 async def get_internal_issue(self, issue_id: str) -> Optional[Dict[str, Any]]:
 """Get an internal issue by ID"""
 await self._ensure_initialized()

 row = await self._client.fetch_one(
 "SELECT * FROM internal_issues WHERE issue_id = %(issue_id)s",
 {"issue_id": issue_id},
 )

 if row:
 result = dict(row)
 result["labels"] = json.loads(result["labels"]) if result["labels"] else []
 result["metadata"] = (
 json.loads(result["metadata"]) if result["metadata"] else {}
 )
 return result

 return None

 async def update_internal_issue(self, issue_id: str, **updates) -> bool:
 """Update an internal issue"""
 await self._ensure_initialized()

 if not updates:
 return False

 # Handle JSON fields
 if "labels" in updates:
 updates["labels"] = json.dumps(updates["labels"])
 if "metadata" in updates:
 updates["metadata"] = json.dumps(updates["metadata"])

 # Build dynamic update query
 set_clauses = []
 params = {"issue_id": issue_id}

 for key, value in updates.items():
 if key in [
 "title",
 "description",
 "status",
 "issue_type",
 "priority",
 "assignee",
 "reporter",
 "project",
 "labels",
 "metadata",
 ]:
 set_clauses.append(f"{key} = %({key})s")
 params[key] = value

 if not set_clauses:
 return False

 # Add updated_at timestamp
 set_clauses.append("updated_at = %(updated_at)s")
 params["updated_at"] = datetime.now(timezone.utc)

 if updates.get("status") in ["resolved", "closed"]:
 set_clauses.append("resolved_at = %(resolved_at)s")
 params["resolved_at"] = datetime.now(timezone.utc)

 query = """
 UPDATE internal_issues
 SET {', '.join(set_clauses)}
 WHERE issue_id = %(issue_id)s
 """

 await self._client.execute(query, params)
 return True

 async def search_internal_issues(
 self,
 status: Optional[str] = None,
 assignee: Optional[str] = None,
 issue_type: Optional[str] = None,
 project: Optional[str] = None,
 text_search: Optional[str] = None,
 limit: int = 50,
 offset: int = 0,
 ) -> List[Dict[str, Any]]:
 """Search internal issues with filters"""
 await self._ensure_initialized()

 conditions = []
 params = {"limit": limit, "offset": offset}

 if status:
 conditions.append("status = %(status)s")
 params["status"] = status

 if assignee:
 conditions.append("assignee = %(assignee)s")
 params["assignee"] = assignee

 if issue_type:
 conditions.append("issue_type = %(issue_type)s")
 params["issue_type"] = issue_type

 if project:
 conditions.append("project = %(project)s")
 params["project"] = project

 if text_search:
 conditions.append(
 "(title ILIKE %(text_search)s OR description ILIKE %(text_search)s)"
 )
 params["text_search"] = f"%{text_search}%"

 where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

 query = """
 SELECT * FROM internal_issues
 {where_clause}
 ORDER BY created_at DESC
 LIMIT %(limit)s OFFSET %(offset)s
 """

 rows = await self._client.fetch_all(query, params)

 results = []
 for row in rows:
 result = dict(row)
 result["labels"] = json.loads(result["labels"]) if result["labels"] else []
 result["metadata"] = (
 json.loads(result["metadata"]) if result["metadata"] else {}
 )
 results.append(result)

 return results


# Global instance
_issue_db: Optional[IssueTrackingDatabase] = None


async def get_issue_database(
 postgres_client: Optional[PostgresClientSecure] = None,
) -> IssueTrackingDatabase:
 """Get global issue tracking database instance"""
 global _issue_db
 if _issue_db is None:
 _issue_db = IssueTrackingDatabase(postgres_client = postgres_client)
 await _issue_db.initialize()
 return _issue_db
