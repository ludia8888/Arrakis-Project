#!/usr/bin/env python3
"""
Enterprise-Level Integration Test Suite for Arrakis Project
============================================================
Comprehensive test suite verifying all core features and production readiness.

Test Categories:
1. Version Control (Git-like features)
2. Ontology Management
3. Advanced Features (AI, Caching, Tracing)
4. Production Readiness Validation
"""

import asyncio
import json
import time
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import redis
import psycopg2
from pathlib import Path
import sys
import uuid
import hashlib
from dataclasses import dataclass
from enum import Enum

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Service URLs
USER_SERVICE_URL = "http://localhost:8010"
AUDIT_SERVICE_URL = "http://localhost:8011"
OMS_SERVICE_URL = "http://localhost:8000"
JAEGER_URL = "http://localhost:16686"
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
ALERTMANAGER_URL = "http://localhost:9093"

class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    SKIP = "SKIP"

@dataclass
class TestResult:
    name: str
    category: str
    status: TestStatus
    duration: float
    details: Dict[str, Any]
    error: Optional[str] = None


class EnterpriseTestSuite:
    def __init__(self):
        self.results = []
        self.token = None
        self.test_user = {
            "username": f"test_user_{uuid.uuid4().hex[:8]}",
            "password": "TestPass123!",
            "email": "test@arrakis.io"
        }
        self.redis_client = None
        self.start_time = datetime.now()
        
    def print_header(self, text: str):
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}{text.center(80)}{RESET}")
        print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")
        
    def print_category(self, text: str):
        print(f"\n{BOLD}{YELLOW}{'='*60}{RESET}")
        print(f"{BOLD}{YELLOW}{text}{RESET}")
        print(f"{BOLD}{YELLOW}{'='*60}{RESET}\n")
        
    def print_test(self, name: str, status: TestStatus, duration: float, details: str = ""):
        color = GREEN if status == TestStatus.PASS else RED if status == TestStatus.FAIL else YELLOW
        status_str = f"[{status.value}]".ljust(10)
        duration_str = f"({duration:.2f}s)"
        
        print(f"{color}{status_str}{RESET} {name} {duration_str}")
        if details:
            print(f"  └─ {details}")
            
    async def setup(self):
        """Setup test environment"""
        print(f"{BOLD}Setting up test environment...{RESET}")
        
        # Check if services are running
        services = {
            "User Service": f"{USER_SERVICE_URL}/health",
            "Audit Service": f"{AUDIT_SERVICE_URL}/health",
            "OMS Service": f"{OMS_SERVICE_URL}/health",
            "Redis": "redis://localhost:6379",
            "PostgreSQL": "postgresql://arrakis_user:arrakis_password@localhost:5432/arrakis_db"
        }
        
        for service, url in services.items():
            try:
                if service == "Redis":
                    self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
                    self.redis_client.ping()
                elif service == "PostgreSQL":
                    conn = psycopg2.connect(url)
                    conn.close()
                elif url.startswith("http"):
                    response = requests.get(url, timeout=5)
                    if response.status_code != 200:
                        raise Exception(f"Service unhealthy: {response.status_code}")
                print(f"  ✓ {service} is running")
            except Exception as e:
                print(f"  ✗ {service} is not accessible: {str(e)}")
                return False
                
        # Create test user and login
        try:
            # Register user
            response = requests.post(
                f"{USER_SERVICE_URL}/api/v1/auth/register",
                json=self.test_user
            )
            if response.status_code not in [200, 201, 400]:  # 400 if user exists
                raise Exception(f"User registration failed: {response.text}")
                
            # Login
            response = requests.post(
                f"{USER_SERVICE_URL}/api/v1/auth/login",
                json={
                    "username": self.test_user["username"],
                    "password": self.test_user["password"]
                }
            )
            if response.status_code != 200:
                raise Exception(f"Login failed: {response.text}")
                
            self.token = response.json()["access_token"]
            print(f"  ✓ Test user created and authenticated")
            
        except Exception as e:
            print(f"  ✗ Authentication setup failed: {str(e)}")
            return False
            
        return True
        
    def get_headers(self):
        """Get authenticated headers"""
        return {"Authorization": f"Bearer {self.token}"}
        
    # ===== VERSION CONTROL TESTS =====
    
    async def test_branch_management(self) -> TestResult:
        """Test Git-like branch management"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            base_branch = "main"
            feature_branch = f"feature/test-{uuid.uuid4().hex[:8]}"
            
            # Create branch
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/branches",
                json={
                    "name": feature_branch,
                    "source_branch": base_branch,
                    "description": "Test feature branch"
                },
                headers=headers
            )
            if response.status_code != 201:
                raise Exception(f"Branch creation failed: {response.text}")
            details["branch_created"] = True
            
            # Create schema on feature branch
            schema_data = {
                "name": "TestEntity",
                "properties": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "name", "type": "string", "required": True},
                    {"name": "value", "type": "integer", "required": False}
                ]
            }
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas?branch={feature_branch}",
                json=schema_data,
                headers=headers
            )
            if response.status_code != 201:
                raise Exception(f"Schema creation failed: {response.text}")
            details["schema_created"] = True
            
            # List branches
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/branches",
                headers=headers
            )
            branches = response.json()
            details["branch_count"] = len(branches)
            
            # Get branch diff
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/branches/{feature_branch}/diff?target={base_branch}",
                headers=headers
            )
            if response.status_code == 200:
                diff = response.json()
                details["diff_changes"] = len(diff.get("changes", []))
            
            return TestResult(
                name="Branch Management",
                category="Version Control",
                status=TestStatus.PASS,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Branch Management",
                category="Version Control",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_merge_operations(self) -> TestResult:
        """Test merge operations with conflict resolution"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            base_branch = "main"
            branch1 = f"feature/merge-test-1-{uuid.uuid4().hex[:8]}"
            branch2 = f"feature/merge-test-2-{uuid.uuid4().hex[:8]}"
            
            # Create two branches
            for branch in [branch1, branch2]:
                response = requests.post(
                    f"{OMS_SERVICE_URL}/api/v1/branches",
                    json={"name": branch, "source_branch": base_branch},
                    headers=headers
                )
                if response.status_code != 201:
                    raise Exception(f"Branch creation failed: {response.text}")
                    
            # Create conflicting changes
            schema_name = f"ConflictTest-{uuid.uuid4().hex[:8]}"
            
            # Change 1 on branch1
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas?branch={branch1}",
                json={
                    "name": schema_name,
                    "properties": [
                        {"name": "field1", "type": "string", "required": True}
                    ]
                },
                headers=headers
            )
            details["branch1_change"] = response.status_code == 201
            
            # Change 2 on branch2 (conflicting)
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas?branch={branch2}",
                json={
                    "name": schema_name,
                    "properties": [
                        {"name": "field1", "type": "integer", "required": True}
                    ]
                },
                headers=headers
            )
            details["branch2_change"] = response.status_code == 201
            
            # Attempt merge (should detect conflict)
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/branches/{branch1}/merge",
                json={
                    "source_branch": branch2,
                    "strategy": "three-way",
                    "resolve_conflicts": False
                },
                headers=headers
            )
            
            if response.status_code == 409:  # Conflict detected
                details["conflict_detected"] = True
                conflict_data = response.json()
                details["conflict_count"] = len(conflict_data.get("conflicts", []))
                
                # Resolve conflicts
                response = requests.post(
                    f"{OMS_SERVICE_URL}/api/v1/branches/{branch1}/merge",
                    json={
                        "source_branch": branch2,
                        "strategy": "three-way",
                        "resolve_conflicts": True,
                        "conflict_resolution": "ours"  # Keep branch1 changes
                    },
                    headers=headers
                )
                details["merge_resolved"] = response.status_code == 200
            else:
                details["conflict_detected"] = False
                details["merge_status"] = response.status_code
                
            return TestResult(
                name="Merge Operations",
                category="Version Control",
                status=TestStatus.PASS if details.get("conflict_detected") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Merge Operations",
                category="Version Control",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_rollback_functionality(self) -> TestResult:
        """Test rollback/revert functionality"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            branch = f"rollback-test-{uuid.uuid4().hex[:8]}"
            
            # Create branch
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/branches",
                json={"name": branch, "source_branch": "main"},
                headers=headers
            )
            if response.status_code != 201:
                raise Exception(f"Branch creation failed: {response.text}")
                
            # Create initial schema
            schema_name = f"RollbackTest-{uuid.uuid4().hex[:8]}"
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas?branch={branch}",
                json={
                    "name": schema_name,
                    "properties": [
                        {"name": "version", "type": "integer", "default": 1}
                    ]
                },
                headers=headers
            )
            if response.status_code != 201:
                raise Exception(f"Initial schema creation failed: {response.text}")
            initial_commit = response.json().get("commit_id")
            details["initial_commit"] = initial_commit
            
            # Make changes
            for i in range(2, 5):
                response = requests.put(
                    f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}?branch={branch}",
                    json={
                        "properties": [
                            {"name": "version", "type": "integer", "default": i}
                        ]
                    },
                    headers=headers
                )
                if response.status_code != 200:
                    raise Exception(f"Schema update {i} failed")
                    
            # Get history
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}/history?branch={branch}",
                headers=headers
            )
            if response.status_code == 200:
                history = response.json()
                details["history_length"] = len(history)
                
            # Rollback to initial version
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}/rollback?branch={branch}",
                json={
                    "target_commit": initial_commit,
                    "strategy": "soft"  # Create new commit
                },
                headers=headers
            )
            details["rollback_status"] = response.status_code
            details["rollback_success"] = response.status_code == 200
            
            # Verify rollback
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}?branch={branch}",
                headers=headers
            )
            if response.status_code == 200:
                current_schema = response.json()
                details["rollback_verified"] = (
                    current_schema.get("properties", [{}])[0].get("default") == 1
                )
                
            return TestResult(
                name="Rollback Functionality",
                category="Version Control",
                status=TestStatus.PASS if details.get("rollback_verified") else TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Rollback Functionality",
                category="Version Control",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    # ===== ONTOLOGY MANAGEMENT TESTS =====
    
    async def test_object_type_management(self) -> TestResult:
        """Test ObjectType creation and management"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Create ObjectType
            object_type = {
                "name": f"TestObject-{uuid.uuid4().hex[:8]}",
                "description": "Test object type",
                "properties": [
                    {
                        "name": "id",
                        "type": "string",
                        "required": True,
                        "description": "Unique identifier"
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "required": True,
                        "validation": {"pattern": "^[A-Za-z0-9_]+$"}
                    },
                    {
                        "name": "created_at",
                        "type": "datetime",
                        "required": True,
                        "default": "now()"
                    }
                ],
                "indexes": [
                    {"fields": ["name"], "unique": True}
                ]
            }
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/object-types",
                json=object_type,
                headers=headers
            )
            details["creation_status"] = response.status_code
            if response.status_code not in [200, 201]:
                raise Exception(f"ObjectType creation failed: {response.text}")
            
            object_type_id = response.json().get("id")
            details["object_type_id"] = object_type_id
            
            # Add property
            new_property = {
                "name": "status",
                "type": "enum",
                "enum_values": ["active", "inactive", "pending"],
                "default": "pending"
            }
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/object-types/{object_type_id}/properties",
                json=new_property,
                headers=headers
            )
            details["add_property"] = response.status_code in [200, 201]
            
            # Create instance
            instance = {
                "type": object_type_id,
                "data": {
                    "id": uuid.uuid4().hex,
                    "name": "TestInstance",
                    "status": "active"
                }
            }
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/objects",
                json=instance,
                headers=headers
            )
            details["instance_created"] = response.status_code in [200, 201]
            
            # Query instances
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/objects?type={object_type_id}",
                headers=headers
            )
            if response.status_code == 200:
                instances = response.json()
                details["instance_count"] = len(instances)
                
            return TestResult(
                name="ObjectType Management",
                category="Ontology Management",
                status=TestStatus.PASS if details.get("instance_created") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="ObjectType Management",
                category="Ontology Management",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_link_type_relationships(self) -> TestResult:
        """Test LinkType relationship management"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Create two object types
            person_type = {
                "name": f"Person-{uuid.uuid4().hex[:8]}",
                "properties": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "name", "type": "string", "required": True}
                ]
            }
            
            project_type = {
                "name": f"Project-{uuid.uuid4().hex[:8]}",
                "properties": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "title", "type": "string", "required": True}
                ]
            }
            
            # Create object types
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/object-types",
                json=person_type,
                headers=headers
            )
            person_type_id = response.json().get("id")
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/object-types",
                json=project_type,
                headers=headers
            )
            project_type_id = response.json().get("id")
            
            # Create LinkType
            link_type = {
                "name": "works_on",
                "source_type": person_type_id,
                "target_type": project_type_id,
                "cardinality": "many-to-many",
                "properties": [
                    {"name": "role", "type": "string", "required": True},
                    {"name": "start_date", "type": "date", "required": True}
                ]
            }
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/link-types",
                json=link_type,
                headers=headers
            )
            details["link_type_created"] = response.status_code in [200, 201]
            link_type_id = response.json().get("id") if response.status_code in [200, 201] else None
            
            # Create instances and link
            person = {
                "type": person_type_id,
                "data": {"id": "p1", "name": "John Doe"}
            }
            project = {
                "type": project_type_id,
                "data": {"id": "proj1", "title": "AI Research"}
            }
            
            response = requests.post(f"{OMS_SERVICE_URL}/api/v1/objects", json=person, headers=headers)
            person_id = response.json().get("id") if response.status_code in [200, 201] else None
            
            response = requests.post(f"{OMS_SERVICE_URL}/api/v1/objects", json=project, headers=headers)
            project_id = response.json().get("id") if response.status_code in [200, 201] else None
            
            # Create link
            if person_id and project_id and link_type_id:
                link = {
                    "type": link_type_id,
                    "source": person_id,
                    "target": project_id,
                    "properties": {
                        "role": "Lead Researcher",
                        "start_date": "2024-01-01"
                    }
                }
                
                response = requests.post(
                    f"{OMS_SERVICE_URL}/api/v1/links",
                    json=link,
                    headers=headers
                )
                details["link_created"] = response.status_code in [200, 201]
                
            # Query relationships
            if person_id:
                response = requests.get(
                    f"{OMS_SERVICE_URL}/api/v1/objects/{person_id}/links",
                    headers=headers
                )
                if response.status_code == 200:
                    links = response.json()
                    details["link_count"] = len(links)
                    
            return TestResult(
                name="LinkType Relationships",
                category="Ontology Management",
                status=TestStatus.PASS if details.get("link_created") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="LinkType Relationships",
                category="Ontology Management",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    # ===== ADVANCED FEATURES TESTS =====
    
    async def test_vector_embeddings(self) -> TestResult:
        """Test Vector Embeddings functionality"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Check if embedding service is available
            response = requests.get("http://localhost:8001/health", timeout=5)
            if response.status_code != 200:
                return TestResult(
                    name="Vector Embeddings",
                    category="Advanced Features",
                    status=TestStatus.SKIP,
                    duration=time.time() - start_time,
                    details={"reason": "Embedding service not available"},
                    error="Service not running"
                )
                
            # Test embedding generation
            test_texts = [
                "Machine learning is a subset of artificial intelligence",
                "Deep learning uses neural networks with multiple layers",
                "Natural language processing enables computers to understand human language"
            ]
            
            for i, text in enumerate(test_texts):
                response = requests.post(
                    "http://localhost:8001/api/v1/embeddings",
                    json={"text": text, "model": "default"},
                    headers=headers
                )
                if response.status_code == 200:
                    embedding = response.json()
                    details[f"embedding_{i}_size"] = len(embedding.get("embedding", []))
                else:
                    details[f"embedding_{i}_error"] = response.status_code
                    
            # Test similarity search
            if details.get("embedding_0_size"):
                response = requests.post(
                    f"{OMS_SERVICE_URL}/api/v1/search/similar",
                    json={
                        "query": "AI and machine learning",
                        "limit": 5,
                        "threshold": 0.7
                    },
                    headers=headers
                )
                details["similarity_search"] = response.status_code == 200
                
            return TestResult(
                name="Vector Embeddings",
                category="Advanced Features",
                status=TestStatus.PASS if details.get("embedding_0_size") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Vector Embeddings",
                category="Advanced Features",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_redis_smart_cache(self) -> TestResult:
        """Test Redis SmartCache functionality"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Test cache warmup
            test_key = f"test:cache:{uuid.uuid4().hex[:8]}"
            test_data = {"value": "test_data", "timestamp": datetime.now().isoformat()}
            
            # Make request that should be cached
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                headers=headers
            )
            initial_response_time = response.elapsed.total_seconds()
            details["initial_response_time"] = initial_response_time
            
            # Make same request again (should be cached)
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                headers=headers
            )
            cached_response_time = response.elapsed.total_seconds()
            details["cached_response_time"] = cached_response_time
            details["cache_hit"] = response.headers.get("X-Cache-Status") == "HIT"
            details["cache_improvement"] = initial_response_time > cached_response_time * 2
            
            # Test cache invalidation
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                json={
                    "name": f"CacheTest-{uuid.uuid4().hex[:8]}",
                    "properties": []
                },
                headers=headers
            )
            
            # Check if cache was invalidated
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                headers=headers
            )
            details["cache_invalidated"] = response.headers.get("X-Cache-Status") != "HIT"
            
            # Test Redis connection
            if self.redis_client:
                self.redis_client.setex(test_key, 60, json.dumps(test_data))
                retrieved = self.redis_client.get(test_key)
                details["redis_direct_access"] = retrieved is not None
                
            return TestResult(
                name="Redis SmartCache",
                category="Advanced Features",
                status=TestStatus.PASS if details.get("cache_hit") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Redis SmartCache",
                category="Advanced Features",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_jaeger_tracing(self) -> TestResult:
        """Test Jaeger distributed tracing"""
        start_time = time.time()
        details = {}
        
        try:
            # Check Jaeger UI
            response = requests.get(f"{JAEGER_URL}/api/services", timeout=5)
            if response.status_code != 200:
                return TestResult(
                    name="Jaeger Tracing",
                    category="Advanced Features",
                    status=TestStatus.SKIP,
                    duration=time.time() - start_time,
                    details={"reason": "Jaeger not available"},
                    error="Service not running"
                )
                
            services = response.json().get("data", [])
            details["services_count"] = len(services)
            details["services"] = services
            
            # Make traced request
            headers = self.get_headers()
            headers["X-Trace-ID"] = f"test-trace-{uuid.uuid4().hex}"
            
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                json={
                    "name": f"TracingTest-{uuid.uuid4().hex[:8]}",
                    "properties": []
                },
                headers=headers
            )
            
            # Wait for trace to be processed
            await asyncio.sleep(2)
            
            # Query traces
            response = requests.get(
                f"{JAEGER_URL}/api/traces?service=oms-service&limit=10",
                timeout=5
            )
            if response.status_code == 200:
                traces = response.json().get("data", [])
                details["traces_found"] = len(traces) > 0
                details["trace_count"] = len(traces)
                
            return TestResult(
                name="Jaeger Tracing",
                category="Advanced Features",
                status=TestStatus.PASS if details.get("traces_found") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Jaeger Tracing",
                category="Advanced Features",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_time_travel_queries(self) -> TestResult:
        """Test Time Travel Queries functionality"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Create schema with multiple versions
            schema_name = f"TimeTravelTest-{uuid.uuid4().hex[:8]}"
            timestamps = []
            
            # Version 1
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                json={
                    "name": schema_name,
                    "properties": [
                        {"name": "version", "type": "integer", "default": 1}
                    ]
                },
                headers=headers
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Schema creation failed: {response.text}")
            timestamps.append(datetime.now())
            await asyncio.sleep(1)
            
            # Version 2
            response = requests.put(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}",
                json={
                    "properties": [
                        {"name": "version", "type": "integer", "default": 2},
                        {"name": "added_field", "type": "string"}
                    ]
                },
                headers=headers
            )
            timestamps.append(datetime.now())
            await asyncio.sleep(1)
            
            # Version 3
            response = requests.put(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{schema_name}",
                json={
                    "properties": [
                        {"name": "version", "type": "integer", "default": 3},
                        {"name": "added_field", "type": "string"},
                        {"name": "another_field", "type": "boolean"}
                    ]
                },
                headers=headers
            )
            timestamps.append(datetime.now())
            
            # Query at different points in time
            for i, timestamp in enumerate(timestamps):
                response = requests.get(
                    f"{OMS_SERVICE_URL}/api/v1/time-travel/schemas/{schema_name}",
                    params={"timestamp": timestamp.isoformat()},
                    headers=headers
                )
                if response.status_code == 200:
                    schema = response.json()
                    version = schema.get("properties", [{}])[0].get("default")
                    details[f"version_at_t{i}"] = version
                    details[f"correct_version_t{i}"] = version == i + 1
                else:
                    details[f"query_t{i}_status"] = response.status_code
                    
            # Test timeline
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/time-travel/schemas/{schema_name}/timeline",
                headers=headers
            )
            if response.status_code == 200:
                timeline = response.json()
                details["timeline_entries"] = len(timeline)
                
            return TestResult(
                name="Time Travel Queries",
                category="Advanced Features",
                status=TestStatus.PASS if all(details.get(f"correct_version_t{i}", False) for i in range(3)) else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Time Travel Queries",
                category="Advanced Features",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    # ===== PRODUCTION READINESS TESTS =====
    
    async def test_monitoring_stack(self) -> TestResult:
        """Test monitoring infrastructure"""
        start_time = time.time()
        details = {}
        
        try:
            # Check Prometheus
            response = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=5)
            if response.status_code == 200:
                targets = response.json().get("data", {}).get("activeTargets", [])
                details["prometheus_targets"] = len(targets)
                details["prometheus_healthy"] = all(t.get("health") == "up" for t in targets)
            else:
                details["prometheus_status"] = response.status_code
                
            # Check Grafana
            response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
            details["grafana_healthy"] = response.status_code == 200
            
            # Check Alertmanager
            response = requests.get(f"{ALERTMANAGER_URL}/api/v1/status", timeout=5)
            details["alertmanager_healthy"] = response.status_code == 200
            
            # Check metrics endpoint
            response = requests.get(f"{OMS_SERVICE_URL}/metrics", timeout=5)
            if response.status_code == 200:
                metrics_text = response.text
                details["metrics_available"] = True
                details["metric_lines"] = len(metrics_text.split('\n'))
                
                # Check for key metrics
                key_metrics = [
                    "http_requests_total",
                    "http_request_duration_seconds",
                    "db_query_duration_seconds",
                    "cache_hit_rate"
                ]
                for metric in key_metrics:
                    details[f"has_{metric}"] = metric in metrics_text
                    
            return TestResult(
                name="Monitoring Stack",
                category="Production Readiness",
                status=TestStatus.PASS if details.get("prometheus_healthy") and details.get("grafana_healthy") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Monitoring Stack",
                category="Production Readiness",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_resilience_patterns(self) -> TestResult:
        """Test resilience patterns (circuit breaker, retry, etc.)"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Test circuit breaker by making failing requests
            failing_endpoint = f"{OMS_SERVICE_URL}/api/v1/test/fail"
            circuit_open = False
            
            for i in range(10):
                response = requests.get(failing_endpoint, headers=headers, timeout=2)
                if response.status_code == 503 and "circuit breaker open" in response.text.lower():
                    circuit_open = True
                    details["circuit_opened_at_request"] = i + 1
                    break
                    
            details["circuit_breaker_triggered"] = circuit_open
            
            # Test retry with backoff
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/test/flaky",
                headers={**headers, "X-Test-Retry": "true"},
                timeout=10
            )
            retry_count = response.headers.get("X-Retry-Count", "0")
            details["retry_count"] = int(retry_count)
            details["retry_successful"] = response.status_code == 200
            
            # Test bulkhead isolation
            import concurrent.futures
            
            def make_request():
                return requests.get(
                    f"{OMS_SERVICE_URL}/api/v1/schemas",
                    headers=headers,
                    timeout=5
                )
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(make_request) for _ in range(20)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
            success_count = sum(1 for r in results if r.status_code == 200)
            rejected_count = sum(1 for r in results if r.status_code == 503)
            
            details["bulkhead_success_count"] = success_count
            details["bulkhead_rejected_count"] = rejected_count
            details["bulkhead_working"] = rejected_count > 0  # Some requests should be rejected
            
            return TestResult(
                name="Resilience Patterns",
                category="Production Readiness",
                status=TestStatus.PASS if details.get("circuit_breaker_triggered") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Resilience Patterns",
                category="Production Readiness",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_security_features(self) -> TestResult:
        """Test security features"""
        start_time = time.time()
        details = {}
        
        try:
            # Test authentication required
            response = requests.get(f"{OMS_SERVICE_URL}/api/v1/schemas")
            details["auth_required"] = response.status_code == 401
            
            # Test invalid token
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                headers={"Authorization": "Bearer invalid_token"}
            )
            details["invalid_token_rejected"] = response.status_code == 401
            
            # Test rate limiting
            headers = self.get_headers()
            rate_limited = False
            
            for i in range(100):
                response = requests.get(
                    f"{OMS_SERVICE_URL}/api/v1/health",
                    headers=headers
                )
                if response.status_code == 429:
                    rate_limited = True
                    details["rate_limited_at_request"] = i + 1
                    break
                    
            details["rate_limiting_active"] = rate_limited
            
            # Test SQL injection protection
            malicious_input = "'; DROP TABLE schemas; --"
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas/{malicious_input}",
                headers=headers
            )
            details["sql_injection_blocked"] = response.status_code in [400, 404]
            
            # Test XSS protection
            xss_payload = "<script>alert('xss')</script>"
            response = requests.post(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                json={"name": xss_payload, "properties": []},
                headers=headers
            )
            details["xss_blocked"] = response.status_code == 400
            
            # Test CORS headers
            response = requests.options(
                f"{OMS_SERVICE_URL}/api/v1/schemas",
                headers={"Origin": "http://malicious.com"}
            )
            details["cors_configured"] = "Access-Control-Allow-Origin" in response.headers
            
            return TestResult(
                name="Security Features",
                category="Production Readiness",
                status=TestStatus.PASS if details.get("auth_required") and details.get("sql_injection_blocked") else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Security Features",
                category="Production Readiness",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def test_performance_benchmarks(self) -> TestResult:
        """Test performance benchmarks"""
        start_time = time.time()
        details = {}
        
        try:
            headers = self.get_headers()
            
            # Test response times
            endpoints = [
                ("/api/v1/schemas", "GET", None),
                ("/api/v1/branches", "GET", None),
                ("/api/v1/health", "GET", None)
            ]
            
            for endpoint, method, data in endpoints:
                times = []
                for _ in range(10):
                    start = time.time()
                    if method == "GET":
                        response = requests.get(f"{OMS_SERVICE_URL}{endpoint}", headers=headers)
                    else:
                        response = requests.post(f"{OMS_SERVICE_URL}{endpoint}", json=data, headers=headers)
                    times.append(time.time() - start)
                    
                avg_time = sum(times) / len(times)
                details[f"{endpoint}_avg_response_time"] = avg_time
                details[f"{endpoint}_under_100ms"] = avg_time < 0.1
                
            # Test concurrent load
            import concurrent.futures
            
            def make_request():
                start = time.time()
                response = requests.get(f"{OMS_SERVICE_URL}/api/v1/health", headers=headers)
                return time.time() - start, response.status_code
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                futures = [executor.submit(make_request) for _ in range(100)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
            response_times = [r[0] for r in results]
            success_count = sum(1 for r in results if r[1] == 200)
            
            details["concurrent_avg_response_time"] = sum(response_times) / len(response_times)
            details["concurrent_95th_percentile"] = sorted(response_times)[95]
            details["concurrent_success_rate"] = success_count / len(results)
            
            # Test database query performance
            schema_name = f"PerfTest-{uuid.uuid4().hex[:8]}"
            
            # Create many objects
            create_start = time.time()
            for i in range(100):
                requests.post(
                    f"{OMS_SERVICE_URL}/api/v1/schemas",
                    json={"name": f"{schema_name}-{i}", "properties": []},
                    headers=headers
                )
            create_time = time.time() - create_start
            details["bulk_create_time"] = create_time
            details["bulk_create_rate"] = 100 / create_time
            
            # Query with pagination
            query_start = time.time()
            response = requests.get(
                f"{OMS_SERVICE_URL}/api/v1/schemas?limit=50&offset=0",
                headers=headers
            )
            query_time = time.time() - query_start
            details["pagination_query_time"] = query_time
            details["pagination_under_50ms"] = query_time < 0.05
            
            return TestResult(
                name="Performance Benchmarks",
                category="Production Readiness",
                status=TestStatus.PASS if details.get("concurrent_success_rate", 0) > 0.95 else TestStatus.PARTIAL,
                duration=time.time() - start_time,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                name="Performance Benchmarks",
                category="Production Readiness",
                status=TestStatus.FAIL,
                duration=time.time() - start_time,
                details=details,
                error=str(e)
            )
            
    async def run_all_tests(self):
        """Run all tests"""
        self.print_header("ENTERPRISE INTEGRATION TEST SUITE")
        
        # Setup
        if not await self.setup():
            print(f"{RED}Setup failed. Exiting...{RESET}")
            return
            
        # Define test categories
        test_categories = [
            ("Version Control", [
                self.test_branch_management,
                self.test_merge_operations,
                self.test_rollback_functionality
            ]),
            ("Ontology Management", [
                self.test_object_type_management,
                self.test_link_type_relationships
            ]),
            ("Advanced Features", [
                self.test_vector_embeddings,
                self.test_redis_smart_cache,
                self.test_jaeger_tracing,
                self.test_time_travel_queries
            ]),
            ("Production Readiness", [
                self.test_monitoring_stack,
                self.test_resilience_patterns,
                self.test_security_features,
                self.test_performance_benchmarks
            ])
        ]
        
        # Run tests by category
        for category_name, tests in test_categories:
            self.print_category(category_name)
            
            for test_func in tests:
                try:
                    result = await test_func()
                    self.results.append(result)
                    self.print_test(
                        result.name,
                        result.status,
                        result.duration,
                        result.error or ""
                    )
                except Exception as e:
                    result = TestResult(
                        name=test_func.__name__.replace("test_", "").replace("_", " ").title(),
                        category=category_name,
                        status=TestStatus.FAIL,
                        duration=0,
                        details={},
                        error=str(e)
                    )
                    self.results.append(result)
                    self.print_test(result.name, result.status, result.duration, str(e))
                    
        # Generate summary
        self.generate_summary()
        
    def generate_summary(self):
        """Generate test summary"""
        self.print_header("TEST SUMMARY")
        
        # Calculate statistics
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        partial = sum(1 for r in self.results if r.status == TestStatus.PARTIAL)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)
        
        total_duration = sum(r.duration for r in self.results)
        
        # Print statistics
        print(f"{BOLD}Total Tests:{RESET} {total_tests}")
        print(f"{GREEN}Passed:{RESET} {passed} ({passed/total_tests*100:.1f}%)")
        print(f"{RED}Failed:{RESET} {failed} ({failed/total_tests*100:.1f}%)")
        print(f"{YELLOW}Partial:{RESET} {partial} ({partial/total_tests*100:.1f}%)")
        print(f"{BLUE}Skipped:{RESET} {skipped} ({skipped/total_tests*100:.1f}%)")
        print(f"\n{BOLD}Total Duration:{RESET} {total_duration:.2f}s")
        print(f"{BOLD}Test Suite Runtime:{RESET} {(datetime.now() - self.start_time).total_seconds():.2f}s")
        
        # Category breakdown
        print(f"\n{BOLD}Results by Category:{RESET}")
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = {"pass": 0, "fail": 0, "partial": 0, "skip": 0}
            categories[result.category][result.status.value.lower()] += 1
            
        for category, stats in categories.items():
            total = sum(stats.values())
            pass_rate = (stats["pass"] / total * 100) if total > 0 else 0
            print(f"\n  {BOLD}{category}:{RESET}")
            print(f"    Pass: {stats['pass']}/{total} ({pass_rate:.1f}%)")
            if stats["fail"] > 0:
                print(f"    Fail: {stats['fail']}")
            if stats["partial"] > 0:
                print(f"    Partial: {stats['partial']}")
                
        # Failed tests detail
        if failed > 0:
            print(f"\n{BOLD}{RED}Failed Tests:{RESET}")
            for result in self.results:
                if result.status == TestStatus.FAIL:
                    print(f"  - {result.name}: {result.error}")
                    
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total_tests,
                "passed": passed,
                "failed": failed,
                "partial": partial,
                "skipped": skipped,
                "duration": total_duration,
                "runtime": (datetime.now() - self.start_time).total_seconds()
            },
            "categories": categories,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "status": r.status.value,
                    "duration": r.duration,
                    "details": r.details,
                    "error": r.error
                }
                for r in self.results
            ]
        }
        
        report_file = f"enterprise_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        print(f"\n{BOLD}Detailed report saved to:{RESET} {report_file}")
        
        # Production readiness assessment
        print(f"\n{BOLD}Production Readiness Assessment:{RESET}")
        
        critical_tests = [
            "Branch Management",
            "Security Features",
            "Monitoring Stack",
            "Resilience Patterns"
        ]
        
        critical_passed = sum(1 for r in self.results 
                            if r.name in critical_tests and r.status == TestStatus.PASS)
        
        if critical_passed == len(critical_tests):
            print(f"{GREEN}✓ All critical tests passed - System is production ready{RESET}")
        else:
            print(f"{RED}✗ Some critical tests failed - System needs attention{RESET}")
            
        # Feature completeness
        print(f"\n{BOLD}Feature Completeness:{RESET}")
        features = {
            "Version Control": ["Branch Management", "Merge Operations", "Rollback Functionality"],
            "Ontology": ["ObjectType Management", "LinkType Relationships"],
            "Caching": ["Redis SmartCache"],
            "Observability": ["Jaeger Tracing", "Monitoring Stack"],
            "Time Travel": ["Time Travel Queries"]
        }
        
        for feature, tests in features.items():
            feature_results = [r for r in self.results if r.name in tests]
            if all(r.status in [TestStatus.PASS, TestStatus.PARTIAL] for r in feature_results):
                print(f"  {GREEN}✓{RESET} {feature}")
            else:
                print(f"  {RED}✗{RESET} {feature}")


if __name__ == "__main__":
    suite = EnterpriseTestSuite()
    asyncio.run(suite.run_all_tests())