#!/usr/bin/env python3
"""
Comprehensive Feature Verification for Arrakis Project
Tests if advertised features are actually functional, not just implemented in code
"""

import json
import time
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Tuple

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class FeatureVerifier:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "features": {},
            "summary": {
                "total": 0,
                "working": 0,
                "partial": 0,
                "not_working": 0
            }
        }
        
    def print_header(self, text: str):
        print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
        print(f"{BOLD}{BLUE}{text}{RESET}")
        print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")
        
    def print_result(self, feature: str, status: str, details: str):
        color = GREEN if status == "WORKING" else YELLOW if status == "PARTIAL" else RED
        print(f"{BOLD}{feature}:{RESET} {color}{status}{RESET}")
        print(f"  {details}\n")
        
    def check_service_running(self, url: str, service_name: str) -> Tuple[bool, str]:
        """Check if a service is running by hitting its endpoint"""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                return True, f"Service responding at {url} (status: {response.status_code})"
            else:
                return False, f"Service error at {url} (status: {response.status_code})"
        except requests.exceptions.ConnectionError:
            return False, f"Service not accessible at {url}"
        except Exception as e:
            return False, f"Error checking service: {str(e)}"
            
    def check_docker_service(self, container_name: str) -> Tuple[bool, str]:
        """Check if a Docker container is running"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            if container_name in result.stdout:
                return True, f"Docker container '{container_name}' is running"
            else:
                return False, f"Docker container '{container_name}' is not running"
        except Exception as e:
            return False, f"Error checking Docker: {str(e)}"
            
    def test_graphql_deep_linking(self) -> Dict[str, Any]:
        """Test GraphQL Deep Linking feature"""
        print(f"{BOLD}Testing: GraphQL Deep Linking{RESET}")
        
        # Check if GraphQL endpoint exists
        graphql_running, graphql_msg = self.check_service_running("http://localhost:4000/graphql", "GraphQL")
        
        # Check if GraphQL code exists
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "graphql", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            graphql_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            code_exists = graphql_files > 0
        except:
            code_exists = False
            graphql_files = 0
            
        if graphql_running:
            status = "WORKING"
            details = f"GraphQL service is running. {graphql_msg}"
        elif code_exists:
            status = "PARTIAL"
            details = f"GraphQL code exists ({graphql_files} files) but service not running. {graphql_msg}"
        else:
            status = "NOT_WORKING"
            details = "No GraphQL service running and minimal code implementation"
            
        return {
            "status": status,
            "details": details,
            "service_running": graphql_running,
            "code_exists": code_exists,
            "files_count": graphql_files
        }
        
    def test_redis_smartcache(self) -> Dict[str, Any]:
        """Test Redis SmartCache feature"""
        print(f"{BOLD}Testing: Redis SmartCache{RESET}")
        
        # Check Redis connection
        try:
            result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            redis_running = result.stdout.strip() == "PONG"
            redis_msg = "Redis server is running" if redis_running else "Redis server not responding"
        except:
            redis_running = False
            redis_msg = "Redis CLI not available"
            
        # Check SmartCache implementation
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "SmartCache\\|smart_cache", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            smartcache_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            smartcache_exists = smartcache_files > 0
        except:
            smartcache_exists = False
            smartcache_files = 0
            
        if redis_running and smartcache_exists:
            status = "WORKING"
            details = f"{redis_msg}. SmartCache implementation found in {smartcache_files} files"
        elif redis_running:
            status = "PARTIAL"
            details = f"{redis_msg} but SmartCache implementation minimal ({smartcache_files} files)"
        else:
            status = "NOT_WORKING"
            details = f"{redis_msg}. SmartCache code exists but not functional"
            
        return {
            "status": status,
            "details": details,
            "redis_running": redis_running,
            "smartcache_exists": smartcache_exists,
            "files_count": smartcache_files
        }
        
    def test_jaeger_tracing(self) -> Dict[str, Any]:
        """Test Jaeger Tracing feature"""
        print(f"{BOLD}Testing: Jaeger Tracing{RESET}")
        
        # Check Jaeger UI
        jaeger_ui_running, ui_msg = self.check_service_running("http://localhost:16686", "Jaeger UI")
        
        # Check if any services are sending traces
        traces_exist = False
        services_count = 0
        if jaeger_ui_running:
            try:
                response = requests.get("http://localhost:16686/api/services")
                data = response.json()
                services_count = len(data.get("data", []))
                traces_exist = services_count > 1  # More than just jaeger-all-in-one
            except:
                pass
                
        # Check Docker container
        docker_running, docker_msg = self.check_docker_service("oms-jaeger")
        
        if jaeger_ui_running and traces_exist:
            status = "WORKING"
            details = f"Jaeger UI accessible with {services_count} services sending traces"
        elif jaeger_ui_running:
            status = "PARTIAL"
            details = f"Jaeger UI accessible but no application traces found (only {services_count} service)"
        else:
            status = "NOT_WORKING"
            details = f"Jaeger not accessible. {ui_msg}"
            
        return {
            "status": status,
            "details": details,
            "ui_running": jaeger_ui_running,
            "docker_running": docker_running,
            "traces_exist": traces_exist,
            "services_count": services_count
        }
        
    def test_time_travel_queries(self) -> Dict[str, Any]:
        """Test Time Travel Queries feature"""
        print(f"{BOLD}Testing: Time Travel Queries{RESET}")
        
        # Check if time travel endpoints exist
        try:
            # First get a token
            auth_response = requests.post(
                "http://localhost:8012/api/v1/auth/login",
                json={"username": "test", "password": "test"}
            )
            token = auth_response.json().get("access_token", "")
            
            # Try time travel endpoint
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                "http://localhost:8010/api/v1/time-travel/health",
                headers=headers,
                timeout=5
            )
            endpoint_exists = response.status_code != 404
            endpoint_working = response.status_code == 200
        except:
            endpoint_exists = False
            endpoint_working = False
            
        # Check code implementation
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "time_travel\\|TimeTravel", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            time_travel_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            code_exists = time_travel_files > 0
        except:
            code_exists = False
            time_travel_files = 0
            
        if endpoint_working:
            status = "WORKING"
            details = f"Time travel API endpoints are functional with {time_travel_files} implementation files"
        elif code_exists:
            status = "PARTIAL"
            details = f"Time travel code exists ({time_travel_files} files) but endpoints not accessible"
        else:
            status = "NOT_WORKING"
            details = "Time travel feature not implemented or accessible"
            
        return {
            "status": status,
            "details": details,
            "endpoint_exists": endpoint_exists,
            "endpoint_working": endpoint_working,
            "code_exists": code_exists,
            "files_count": time_travel_files
        }
        
    def test_unfoldable_documents(self) -> Dict[str, Any]:
        """Test @unfoldable Documents feature"""
        print(f"{BOLD}Testing: @unfoldable Documents{RESET}")
        
        # Check code implementation
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "@unfoldable\\|unfoldable", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            unfoldable_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            code_exists = unfoldable_files > 0
        except:
            code_exists = False
            unfoldable_files = 0
            
        # Check if there's a test endpoint
        test_endpoint_exists = False
        try:
            with open("/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/api/test_endpoints.py", "r") as f:
                content = f.read()
                test_endpoint_exists = "unfoldable" in content.lower()
        except:
            pass
            
        if code_exists and test_endpoint_exists:
            status = "PARTIAL"
            details = f"@unfoldable code exists ({unfoldable_files} files) with test endpoints but no production API"
        elif code_exists:
            status = "PARTIAL"
            details = f"@unfoldable code exists ({unfoldable_files} files) but no accessible endpoints"
        else:
            status = "NOT_WORKING"
            details = "@unfoldable feature not implemented"
            
        return {
            "status": status,
            "details": details,
            "code_exists": code_exists,
            "test_endpoint_exists": test_endpoint_exists,
            "files_count": unfoldable_files
        }
        
    def test_metadata_frames(self) -> Dict[str, Any]:
        """Test @metadata Frames feature"""
        print(f"{BOLD}Testing: @metadata Frames{RESET}")
        
        # Check code implementation
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "@metadata\\|metadata.*frame", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            metadata_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            code_exists = metadata_files > 0
        except:
            code_exists = False
            metadata_files = 0
            
        # Check if metadata frames module exists
        module_exists = False
        try:
            import os
            module_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/core/documents/metadata_frames.py"
            module_exists = os.path.exists(module_path)
        except:
            pass
            
        if code_exists and module_exists:
            status = "PARTIAL"
            details = f"@metadata frames code exists ({metadata_files} files) with dedicated module but no production endpoints"
        elif code_exists:
            status = "PARTIAL"
            details = f"@metadata frames code exists ({metadata_files} files) but implementation incomplete"
        else:
            status = "NOT_WORKING"
            details = "@metadata frames feature not implemented"
            
        return {
            "status": status,
            "details": details,
            "code_exists": code_exists,
            "module_exists": module_exists,
            "files_count": metadata_files
        }
        
    def test_vector_embeddings(self) -> Dict[str, Any]:
        """Test Vector Embeddings feature"""
        print(f"{BOLD}Testing: Vector Embeddings{RESET}")
        
        # Check if embedding service is running
        embedding_service_running = False
        embedding_port = None
        
        # Check common embedding service ports
        for port in [8001, 8002, 8003, 8004]:
            running, msg = self.check_service_running(f"http://localhost:{port}/embeddings", "Embedding Service")
            if running:
                embedding_service_running = True
                embedding_port = port
                break
                
        # Check code implementation
        try:
            result = subprocess.run(
                ["find", ".", "-name", "*.py", "-type", "f", "-exec", "grep", "-l", "embedding\\|vector.*embed", "{}", "+"],
                capture_output=True, text=True, cwd="/Users/isihyeon/Desktop/Arrakis-Project"
            )
            embedding_files = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            code_exists = embedding_files > 0
        except:
            code_exists = False
            embedding_files = 0
            
        # Check if it's just a stub
        is_stub = False
        try:
            with open("/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/shared/embedding_stub.py", "r") as f:
                is_stub = True
        except:
            pass
            
        if embedding_service_running:
            status = "WORKING"
            details = f"Embedding service running on port {embedding_port} with {embedding_files} implementation files"
        elif code_exists and not is_stub:
            status = "PARTIAL"
            details = f"Embedding code exists ({embedding_files} files) but service not running"
        else:
            status = "NOT_WORKING"
            details = f"Embedding feature mostly stub implementation ({embedding_files} files, stub exists: {is_stub})"
            
        return {
            "status": status,
            "details": details,
            "service_running": embedding_service_running,
            "code_exists": code_exists,
            "is_stub": is_stub,
            "files_count": embedding_files
        }
        
    def run_all_tests(self):
        """Run all feature tests"""
        self.print_header("ARRAKIS PROJECT FEATURE VERIFICATION")
        print(f"Testing if advertised features are actually functional...\n")
        
        features = [
            ("GraphQL Deep Linking", self.test_graphql_deep_linking),
            ("Redis SmartCache", self.test_redis_smartcache),
            ("Jaeger Tracing", self.test_jaeger_tracing),
            ("Time Travel Queries", self.test_time_travel_queries),
            ("@unfoldable Documents", self.test_unfoldable_documents),
            ("@metadata Frames", self.test_metadata_frames),
            ("Vector Embeddings", self.test_vector_embeddings)
        ]
        
        for feature_name, test_func in features:
            try:
                result = test_func()
                self.results["features"][feature_name] = result
                self.print_result(feature_name, result["status"], result["details"])
                
                # Update summary
                self.results["summary"]["total"] += 1
                if result["status"] == "WORKING":
                    self.results["summary"]["working"] += 1
                elif result["status"] == "PARTIAL":
                    self.results["summary"]["partial"] += 1
                else:
                    self.results["summary"]["not_working"] += 1
                    
            except Exception as e:
                print(f"{RED}Error testing {feature_name}: {str(e)}{RESET}\n")
                self.results["features"][feature_name] = {
                    "status": "ERROR",
                    "details": str(e)
                }
                self.results["summary"]["total"] += 1
                self.results["summary"]["not_working"] += 1
                
        # Print summary
        self.print_header("SUMMARY")
        summary = self.results["summary"]
        print(f"{BOLD}Total Features Tested:{RESET} {summary['total']}")
        print(f"{GREEN}Working:{RESET} {summary['working']}")
        print(f"{YELLOW}Partial (Code exists but not fully functional):{RESET} {summary['partial']}")
        print(f"{RED}Not Working:{RESET} {summary['not_working']}")
        
        # Calculate percentage
        if summary["total"] > 0:
            working_pct = (summary["working"] / summary["total"]) * 100
            partial_pct = (summary["partial"] / summary["total"]) * 100
            not_working_pct = (summary["not_working"] / summary["total"]) * 100
            
            print(f"\n{BOLD}Feature Implementation Status:{RESET}")
            print(f"  {GREEN}Fully Working: {working_pct:.1f}%{RESET}")
            print(f"  {YELLOW}Partially Implemented: {partial_pct:.1f}%{RESET}")
            print(f"  {RED}Not Working: {not_working_pct:.1f}%{RESET}")
            
        # Save results
        output_file = f"feature_verification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n{BOLD}Detailed results saved to:{RESET} {output_file}")
        
        # Print recommendations
        self.print_header("RECOMMENDATIONS")
        if summary["working"] == 0:
            print(f"{RED}⚠️  None of the advertised features are fully functional!{RESET}")
            print(f"{YELLOW}Most features have code implementations but lack running services.{RESET}")
            print(f"\nTo make features functional:")
            print(f"1. Start the GraphQL service (not found running)")
            print(f"2. Configure and run the embedding service")
            print(f"3. Set up proper time travel API endpoints")
            print(f"4. Create production endpoints for @unfoldable and @metadata features")
        elif summary["partial"] > 0:
            print(f"{YELLOW}Several features have code but need services to be started:{RESET}")
            for feature, result in self.results["features"].items():
                if result["status"] == "PARTIAL":
                    print(f"  • {feature}: {result['details']}")
                    
                    
if __name__ == "__main__":
    verifier = FeatureVerifier()
    verifier.run_all_tests()