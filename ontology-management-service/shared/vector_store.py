"""
Vector Storage and Similarity Search with TerminusDB Integration
Provides vector storage, retrieval, and similarity search capabilities
"""
import asyncio
import json
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
 """Represents a document with its vector embedding"""
 id: str
 text: str
 embedding: List[float]
 metadata: Dict[str, Any]
 collection: str = "default"
 created_at: Optional[str] = None
 updated_at: Optional[str] = None

 def __post_init__(self):
 if self.created_at is None:
 self.created_at = datetime.utcnow().isoformat()
 self.updated_at = datetime.utcnow().isoformat()


@dataclass
class SimilarityResult:
 """Represents a similarity search result"""
 document: VectorDocument
 similarity_score: float
 distance: float
 rank: int


class VectorStore:
 """
 Vector storage and similarity search with TerminusDB integration
 Provides persistent storage and efficient similarity search
 """

 def __init__(self, terminus_client, collection_prefix: str = "oms_vectors"):
 self.terminus_client = terminus_client
 self.collection_prefix = collection_prefix
 self._initialized = False

 async def initialize(self):
 """Initialize the vector store"""
 if self._initialized:
 return

 try:
 # Create vector storage schema in TerminusDB
 await self._create_vector_schema()
 self._initialized = True
 logger.info("Vector store initialized successfully")
 except Exception as e:
 logger.error(f"Failed to initialize vector store: {e}")
 raise

 async def store_vector(
 self,
 document: VectorDocument
 ) -> bool:
 """
 Store a vector document in TerminusDB

 Args:
 document: The vector document to store

 Returns:
 bool: True if successful, False otherwise
 """
 try:
 # Create TerminusDB document
 doc_data = {
 "@type": "VectorDocument",
 "@id": f"vector_doc_{document.id}",
 "document_id": document.id,
 "text": document.text,
 "embedding": document.embedding,
 "metadata": json.dumps(document.metadata),
 "collection": f"{self.collection_prefix}_{document.collection}",
 "created_at": document.created_at,
 "updated_at": document.updated_at,
 "embedding_dimension": len(document.embedding),
 "text_hash": hashlib.md5(document.text.encode()).hexdigest()
 }

 # Store in TerminusDB
 result = await self.terminus_client.insert_document(doc_data)

 logger.debug(f"Stored vector document {document.id} in collection {document.collection}")
 return True

 except Exception as e:
 logger.error(f"Failed to store vector document {document.id}: {e}")
 return False

 async def store_vectors(
 self,
 documents: List[VectorDocument]
 ) -> Dict[str, bool]:
 """
 Store multiple vector documents

 Args:
 documents: List of vector documents to store

 Returns:
 Dict mapping document IDs to success status
 """
 results = {}

 # Store documents concurrently
 tasks = []
 for doc in documents:
 task = self.store_vector(doc)
 tasks.append((doc.id, task))

 # Wait for all tasks to complete
 for doc_id, task in tasks:
 try:
 results[doc_id] = await task
 except Exception as e:
 logger.error(f"Failed to store document {doc_id}: {e}")
 results[doc_id] = False

 success_count = sum(1 for success in results.values() if success)
 logger.info(f"Stored {success_count}/{len(documents)} vector documents")

 return results

 async def get_vector(
 self,
 document_id: str,
 collection: str = "default"
 ) -> Optional[VectorDocument]:
 """
 Retrieve a vector document by ID

 Args:
 document_id: The document ID
 collection: The collection name

 Returns:
 VectorDocument if found, None otherwise
 """
 try:
 # Query TerminusDB for the document
 query = {
 "@type": "Triple",
 "subject": {"@type": "Variable", "name": "Doc"},
 "predicate": {"@type": "NodeValue", "node": "document_id"},
 "object": {"@type": "Value", "data": document_id}
 }

 results = await self.terminus_client.query(query)

 if not results:
 return None

 # Convert back to VectorDocument
 doc_data = results[0]
 return self._terminus_doc_to_vector_doc(doc_data)

 except Exception as e:
 logger.error(f"Failed to retrieve vector document {document_id}: {e}")
 return None

 async def delete_vector(
 self,
 document_id: str,
 collection: str = "default"
 ) -> bool:
 """
 Delete a vector document

 Args:
 document_id: The document ID
 collection: The collection name

 Returns:
 bool: True if successful, False otherwise
 """
 try:
 # Delete from TerminusDB
 doc_uri = f"vector_doc_{document_id}"
 result = await self.terminus_client.delete_document(doc_uri)

 logger.debug(f"Deleted vector document {document_id}")
 return True

 except Exception as e:
 logger.error(f"Failed to delete vector document {document_id}: {e}")
 return False

 async def similarity_search(
 self,
 query_embedding: List[float],
 collection: str = "default",
 top_k: int = 10,
 similarity_threshold: float = 0.0,
 filters: Optional[Dict[str, Any]] = None
 ) -> List[SimilarityResult]:
 """
 Perform similarity search

 Args:
 query_embedding: The query vector
 collection: Collection to search in
 top_k: Number of results to return
 similarity_threshold: Minimum similarity score
 filters: Additional metadata filters

 Returns:
 List of similarity results
 """
 try:
 # Get all vectors from the collection
 collection_name = f"{self.collection_prefix}_{collection}"

 query = {
 "@type": "Triple",
 "subject": {"@type": "Variable", "name": "Doc"},
 "predicate": {"@type": "NodeValue", "node": "collection"},
 "object": {"@type": "Value", "data": collection_name}
 }

 # Add metadata filters if provided
 if filters:
 # This would need to be expanded based on TerminusDB query capabilities
 pass

 documents = await self.terminus_client.query(query)

 if not documents:
 return []

 # Calculate similarities
 results = []
 query_vector = np.array(query_embedding)

 for doc_data in documents:
 try:
 doc = self._terminus_doc_to_vector_doc(doc_data)
 if not doc:
 continue

 # Calculate cosine similarity
 doc_vector = np.array(doc.embedding)
 similarity = self._cosine_similarity(query_vector, doc_vector)

 if similarity >= similarity_threshold:
 # Calculate Euclidean distance as well
 distance = float(np.linalg.norm(query_vector - doc_vector))

 results.append(SimilarityResult(
 document = doc,
 similarity_score = similarity,
 distance = distance,
 rank = 0 # Will be set after sorting
 ))

 except Exception as e:
 logger.warning(f"Failed to process document in similarity search: {e}")
 continue

 # Sort by similarity score (descending)
 results.sort(key = lambda x: x.similarity_score, reverse = True)

 # Set ranks and limit results
 for i, result in enumerate(results[:top_k]):
 result.rank = i + 1

 logger.debug(f"Similarity search found {len(results[:top_k])} results")
 return results[:top_k]

 except Exception as e:
 logger.error(f"Similarity search failed: {e}")
 return []

 async def semantic_search(
 self,
 query_text: str,
 embedding_function,
 collection: str = "default",
 top_k: int = 10,
 similarity_threshold: float = 0.7,
 filters: Optional[Dict[str, Any]] = None
 ) -> List[SimilarityResult]:
 """
 Perform semantic search using text query

 Args:
 query_text: The text query
 embedding_function: Function to generate embeddings
 collection: Collection to search in
 top_k: Number of results to return
 similarity_threshold: Minimum similarity score
 filters: Additional metadata filters

 Returns:
 List of similarity results
 """
 try:
 # Generate embedding for the query text
 query_embedding = await embedding_function(query_text)

 # Perform similarity search
 return await self.similarity_search(
 query_embedding = query_embedding,
 collection = collection,
 top_k = top_k,
 similarity_threshold = similarity_threshold,
 filters = filters
 )

 except Exception as e:
 logger.error(f"Semantic search failed: {e}")
 return []

 async def get_collection_stats(
 self,
 collection: str = "default"
 ) -> Dict[str, Any]:
 """
 Get statistics for a collection

 Args:
 collection: Collection name

 Returns:
 Dictionary with collection statistics
 """
 try:
 collection_name = f"{self.collection_prefix}_{collection}"

 # Count documents in collection
 count_query = {
 "@type": "Triple",
 "subject": {"@type": "Variable", "name": "Doc"},
 "predicate": {"@type": "NodeValue", "node": "collection"},
 "object": {"@type": "Value", "data": collection_name}
 }

 documents = await self.terminus_client.query(count_query)

 stats = {
 "collection": collection,
 "document_count": len(documents),
 "total_size_bytes": 0,
 "avg_embedding_dimension": 0,
 "created_at": None,
 "last_updated": None
 }

 if documents:
 # Calculate additional stats
 dimensions = []
 created_times = []
 updated_times = []

 for doc_data in documents:
 try:
 if "embedding_dimension" in doc_data:
 dimensions.append(doc_data["embedding_dimension"])
 if "created_at" in doc_data:
 created_times.append(doc_data["created_at"])
 if "updated_at" in doc_data:
 updated_times.append(doc_data["updated_at"])

 # Estimate size (rough calculation)
 doc_size = len(json.dumps(doc_data).encode('utf-8'))
 stats["total_size_bytes"] += doc_size

 except Exception as e:
 logger.warning(f"Failed to process document stats: {e}")

 if dimensions:
 stats["avg_embedding_dimension"] = sum(dimensions) / len(dimensions)
 if created_times:
 stats["created_at"] = min(created_times)
 if updated_times:
 stats["last_updated"] = max(updated_times)

 return stats

 except Exception as e:
 logger.error(f"Failed to get collection stats: {e}")
 return {"collection": collection, "error": str(e)}

 async def list_collections(self) -> List[str]:
 """
 List all available collections

 Returns:
 List of collection names
 """
 try:
 # Query for all collections
 query = {
 "@type": "Triple",
 "subject": {"@type": "Variable", "name": "Doc"},
 "predicate": {"@type": "NodeValue", "node": "collection"},
 "object": {"@type": "Variable", "name": "Collection"}
 }

 results = await self.terminus_client.query(query)

 # Extract unique collection names
 collections = set()
 for result in results:
 if "Collection" in result:
 collection_name = result["Collection"]
 if collection_name.startswith(self.collection_prefix):
 # Remove prefix to get the actual collection name
 actual_name = collection_name[len(self.collection_prefix)+1:]
 collections.add(actual_name)

 return sorted(list(collections))

 except Exception as e:
 logger.error(f"Failed to list collections: {e}")
 return []

 def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
 """Calculate cosine similarity between two vectors"""
 try:
 dot_product = np.dot(vec1, vec2)
 norm1 = np.linalg.norm(vec1)
 norm2 = np.linalg.norm(vec2)

 if norm1 == 0 or norm2 == 0:
 return 0.0

 return float(dot_product / (norm1 * norm2))

 except Exception as e:
 logger.warning(f"Failed to calculate cosine similarity: {e}")
 return 0.0

 def _terminus_doc_to_vector_doc(self, doc_data: Dict[str, Any]) -> Optional[VectorDocument]:
 """Convert TerminusDB document to VectorDocument"""
 try:
 metadata = {}
 if "metadata" in doc_data:
 try:
 metadata = json.loads(doc_data["metadata"])
 except json.JSONDecodeError:
 metadata = {}

 # Extract collection name by removing prefix
 collection = "default"
 if "collection" in doc_data:
 collection_name = doc_data["collection"]
 if collection_name.startswith(self.collection_prefix):
 collection = collection_name[len(self.collection_prefix)+1:]

 return VectorDocument(
 id = doc_data.get("document_id", ""),
 text = doc_data.get("text", ""),
 embedding = doc_data.get("embedding", []),
 metadata = metadata,
 collection = collection,
 created_at = doc_data.get("created_at"),
 updated_at = doc_data.get("updated_at")
 )

 except Exception as e:
 logger.error(f"Failed to convert TerminusDB document: {e}")
 return None

 async def _create_vector_schema(self):
 """Create the vector storage schema in TerminusDB"""
 try:
 # Define the VectorDocument schema
 schema = {
 "@type": "Class",
 "@id": "VectorDocument",
 "@key": {
 "@type": "Lexical",
 "@fields": ["document_id"]
 },
 "document_id": "xsd:string",
 "text": "xsd:string",
 "embedding": {
 "@type": "List",
 "@class": "xsd:decimal"
 },
 "metadata": "xsd:string",
 "collection": "xsd:string",
 "created_at": "xsd:dateTime",
 "updated_at": "xsd:dateTime",
 "embedding_dimension": "xsd:integer",
 "text_hash": "xsd:string"
 }

 # Insert schema into TerminusDB
 await self.terminus_client.insert_schema(schema)
 logger.info("Vector storage schema created successfully")

 except Exception as e:
 # Schema might already exist, which is fine
 logger.debug(f"Vector schema creation result: {e}")


# Utility functions for integration
async def create_vector_store(terminus_client) -> VectorStore:
 """Create and initialize a vector store"""
 store = VectorStore(terminus_client)
 await store.initialize()
 return store


async def store_text_with_embedding(
 vector_store: VectorStore,
 text: str,
 embedding_function,
 document_id: Optional[str] = None,
 collection: str = "default",
 metadata: Optional[Dict[str, Any]] = None
) -> bool:
 """
 Store text with its generated embedding

 Args:
 vector_store: The vector store instance
 text: Text to store
 embedding_function: Function to generate embeddings
 document_id: Optional document ID (auto-generated if not provided)
 collection: Collection name
 metadata: Optional metadata

 Returns:
 bool: True if successful
 """
 try:
 # Generate document ID if not provided
 if document_id is None:
 document_id = hashlib.md5(text.encode()).hexdigest()

 # Generate embedding
 embedding = await embedding_function(text)

 # Create vector document
 doc = VectorDocument(
 id = document_id,
 text = text,
 embedding = embedding,
 metadata = metadata or {},
 collection = collection
 )

 # Store in vector store
 return await vector_store.store_vector(doc)

 except Exception as e:
 logger.error(f"Failed to store text with embedding: {e}")
 return False
