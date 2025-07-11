#\!/usr/bin/env python3
"""
Comprehensive integration test for the Arrakis microservices system
Tests authentication, schema creation, and document operations
"""
import asyncio
import logging
import json
from datetime import datetime
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_comprehensive_integration():
    """Comprehensive integration test"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "summary": {"passed": 0, "failed": 0}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health checks for all services
        logger.info("\n=== Testing Service Health ===")
        services = [
            ("User Service", "http://localhost:8080/health"),
            ("OMS Service", "http://localhost:8091/health"),
            ("Auth Service", "http://localhost:8080/auth/health")
        ]
        
        for service_name, url in services:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info(f"✅ {service_name} health check passed")
                    results["tests"].append({
                        "name": f"{service_name.lower().replace(' ', '_')}_health",
                        "status": "passed"
                    })
                    results["summary"]["passed"] += 1
                else:
                    logger.error(f"❌ {service_name} health check failed: {response.status_code}")
                    results["tests"].append({
                        "name": f"{service_name.lower().replace(' ', '_')}_health",
                        "status": "failed",
                        "error": f"Status {response.status_code}"
                    })
                    results["summary"]["failed"] += 1
            except Exception as e:
                logger.error(f"❌ {service_name} health check error: {e}")
                results["tests"].append({
                    "name": f"{service_name.lower().replace(' ', '_')}_health",
                    "status": "failed",
                    "error": str(e)
                })
                results["summary"]["failed"] += 1
        
        # 2. Authentication flow
        logger.info("\n=== Testing Authentication ===")
        token = None
        try:
            # Login start
            login_response = await client.post(
                "http://localhost:8080/auth/login",
                json={"username": "admin", "password": "admin123"}
            )
            if login_response.status_code == 200:
                challenge_data = login_response.json()
                challenge_token = challenge_data.get("challenge_token")
                
                # Login complete
                complete_response = await client.post(
                    "http://localhost:8080/auth/login/complete",
                    json={"challenge_token": challenge_token}
                )
                if complete_response.status_code == 200:
                    auth_data = complete_response.json()
                    token = auth_data.get("access_token")
                    logger.info("✅ Authentication successful")
                    results["tests"].append({"name": "authentication_flow", "status": "passed"})
                    results["summary"]["passed"] += 1
                    
                    # Test token validation
                    validate_response = await client.post(
                        "http://localhost:8080/auth/validate",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if validate_response.status_code == 200:
                        logger.info("✅ Token validation successful")
                        results["tests"].append({"name": "token_validation", "status": "passed"})
                        results["summary"]["passed"] += 1
                    else:
                        logger.error(f"❌ Token validation failed: {validate_response.status_code}")
                        results["tests"].append({
                            "name": "token_validation",
                            "status": "failed",
                            "error": f"Status {validate_response.status_code}"
                        })
                        results["summary"]["failed"] += 1
                else:
                    raise Exception(f"Login complete failed: {complete_response.status_code}")
            else:
                raise Exception(f"Login failed: {login_response.status_code}")
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            results["tests"].append({"name": "authentication_flow", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1
        
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            
            # 3. Schema operations
            logger.info("\n=== Testing Schema Operations ===")
            
            # Create schema
            try:
                schema_data = {
                    "name": "TestProduct",
                    "display_name": "Test Product Schema",
                    "description": "Schema for testing products",
                    "use_branch_workflow": False
                }
                
                response = await client.post(
                    "http://localhost:8091/api/v1/schemas/main/object-types",
                    json=schema_data,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    logger.info("✅ Schema creation successful")
                    results["tests"].append({"name": "schema_create", "status": "passed"})
                    results["summary"]["passed"] += 1
                    
                    # List schemas
                    list_response = await client.get(
                        "http://localhost:8091/api/v1/schemas/main/object-types",
                        headers=headers
                    )
                    if list_response.status_code == 200:
                        schemas = list_response.json()
                        logger.info(f"✅ Schema list successful: {len(schemas)} schemas found")
                        results["tests"].append({"name": "schema_list", "status": "passed"})
                        results["summary"]["passed"] += 1
                    else:
                        logger.error(f"❌ Schema list failed: {list_response.status_code}")
                        results["tests"].append({
                            "name": "schema_list",
                            "status": "failed",
                            "error": f"Status {list_response.status_code}"
                        })
                        results["summary"]["failed"] += 1
                else:
                    logger.error(f"❌ Schema creation failed: {response.status_code} - {response.text}")
                    results["tests"].append({
                        "name": "schema_create",
                        "status": "failed",
                        "error": f"Status {response.status_code}: {response.text}"
                    })
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                logger.error(f"❌ Schema operations error: {e}")
                results["tests"].append({"name": "schema_create", "status": "failed", "error": str(e)})
                results["summary"]["failed"] += 1
            
            # 4. Document operations
            logger.info("\n=== Testing Document Operations ===")
            
            # Create document
            try:
                doc_data = {
                    "name": "Test Product 1",
                    "object_type": "TestProduct",
                    "content": {"price": 99.99, "in_stock": True},
                    "metadata": {"category": "electronics"},
                    "tags": ["test", "product"]
                }
                
                response = await client.post(
                    "http://localhost:8091/api/v1/documents/main",
                    json=doc_data,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    logger.info("✅ Document creation successful")
                    results["tests"].append({"name": "document_create", "status": "passed"})
                    results["summary"]["passed"] += 1
                    
                    created_doc = response.json()
                    doc_id = created_doc.get("id")
                    
                    if doc_id:
                        # Get document
                        get_response = await client.get(
                            f"http://localhost:8091/api/v1/documents/main/{doc_id}",
                            headers=headers
                        )
                        if get_response.status_code == 200:
                            logger.info("✅ Document retrieval successful")
                            results["tests"].append({"name": "document_get", "status": "passed"})
                            results["summary"]["passed"] += 1
                        else:
                            logger.error(f"❌ Document retrieval failed: {get_response.status_code}")
                            results["tests"].append({
                                "name": "document_get",
                                "status": "failed",
                                "error": f"Status {get_response.status_code}"
                            })
                            results["summary"]["failed"] += 1
                else:
                    logger.error(f"❌ Document creation failed: {response.status_code} - {response.text}")
                    results["tests"].append({
                        "name": "document_create",
                        "status": "failed",
                        "error": f"Status {response.status_code}: {response.text}"
                    })
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                logger.error(f"❌ Document operations error: {e}")
                results["tests"].append({"name": "document_create", "status": "failed", "error": str(e)})
                results["summary"]["failed"] += 1
    
    # Save results
    with open("comprehensive_integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("Test Summary:")
    logger.info(f"  Passed: {results['summary']['passed']}")
    logger.info(f"  Failed: {results['summary']['failed']}")
    logger.info(f"  Total: {results['summary']['passed'] + results['summary']['failed']}")
    logger.info(f"  Success Rate: {results['summary']['passed'] / (results['summary']['passed'] + results['summary']['failed']) * 100:.1f}%")
    logger.info(f"{'='*60}\n")
    
    # Print failed tests
    if results['summary']['failed'] > 0:
        logger.info("Failed Tests:")
        for test in results['tests']:
            if test['status'] == 'failed':
                logger.info(f"  - {test['name']}: {test.get('error', 'Unknown error')}")
    
    return results["summary"]["failed"] == 0


if __name__ == "__main__":
    success = asyncio.run(test_comprehensive_integration())
    exit(0 if success else 1)