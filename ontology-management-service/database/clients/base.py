"""Base classes and enums for database clients"""
from enum import Enum


class DatabaseBackend(Enum):
    """Supported database backends"""
    TERMINUSDB = "terminusdb"
    POSTGRES = "postgres"
    SQLITE = "sqlite"