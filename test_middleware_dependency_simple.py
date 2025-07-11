#!/usr/bin/env python3
"""
Simplified Middleware Dependency and Order Test
미들웨어 의존성 및 순서 충돌 자동 테스트 (networkx 없이)
"""

import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import datetime
import json
from collections import defaultdict

class SimpleMiddlewareDependencyAnalyzer:
    """미들웨어 의존성 및 잠재적 순서 충돌 분석"""
    
    def __init__(self):
        self.base_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
        self.dependencies = defaultdict(dict)
        self.dependency_graph = defaultdict(set)  # source -> targets
        
    def analyze_middleware_dependencies(self, file_path: str, class_name: str) -> Dict[str, Set[str]]:
        """미들웨어가 의존하는 것과 제공하는 것을 분석"""
        full_path = os.path.join(self.base_path, file_path)
        
        result = {
            "requires": set(),  # request.state에서 필요한 것
            "provides": set(),  # request.state에 추가하는 것
            "modifies": set(),  # request.state에서 수정하는 것
            "headers_required": set(),  # 필요한 HTTP 헤더
            "headers_added": set(),  # 추가하는 HTTP 헤더
        }
        
        try:
            with open(full_path, 'r') as f:
                content = f.read()
                tree = ast.parse(content)
                
            # request.state 접근 분석
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    # request.state.xxx 패턴 찾기
                    if (isinstance(node.value, ast.Attribute) and 
                        hasattr(node.value.value, 'id') and 
                        node.value.value.id == 'request' and 
                        node.value.attr == 'state'):
                        
                        # 읽기 vs 쓰기 판단
                        if self._is_assignment_target(node, tree):
                            result["provides"].add(node.attr)
                            result["modifies"].add(node.attr)
                        else:
                            result["requires"].add(node.attr)
                
            # 문자열 기반 패턴 분석 (더 정확한 탐지를 위해)
            lines = content.split('\n')
            for line in lines:
                # request.state 패턴
                if 'request.state.' in line:
                    # 할당 패턴
                    if '=' in line and 'request.state.' in line.split('=')[0]:
                        # request.state.xxx = 형태
                        parts = line.split('=')[0].strip()
                        if 'request.state.' in parts:
                            attr = parts.split('request.state.')[-1].split()[0].strip()
                            if attr and attr.isidentifier():
                                result["provides"].add(attr)
                    else:
                        # 읽기 패턴
                        import re
                        matches = re.findall(r'request\.state\.(\w+)', line)
                        for match in matches:
                            if line.strip().startswith('request.state.') and '=' in line:
                                result["provides"].add(match)
                            else:
                                result["requires"].add(match)
                
                # 헤더 패턴
                if 'headers[' in line or 'headers.get(' in line:
                    import re
                    # headers["X-Something"] 또는 headers.get("X-Something")
                    header_matches = re.findall(r'headers\[["\']([^"\']+)["\']\]|headers\.get\(["\']([^"\']+)["\']', line)
                    for match_tuple in header_matches:
                        header = match_tuple[0] or match_tuple[1]
                        if '=' in line and 'headers[' in line.split('=')[0]:
                            result["headers_added"].add(header)
                        else:
                            result["headers_required"].add(header)
                            
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def _is_assignment_target(self, node, tree):
        """노드가 할당의 대상인지 확인"""
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.Assign, ast.AugAssign)):
                for target in ast.walk(parent.target if isinstance(parent, ast.AugAssign) else parent.targets[0]):
                    if target == node:
                        return True
        return False
    
    def build_dependency_graph(self, middlewares: List[Dict[str, str]]) -> Dict[str, Set[str]]:
        """미들웨어 의존성 그래프 구축"""
        
        # 각 미들웨어 분석
        for mw in middlewares:
            if mw.get("file") and mw["name"] != "CORSMiddleware":  # Skip built-in
                deps = self.analyze_middleware_dependencies(mw["file"], mw.get("class", ""))
                self.dependencies[mw["name"]] = deps
        
        # 의존성 기반 엣지 생성
        for mw_name, deps in self.dependencies.items():
            # state 요구사항 기반 의존성
            for required_state in deps["requires"]:
                # 이 state를 제공하는 미들웨어 찾기
                for other_mw, other_deps in self.dependencies.items():
                    if required_state in other_deps["provides"]:
                        self.dependency_graph[other_mw].add(mw_name)
        
        return dict(self.dependency_graph)
    
    def detect_circular_dependencies(self) -> List[List[str]]:
        """순환 의존성 감지"""
        cycles = []
        
        def dfs(node, path, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    # 순환 발견
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        visited = set()
        for node in self.dependency_graph:
            if node not in visited:
                dfs(node, [], visited, set())
        
        return cycles
    
    def validate_current_order(self, current_order: List[str]) -> Dict[str, Any]:
        """현재 미들웨어 순서가 모든 의존성을 만족하는지 검증"""
        violations = []
        warnings = []
        
        # 각 미들웨어에 대해
        for i, mw in enumerate(current_order):
            if mw not in self.dependencies:
                continue
                
            deps = self.dependencies[mw]
            
            # 필요한 state 확인
            for required_state in deps["requires"]:
                provider_found = False
                provider_name = None
                
                # 이전 미들웨어들 중에서 제공자 찾기
                for j in range(i):
                    prev_mw = current_order[j]
                    if prev_mw in self.dependencies:
                        if required_state in self.dependencies[prev_mw]["provides"]:
                            provider_found = True
                            provider_name = prev_mw
                            break
                
                if not provider_found:
                    # 이후 미들웨어에서 제공하는지 확인
                    for j in range(i + 1, len(current_order)):
                        next_mw = current_order[j]
                        if next_mw in self.dependencies:
                            if required_state in self.dependencies[next_mw]["provides"]:
                                violations.append({
                                    "type": "순서 위반",
                                    "middleware": mw,
                                    "requires": required_state,
                                    "provided_by": next_mw,
                                    "current_position": i,
                                    "provider_position": j,
                                    "fix": f"{next_mw}를 {mw} 앞으로 이동"
                                })
                                break
                    else:
                        warnings.append({
                            "type": "제공자 없음",
                            "middleware": mw,
                            "requires": required_state,
                            "suggestion": f"'{required_state}'를 제공하는 미들웨어를 {mw} 앞에 추가"
                        })
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "cycles": self.detect_circular_dependencies()
        }
    
    def suggest_optimal_order(self, current_order: List[str]) -> List[str]:
        """최적의 미들웨어 실행 순서 제안 (간단한 토폴로지 정렬)"""
        # 의존성 그래프의 역방향 (누가 나를 필요로 하는가)
        reverse_graph = defaultdict(set)
        in_degree = defaultdict(int)
        
        for source, targets in self.dependency_graph.items():
            for target in targets:
                reverse_graph[target].add(source)
                in_degree[target] += 1
        
        # 진입 차수가 0인 노드부터 시작
        queue = []
        for mw in current_order:
            if mw in self.dependencies and in_degree[mw] == 0:
                queue.append(mw)
        
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in self.dependency_graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 순서에 포함되지 않은 미들웨어 추가
        for mw in current_order:
            if mw not in result:
                result.append(mw)
        
        return result

