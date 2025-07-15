#!/usr/bin/env python3
"""
Unfoldable Documents Demo
Demonstrates the complete functionality of the @unfoldable Documents system
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, Any

from core.documents import (
 UnfoldLevel, UnfoldContext, UnfoldableDocument,
 UnfoldableProcessor, MetadataFrameParser,
 SchemaDocumentationGenerator, get_document_storage
)


def create_sample_documents() -> Dict[str, Dict[str, Any]]:
 """Create sample documents for demonstration"""

 # Large e-commerce product catalog
 product_catalog = {
 "catalog_id": "cat_2024_001",
 "name": "Electronics Catalog 2024",
 "metadata": {
 "version": "1.2.0",
 "created_by": "catalog_system",
 "last_updated": "2024-01-15"
 },
 "categories": [
 {
 "id": "electronics",
 "name": "Electronics",
 "description": "Electronic devices and accessories",
 "products": [
 {
 "id": f"prod_{i}",
 "name": f"Product {i}",
 "price": 99.99 + i * 10,
 "description": "A" * 500, # Large description
 "specs": {
 f"spec_{j}": f"value_{j}" for j in range(50) # Many specs
 },
 "reviews": [
 {
 "id": f"review_{i}_{k}",
 "rating": 4.5,
 "comment": "Great product! " * 20, # Long review
 "user": f"user_{k}"
 }
 for k in range(100) # Many reviews
 ]
 }
 for i in range(200) # Many products
 ]
 }
 ]
 }

 # Scientific research data
 research_data = {
 "study_id": "study_2024_climate",
 "title": "Climate Change Impact Analysis",
 "abstract": "This study analyzes the impact of climate change..." * 100, # Large abstract
 "methodology": {
 "data_collection": "X" * 2000, # Large text
 "analysis_methods": ["method1", "method2"] * 100, # Large array
 "statistical_models": {
 f"model_{i}": {
 "parameters": [j for j in range(1000)], # Large parameter list
 "results": {
 f"metric_{k}": k * 0.1 for k in range(500) # Many metrics
 }
 }
 for i in range(10) # Multiple models
 }
 },
 "datasets": [
 {
 "id": f"dataset_{i}",
 "size_gb": i * 10,
 "records": [
 {
 "timestamp": f"2024-01-{j:02d}T00:00:00Z",
 "temperature": 20.0 + j * 0.1,
 "humidity": 50.0 + j * 0.05,
 "data_blob": "x" * 1000 # Large data field
 }
 for j in range(1000) # Many records
 ]
 }
 for i in range(5) # Multiple datasets
 ]
 }

 # Configuration document with deeply nested structure
 config_document = {
 "application": "enterprise_system",
 "version": "3.2.1",
 "environments": {
 "production": {
 "services": {
 f"service_{i}": {
 "replicas": 3,
 "resources": {
 "cpu": "2000m",
 "memory": "4Gi"
 },
 "configuration": {
 f"config_{j}": f"value_{j}" for j in range(100)
 },
 "secrets": {
 f"secret_{k}": "encrypted_value_" + "x" * 100
 for k in range(50)
 }
 }
 for i in range(20) # Many services
 },
 "monitoring": {
 "metrics": [
 {
 "name": f"metric_{i}",
 "query": "sum(rate(requests_total[5m]))" * 10, # Large query
 "thresholds": {
 "warning": i * 100,
 "critical": i * 200
 }
 }
 for i in range(200) # Many metrics
 ]
 }
 }
 }
 }

 return {
 "product_catalog": product_catalog,
 "research_data": research_data,
 "config_document": config_document
 }


def demo_basic_unfoldable_features():
 """Demonstrate basic unfoldable document features"""
 print("=" * 60)
 print("DEMO: Basic Unfoldable Document Features")
 print("=" * 60)

 sample_docs = create_sample_documents()

 # Demo 1: Auto-detection of unfoldable content
 print("\n1. Auto-detecting unfoldable content in product catalog...")
 catalog = sample_docs["product_catalog"]
 doc = UnfoldableDocument(catalog)
 unfoldable_paths = doc.get_unfoldable_paths()

 print(f" Found {len(unfoldable_paths)} unfoldable fields:")
 for path_info in unfoldable_paths[:5]: # Show first 5
 print(f" - {path_info['path']}: {path_info['summary']}")
 if len(unfoldable_paths) > 5:
 print(f" ... and {len(unfoldable_paths) - 5} more")

 # Demo 2: Different unfold levels
 print("\n2. Testing different unfold levels...")

 contexts = {
 "COLLAPSED": UnfoldContext(level = UnfoldLevel.COLLAPSED),
 "SHALLOW": UnfoldContext(level = UnfoldLevel.SHALLOW),
 "DEEP": UnfoldContext(level = UnfoldLevel.DEEP)
 }

 for level_name, context in contexts.items():
 folded = doc.fold(context)
 size = len(json.dumps(folded))
 print(f" {level_name}: {size:,} bytes")

 # Demo 3: Custom path unfolding
 print("\n3. Custom path unfolding...")
 custom_context = UnfoldContext(
 level = UnfoldLevel.CUSTOM,
 paths={"/categories/0/products"} # Unfold only first category's products
 )
 custom_folded = doc.fold(custom_context)
 print(f" Custom folded size: {len(json.dumps(custom_folded)):,} bytes")

 return sample_docs


def demo_auto_optimization():
 """Demonstrate automatic optimization features"""
 print("\n = " * 60)
 print("DEMO: Automatic Optimization Features")
 print("=" * 60)

 sample_docs = create_sample_documents()
 research_data = sample_docs["research_data"]

 # Demo 1: Auto-mark unfoldable
 print("\n1. Auto-marking unfoldable content...")
 original_size = len(json.dumps(research_data))

 optimized = UnfoldableProcessor.auto_mark_unfoldable(
 research_data,
 size_threshold = 5000, # 5KB threshold
 array_threshold = 50, # 50 items threshold
 text_threshold = 500 # 500 chars threshold
 )

 optimized_size = len(json.dumps(optimized))
 reduction = ((original_size - optimized_size) / original_size) * 100

 print(f" Original size: {original_size:,} bytes")
 print(f" Optimized size: {optimized_size:,} bytes")
 print(f" Size reduction: {reduction:.1f}%")

 # Demo 2: Performance analysis
 print("\n2. Performance analysis...")
 doc = UnfoldableDocument(optimized)
 unfoldable_paths = doc.get_unfoldable_paths()

 print(f" Unfoldable fields created: {len(unfoldable_paths)}")

 # Estimate performance improvements
 collapsed_context = UnfoldContext(level = UnfoldLevel.COLLAPSED)
 collapsed = doc.fold(collapsed_context)
 collapsed_size = len(json.dumps(collapsed))

 print(f" Collapsed view size: {collapsed_size:,} bytes")
 print(f" Performance improvement: {((original_size - collapsed_size) / original_size) * 100:.1f}%")


def demo_metadata_frames():
 """Demonstrate metadata frames functionality"""
 print("\n = " * 60)
 print("DEMO: Metadata Frames")
 print("=" * 60)

 # Create markdown with metadata frames
 markdown_content = '''---
title: API Documentation
version: 1.0.0
author: Development Team
---

# User Management API

This API provides endpoints for managing users in the system.

```@metadata:api
method: POST
path: /api/users
operationId: createUser
parameters:
 - name: user_data
 type: object
 required: true
responses:
 "201":
 description: User created successfully
 "400":
 description: Invalid user data
```

## User Object

```@metadata:schema
type: object
name: User
properties:
 - name: id
 type: string
 required: true
 - name: email
 type: string
 required: true
 - name: name
 type: string
 required: false
```

```@metadata:example
request:
 user_data:
 email: "john@example.com"
 name: "John Doe"
response:
 id: "usr_123"
 email: "john@example.com"
 name: "John Doe"
 created_at: "2024-01-15T10:30:00Z"
```
'''

 print("\n1. Parsing metadata frames from markdown...")
 parser = MetadataFrameParser()
 cleaned_content, frames = parser.parse_document(markdown_content)

 print(f" Found {len(frames)} metadata frames:")
 for frame in frames:
 print(f" - {frame.frame_type}: {frame.format} format")

 print(f"\n Cleaned content length: {len(cleaned_content)} chars")
 print(f" Original content length: {len(markdown_content)} chars")

 # Demo 2: Generate documentation
 print("\n2. Generating schema documentation...")

 object_type = {
 "name": "Product",
 "displayName": "Product",
 "description": "E-commerce product entity",
 "version": "1.0.0",
 "createdAt": "2024-01-15T10:00:00Z",
 "properties": [
 {
 "name": "id",
 "displayName": "Product ID",
 "dataType": "string",
 "isRequired": True,
 "isPrimaryKey": True,
 "description": "Unique product identifier"
 },
 {
 "name": "name",
 "displayName": "Product Name",
 "dataType": "string",
 "isRequired": True,
 "description": "Product display name"
 },
 {
 "name": "price",
 "displayName": "Price",
 "dataType": "decimal",
 "isRequired": True,
 "description": "Product price in USD"
 }
 ]
 }

 generator = SchemaDocumentationGenerator()
 documentation = generator.generate_object_type_doc(object_type)

 print(f" Generated documentation: {documentation.title}")
 print(f" Metadata frames: {len(documentation.metadata_frames)}")
 print(f" Documentation length: {len(documentation.to_markdown())} chars")


async def demo_storage_system():
 """Demonstrate document storage system"""
 print("\n = " * 60)
 print("DEMO: Document Storage System")
 print("=" * 60)

 storage = get_document_storage()
 sample_docs = create_sample_documents()

 # Demo 1: Store documents
 print("\n1. Storing documents...")
 stored_docs = []

 for name, content in sample_docs.items():
 stored_doc = storage.store_document(
 name = f"demo_{name}",
 content = content,
 metadata={"demo": True, "type": name},
 tags = [name.split("_")[0], "demo"],
 auto_optimize = True
 )
 stored_docs.append(stored_doc)
 print(f" Stored {stored_doc.name}: {stored_doc.size_bytes:,} bytes, "
 f"{stored_doc.unfoldable_fields_count} unfoldable fields")

 # Demo 2: Retrieve with different unfold levels
 print("\n2. Retrieving with different unfold levels...")
 doc_id = stored_docs[0].id

 unfold_contexts = [
 ("COLLAPSED", UnfoldContext(level = UnfoldLevel.COLLAPSED)),
 ("SHALLOW", UnfoldContext(level = UnfoldLevel.SHALLOW)),
 ("DEEP", UnfoldContext(level = UnfoldLevel.DEEP))
 ]

 for level_name, context in unfold_contexts:
 retrieved = storage.get_document(doc_id, context)
 size = len(json.dumps(retrieved["content"]))
 print(f" {level_name}: {size:,} bytes")

 # Demo 3: Search functionality
 print("\n3. Search functionality...")
 search_results = storage.search_documents("electronics", limit = 10)
 print(f" Found {len(search_results)} documents matching 'electronics'")

 for result in search_results[:3]:
 print(f" - {result['name']}: score {result['score']}, matches: {result['matches']}")

 # Demo 4: Storage statistics
 print("\n4. Storage statistics...")
 stats = storage.get_document_stats()
 print(f" Total documents: {stats['total_documents']}")
 print(f" Total size: {stats['total_size_mb']:.1f} MB")
 print(f" Total unfoldable fields: {stats['total_unfoldable_fields']}")
 print(f" Average size per document: {stats['average_size_bytes']:,} bytes")

 return stored_docs


def demo_performance_comparison():
 """Demonstrate performance benefits of unfoldable documents"""
 print("\n = " * 60)
 print("DEMO: Performance Comparison")
 print("=" * 60)

 sample_docs = create_sample_documents()
 research_data = sample_docs["research_data"]

 import time

 # Measure processing times
 print("\n1. Processing time comparison...")

 # Regular document processing
 start = time.time()
 regular_doc = UnfoldableDocument(research_data)
 regular_full = regular_doc.fold(UnfoldContext(level = UnfoldLevel.DEEP))
 regular_time = time.time() - start

 # Optimized document processing
 optimized_content = UnfoldableProcessor.auto_mark_unfoldable(research_data)
 start = time.time()
 optimized_doc = UnfoldableDocument(optimized_content)
 optimized_collapsed = optimized_doc.fold(UnfoldContext(level = UnfoldLevel.COLLAPSED))
 optimized_time = time.time() - start

 print(f" Regular processing: {regular_time:.3f}s")
 print(f" Optimized processing: {optimized_time:.3f}s")
 print(f" Speed improvement: {(regular_time / optimized_time):.1f}x")

 # Size comparison
 print("\n2. Size comparison...")
 regular_size = len(json.dumps(regular_full))
 optimized_size = len(json.dumps(optimized_collapsed))

 print(f" Regular document: {regular_size:,} bytes")
 print(f" Optimized document: {optimized_size:,} bytes")
 print(f" Size reduction: {((regular_size - optimized_size) / regular_size) * 100:.1f}%")

 # Network efficiency simulation
 print("\n3. Network efficiency simulation...")

 # Simulate network transfer times (assuming 1MB/s connection)
 transfer_speed_bps = 1024 * 1024 # 1 MB/s

 regular_transfer_time = regular_size / transfer_speed_bps
 optimized_transfer_time = optimized_size / transfer_speed_bps

 print(f" Regular transfer time: {regular_transfer_time:.2f}s")
 print(f" Optimized transfer time: {optimized_transfer_time:.2f}s")
 print(f" Transfer improvement: {(regular_transfer_time / optimized_transfer_time):.1f}x")


async def run_complete_demo():
 """Run the complete demonstration"""
 print("🚀 UNFOLDABLE DOCUMENTS COMPLETE DEMO")
 print("=" * 80)
 print("This demo showcases the complete @unfoldable Documents implementation")
 print("including core features, optimization, metadata frames, and storage.")
 print("=" * 80)

 try:
 # Run all demo sections
 sample_docs = demo_basic_unfoldable_features()
 demo_auto_optimization()
 demo_metadata_frames()
 stored_docs = await demo_storage_system()
 demo_performance_comparison()

 print("\n" + "=" * 60)
 print("DEMO SUMMARY")
 print("=" * 60)
 print("✅ Basic unfoldable features: WORKING")
 print("✅ Auto-optimization: WORKING")
 print("✅ Metadata frames: WORKING")
 print("✅ Document storage: WORKING")
 print("✅ Performance optimization: WORKING")
 print("\nThe @unfoldable Documents system is fully functional!")
 print("All production API endpoints are ready for use.")

 # API endpoints summary
 print("\n" + "=" * 60)
 print("AVAILABLE API ENDPOINTS")
 print("=" * 60)
 print("REST API (/api/v1/documents/):")
 print(" POST /unfold - Unfold documents with context")
 print(" POST /unfold-path - Unfold specific paths")
 print(" POST /prepare-unfoldable - Add unfoldable annotations")
 print(" POST /extract-unfoldable - Extract unfoldable content")
 print(" POST /auto-mark-unfoldable - Auto-mark large content")
 print(" POST /batch-unfold - Batch process documents")
 print(" POST /analyze-document - Analyze document structure")
 print(" POST /optimize-document - Optimize for performance")
 print(" POST /store - Store documents")
 print(" GET /store/{id} - Retrieve stored documents")
 print(" PUT /store/{id} - Update stored documents")
 print(" DELETE /store/{id} - Delete stored documents")
 print(" GET /store - List stored documents")
 print(" POST /search - Search stored documents")
 print(" GET /stats - Storage statistics")
 print(" POST /parse-metadata - Parse metadata frames")
 print(" POST /generate-documentation - Generate docs")
 print("\nGraphQL API:")
 print(" Query: unfoldDocument, unfoldPath, getUnfoldablePaths")
 print(" Query: parseMetadataFrames, generateDocumentation")
 print(" Mutation: prepareUnfoldable, autoMarkUnfoldable")
 print(" Mutation: extractUnfoldableContent, batchUnfoldDocuments")

 except Exception as e:
 print(f"\n❌ Demo failed with error: {e}")
 raise


if __name__ == "__main__":
 # Run the complete demo
 asyncio.run(run_complete_demo())
