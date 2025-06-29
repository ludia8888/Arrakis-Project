#!/usr/bin/env python3
"""
전체 코드베이스에서 레거시 코드와 중복 기능 찾기
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import ast

PROJECT_ROOT = Path(__file__).parent.parent

class LegacyCodeFinder:
    """레거시 코드 및 중복 기능 탐지"""
    
    def __init__(self):
        self.findings = {
            "deprecated_patterns": [],
            "duplicate_functionality": [],
            "dead_code": [],
            "overlapping_modules": [],
            "old_patterns": [],
            "large_files": [],
            "todo_fixme": []
        }
        
        # 레거시 패턴들
        self.legacy_patterns = {
            "old_imports": [
                r"from __future__ import",
                r"import imp\b",
                r"from imp import",
                r"import urllib2",
                r"import ConfigParser",
            ],
            "deprecated_methods": [
                r"\.has_key\(",
                r"apply\(",
                r"buffer\(",
                r"cmp\(",
                r"execfile\(",
            ],
            "old_string_formatting": [
                r"%\s*\([^)]+\)\s*%",  # Old % formatting
                r"\.format\(",  # .format() instead of f-strings
            ],
            "commented_code": [
                r"^\s*#.*\b(def|class|import|from)\b",
                r"^\s*'''.*(def|class|import|from).*'''",
                r'^\s*""".*(def|class|import|from).*"""',
            ],
            "todo_patterns": [
                r"#\s*(TODO|FIXME|HACK|XXX|BUG|DEPRECATED)",
                r"//\s*(TODO|FIXME|HACK|XXX|BUG|DEPRECATED)",
            ]
        }
        
        # 중복 가능성이 있는 모듈 이름들
        self.duplicate_indicators = {
            "validation": ["validate", "validator", "validation", "check", "verify"],
            "database": ["db", "database", "client", "connection", "query"],
            "cache": ["cache", "caching", "cached", "memoize", "store"],
            "auth": ["auth", "authentication", "authorize", "permission", "access"],
            "utils": ["util", "utils", "helper", "helpers", "common", "shared"],
            "config": ["config", "configuration", "settings", "env", "environment"],
            "test": ["test", "tests", "testing", "_test", "test_"],
        }
        
    def scan_directory(self, directory: Path) -> Dict[str, List]:
        """디렉토리 전체 스캔"""
        print(f"\n🔍 Scanning directory: {directory.name}")
        
        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', 'node_modules', 'venv', 
                '.pytest_cache', 'htmlcov', 'dist', 'build',
                'backups', '.idea', '.vscode'
            ]]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    file_path = Path(root) / file
                    self._analyze_file(file_path)
        
        return self.findings
    
    def _analyze_file(self, file_path: Path):
        """파일 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
            
            # 파일 크기 체크
            if len(lines) > 500:
                self.findings["large_files"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "lines": len(lines),
                    "size_kb": len(content) / 1024
                })
            
            # 레거시 패턴 검색
            for pattern_type, patterns in self.legacy_patterns.items():
                for pattern in patterns:
                    matches = []
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            matches.append((i, line.strip()))
                    
                    if matches:
                        self.findings["old_patterns"].append({
                            "file": str(file_path.relative_to(PROJECT_ROOT)),
                            "pattern_type": pattern_type,
                            "matches": matches[:5]  # First 5 matches
                        })
            
            # TODO/FIXME 검색
            for pattern in self.legacy_patterns["todo_patterns"]:
                for i, line in enumerate(lines, 1):
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        self.findings["todo_fixme"].append({
                            "file": str(file_path.relative_to(PROJECT_ROOT)),
                            "line": i,
                            "type": match.group(1),
                            "content": line.strip()
                        })
            
            # Python 파일인 경우 추가 분석
            if file_path.suffix == '.py':
                self._analyze_python_file(file_path, content)
                
        except Exception as e:
            pass  # Skip files that can't be read
    
    def _analyze_python_file(self, file_path: Path, content: str):
        """Python 파일 심층 분석"""
        try:
            tree = ast.parse(content)
            
            # 사용되지 않는 import 찾기
            imports = []
            used_names = set()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.Name):
                    used_names.add(node.id)
            
            # Unused imports (simplified check)
            unused = [imp for imp in imports if imp.split('.')[0] not in str(content)]
            if unused:
                self.findings["dead_code"].append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "type": "unused_imports",
                    "items": unused[:5]
                })
                
        except:
            pass
    
    def find_duplicate_modules(self):
        """중복 가능성이 있는 모듈 찾기"""
        print("\n🔍 Finding duplicate modules...")
        
        module_groups = defaultdict(list)
        
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Skip certain directories
            if any(skip in root for skip in ['__pycache__', '.git', 'backups', 'tests']):
                continue
                
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(PROJECT_ROOT)
                    
                    # 파일명으로 그룹화
                    base_name = file.replace('.py', '').lower()
                    
                    # 중복 가능성 체크
                    for category, indicators in self.duplicate_indicators.items():
                        for indicator in indicators:
                            if indicator in base_name:
                                module_groups[category].append(str(rel_path))
                                break
        
        # 중복 가능성이 있는 그룹 저장
        for category, paths in module_groups.items():
            if len(paths) > 1:
                self.findings["duplicate_functionality"].append({
                    "category": category,
                    "files": sorted(paths),
                    "count": len(paths)
                })
    
    def analyze_api_folder(self):
        """API 폴더 분석"""
        print("\n🔍 Analyzing API folder...")
        
        api_path = PROJECT_ROOT / "api"
        if not api_path.exists():
            return
        
        endpoints = defaultdict(list)
        
        for root, dirs, files in os.walk(api_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Find route decorators
                        routes = re.findall(r'@.*\.(get|post|put|patch|delete|route)\(["\']([^"\']+)', content)
                        for method, route in routes:
                            endpoints[route].append({
                                "file": str(file_path.relative_to(PROJECT_ROOT)),
                                "method": method
                            })
                    except:
                        pass
        
        # Find duplicate endpoints
        for route, definitions in endpoints.items():
            if len(definitions) > 1:
                self.findings["overlapping_modules"].append({
                    "type": "duplicate_endpoint",
                    "route": route,
                    "definitions": definitions
                })
    
    def analyze_database_folder(self):
        """Database 폴더 분석"""
        print("\n🔍 Analyzing database folder...")
        
        db_path = PROJECT_ROOT / "database"
        if not db_path.exists():
            return
        
        db_clients = []
        connection_patterns = []
        
        for root, dirs, files in os.walk(db_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(PROJECT_ROOT)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # DB client patterns
                        if any(pattern in content for pattern in [
                            'class.*Client', 'class.*Connection', 'def connect',
                            'create_engine', 'MongoClient', 'TerminusDB'
                        ]):
                            db_clients.append(str(rel_path))
                        
                        # Connection string patterns
                        conn_patterns = re.findall(r'(mongodb://|postgresql://|mysql://|terminus://)', content)
                        if conn_patterns:
                            connection_patterns.append({
                                "file": str(rel_path),
                                "types": list(set(conn_patterns))
                            })
                    except:
                        pass
        
        if len(db_clients) > 1:
            self.findings["duplicate_functionality"].append({
                "category": "database_clients",
                "files": db_clients,
                "note": "Multiple database client implementations found"
            })
    
    def generate_report(self):
        """분석 결과 리포트 생성"""
        print("\n" + "=" * 70)
        print("📊 Legacy Code Analysis Report")
        print("=" * 70)
        
        # 1. Large files
        if self.findings["large_files"]:
            print("\n🗂️  Large Files (>500 lines):")
            print("-" * 50)
            sorted_files = sorted(self.findings["large_files"], key=lambda x: x["lines"], reverse=True)
            for file_info in sorted_files[:10]:
                print(f"{file_info['file']:.<50} {file_info['lines']} lines ({file_info['size_kb']:.1f} KB)")
        
        # 2. Duplicate functionality
        if self.findings["duplicate_functionality"]:
            print("\n🔄 Duplicate/Similar Functionality:")
            print("-" * 50)
            for dup in self.findings["duplicate_functionality"]:
                print(f"\n{dup['category'].upper()} ({dup.get('count', len(dup['files']))} files):")
                for file in dup['files'][:5]:
                    print(f"  - {file}")
                if len(dup['files']) > 5:
                    print(f"  ... and {len(dup['files']) - 5} more")
        
        # 3. Old patterns
        if self.findings["old_patterns"]:
            print("\n🕰️  Legacy Patterns Found:")
            print("-" * 50)
            pattern_summary = defaultdict(list)
            for finding in self.findings["old_patterns"]:
                pattern_summary[finding["pattern_type"]].append(finding["file"])
            
            for pattern_type, files in pattern_summary.items():
                print(f"\n{pattern_type}:")
                for file in list(set(files))[:5]:
                    print(f"  - {file}")
        
        # 4. TODO/FIXME
        if self.findings["todo_fixme"]:
            print("\n📝 TODO/FIXME/HACK Comments:")
            print("-" * 50)
            todo_summary = defaultdict(int)
            for todo in self.findings["todo_fixme"]:
                todo_summary[todo["type"]] += 1
            
            for todo_type, count in sorted(todo_summary.items(), key=lambda x: x[1], reverse=True):
                print(f"{todo_type}: {count}")
        
        # 5. Dead code
        if self.findings["dead_code"]:
            print("\n☠️  Potential Dead Code:")
            print("-" * 50)
            for dead in self.findings["dead_code"][:10]:
                print(f"{dead['file']}: {dead['type']} - {', '.join(dead['items'][:3])}")
        
        # Summary
        print("\n📈 Summary:")
        print("-" * 50)
        print(f"Large files (>500 lines): {len(self.findings['large_files'])}")
        print(f"Duplicate functionality groups: {len(self.findings['duplicate_functionality'])}")
        print(f"Legacy patterns found: {len(self.findings['old_patterns'])}")
        print(f"TODO/FIXME comments: {len(self.findings['todo_fixme'])}")
        print(f"Potential dead code: {len(self.findings['dead_code'])}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        print("-" * 50)
        print("1. Review and refactor large files (>500 lines)")
        print("2. Consolidate duplicate database clients and validation logic")
        print("3. Update old string formatting to f-strings")
        print("4. Remove commented-out code")
        print("5. Address TODO/FIXME comments")
        print("6. Consider splitting utils/helpers into specific modules")

def main():
    """메인 실행 함수"""
    finder = LegacyCodeFinder()
    
    # 전체 프로젝트 스캔
    finder.scan_directory(PROJECT_ROOT)
    
    # 특정 분석
    finder.find_duplicate_modules()
    finder.analyze_api_folder()
    finder.analyze_database_folder()
    
    # 리포트 생성
    finder.generate_report()
    
    # 상세 결과 파일로 저장
    import json
    with open(PROJECT_ROOT / "legacy_code_analysis.json", "w") as f:
        json.dump(finder.findings, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: legacy_code_analysis.json")

if __name__ == "__main__":
    main()