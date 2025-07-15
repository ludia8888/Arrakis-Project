"""Base classes and enums for database clients"""
from enum import Enum


class DatabaseBackend(Enum):
    """Supported database backends - PostgreSQL-only architecture"""

    TERMINUSDB = "terminusdb"
    POSTGRES = "postgres"
    # SQLITE = "sqlite" # Removed - PostgreSQL-only architecture
