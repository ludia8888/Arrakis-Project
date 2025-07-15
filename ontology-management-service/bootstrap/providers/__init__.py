"""Provider modules for dependency injection"""

from .database import PostgresClientProvider, UnifiedDatabaseProvider
from .embedding import EmbeddingServiceProvider

# SQLiteClientProvider removed - PostgreSQL-only architecture
from .event import EventProvider
from .schema import SchemaProvider
from .validation import ValidationProvider

__all__ = [
 "PostgresClientProvider",
 # "SQLiteClientProvider", # Removed - PostgreSQL-only architecture
 "UnifiedDatabaseProvider",
 "EventProvider",
 "SchemaProvider",
 "ValidationProvider",
 "EmbeddingServiceProvider",
]
