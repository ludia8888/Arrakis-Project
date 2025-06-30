"""
Version Repository - Database operations for version tracking
"""
import json
import aiosqlite
import os
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from models.etag import VersionInfo, ResourceVersion
from utils.logger import get_logger

logger = get_logger(__name__)


class VersionRepositoryProtocol(ABC):
    """Protocol for version repository implementations"""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the repository"""
        pass
    
    @abstractmethod
    async def save_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version_info: VersionInfo,
        content_hash: str,
        content_size: int,
        content: Dict[str, Any]
    ):
        """Save a resource version"""
        pass
    
    @abstractmethod
    async def get_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version: Optional[int] = None
    ) -> Optional[ResourceVersion]:
        """Get a resource version"""
        pass
    
    @abstractmethod
    async def update_branch_head(
        self,
        branch: str,
        resource_type: str,
        commit_hash: str,
        version: int
    ):
        """Update branch head"""
        pass
    
    @abstractmethod
    async def get_content(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version: int
    ) -> Optional[Dict[str, Any]]:
        """Get content for a specific version"""
        pass


class SQLiteVersionRepository(VersionRepositoryProtocol):
    """SQLite implementation of version repository"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "data", "versions.db"
        )
        self._initialized = False
    
    async def initialize(self):
        """Initialize version tracking database"""
        if self._initialized:
            return
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create tables
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS resource_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    commit_hash TEXT NOT NULL,
                    parent_commit TEXT,
                    content_hash TEXT NOT NULL,
                    content_size INTEGER NOT NULL,
                    etag TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    change_summary TEXT,
                    fields_changed TEXT,  -- JSON array
                    modified_by TEXT NOT NULL,
                    modified_at TIMESTAMP NOT NULL,
                    content TEXT,  -- JSON content
                    
                    UNIQUE(resource_type, resource_id, branch, version)
                );
                
                CREATE INDEX IF NOT EXISTS idx_resource ON resource_versions (resource_type, resource_id, branch);
                CREATE INDEX IF NOT EXISTS idx_commit ON resource_versions (commit_hash);
                CREATE INDEX IF NOT EXISTS idx_modified ON resource_versions (modified_at);
                
                CREATE TABLE IF NOT EXISTS version_deltas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    from_version INTEGER NOT NULL,
                    to_version INTEGER NOT NULL,
                    delta_type TEXT NOT NULL,  -- patch or full
                    delta_content TEXT NOT NULL,  -- JSON
                    delta_size INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_delta ON version_deltas (resource_type, resource_id, branch, from_version, to_version);
                
                CREATE TABLE IF NOT EXISTS branch_heads (
                    branch TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    latest_commit TEXT NOT NULL,
                    latest_version INTEGER NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    
                    PRIMARY KEY (branch, resource_type)
                );
            """)
            await db.commit()
        
        self._initialized = True
        logger.info(f"Version repository initialized at {self.db_path}")
    
    async def save_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version_info: VersionInfo,
        content_hash: str,
        content_size: int,
        content: Dict[str, Any]
    ):
        """Save a resource version"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO resource_versions (
                    resource_type, resource_id, branch, version,
                    commit_hash, parent_commit, content_hash, content_size,
                    etag, change_type, change_summary, fields_changed,
                    modified_by, modified_at, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resource_type, resource_id, branch, version_info.version,
                version_info.commit_hash, version_info.parent_commit,
                content_hash, content_size, version_info.etag,
                version_info.change_type, version_info.change_summary,
                json.dumps(version_info.fields_changed or []),
                version_info.modified_by, version_info.last_modified.isoformat(),
                json.dumps(content)
            ))
            await db.commit()
    
    async def get_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version: Optional[int] = None
    ) -> Optional[ResourceVersion]:
        """Get a resource version"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if version is None:
                # Get latest version
                cursor = await db.execute("""
                    SELECT * FROM resource_versions
                    WHERE resource_type = ? AND resource_id = ? AND branch = ?
                    ORDER BY version DESC
                    LIMIT 1
                """, (resource_type, resource_id, branch))
            else:
                # Get specific version
                cursor = await db.execute("""
                    SELECT * FROM resource_versions
                    WHERE resource_type = ? AND resource_id = ? AND branch = ? AND version = ?
                """, (resource_type, resource_id, branch, version))
            
            row = await cursor.fetchone()
            if not row:
                return None
            
            version_info = VersionInfo(
                version=row['version'],
                commit_hash=row['commit_hash'],
                etag=row['etag'],
                last_modified=datetime.fromisoformat(row['modified_at']),
                modified_by=row['modified_by'],
                parent_version=row['version'] - 1 if row['version'] > 1 else None,
                parent_commit=row['parent_commit'],
                change_type=row['change_type'],
                change_summary=row['change_summary'],
                fields_changed=json.loads(row['fields_changed'])
            )
            
            return ResourceVersion(
                resource_type=resource_type,
                resource_id=resource_id,
                branch=branch,
                current_version=version_info,
                content_hash=row['content_hash'],
                content_size=row['content_size']
            )
    
    async def update_branch_head(
        self,
        branch: str,
        resource_type: str,
        commit_hash: str,
        version: int
    ):
        """Update branch head"""
        async with aiosqlite.connect(self.db_path) as db:
            timestamp = datetime.now(timezone.utc)
            await db.execute("""
                INSERT OR REPLACE INTO branch_heads (
                    branch, resource_type, latest_commit, latest_version, updated_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (branch, resource_type, commit_hash, version, timestamp.isoformat()))
            await db.commit()
    
    async def get_content(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version: int
    ) -> Optional[Dict[str, Any]]:
        """Get content for a specific version"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT content FROM resource_versions
                WHERE resource_type = ? AND resource_id = ? AND branch = ? AND version = ?
            """, (resource_type, resource_id, branch, version))
            
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
    
    async def get_previous_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str
    ) -> Optional[Tuple[int, str, str]]:
        """Get previous version info (version, commit_hash, content_hash)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT version, commit_hash, content_hash
                FROM resource_versions
                WHERE resource_type = ? AND resource_id = ? AND branch = ?
                ORDER BY version DESC
                LIMIT 1
            """, (resource_type, resource_id, branch))
            
            row = await cursor.fetchone()
            return row if row else None
    
    async def save_delta(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        from_version: int,
        to_version: int,
        delta_type: str,
        delta_content: Any,
        delta_size: int
    ):
        """Save delta between versions"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO version_deltas (
                    resource_type, resource_id, branch,
                    from_version, to_version, delta_type,
                    delta_content, delta_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resource_type, resource_id, branch,
                from_version, to_version, delta_type,
                json.dumps(delta_content), delta_size
            ))
            await db.commit()
    
    async def get_delta(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        from_version: int,
        to_version: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached delta"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM version_deltas
                WHERE resource_type = ? AND resource_id = ? AND branch = ?
                AND from_version = ? AND to_version = ?
            """, (resource_type, resource_id, branch, from_version, to_version))
            
            row = await cursor.fetchone()
            if row:
                return {
                    'delta_type': row['delta_type'],
                    'delta_content': json.loads(row['delta_content']),
                    'delta_size': row['delta_size']
                }
            return None
    
    async def validate_etag(
        self,
        resource_type: str,
        resource_id: str,
        branch: str
    ) -> Optional[str]:
        """Get current ETag for validation"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT etag FROM resource_versions
                WHERE resource_type = ? AND resource_id = ? AND branch = ?
                ORDER BY version DESC
                LIMIT 1
            """, (resource_type, resource_id, branch))
            
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_branch_summary(
        self,
        branch: str,
        resource_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get version summary for a branch"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Build query
            query = """
                SELECT 
                    resource_type,
                    COUNT(DISTINCT resource_id) as resource_count,
                    MAX(version) as max_version,
                    MAX(modified_at) as last_modified
                FROM resource_versions
                WHERE branch = ?
            """
            params = [branch]
            
            if resource_types:
                placeholders = ','.join('?' * len(resource_types))
                query += f" AND resource_type IN ({placeholders})"
                params.extend(resource_types)
            
            query += " GROUP BY resource_type"
            
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            summary = {
                "branch": branch,
                "resource_types": {},
                "total_resources": 0,
                "last_modified": None
            }
            
            for row in rows:
                summary["resource_types"][row['resource_type']] = {
                    "count": row['resource_count'],
                    "max_version": row['max_version'],
                    "last_modified": row['last_modified']
                }
                summary["total_resources"] += row['resource_count']
                
                if summary["last_modified"] is None or row['last_modified'] > summary["last_modified"]:
                    summary["last_modified"] = row['last_modified']
            
            return summary