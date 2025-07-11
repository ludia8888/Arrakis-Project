#!/usr/bin/env python3
"""
Static Middleware Verification Test
Verifies middleware implementations without running the service
"""

import os
import ast
import importlib.util
from typing import Dict, List, Any, Optional
from datetime import datetime

class MiddlewareStaticVerifier:
    """Static verification of middleware implementations"""
    
    def __init__(self):
        self.base_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
        self.results = {}
        
    def verify_middleware_file_exists(self, middleware_name: str, file_path: str) -> Dict[str, Any]:
        """Verify middleware file exists"""
        full_path = os.path.join(self.base_path, file_path)
        exists = os.path.exists(full_path)
        
        result = {
            "middleware": middleware_name,
            "file_path": file_path,
            "exists": exists
        }
        
        if exists:
            # Check file size
            result["file_size"] = os.path.getsize(full_path)
            result["last_modified"] = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
            
            # Check for middleware class
            with open(full_path, 'r') as f:
                content = f.read()
                result["has_middleware_class"] = "Middleware" in content
                result["imports_starlette"] = "from starlette.middleware" in content or "from fastapi.middleware" in content
                
        return result
    
    def verify_middleware_implementation(self, file_path: str, class_name: str) -> Dict[str, Any]:
        """Verify middleware implementation details"""
        full_path = os.path.join(self.base_path, file_path)
        
        result = {
            "class_name": class_name,
            "has_class": False,
            "has_dispatch_method": False,
            "has_init_method": False,
            "imports": []
        }
        
        try:
            with open(full_path, 'r') as f:
                tree = ast.parse(f.read())
                
            for node in ast.walk(tree):
                # Find imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        result["imports"].append(f"{module}.{alias.name}")
                
                # Find class definition
                elif isinstance(node, ast.ClassDef) and node.name == class_name:
                    result["has_class"] = True
                    
                    # Check methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name == "__init__":
                                result["has_init_method"] = True
                            elif item.name == "dispatch":
                                result["has_dispatch_method"] = True
                                # Check if it's async
                                result["dispatch_is_async"] = isinstance(item, ast.AsyncFunctionDef)
                    
                    # Check base classes
                    result["base_classes"] = [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
                    
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def verify_middleware_registration(self, middleware_name: str) -> Dict[str, Any]:
        """Verify middleware is registered in app.py"""
        app_path = os.path.join(self.base_path, "bootstrap/app.py")
        
        result = {
            "middleware": middleware_name,
            "imported": False,
            "added_to_app": False,
            "import_line": None,
            "add_middleware_line": None
        }
        
        try:
            with open(app_path, 'r') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                # Check imports (including aliases)
                if (f"from middleware.{middleware_name.lower()}" in line or 
                    f"import {middleware_name}" in line or
                    f"as {middleware_name}" in line or
                    middleware_name in line and ("import" in line or "from" in line)):
                    result["imported"] = True
                    result["import_line"] = i + 1
                
                # Check middleware addition
                if f"app.add_middleware({middleware_name}" in line:
                    result["added_to_app"] = True
                    result["add_middleware_line"] = i + 1
                    
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def run_verification(self) -> Dict[str, Any]:
        """Run comprehensive static verification"""
        print("🔍 Starting Static Middleware Verification")
        print("=" * 70)
        
        # Define all middlewares to verify
        middlewares = [
            {
                "name": "GlobalCircuitBreakerMiddleware",
                "file": "middleware/circuit_breaker_global.py",
                "class": "GlobalCircuitBreakerMiddleware"
            },
            {
                "name": "ErrorHandlerMiddleware",
                "file": "middleware/error_handler.py",
                "class": "ErrorHandlerMiddleware"
            },
            {
                "name": "CORSMiddleware",
                "file": None,  # Built-in FastAPI
                "class": None
            },
            {
                "name": "ETagMiddleware",
                "file": "middleware/etag_middleware.py",
                "class": "ETagMiddleware"
            },
            {
                "name": "AuthMiddleware",
                "file": "middleware/auth_middleware.py",
                "class": "AuthMiddleware"
            },
            {
                "name": "TerminusContextMiddleware",
                "file": "middleware/terminus_context_middleware.py",
                "class": "TerminusContextMiddleware"
            },
            {
                "name": "CoreDatabaseContextMiddleware",
                "file": "core/auth_utils/database_context.py",
                "class": "DatabaseContextMiddleware"
            },
            {
                "name": "ScopeRBACMiddleware",
                "file": "core/iam/scope_rbac_middleware.py",
                "class": "ScopeRBACMiddleware"
            },
            {
                "name": "RequestIdMiddleware",
                "file": "middleware/request_id.py",
                "class": "RequestIdMiddleware"
            },
            {
                "name": "AuditLogMiddleware",
                "file": "middleware/audit_log.py",
                "class": "AuditLogMiddleware"
            },
            {
                "name": "SchemaFreezeMiddleware",
                "file": "middleware/schema_freeze_middleware.py",
                "class": "SchemaFreezeMiddleware"
            },
            {
                "name": "ThreeWayMergeMiddleware",
                "file": "middleware/three_way_merge.py",
                "class": "ThreeWayMergeMiddleware"
            },
            {
                "name": "EventStateStoreMiddleware",
                "file": "middleware/event_state_store.py",
                "class": "EventStateStoreMiddleware"
            },
            {
                "name": "IssueTrackingMiddleware",
                "file": "middleware/issue_tracking_middleware.py",
                "class": "IssueTrackingMiddleware"
            },
            {
                "name": "ComponentMiddleware",
                "file": "middleware/component_middleware.py",
                "class": "ComponentMiddleware"
            },
            {
                "name": "RateLimitingMiddleware",
                "file": "middleware/rate_limiting/fastapi_middleware.py",
                "class": "RateLimitingMiddleware"
            }
        ]
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "middlewares": [],
            "summary": {
                "total": len(middlewares),
                "files_exist": 0,
                "implementations_valid": 0,
                "registered_in_app": 0,
                "fully_active": 0
            }
        }
        
        for mw in middlewares:
            print(f"\n📋 Verifying {mw['name']}...")
            
            mw_result = {
                "name": mw["name"],
                "verification": {}
            }
            
            # Skip built-in middlewares
            if mw["file"] is None:
                mw_result["verification"]["built_in"] = True
                mw_result["status"] = "✅ Built-in"
                results["middlewares"].append(mw_result)
                results["summary"]["fully_active"] += 1
                continue
            
            # 1. Check file exists
            file_check = self.verify_middleware_file_exists(mw["name"], mw["file"])
            mw_result["verification"]["file"] = file_check
            
            if file_check["exists"]:
                results["summary"]["files_exist"] += 1
                print(f"  ✅ File exists: {mw['file']}")
                
                # 2. Check implementation
                if mw["class"]:
                    impl_check = self.verify_middleware_implementation(mw["file"], mw["class"])
                    mw_result["verification"]["implementation"] = impl_check
                    
                    if impl_check["has_class"] and impl_check["has_dispatch_method"]:
                        results["summary"]["implementations_valid"] += 1
                        print(f"  ✅ Class {mw['class']} properly implemented")
                    else:
                        print(f"  ❌ Implementation issues: class={impl_check['has_class']}, dispatch={impl_check['has_dispatch_method']}")
                
                # 3. Check registration
                reg_check = self.verify_middleware_registration(mw["name"])
                mw_result["verification"]["registration"] = reg_check
                
                if reg_check["imported"] and reg_check["added_to_app"]:
                    results["summary"]["registered_in_app"] += 1
                    print(f"  ✅ Registered in app.py (line {reg_check['add_middleware_line']})")
                else:
                    print(f"  ❌ Registration issues: imported={reg_check['imported']}, added={reg_check['added_to_app']}")
                
                # Overall status
                if (file_check["exists"] and 
                    (not mw["class"] or (impl_check["has_class"] and impl_check["has_dispatch_method"])) and
                    reg_check["imported"] and reg_check["added_to_app"]):
                    mw_result["status"] = "✅ Fully Active"
                    results["summary"]["fully_active"] += 1
                else:
                    mw_result["status"] = "⚠️ Partially Active"
            else:
                print(f"  ❌ File not found: {mw['file']}")
                mw_result["status"] = "❌ Inactive"
            
            results["middlewares"].append(mw_result)
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print verification summary"""
        print("\n" + "=" * 70)
        print("📊 MIDDLEWARE VERIFICATION SUMMARY")
        print("=" * 70)
        
        summary = results["summary"]
        print(f"\n🎯 Overall Status:")
        print(f"  Total Middlewares: {summary['total']}")
        print(f"  Files Exist: {summary['files_exist']}")
        print(f"  Valid Implementations: {summary['implementations_valid']}")
        print(f"  Registered in App: {summary['registered_in_app']}")
        print(f"  Fully Active: {summary['fully_active']}/{summary['total']} ({summary['fully_active']/summary['total']*100:.1f}%)")
        
        print(f"\n📋 Individual Status:")
        for mw in results["middlewares"]:
            print(f"  {mw['status']} - {mw['name']}")
        
        # Write detailed results
        import json
        filename = f"middleware_static_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {filename}")

def main():
    """Run static verification"""
    verifier = MiddlewareStaticVerifier()
    results = verifier.run_verification()
    verifier.print_summary(results)
    
    # Return verdict
    if results["summary"]["fully_active"] == results["summary"]["total"]:
        print("\n🎉 SUCCESS: All middlewares are properly implemented and registered!")
        return 0
    else:
        inactive = results["summary"]["total"] - results["summary"]["fully_active"]
        print(f"\n⚠️ WARNING: {inactive} middleware(s) have issues.")
        return 1

if __name__ == "__main__":
    exit(main())