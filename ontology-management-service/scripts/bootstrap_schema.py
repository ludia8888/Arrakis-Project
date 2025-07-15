"""
TerminusDB Base Schema Bootstrap
Creates essential document types and schema definitions required for production
"""
import asyncio
import logging
import os
import sys
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootstrap.config import get_config
from database.clients.terminus_db import TerminusDBClient
from utils.retry_strategy import DB_CRITICAL_CONFIG, with_retry

logger = logging.getLogger(__name__)


class SchemaBootstrap:
 """Initialize base schema types in TerminusDB for production use"""

 def __init__(self, tdb_client: TerminusDBClient):
 self.tdb = tdb_client
 self.db_name = os.getenv("TERMINUSDB_DB", "oms")

 async def create_base_schema(self) -> bool:
 """Create all base schema types required for the system"""
 try:
 logger.info(f"Starting schema bootstrap for database: {self.db_name}")

 # Ensure database exists
 await self._ensure_database_exists()

 # Create base document types
 await self._create_schema_definition_type()
 await self._create_object_type_schema()
 await self._create_property_type_schema()
 await self._create_link_type_schema()
 await self._create_branch_metadata_schema()
 await self._create_migration_metadata_schema()
 await self._create_audit_event_schema()

 logger.info("Schema bootstrap completed successfully")
 return True

 except Exception as e:
 logger.error(f"Schema bootstrap failed: {e}")
 raise

 async def _ensure_database_exists(self):
 """Ensure the target database exists"""
 try:
 databases = await self.tdb.get_databases()
 db_names = [db.get("name") for db in databases]

 if self.db_name not in db_names:
 logger.info(f"Creating database: {self.db_name}")
 await self.tdb.create_database(
 self.db_name, label = f"{self.db_name.upper()} Database"
 )
 except Exception as e:
 logger.error(f"Failed to ensure database exists: {e}")
 raise

 async def _create_schema_definition_type(self):
 """Create the SchemaDefinition document type used by SchemaRepository"""
 logger.info("Creating SchemaDefinition document type")

 schema_def = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "SchemaDefinition"},
 {
 "type": "label",
 "class_name": "SchemaDefinition",
 "label": "Schema Definition",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "SchemaDefinition",
 "description": "Base type for storing schema definitions as documents",
 "language": "en",
 },
 # Add required properties
 {
 "type": "add_property",
 "property_name": "schemaId",
 "domain": "SchemaDefinition",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "version",
 "domain": "SchemaDefinition",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "schemaContent",
 "domain": "SchemaDefinition",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "createdAt",
 "domain": "SchemaDefinition",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "updatedAt",
 "domain": "SchemaDefinition",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "isActive",
 "domain": "SchemaDefinition",
 "range": "xsd:boolean",
 },
 ],
 }

 await self.tdb.query(
 self.db_name, schema_def, "Bootstrap: Create SchemaDefinition type"
 )

 async def _create_object_type_schema(self):
 """Create ObjectType schema for Foundry compatibility"""
 logger.info("Creating ObjectType schema")

 object_type_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "ObjectType"},
 {
 "type": "label",
 "class_name": "ObjectType",
 "label": "Object Type",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "ObjectType",
 "description": "Foundry-compatible object type definition",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "objectTypeId",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "apiName",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "displayName",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "pluralDisplayName",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "primaryKey",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "titleProperty",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "icon",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "color",
 "domain": "ObjectType",
 "range": "xsd:string",
 },
 ],
 }

 await self.tdb.query(
 self.db_name, object_type_schema, "Bootstrap: Create ObjectType schema"
 )

 async def _create_property_type_schema(self):
 """Create Property schema for object properties"""
 logger.info("Creating Property schema")

 property_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "Property"},
 {
 "type": "label",
 "class_name": "Property",
 "label": "Property",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "Property",
 "description": "Property definition for object types",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "propertyId",
 "domain": "Property",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "propertyName",
 "domain": "Property",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "displayName",
 "domain": "Property",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "dataType",
 "domain": "Property",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "cardinality",
 "domain": "Property",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "isRequired",
 "domain": "Property",
 "range": "xsd:boolean",
 },
 {
 "type": "add_property",
 "property_name": "isIndexed",
 "domain": "Property",
 "range": "xsd:boolean",
 },
 {
 "type": "add_property",
 "property_name": "isUnique",
 "domain": "Property",
 "range": "xsd:boolean",
 },
 ],
 }

 await self.tdb.query(
 self.db_name, property_schema, "Bootstrap: Create Property schema"
 )

 async def _create_link_type_schema(self):
 """Create LinkType schema for relationships"""
 logger.info("Creating LinkType schema")

 link_type_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "LinkType"},
 {
 "type": "label",
 "class_name": "LinkType",
 "label": "Link Type",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "LinkType",
 "description": "Link type definition for object relationships",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "linkTypeId",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "apiName",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "displayName",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "sourceObjectType",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "targetObjectType",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "cardinality",
 "domain": "LinkType",
 "range": "xsd:string",
 },
 ],
 }

 await self.tdb.query(
 self.db_name, link_type_schema, "Bootstrap: Create LinkType schema"
 )

 async def _create_branch_metadata_schema(self):
 """Create branch metadata schema for tracking branch information"""
 logger.info("Creating BranchMetadata schema")

 branch_metadata_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "BranchMetadata"},
 {
 "type": "label",
 "class_name": "BranchMetadata",
 "label": "Branch Metadata",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "BranchMetadata",
 "description": "Metadata for tracking branch information",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "branchName",
 "domain": "BranchMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "sourceBranch",
 "domain": "BranchMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "createdBy",
 "domain": "BranchMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "createdAt",
 "domain": "BranchMetadata",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "lastModifiedAt",
 "domain": "BranchMetadata",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "isProtected",
 "domain": "BranchMetadata",
 "range": "xsd:boolean",
 },
 ],
 }

 await self.tdb.query(
 self.db_name,
 branch_metadata_schema,
 "Bootstrap: Create BranchMetadata schema",
 )

 async def _create_migration_metadata_schema(self):
 """Create migration metadata schema"""
 logger.info("Creating MigrationMetadata schema")

 migration_metadata_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "MigrationMetadata"},
 {
 "type": "label",
 "class_name": "MigrationMetadata",
 "label": "Migration Metadata",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "MigrationMetadata",
 "description": "Metadata for tracking migration execution",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "migrationId",
 "domain": "MigrationMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "planId",
 "domain": "MigrationMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "status",
 "domain": "MigrationMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "executedBy",
 "domain": "MigrationMetadata",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "startedAt",
 "domain": "MigrationMetadata",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "completedAt",
 "domain": "MigrationMetadata",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "stepsExecuted",
 "domain": "MigrationMetadata",
 "range": "xsd:integer",
 },
 {
 "type": "add_property",
 "property_name": "errors",
 "domain": "MigrationMetadata",
 "range": "xsd:string",
 },
 ],
 }

 await self.tdb.query(
 self.db_name,
 migration_metadata_schema,
 "Bootstrap: Create MigrationMetadata schema",
 )

 async def _create_audit_event_schema(self):
 """Create audit event schema for tracking system events"""
 logger.info("Creating AuditEvent schema")

 audit_event_schema = {
 "type": "and",
 "clauses": [
 {"type": "add_class", "class_name": "AuditEvent"},
 {
 "type": "label",
 "class_name": "AuditEvent",
 "label": "Audit Event",
 "language": "en",
 },
 {
 "type": "description",
 "class_name": "AuditEvent",
 "description": "Audit event for tracking system operations",
 "language": "en",
 },
 {
 "type": "add_property",
 "property_name": "eventId",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "eventType",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "userId",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "resourceType",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "resourceId",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "action",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 {
 "type": "add_property",
 "property_name": "timestamp",
 "domain": "AuditEvent",
 "range": "xsd:dateTime",
 },
 {
 "type": "add_property",
 "property_name": "metadata",
 "domain": "AuditEvent",
 "range": "xsd:string",
 },
 ],
 }

 await self.tdb.query(
 self.db_name, audit_event_schema, "Bootstrap: Create AuditEvent schema"
 )

 async def verify_schema(self) -> bool:
 """Verify that all required schema types exist"""
 try:
 logger.info("Verifying schema bootstrap")

 required_types = [
 "SchemaDefinition",
 "ObjectType",
 "Property",
 "LinkType",
 "BranchMetadata",
 "MigrationMetadata",
 "AuditEvent",
 ]

 for doc_type in required_types:
 # Check if type exists by querying for it
 query = {
 "type": "triple",
 "subject": {"@type": "Node", "node": doc_type},
 "predicate": {"@type": "Node", "node": "rdf:type"},
 "object": {"@type": "Node", "node": "sys:Class"},
 }

 result = await self.tdb.query(self.db_name, query)
 if not result or not result.get("bindings"):
 logger.error(f"Schema type '{doc_type}' not found")
 return False

 logger.info(f"Verified schema type: {doc_type}")

 logger.info("All schema types verified successfully")
 return True

 except Exception as e:
 logger.error(f"Schema verification failed: {e}")
 return False


async def main():
 """Bootstrap the TerminusDB schema"""
 logging.basicConfig(
 level = logging.INFO,
 format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
 )

 try:
 # Get configuration
 config = get_config()
 tdb_config = config.terminusdb

 # Create TerminusDB client
 tdb_client = TerminusDBClient(tdb_config, service_name = "schema-bootstrap")

 async with tdb_client:
 # Create schema bootstrap instance
 bootstrap = SchemaBootstrap(tdb_client)

 # Create base schema
 success = await bootstrap.create_base_schema()
 if not success:
 logger.error("Schema bootstrap failed")
 sys.exit(1)

 # Verify schema
 verified = await bootstrap.verify_schema()
 if not verified:
 logger.error("Schema verification failed")
 sys.exit(1)

 logger.info("Schema bootstrap and verification completed successfully")

 except Exception as e:
 logger.error(f"Bootstrap failed: {e}")
 sys.exit(1)


if __name__ == "__main__":
 asyncio.run(main())
