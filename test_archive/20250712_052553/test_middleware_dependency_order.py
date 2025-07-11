#!/usr/bin/env python3
"""
Middleware Dependency and Order Conflict Test
Automatically validates middleware dependencies and execution order
"""

import ast
import os
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

class MiddlewareDependencyAnalyzer:
    """Analyzes middleware dependencies and potential order conflicts"""
    
    def __init__(self):
        self.base_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
        self.middleware_graph = nx.DiGraph()
        self.dependencies = defaultdict(set)
        self.state_modifications = defaultdict(set)
        self.state_requirements = defaultdict(set)
        
    def analyze_middleware_dependencies(self, file_path: str, class_name: str) -> Dict[str, Set[str]]:
        """Analyze what a middleware depends on and what it provides"""
        full_path = os.path.join(self.base_path, file_path)
        
        result = {
            "requires": set(),  # What this middleware needs from request.state
            "provides": set(),  # What this middleware adds to request.state
            "modifies": set(),  # What this middleware modifies in request.state
            "headers_required": set(),  # HTTP headers required
            "headers_added": set(),  # HTTP headers added
            "must_run_before": set(),  # Explicit ordering requirements
            "must_run_after": set()   # Explicit ordering requirements
        }
        
        try:
            with open(full_path, 'r') as f:
                tree = ast.parse(f.read())
                
            for node in ast.walk(tree):
                # Find request.state accesses
                if isinstance(node, ast.Attribute):
                    if (isinstance(node.value, ast.Attribute) and 
                        hasattr(node.value.value, 'id') and 
                        node.value.value.id == 'request' and 
                        node.value.attr == 'state'):
                        
                        # Determine if it's a read or write
                        parent = self._find_parent_assign(node, tree)
                        if parent:
                            result["provides"].add(node.attr)
                            result["modifies"].add(node.attr)
                        else:
                            result["requires"].add(node.attr)
                
                # Find header accesses
                if isinstance(node, ast.Subscript):
                    if (isinstance(node.value, ast.Attribute) and
                        hasattr(node.value, 'attr') and
                        node.value.attr == 'headers'):
                        
                        if isinstance(node.slice, ast.Constant):
                            header_name = node.slice.value
                            parent = self._find_parent_assign(node, tree)
                            if parent:
                                result["headers_added"].add(header_name)
                            else:
                                result["headers_required"].add(header_name)
                
                # Find comments about ordering
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    comment = str(node.value.value).lower()
                    if "must run after" in comment:
                        # Extract middleware names from comment
                        words = comment.split()
                        for i, word in enumerate(words):
                            if word == "after" and i + 1 < len(words):
                                result["must_run_after"].add(words[i + 1].strip(',:'))
                    elif "must run before" in comment:
                        words = comment.split()
                        for i, word in enumerate(words):
                            if word == "before" and i + 1 < len(words):
                                result["must_run_before"].add(words[i + 1].strip(',:'))
                                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def _find_parent_assign(self, node, tree):
        """Check if node is part of an assignment"""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.Assign):
                if node in ast.walk(parent.targets[0]):
                    return parent
            elif isinstance(parent, ast.AugAssign):
                if node in ast.walk(parent.target):
                    return parent
        return None
    
    def build_dependency_graph(self, middlewares: List[Dict[str, str]]) -> nx.DiGraph:
        """Build a directed graph of middleware dependencies"""
        
        # Analyze each middleware
        for mw in middlewares:
            if mw.get("file"):
                deps = self.analyze_middleware_dependencies(mw["file"], mw["class"])
                self.dependencies[mw["name"]] = deps
                self.middleware_graph.add_node(mw["name"], **deps)
        
        # Create edges based on dependencies
        for mw_name, deps in self.dependencies.items():
            # Direct dependencies from state requirements
            for required_state in deps["requires"]:
                # Find which middleware provides this state
                for other_mw, other_deps in self.dependencies.items():
                    if required_state in other_deps["provides"]:
                        self.middleware_graph.add_edge(other_mw, mw_name, 
                                                      reason=f"provides {required_state}")
            
            # Explicit ordering requirements
            for before_mw in deps["must_run_before"]:
                if before_mw in self.middleware_graph:
                    self.middleware_graph.add_edge(mw_name, before_mw, 
                                                  reason="explicit ordering")
            
            for after_mw in deps["must_run_after"]:
                if after_mw in self.middleware_graph:
                    self.middleware_graph.add_edge(after_mw, mw_name, 
                                                  reason="explicit ordering")
        
        return self.middleware_graph
    
    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in middleware chain"""
        try:
            cycles = list(nx.simple_cycles(self.middleware_graph))
            return cycles
        except:
            return []
    
    def validate_current_order(self, current_order: List[str]) -> Dict[str, Any]:
        """Validate if current middleware order satisfies all dependencies"""
        violations = []
        warnings = []
        
        # Check each edge in dependency graph
        for source, target, data in self.middleware_graph.edges(data=True):
            source_idx = current_order.index(source) if source in current_order else -1
            target_idx = current_order.index(target) if target in current_order else -1
            
            if source_idx >= 0 and target_idx >= 0:
                if source_idx > target_idx:
                    violations.append({
                        "type": "order_violation",
                        "middleware": source,
                        "should_run_before": target,
                        "reason": data.get("reason", "dependency"),
                        "current_position": source_idx,
                        "required_position": f"before {target_idx}"
                    })
        
        # Check for missing dependencies
        for mw in current_order:
            if mw in self.dependencies:
                deps = self.dependencies[mw]
                for required_state in deps["requires"]:
                    provider_found = False
                    for other_mw in current_order[:current_order.index(mw)]:
                        if (other_mw in self.dependencies and 
                            required_state in self.dependencies[other_mw]["provides"]):
                            provider_found = True
                            break
                    
                    if not provider_found:
                        warnings.append({
                            "type": "missing_provider",
                            "middleware": mw,
                            "requires": required_state,
                            "suggestion": f"Add middleware that provides '{required_state}' before {mw}"
                        })
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "cycles": self.detect_circular_dependencies()
        }
    
    def suggest_optimal_order(self) -> List[str]:
        """Suggest an optimal middleware execution order"""
        try:
            # Use topological sort to find a valid order
            return list(nx.topological_sort(self.middleware_graph))
        except nx.NetworkXUnfeasible:
            # Graph has cycles, need to break them
            # For now, return current order
            return []
    
    def visualize_dependencies(self, output_file: str = "middleware_dependencies.png"):
        """Create a visual graph of middleware dependencies"""
        plt.figure(figsize=(12, 8))
        
        # Layout the graph
        pos = nx.spring_layout(self.middleware_graph, k=2, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(self.middleware_graph, pos, 
                              node_color='lightblue', 
                              node_size=3000)
        
        # Draw edges with labels
        nx.draw_networkx_edges(self.middleware_graph, pos, 
                              edge_color='gray', 
                              arrows=True,
                              arrowsize=20)
        
        # Draw labels
        nx.draw_networkx_labels(self.middleware_graph, pos, 
                               font_size=8, 
                               font_weight='bold')
        
        # Draw edge labels
        edge_labels = nx.get_edge_attributes(self.middleware_graph, 'reason')
        nx.draw_networkx_edge_labels(self.middleware_graph, pos, 
                                    edge_labels, 
                                    font_size=6)
        
        plt.title("Middleware Dependencies Graph")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file

def analyze_current_middleware_setup():
    """Analyze the current middleware setup in app.py"""
    analyzer = MiddlewareDependencyAnalyzer()
    
    # Define all middlewares
    middlewares = [
        {"name": "GlobalCircuitBreakerMiddleware", "file": "middleware/circuit_breaker_global.py", "class": "GlobalCircuitBreakerMiddleware"},
        {"name": "ErrorHandlerMiddleware", "file": "middleware/error_handler.py", "class": "ErrorHandlerMiddleware"},
        {"name": "CORSMiddleware", "file": None, "class": None},  # Built-in
        {"name": "ETagMiddleware", "file": "middleware/etag_middleware.py", "class": "ETagMiddleware"},
        {"name": "AuthMiddleware", "file": "middleware/auth_middleware.py", "class": "AuthMiddleware"},
        {"name": "TerminusContextMiddleware", "file": "middleware/terminus_context_middleware.py", "class": "TerminusContextMiddleware"},
        {"name": "CoreDatabaseContextMiddleware", "file": "core/auth_utils/database_context.py", "class": "DatabaseContextMiddleware"},
        {"name": "ScopeRBACMiddleware", "file": "core/iam/scope_rbac_middleware.py", "class": "ScopeRBACMiddleware"},
        {"name": "RequestIdMiddleware", "file": "middleware/request_id.py", "class": "RequestIdMiddleware"},
        {"name": "AuditLogMiddleware", "file": "middleware/audit_log.py", "class": "AuditLogMiddleware"},
        {"name": "SchemaFreezeMiddleware", "file": "middleware/schema_freeze_middleware.py", "class": "SchemaFreezeMiddleware"},
        {"name": "ThreeWayMergeMiddleware", "file": "middleware/three_way_merge.py", "class": "ThreeWayMergeMiddleware"},
        {"name": "EventStateStoreMiddleware", "file": "middleware/event_state_store.py", "class": "EventStateStoreMiddleware"},
        {"name": "IssueTrackingMiddleware", "file": "middleware/issue_tracking_middleware.py", "class": "IssueTrackingMiddleware"},
        {"name": "ComponentMiddleware", "file": "middleware/component_middleware.py", "class": "ComponentMiddleware"},
        {"name": "RateLimitingMiddleware", "file": "middleware/rate_limiting/fastapi_middleware.py", "class": "RateLimitingMiddleware"},
    ]
    
    # Current order in app.py (reverse order because of how FastAPI adds middleware)
    current_order = [
        "RateLimitingMiddleware",
        "ComponentMiddleware",
        "IssueTrackingMiddleware",
        "EventStateStoreMiddleware",
        "ThreeWayMergeMiddleware",
        "SchemaFreezeMiddleware",
        "AuditLogMiddleware",
        "RequestIdMiddleware",
        "ScopeRBACMiddleware",
        "CoreDatabaseContextMiddleware",
        "TerminusContextMiddleware",
        "AuthMiddleware",
        "ETagMiddleware",
        "CORSMiddleware",
        "ErrorHandlerMiddleware",
        "GlobalCircuitBreakerMiddleware"
    ]
    
    print("🔍 Analyzing Middleware Dependencies and Order...")
    print("=" * 70)
    
    # Build dependency graph
    graph = analyzer.build_dependency_graph(middlewares)
    
    # Analyze each middleware
    print("\n📊 Middleware Dependencies:")
    for mw_name, deps in analyzer.dependencies.items():
        if deps.get("requires") or deps.get("provides"):
            print(f"\n{mw_name}:")
            if deps.get("requires"):
                print(f"  📥 Requires: {', '.join(deps['requires'])}")
            if deps.get("provides"):
                print(f"  📤 Provides: {', '.join(deps['provides'])}")
            if deps.get("headers_required"):
                print(f"  🔍 Headers Required: {', '.join(deps['headers_required'])}")
            if deps.get("headers_added"):
                print(f"  ➕ Headers Added: {', '.join(deps['headers_added'])}")
    
    # Validate current order
    print("\n🔄 Validating Current Middleware Order...")
    validation = analyzer.validate_current_order(current_order)
    
    if validation["valid"]:
        print("✅ Current middleware order is valid!")
    else:
        print("❌ Order violations detected:")
        for violation in validation["violations"]:
            print(f"  - {violation['middleware']} should run before {violation['should_run_before']} ({violation['reason']})")
    
    if validation["warnings"]:
        print("\n⚠️ Warnings:")
        for warning in validation["warnings"]:
            print(f"  - {warning['middleware']}: {warning['suggestion']}")
    
    if validation["cycles"]:
        print("\n🔄 Circular dependencies detected:")
        for cycle in validation["cycles"]:
            print(f"  - {' -> '.join(cycle + [cycle[0]])}")
    
    # Suggest optimal order
    optimal_order = analyzer.suggest_optimal_order()
    if optimal_order and optimal_order != current_order:
        print("\n💡 Suggested optimal order:")
        for i, mw in enumerate(optimal_order):
            print(f"  {i+1}. {mw}")
    
    # Create visualization
    print("\n📊 Creating dependency graph visualization...")
    graph_file = analyzer.visualize_dependencies()
    print(f"   Graph saved to: {graph_file}")
    
    # Save analysis results
    results = {
        "timestamp": datetime.now().isoformat(),
        "current_order": current_order,
        "dependencies": {k: {key: list(v) for key, v in deps.items() if isinstance(v, set)} 
                        for k, deps in analyzer.dependencies.items()},
        "validation": validation,
        "optimal_order": optimal_order,
        "graph_edges": list(graph.edges(data=True))
    }
    
    filename = f"middleware_dependency_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Analysis results saved to: {filename}")
    
    return results

if __name__ == "__main__":
    analyze_current_middleware_setup()