def analyze_current_middleware_setup():
    """현재 미들웨어 설정 분석"""
    analyzer = SimpleMiddlewareDependencyAnalyzer()
    
    # 모든 미들웨어 정의
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
    
    # app.py의 현재 순서 (FastAPI는 역순으로 추가하므로)
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
    
    print("🔍 미들웨어 의존성 및 순서 분석 중...")
    print("=" * 70)
    
    # 의존성 그래프 구축
    graph = analyzer.build_dependency_graph(middlewares)
    
    # 각 미들웨어 분석
    print("\n📊 미들웨어 의존성:")
    for mw_name, deps in analyzer.dependencies.items():
        if deps.get("requires") or deps.get("provides"):
            print(f"\n{mw_name}:")
            if deps.get("requires"):
                print(f"  📥 필요: {', '.join(deps['requires'])}")
            if deps.get("provides"):
                print(f"  📤 제공: {', '.join(deps['provides'])}")
            if deps.get("headers_required"):
                print(f"  🔍 필요한 헤더: {', '.join(deps['headers_required'])}")
            if deps.get("headers_added"):
                print(f"  ➕ 추가하는 헤더: {', '.join(deps['headers_added'])}")
    
    # 현재 순서 검증
    print("\n🔄 현재 미들웨어 순서 검증 중...")
    validation = analyzer.validate_current_order(current_order)
    
    if validation["valid"]:
        print("✅ 현재 미들웨어 순서가 유효합니다!")
    else:
        print("❌ 순서 위반 감지:")
        for violation in validation["violations"]:
            print(f"  - {violation['middleware']}가 {violation['requires']}를 필요로 하지만")
            print(f"    {violation['provided_by']}가 뒤에 있습니다 ({violation['fix']})")
    
    if validation["warnings"]:
        print("\n⚠️ 경고:")
        for warning in validation["warnings"]:
            print(f"  - {warning['middleware']}: {warning['suggestion']}")
    
    if validation["cycles"]:
        print("\n🔄 순환 의존성 감지:")
        for cycle in validation["cycles"]:
            print(f"  - {' -> '.join(cycle)}")
    
    # 최적 순서 제안
    optimal_order = analyzer.suggest_optimal_order(current_order)
    if optimal_order and optimal_order != current_order:
        print("\n💡 제안하는 최적 순서:")
        for i, mw in enumerate(optimal_order):
            print(f"  {i+1}. {mw}")
    
    # 의존성 그래프 시각화 (텍스트)
    if graph:
        print("\n📊 의존성 그래프:")
        for source, targets in graph.items():
            if targets:
                print(f"  {source} → {', '.join(targets)}")
    
    # 분석 결과 저장
    results = {
        "timestamp": datetime.now().isoformat(),
        "current_order": current_order,
        "dependencies": {k: {key: list(v) for key, v in deps.items() if isinstance(v, set)} 
                        for k, deps in analyzer.dependencies.items()},
        "validation": validation,
        "optimal_order": optimal_order,
        "dependency_graph": {k: list(v) for k, v in graph.items()}
    }
    
    filename = f"middleware_dependency_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 분석 결과 저장됨: {filename}")
    
    return results

if __name__ == "__main__":
    analyze_current_middleware_setup()