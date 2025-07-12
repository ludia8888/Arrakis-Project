#!/usr/bin/env python3
"""
Arrakis Project - Ultra Deep Code Analysis
철저한 dead code, 조용히 실패하는 코드, mock implementations 탐지
"""

import os
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Set
from datetime import datetime

class UltraDeepCodeAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.analysis_results = {
            "scan_time": datetime.now().isoformat(),
            "dead_code": [],
            "silent_failures": [],
            "mock_implementations": [],
            "unimplemented_functions": [],
            "import_failures": [],
            "empty_exception_handlers": [],
            "hardcoded_mocks": [],
            "unused_routes": [],
            "statistics": {}
        }
        
        # 의심스러운 패턴들
        self.mock_patterns = [
            r"return\s+\{\s*['\"]status['\"]:\s*['\"]mock['\"]",
            r"return\s+\[\]",
            r"return\s+\{\}",
            r"pass\s*#.*mock",
            r"raise\s+NotImplementedError",
            r"print\s*\(\s*['\"]TODO",
            r"print\s*\(\s*['\"]FIXME",
            r"# TODO:",
            r"# FIXME:",
            r"mock_.*=",
            r"return\s+None\s*#.*not.*implemented"
        ]
        
        self.failure_patterns = [
            r"except.*:\s*pass",
            r"except.*Exception.*:\s*pass",
            r"try:.*except.*:\s*continue",
            r"if.*False:",
            r"return\s+False\s*#.*fail"
        ]

    def scan_python_files(self) -> List[Path]:
        """Python 파일들 스캔"""
        python_files = []
        
        # 서비스 디렉토리들
        service_dirs = [
            "ontology-management-service",
            "user-service", 
            "audit-service"
        ]
        
        for service_dir in service_dirs:
            service_path = self.project_root / service_dir
            if service_path.exists():
                for py_file in service_path.rglob("*.py"):
                    # 가상환경과 캐시 제외
                    if not any(part in str(py_file) for part in ["venv", "__pycache__", ".git"]):
                        python_files.append(py_file)
        
        return python_files

    def analyze_file_content(self, file_path: Path) -> Dict[str, Any]:
        """개별 파일 내용 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}
        
        analysis = {
            "file": str(file_path.relative_to(self.project_root)),
            "lines": len(content.splitlines()),
            "mock_patterns_found": [],
            "silent_failures_found": [],
            "dead_functions": [],
            "import_issues": [],
            "suspicious_code": []
        }
        
        # Mock 패턴 검사
        for pattern in self.mock_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_no = content[:match.start()].count('\n') + 1
                analysis["mock_patterns_found"].append({
                    "pattern": pattern,
                    "line": line_no,
                    "code": match.group().strip()
                })
        
        # Silent failure 패턴 검사
        for pattern in self.failure_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_no = content[:match.start()].count('\n') + 1
                analysis["silent_failures_found"].append({
                    "pattern": pattern,
                    "line": line_no,
                    "code": match.group().strip()
                })
        
        # AST 분석으로 더 정교한 검사
        try:
            tree = ast.parse(content)
            ast_analysis = self.analyze_ast(tree, content)
            analysis.update(ast_analysis)
        except SyntaxError as e:
            analysis["syntax_error"] = str(e)
        
        return analysis

    def analyze_ast(self, tree: ast.AST, content: str) -> Dict[str, Any]:
        """AST를 사용한 정교한 분석"""
        ast_analysis = {
            "functions": [],
            "classes": [],
            "imports": [],
            "raises_not_implemented": [],
            "empty_functions": [],
            "hardcoded_returns": []
        }
        
        for node in ast.walk(tree):
            # 함수 분석
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "is_empty": len(node.body) == 1 and isinstance(node.body[0], ast.Pass),
                    "has_docstring": ast.get_docstring(node) is not None,
                    "returns_hardcoded": False
                }
                
                # Return 문 분석
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and isinstance(child.value, (ast.Dict, ast.List)):
                        func_info["returns_hardcoded"] = True
                    
                    if isinstance(child, ast.Raise) and isinstance(child.exc, ast.Call):
                        if hasattr(child.exc.func, 'id') and child.exc.func.id == 'NotImplementedError':
                            ast_analysis["raises_not_implemented"].append({
                                "function": node.name,
                                "line": child.lineno
                            })
                
                if func_info["is_empty"]:
                    ast_analysis["empty_functions"].append(func_info)
                
                ast_analysis["functions"].append(func_info)
            
            # Import 분석
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = {
                    "line": node.lineno,
                    "module": getattr(node, 'module', None),
                    "names": [alias.name for alias in node.names] if hasattr(node, 'names') else []
                }
                ast_analysis["imports"].append(import_info)
        
        return ast_analysis

    def check_route_usage(self, file_path: Path) -> List[Dict]:
        """라우트 정의와 실제 사용 확인"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return []
        
        # FastAPI 라우트 패턴 찾기
        route_patterns = [
            r"@router\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]",
            r"@app\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]"
        ]
        
        found_routes = []
        for pattern in route_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_no = content[:match.start()].count('\n') + 1
                found_routes.append({
                    "method": match.group(1).upper(),
                    "path": match.group(2),
                    "line": line_no,
                    "file": str(file_path.relative_to(self.project_root))
                })
        
        return found_routes

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """포괄적인 분석 실행"""
        print("🔍 ULTRA DEEP CODE ANALYSIS - Detecting Dead Code & Silent Failures")
        print("=" * 80)
        
        python_files = self.scan_python_files()
        print(f"📁 Scanning {len(python_files)} Python files...")
        
        all_routes = []
        total_mock_patterns = 0
        total_silent_failures = 0
        total_functions = 0
        total_empty_functions = 0
        
        for file_path in python_files:
            print(f"   🔍 Analyzing: {file_path.name}")
            
            # 파일 내용 분석
            file_analysis = self.analyze_file_content(file_path)
            
            # 통계 수집
            total_mock_patterns += len(file_analysis.get("mock_patterns_found", []))
            total_silent_failures += len(file_analysis.get("silent_failures_found", []))
            total_functions += len(file_analysis.get("functions", []))
            total_empty_functions += len(file_analysis.get("empty_functions", []))
            
            # 문제가 있는 파일만 결과에 포함
            if (file_analysis.get("mock_patterns_found") or 
                file_analysis.get("silent_failures_found") or
                file_analysis.get("raises_not_implemented") or
                file_analysis.get("empty_functions")):
                
                if file_analysis.get("mock_patterns_found"):
                    self.analysis_results["mock_implementations"].append(file_analysis)
                if file_analysis.get("silent_failures_found"):
                    self.analysis_results["silent_failures"].append(file_analysis)
                if file_analysis.get("empty_functions"):
                    self.analysis_results["dead_code"].append(file_analysis)
                if file_analysis.get("raises_not_implemented"):
                    self.analysis_results["unimplemented_functions"].append(file_analysis)
            
            # 라우트 검사
            routes = self.check_route_usage(file_path)
            all_routes.extend(routes)
        
        # 통계 계산
        self.analysis_results["statistics"] = {
            "total_files_scanned": len(python_files),
            "total_functions_found": total_functions,
            "empty_functions": total_empty_functions,
            "mock_patterns_detected": total_mock_patterns,
            "silent_failures_detected": total_silent_failures,
            "total_routes_found": len(all_routes),
            "files_with_issues": len([f for f in [
                self.analysis_results["mock_implementations"],
                self.analysis_results["silent_failures"], 
                self.analysis_results["dead_code"],
                self.analysis_results["unimplemented_functions"]
            ] if f])
        }
        
        self.analysis_results["all_routes"] = all_routes
        
        return self.analysis_results

    def generate_report(self):
        """상세한 보고서 생성"""
        stats = self.analysis_results["statistics"]
        
        print("\n" + "=" * 80)
        print("📊 ULTRA DEEP ANALYSIS RESULTS")
        print("=" * 80)
        
        print(f"📁 Files Scanned: {stats['total_files_scanned']}")
        print(f"🔧 Functions Found: {stats['total_functions_found']}")
        print(f"📋 Routes Discovered: {stats['total_routes_found']}")
        
        print(f"\n🚨 ISSUES DETECTED:")
        print(f"   💀 Dead Code Files: {len(self.analysis_results['dead_code'])}")
        print(f"   🤫 Silent Failure Files: {len(self.analysis_results['silent_failures'])}")  
        print(f"   🎭 Mock Implementation Files: {len(self.analysis_results['mock_implementations'])}")
        print(f"   ❌ Unimplemented Function Files: {len(self.analysis_results['unimplemented_functions'])}")
        
        # 상세한 문제 보고
        if self.analysis_results["mock_implementations"]:
            print(f"\n🎭 MOCK IMPLEMENTATIONS DETECTED:")
            for file_info in self.analysis_results["mock_implementations"]:
                print(f"   📄 {file_info['file']}:")
                for mock in file_info.get("mock_patterns_found", []):
                    print(f"      Line {mock['line']}: {mock['code'][:50]}...")
        
        if self.analysis_results["silent_failures"]:
            print(f"\n🤫 SILENT FAILURES DETECTED:")
            for file_info in self.analysis_results["silent_failures"]:
                print(f"   📄 {file_info['file']}:")
                for failure in file_info.get("silent_failures_found", []):
                    print(f"      Line {failure['line']}: {failure['code'][:50]}...")
        
        if self.analysis_results["dead_code"]:
            print(f"\n💀 DEAD CODE DETECTED:")
            for file_info in self.analysis_results["dead_code"]:
                print(f"   📄 {file_info['file']}:")
                for func in file_info.get("empty_functions", []):
                    print(f"      Empty function '{func['name']}' at line {func['line']}")
        
        # 실제 구현률 계산
        total_issues = (len(self.analysis_results["dead_code"]) + 
                       len(self.analysis_results["silent_failures"]) + 
                       len(self.analysis_results["mock_implementations"]) +
                       len(self.analysis_results["unimplemented_functions"]))
        
        files_with_issues = len(set([
            file_info['file'] for file_list in [
                self.analysis_results["dead_code"],
                self.analysis_results["silent_failures"],
                self.analysis_results["mock_implementations"],
                self.analysis_results["unimplemented_functions"]
            ] for file_info in file_list
        ]))
        
        clean_files = stats['total_files_scanned'] - files_with_issues
        actual_implementation_rate = (clean_files / stats['total_files_scanned']) * 100 if stats['total_files_scanned'] > 0 else 0
        
        print(f"\n🎯 ACTUAL IMPLEMENTATION ANALYSIS:")
        print(f"   Clean Files: {clean_files}/{stats['total_files_scanned']}")
        print(f"   Files with Issues: {files_with_issues}")
        print(f"   Actual Implementation Rate: {actual_implementation_rate:.1f}%")
        
        if actual_implementation_rate >= 85:
            print("🎉 EXCELLENT: 85%+ Clean Implementation")
        elif actual_implementation_rate >= 70:
            print("✅ GOOD: 70%+ Clean Implementation")
        elif actual_implementation_rate >= 50:
            print("⚠️  MODERATE: 50%+ Clean Implementation") 
        else:
            print("🚨 NEEDS WORK: <50% Clean Implementation")

def main():
    analyzer = UltraDeepCodeAnalyzer("/Users/isihyeon/Desktop/Arrakis-Project")
    results = analyzer.run_comprehensive_analysis()
    analyzer.generate_report()
    
    # 결과 저장
    results_file = f"/Users/isihyeon/Desktop/Arrakis-Project/ultra_deep_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Detailed results saved to: {results_file}")

if __name__ == "__main__":
    main()