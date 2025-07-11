#!/usr/bin/env python3
"""
MSA 서비스 간 중복 코드 분석 도구
JWT 검증, 감사 로깅, 유틸리티 함수 등의 중복을 찾아냅니다.
"""
import os
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import json

class DuplicateCodeFinder:
    """중복 코드 찾기 도구"""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.services = ['user-service', 'audit-service', 'ontology-management-service']
        self.duplicates = defaultdict(list)
        self.function_signatures = defaultdict(list)
        self.imports = defaultdict(set)
        
    def analyze_all_services(self):
        """모든 서비스 분석"""
        print("🔍 MSA 서비스 간 중복 코드 분석 시작...")
        print("="*80)
        
        # 1. 각 서비스의 함수 시그니처 수집
        for service in self.services:
            service_path = self.root_dir / service
            if service_path.exists():
                self._analyze_service(service, service_path)
        
        # 2. 중복 함수 찾기
        self._find_duplicate_functions()
        
        # 3. JWT 관련 중복 찾기
        self._find_jwt_duplicates()
        
        # 4. 감사 로깅 중복 찾기
        self._find_audit_duplicates()
        
        # 5. 유틸리티 함수 중복 찾기
        self._find_utility_duplicates()
        
        # 6. 설정 관련 중복 찾기
        self._find_config_duplicates()
        
        # 7. 모델/스키마 중복 찾기
        self._find_model_duplicates()
        
        # 8. 결과 출력
        self._print_report()
        
    def _analyze_service(self, service_name: str, service_path: Path):
        """개별 서비스 분석"""
        print(f"\n📁 {service_name} 분석 중...")
        
        for py_file in service_path.rglob("*.py"):
            # venv, __pycache__ 등 제외
            if any(skip in str(py_file) for skip in ['venv', '__pycache__', 'migrations', '.git']):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # AST 파싱
                tree = ast.parse(content)
                
                # 함수 추출
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_sig = self._get_function_signature(node)
                        func_body_hash = self._hash_function_body(node)
                        
                        self.function_signatures[func_sig].append({
                            'service': service_name,
                            'file': str(py_file.relative_to(self.root_dir)),
                            'line': node.lineno,
                            'body_hash': func_body_hash,
                            'name': node.name
                        })
                    
                    # Import 추출
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        import_name = self._get_import_name(node)
                        if import_name:
                            self.imports[service_name].add(import_name)
                            
            except Exception as e:
                # 파싱 오류는 무시
                pass
    
    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """함수 시그니처 추출"""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({','.join(args)})"
    
    def _hash_function_body(self, node: ast.FunctionDef) -> str:
        """함수 본문 해시"""
        body_str = ast.dump(node)
        return hashlib.md5(body_str.encode()).hexdigest()[:8]
    
    def _get_import_name(self, node) -> str:
        """Import 이름 추출"""
        if isinstance(node, ast.Import):
            return node.names[0].name
        elif isinstance(node, ast.ImportFrom):
            return node.module
        return None
    
    def _find_duplicate_functions(self):
        """중복 함수 찾기"""
        print("\n🔎 중복 함수 검색...")
        
        # 같은 시그니처를 가진 함수들
        for func_sig, locations in self.function_signatures.items():
            if len(locations) > 1:
                # 서로 다른 서비스에 있는지 확인
                services = set(loc['service'] for loc in locations)
                if len(services) > 1:
                    self.duplicates['functions'].append({
                        'signature': func_sig,
                        'locations': locations,
                        'services': list(services)
                    })
    
    def _find_jwt_duplicates(self):
        """JWT 관련 중복 찾기"""
        print("\n🔐 JWT 검증 중복 검색...")
        
        jwt_patterns = [
            'jwt.decode', 'jwt.encode', 'verify_token', 'validate_token',
            'get_current_user', 'decode_token', 'create_access_token',
            'create_jwt_token', 'verify_jwt', 'PyJWKClient', 'get_signing_key'
        ]
        
        jwt_files = defaultdict(list)
        
        for service in self.services:
            service_path = self.root_dir / service
            for py_file in service_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in ['venv', '__pycache__']):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in jwt_patterns:
                        if pattern in content:
                            jwt_files[pattern].append({
                                'service': service,
                                'file': str(py_file.relative_to(self.root_dir))
                            })
                            
                except:
                    pass
        
        # 여러 서비스에서 사용되는 JWT 패턴
        for pattern, locations in jwt_files.items():
            services = set(loc['service'] for loc in locations)
            if len(services) > 1:
                self.duplicates['jwt'].append({
                    'pattern': pattern,
                    'locations': locations,
                    'services': list(services)
                })
    
    def _find_audit_duplicates(self):
        """감사 로깅 중복 찾기"""
        print("\n📝 감사 로깅 중복 검색...")
        
        audit_patterns = [
            'audit_log', 'log_event', 'log_action', 'log_activity',
            'create_audit_log', 'save_audit_event', 'audit_trail',
            'log_user_action', 'record_event'
        ]
        
        audit_files = defaultdict(list)
        
        for service in self.services:
            service_path = self.root_dir / service
            for py_file in service_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in ['venv', '__pycache__']):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in audit_patterns:
                        if pattern in content:
                            audit_files[pattern].append({
                                'service': service,
                                'file': str(py_file.relative_to(self.root_dir))
                            })
                            
                except:
                    pass
        
        # 여러 서비스에서 사용되는 감사 패턴
        for pattern, locations in audit_files.items():
            services = set(loc['service'] for loc in locations)
            if len(services) > 1:
                self.duplicates['audit'].append({
                    'pattern': pattern,
                    'locations': locations,
                    'services': list(services)
                })
    
    def _find_utility_duplicates(self):
        """유틸리티 함수 중복 찾기"""
        print("\n🔧 유틸리티 함수 중복 검색...")
        
        utility_patterns = [
            'hash_password', 'verify_password', 'generate_token',
            'validate_email', 'validate_password', 'sanitize_input',
            'format_datetime', 'parse_datetime', 'generate_uuid',
            'calculate_hash', 'encode_base64', 'decode_base64'
        ]
        
        utility_files = defaultdict(list)
        
        for service in self.services:
            service_path = self.root_dir / service
            for py_file in service_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in ['venv', '__pycache__']):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in utility_patterns:
                        if pattern in content:
                            utility_files[pattern].append({
                                'service': service,
                                'file': str(py_file.relative_to(self.root_dir))
                            })
                            
                except:
                    pass
        
        # 여러 서비스에서 사용되는 유틸리티
        for pattern, locations in utility_files.items():
            services = set(loc['service'] for loc in locations)
            if len(services) > 1:
                self.duplicates['utility'].append({
                    'pattern': pattern,
                    'locations': locations,
                    'services': list(services)
                })
    
    def _find_config_duplicates(self):
        """설정 관련 중복 찾기"""
        print("\n⚙️  설정 관련 중복 검색...")
        
        config_patterns = [
            'JWT_SECRET', 'JWT_ALGORITHM', 'DATABASE_URL',
            'REDIS_URL', 'get_settings', 'Settings', 'Config',
            'load_config', 'get_env'
        ]
        
        config_files = defaultdict(list)
        
        for service in self.services:
            service_path = self.root_dir / service
            for py_file in service_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in ['venv', '__pycache__']):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in config_patterns:
                        if pattern in content:
                            config_files[pattern].append({
                                'service': service,
                                'file': str(py_file.relative_to(self.root_dir))
                            })
                            
                except:
                    pass
        
        # 여러 서비스에서 사용되는 설정
        for pattern, locations in config_files.items():
            services = set(loc['service'] for loc in locations)
            if len(services) > 1:
                self.duplicates['config'].append({
                    'pattern': pattern,
                    'locations': locations,
                    'services': list(services)
                })
    
    def _find_model_duplicates(self):
        """모델/스키마 중복 찾기"""
        print("\n📊 모델/스키마 중복 검색...")
        
        model_patterns = [
            'class User', 'class Token', 'class AuditLog',
            'class BaseModel', 'UserCreate', 'UserResponse',
            'TokenData', 'AuditEvent'
        ]
        
        model_files = defaultdict(list)
        
        for service in self.services:
            service_path = self.root_dir / service
            for py_file in service_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in ['venv', '__pycache__']):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in model_patterns:
                        if pattern in content:
                            model_files[pattern].append({
                                'service': service,
                                'file': str(py_file.relative_to(self.root_dir))
                            })
                            
                except:
                    pass
        
        # 여러 서비스에서 정의된 모델
        for pattern, locations in model_files.items():
            services = set(loc['service'] for loc in locations)
            if len(services) > 1:
                self.duplicates['models'].append({
                    'pattern': pattern,
                    'locations': locations,
                    'services': list(services)
                })
    
    def _print_report(self):
        """분석 결과 출력"""
        print("\n" + "="*80)
        print("📋 중복 코드 분석 결과")
        print("="*80)
        
        total_duplicates = 0
        
        # 각 카테고리별 결과
        categories = {
            'functions': '🔄 중복 함수',
            'jwt': '🔐 JWT 관련 중복',
            'audit': '📝 감사 로깅 중복',
            'utility': '🔧 유틸리티 중복',
            'config': '⚙️  설정 관련 중복',
            'models': '📊 모델/스키마 중복'
        }
        
        for category, title in categories.items():
            duplicates = self.duplicates[category]
            if duplicates:
                print(f"\n{title}: {len(duplicates)}개")
                total_duplicates += len(duplicates)
                
                for dup in duplicates[:5]:  # 상위 5개만 표시
                    if 'signature' in dup:
                        print(f"  - {dup['signature']}")
                    else:
                        print(f"  - {dup['pattern']}")
                    print(f"    서비스: {', '.join(dup['services'])}")
                    if len(duplicates) > 5:
                        print(f"    ... 외 {len(duplicates)-5}개")
                        break
        
        print(f"\n📊 총 중복 항목: {total_duplicates}개")
        
        # JSON 파일로 저장
        report = {
            'summary': {
                'total_duplicates': total_duplicates,
                'analyzed_services': self.services
            },
            'duplicates': dict(self.duplicates)
        }
        
        with open('duplicate_code_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        print("\n💾 상세 보고서 저장됨: duplicate_code_report.json")
        
        # 제거 권장사항
        print("\n💡 중복 제거 권장사항:")
        print("1. 공통 라이브러리 패키지 생성 (arrakis-common)")
        print("2. JWT 검증 로직을 공통 모듈로 추출")
        print("3. 감사 로깅 클라이언트 통합")
        print("4. 유틸리티 함수 중앙화")
        print("5. 공통 모델/스키마 정의")


if __name__ == "__main__":
    finder = DuplicateCodeFinder("/Users/isihyeon/Desktop/Arrakis-Project")
    finder.analyze_all_services()