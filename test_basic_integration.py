#!/usr/bin/env python3
"""
기본 통합 테스트 - 브랜치 워크플로우 없이 단순 테스트
"""
import asyncio
import logging
import json
from datetime import datetime
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_integration():
    """기본 통합 테스트"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "summary": {"passed": 0, "failed": 0}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health check
        try:
            response = await client.get("http://localhost:8091/health")
            if response.status_code == 200:
                logger.info("✅ OMS health check passed")
                results["tests"].append({"name": "health_check", "status": "passed"})
                results["summary"]["passed"] += 1
            else:
                logger.error(f"❌ OMS health check failed: {response.status_code}")
                results["tests"].append({"name": "health_check", "status": "failed", "error": f"Status {response.status_code}"})
                results["summary"]["failed"] += 1
        except Exception as e:
            logger.error(f"❌ OMS health check error: {e}")
            results["tests"].append({"name": "health_check", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1
        
        # 2. Get JWT token
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
                    results["tests"].append({"name": "authentication", "status": "passed"})
                    results["summary"]["passed"] += 1
                else:
                    logger.error(f"❌ Authentication failed: {complete_response.status_code}")
                    results["tests"].append({"name": "authentication", "status": "failed", "error": f"Status {complete_response.status_code}"})
                    results["summary"]["failed"] += 1
            else:
                logger.error(f"❌ Login failed: {login_response.status_code}")
                results["tests"].append({"name": "authentication", "status": "failed", "error": f"Login status {login_response.status_code}"})
                results["summary"]["failed"] += 1
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            results["tests"].append({"name": "authentication", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1
        
        # 3. Test simple schema creation (without branch workflow)
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            
            # Try to create a simple schema
            try:
                schema_data = {
                    "name": "SimpleTestSchema",
                    "display_name": "Simple Test Schema",
                    "description": "A simple test schema",
                    "use_branch_workflow": False  # Don't use branch workflow
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
                else:
                    logger.error(f"❌ Schema creation failed: {response.status_code} - {response.text}")
                    results["tests"].append({"name": "schema_create", "status": "failed", "error": f"Status {response.status_code}: {response.text}"})
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                logger.error(f"❌ Schema creation error: {e}")
                results["tests"].append({"name": "schema_create", "status": "failed", "error": str(e)})
                results["summary"]["failed"] += 1
    
    # Save results
    with open("basic_integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("Test Summary:")
    logger.info(f"  Passed: {results['summary']['passed']}")
    logger.info(f"  Failed: {results['summary']['failed']}")
    logger.info(f"  Total: {results['summary']['passed'] + results['summary']['failed']}")
    logger.info(f"{'='*60}\n")
    
    return results["summary"]["failed"] == 0


if __name__ == "__main__":
    success = asyncio.run(test_basic_integration())
    exit(0 if success else 1)