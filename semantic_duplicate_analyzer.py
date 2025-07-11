#!/usr/bin/env python3
"""
시맨틱 중복 코드 분석기 - Ultra Deep Analysis
기능적으로, 맥락적으로 같은 역할을 하는 코드들을 찾아내는 심층 분석 도구

단순한 코드 중복이 아닌, 비즈니스 로직과 아키텍처 레벨에서의 의미적 중복을 탐지
"""

import os
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
from collections import defaultdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SemanticDuplicateAnalyzer:
    """의미적 중복 분석기"""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        
        # 기능별 패턴 저장소
        self.auth_patterns = defaultdict(list)          # 인증 관련 기능들
        self.validation_patterns = defaultdict(list)    # 검증 로직들
        self.database_patterns = defaultdict(list)      # 데이터베이스 연결/쿼리들
        self.api_patterns = defaultdict(list)           # API 엔드포인트 패턴들
        self.error_handling_patterns = defaultdict(list) # 에러 처리 패턴들
        self.config_patterns = defaultdict(list)        # 설정 관리 패턴들
        self.logging_patterns = defaultdict(list)       # 로깅 패턴들
        self.serialization_patterns = defaultdict(list) # 직렬화/역직렬화 패턴들
        self.business_logic_patterns = defaultdict(list) # 비즈니스 로직 패턴들
        self.integration_patterns = defaultdict(list)   # 외부 서비스 연동 패턴들
        
        # 아키텍처 레벨 패턴들
        self.service_patterns = defaultdict(list)       # 서비스 레이어 패턴들
        self.repository_patterns = defaultdict(list)    # 레포지토리 패턴들
        self.middleware_patterns = defaultdict(list)    # 미들웨어 패턴들
        self.model_patterns = defaultdict(list)         # 모델/스키마 패턴들
        
        # 데이터 플로우 패턴들
        self.transformation_patterns = defaultdict(list) # 데이터 변환 패턴들
        self.filtering_patterns = defaultdict(list)     # 데이터 필터링 패턴들
        self.aggregation_patterns = defaultdict(list)   # 데이터 집계 패턴들
        
    def analyze_codebase(self) -> Dict[str, Any]:
        """코드베이스 전체 의미적 분석"""
        logger.info("🧠 의미적 중복 분석 시작 - 심층 분석 모드")
        
        # 주요 서비스 디렉토리들
        service_dirs = [
            "user-service",
            "audit-service", 
            "ontology-management-service",
            "arrakis-common"
        ]
        
        all_files = []
        for service_dir in service_dirs:
            service_path = self.root_dir / service_dir
            if service_path.exists():
                for py_file in service_path.rglob("*.py"):
                    if self._is_relevant_file(py_file):
                        all_files.append(py_file)
        
        # 루트의 중요한 파일들도 포함
        for py_file in self.root_dir.glob("*.py"):
            if self._is_relevant_file(py_file):
                all_files.append(py_file)
        
        logger.info(f"📁 {len(all_files)}개 핵심 파일 분석")
        
        # 각 파일의 의미적 패턴 분석
        for file_path in all_files:
            self._analyze_file_semantics(file_path)
        
        # 의미적 중복 탐지
        semantic_duplicates = self._detect_semantic_duplicates()
        
        return semantic_duplicates
    
    def _is_relevant_file(self, file_path: Path) -> bool:
        """분석 대상 파일인지 확인"""
        # 제외할 패턴들
        exclude_patterns = [
            '__pycache__',
            '.git',
            'venv',
            'env',
            '.pytest_cache',
            'migrations',
            '__init__.py',
            'test_',  # 테스트 파일은 일단 제외
            '.pyc'
        ]
        
        file_str = str(file_path)
        return not any(pattern in file_str for pattern in exclude_patterns)
    
    def _analyze_file_semantics(self, file_path: Path):
        """파일의 의미적 패턴 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # 파일 컨텍스트 분석
            file_context = self._analyze_file_context(file_path, content)
            
            # AST 순회하며 의미적 패턴 추출
            for node in ast.walk(tree):
                self._extract_semantic_patterns(node, file_path, content, file_context)
                
        except Exception as e:
            logger.debug(f"파일 분석 건너뜀 {file_path}: {e}")
    
    def _analyze_file_context(self, file_path: Path, content: str) -> Dict[str, Any]:
        """파일의 전체적인 컨텍스트 분석"""
        context = {
            'file_path': str(file_path),
            'is_service': 'service' in str(file_path).lower(),
            'is_repository': 'repository' in str(file_path).lower() or 'repo' in str(file_path).lower(),
            'is_model': 'model' in str(file_path).lower() or 'schema' in str(file_path).lower(),
            'is_api': 'api' in str(file_path).lower() or 'route' in str(file_path).lower(),
            'is_middleware': 'middleware' in str(file_path).lower(),
            'is_config': 'config' in str(file_path).lower() or 'setting' in str(file_path).lower(),
            'is_auth': 'auth' in str(file_path).lower() or 'jwt' in str(file_path).lower(),
            'is_audit': 'audit' in str(file_path).lower(),
            'service_type': self._determine_service_type(file_path),
            'imports': self._extract_imports(content),
            'external_dependencies': self._extract_external_dependencies(content)
        }
        
        return context
    
    def _determine_service_type(self, file_path: Path) -> str:
        """서비스 타입 결정"""
        path_str = str(file_path).lower()
        
        if 'user-service' in path_str or 'user_service' in path_str:
            return 'user_service'
        elif 'audit-service' in path_str or 'audit_service' in path_str:
            return 'audit_service'
        elif 'ontology' in path_str or 'oms' in path_str:
            return 'ontology_service'
        elif 'arrakis-common' in path_str:
            return 'common_library'
        else:
            return 'unknown'
    
    def _extract_imports(self, content: str) -> List[str]:
        """중요한 import들 추출"""
        important_imports = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # 외부 라이브러리들 식별
                if any(lib in line for lib in ['fastapi', 'sqlalchemy', 'jwt', 'bcrypt', 'redis', 'httpx', 'pydantic']):
                    important_imports.append(line)
        
        return important_imports
    
    def _extract_external_dependencies(self, content: str) -> List[str]:
        """외부 의존성 패턴 추출"""
        dependencies = []
        
        # 데이터베이스 연결 패턴
        if re.search(r'database|db|Database|DB', content):
            dependencies.append('database')
        
        # Redis 사용 패턴
        if re.search(r'redis|Redis', content):
            dependencies.append('redis')
        
        # HTTP 클라이언트 패턴
        if re.search(r'httpx|requests|aiohttp', content):
            dependencies.append('http_client')
        
        # JWT 관련 패턴
        if re.search(r'jwt|JWT|token|Token', content):
            dependencies.append('jwt')
        
        return dependencies
    
    def _extract_semantic_patterns(self, node: ast.AST, file_path: Path, content: str, file_context: Dict[str, Any]):
        """의미적 패턴 추출"""
        
        if isinstance(node, ast.FunctionDef):
            self._analyze_function_semantics(node, file_path, content, file_context)
        elif isinstance(node, ast.ClassDef):
            self._analyze_class_semantics(node, file_path, content, file_context)
        elif isinstance(node, ast.Assign):
            self._analyze_assignment_semantics(node, file_path, content, file_context)
    
    def _analyze_function_semantics(self, node: ast.FunctionDef, file_path: Path, content: str, file_context: Dict[str, Any]):
        """함수의 의미적 역할 분석"""
        func_name = node.name.lower()
        
        # 함수 본문에서 주요 패턴들 추출
        func_lines = content.split('\n')[node.lineno-1:node.end_lineno if hasattr(node, 'end_lineno') else node.lineno+10]
        func_content = '\n'.join(func_lines)
        
        func_info = {
            'name': node.name,
            'file': str(file_path),
            'service_type': file_context['service_type'],
            'line_start': node.lineno,
            'args': [arg.arg for arg in node.args.args],
            'content_snippet': func_content[:200] + '...' if len(func_content) > 200 else func_content,
            'semantic_role': self._determine_function_role(func_name, func_content),
            'business_domain': self._determine_business_domain(func_name, func_content),
            'data_operations': self._extract_data_operations(func_content),
            'external_calls': self._extract_external_calls(func_content)
        }
        
        # 의미적 카테고리별로 분류
        self._categorize_function_semantically(func_info, func_content)
    
    def _determine_function_role(self, func_name: str, func_content: str) -> str:
        """함수의 의미적 역할 결정"""
        
        # 인증 관련
        if any(keyword in func_name for keyword in ['auth', 'login', 'logout', 'verify', 'validate', 'token', 'jwt']):
            if 'password' in func_content.lower() or 'credential' in func_content.lower():
                return 'authentication'
            elif 'token' in func_content.lower() or 'jwt' in func_content.lower():
                return 'token_management'
            else:
                return 'authorization'
        
        # 데이터 CRUD
        if any(keyword in func_name for keyword in ['create', 'insert', 'add', 'save']):
            return 'data_creation'
        elif any(keyword in func_name for keyword in ['get', 'find', 'fetch', 'retrieve', 'select', 'query']):
            return 'data_retrieval'
        elif any(keyword in func_name for keyword in ['update', 'modify', 'edit', 'change']):
            return 'data_modification'
        elif any(keyword in func_name for keyword in ['delete', 'remove', 'destroy']):
            return 'data_deletion'
        
        # 검증 관련
        if any(keyword in func_name for keyword in ['validate', 'check', 'verify', 'ensure']):
            return 'validation'
        
        # 변환 관련
        if any(keyword in func_name for keyword in ['convert', 'transform', 'format', 'serialize', 'deserialize']):
            return 'data_transformation'
        
        # 비즈니스 로직
        if any(keyword in func_name for keyword in ['process', 'handle', 'execute', 'perform']):
            return 'business_logic'
        
        # 외부 연동
        if any(keyword in func_name for keyword in ['call', 'request', 'send', 'fetch', 'client']):
            return 'external_integration'
        
        # 설정 관련
        if any(keyword in func_name for keyword in ['config', 'setup', 'init', 'configure']):
            return 'configuration'
        
        return 'unknown'
    
    def _determine_business_domain(self, func_name: str, func_content: str) -> str:
        """비즈니스 도메인 결정"""
        content_lower = func_content.lower()
        func_name_lower = func_name.lower()
        
        # 사용자 관리
        if any(keyword in func_name_lower or keyword in content_lower 
               for keyword in ['user', 'account', 'profile', 'member']):
            return 'user_management'
        
        # 인증/보안
        if any(keyword in func_name_lower or keyword in content_lower 
               for keyword in ['auth', 'security', 'permission', 'role', 'jwt', 'token']):
            return 'authentication_security'
        
        # 감사/로깅
        if any(keyword in func_name_lower or keyword in content_lower 
               for keyword in ['audit', 'log', 'event', 'tracking']):
            return 'audit_logging'
        
        # 온톨로지/스키마
        if any(keyword in func_name_lower or keyword in content_lower 
               for keyword in ['schema', 'ontology', 'branch', 'document', 'property']):
            return 'ontology_management'
        
        # 데이터베이스
        if any(keyword in func_name_lower or keyword in content_lower 
               for keyword in ['database', 'query', 'transaction', 'connection']):
            return 'database_operations'
        
        return 'general'
    
    def _extract_data_operations(self, func_content: str) -> List[str]:
        """데이터 조작 패턴 추출"""
        operations = []
        content_lower = func_content.lower()
        
        # SQL 패턴
        if re.search(r'select|insert|update|delete|create table', content_lower):
            operations.append('sql_operations')
        
        # ORM 패턴
        if re.search(r'\.query\(|\.filter\(|\.join\(|\.add\(|\.commit\(', content_lower):
            operations.append('orm_operations')
        
        # JSON 처리
        if re.search(r'json\.|\.json\(|json\.loads|json\.dumps', content_lower):
            operations.append('json_processing')
        
        # 검증 패턴
        if re.search(r'validate|check|verify|assert', content_lower):
            operations.append('validation')
        
        # 변환 패턴
        if re.search(r'convert|transform|serialize|deserialize|format', content_lower):
            operations.append('transformation')
        
        return operations
    
    def _extract_external_calls(self, func_content: str) -> List[str]:
        """외부 호출 패턴 추출"""
        external_calls = []
        content_lower = func_content.lower()
        
        # HTTP 호출
        if re.search(r'httpx\.|requests\.|\.get\(|\.post\(|\.put\(|\.delete\(', content_lower):
            external_calls.append('http_calls')
        
        # 데이터베이스 호출
        if re.search(r'session\.|db\.|database\.|connection\.', content_lower):
            external_calls.append('database_calls')
        
        # Redis 호출
        if re.search(r'redis\.|cache\.|\.set\(|\.get\(.*redis', content_lower):
            external_calls.append('cache_calls')
        
        # TerminusDB 호출
        if re.search(r'terminusdb|terminus', content_lower):
            external_calls.append('terminusdb_calls')
        
        return external_calls
    
    def _categorize_function_semantically(self, func_info: Dict[str, Any], func_content: str):
        """함수를 의미적 카테고리에 분류"""
        role = func_info['semantic_role']
        domain = func_info['business_domain']
        
        # 역할별 카테고리
        if role == 'authentication':
            self.auth_patterns['authentication'].append(func_info)
        elif role == 'token_management':
            self.auth_patterns['token_management'].append(func_info)
        elif role == 'authorization':
            self.auth_patterns['authorization'].append(func_info)
        elif role == 'validation':
            self.validation_patterns[domain].append(func_info)
        elif role in ['data_creation', 'data_retrieval', 'data_modification', 'data_deletion']:
            self.database_patterns[role].append(func_info)
        elif role == 'data_transformation':
            self.transformation_patterns[domain].append(func_info)
        elif role == 'business_logic':
            self.business_logic_patterns[domain].append(func_info)
        elif role == 'external_integration':
            self.integration_patterns[domain].append(func_info)
        elif role == 'configuration':
            self.config_patterns[domain].append(func_info)
        
        # 특별한 패턴들
        if 'error' in func_content.lower() or 'exception' in func_content.lower():
            self.error_handling_patterns[domain].append(func_info)
        
        if 'log' in func_content.lower() or 'logger' in func_content.lower():
            self.logging_patterns[domain].append(func_info)
    
    def _analyze_class_semantics(self, node: ast.ClassDef, file_path: Path, content: str, file_context: Dict[str, Any]):
        """클래스의 의미적 역할 분석"""
        class_name = node.name.lower()
        
        class_info = {
            'name': node.name,
            'file': str(file_path),
            'service_type': file_context['service_type'],
            'methods': [method.name for method in node.body if isinstance(method, ast.FunctionDef)],
            'bases': [self._get_base_name(base) for base in node.bases],
            'semantic_role': self._determine_class_role(class_name, node),
            'business_domain': self._determine_business_domain(class_name, content)
        }
        
        # 클래스 역할별 분류
        role = class_info['semantic_role']
        if role == 'service':
            self.service_patterns[class_info['business_domain']].append(class_info)
        elif role == 'repository':
            self.repository_patterns[class_info['business_domain']].append(class_info)
        elif role == 'model':
            self.model_patterns[class_info['business_domain']].append(class_info)
        elif role == 'middleware':
            self.middleware_patterns[class_info['business_domain']].append(class_info)
    
    def _determine_class_role(self, class_name: str, node: ast.ClassDef) -> str:
        """클래스의 의미적 역할 결정"""
        
        # 서비스 클래스
        if 'service' in class_name:
            return 'service'
        
        # 레포지토리 클래스
        if any(keyword in class_name for keyword in ['repository', 'repo', 'dao']):
            return 'repository'
        
        # 모델 클래스
        if any(keyword in class_name for keyword in ['model', 'schema', 'entity']):
            return 'model'
        
        # 미들웨어 클래스
        if 'middleware' in class_name:
            return 'middleware'
        
        # 클라이언트 클래스
        if 'client' in class_name:
            return 'client'
        
        # 핸들러 클래스
        if 'handler' in class_name:
            return 'handler'
        
        # 메서드 이름으로 추론
        methods = [method.name for method in node.body if isinstance(method, ast.FunctionDef)]
        
        # CRUD 메서드가 많으면 레포지토리
        crud_methods = sum(1 for method in methods if any(crud in method.lower() 
                          for crud in ['create', 'read', 'update', 'delete', 'find', 'get', 'save']))
        if crud_methods >= 2:
            return 'repository'
        
        # 비즈니스 메서드가 많으면 서비스
        business_methods = sum(1 for method in methods if any(biz in method.lower() 
                              for biz in ['process', 'handle', 'execute', 'perform', 'manage']))
        if business_methods >= 2:
            return 'service'
        
        return 'unknown'
    
    def _get_base_name(self, node: ast.AST) -> str:
        """베이스 클래스 이름 추출"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_base_name(node.value)}.{node.attr}"
        return 'unknown'
    
    def _analyze_assignment_semantics(self, node: ast.Assign, file_path: Path, content: str, file_context: Dict[str, Any]):
        """변수 할당의 의미적 패턴 분석"""
        # 설정 변수들 분석
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if self._is_config_variable(var_name):
                    config_info = {
                        'name': var_name,
                        'file': str(file_path),
                        'service_type': file_context['service_type'],
                        'config_type': self._determine_config_type(var_name)
                    }
                    self.config_patterns[config_info['config_type']].append(config_info)
    
    def _is_config_variable(self, var_name: str) -> bool:
        """설정 변수인지 확인"""
        config_patterns = [
            'URL', 'HOST', 'PORT', 'KEY', 'SECRET', 'TOKEN', 'DATABASE', 
            'REDIS', 'CONFIG', 'SETTING', 'ENDPOINT', 'API_KEY'
        ]
        return any(pattern in var_name.upper() for pattern in config_patterns)
    
    def _determine_config_type(self, var_name: str) -> str:
        """설정 타입 결정"""
        var_upper = var_name.upper()
        
        if 'DATABASE' in var_upper or 'DB' in var_upper:
            return 'database_config'
        elif 'JWT' in var_upper or 'TOKEN' in var_upper:
            return 'auth_config'
        elif 'REDIS' in var_upper:
            return 'cache_config'
        elif 'URL' in var_upper or 'ENDPOINT' in var_upper:
            return 'service_config'
        else:
            return 'general_config'
    
    def _detect_semantic_duplicates(self) -> Dict[str, Any]:
        """의미적 중복 탐지"""
        logger.info("🔍 의미적 중복 패턴 탐지 중...")
        
        duplicates = {
            'authentication_duplicates': self._find_auth_duplicates(),
            'data_access_duplicates': self._find_data_access_duplicates(),
            'validation_duplicates': self._find_validation_duplicates(),
            'business_logic_duplicates': self._find_business_logic_duplicates(),
            'configuration_duplicates': self._find_config_duplicates(),
            'integration_duplicates': self._find_integration_duplicates(),
            'error_handling_duplicates': self._find_error_handling_duplicates(),
            'service_layer_duplicates': self._find_service_layer_duplicates(),
            'model_duplicates': self._find_model_duplicates(),
            'transformation_duplicates': self._find_transformation_duplicates()
        }
        
        return duplicates
    
    def _find_auth_duplicates(self) -> List[Dict[str, Any]]:
        """인증 관련 중복 찾기"""
        duplicates = []
        
        # 토큰 관리 중복
        if len(self.auth_patterns['token_management']) > 1:
            duplicates.append({
                'type': 'token_management',
                'description': '토큰 관리 로직이 여러 곳에서 구현됨',
                'severity': 'high',
                'functions': self.auth_patterns['token_management'],
                'recommendation': 'arrakis-common의 JWT 핸들러로 통합'
            })
        
        # 인증 로직 중복
        if len(self.auth_patterns['authentication']) > 1:
            services = set(func['service_type'] for func in self.auth_patterns['authentication'])
            if len(services) > 1:
                duplicates.append({
                    'type': 'authentication_logic',
                    'description': '인증 로직이 여러 서비스에서 중복 구현됨',
                    'severity': 'high',
                    'functions': self.auth_patterns['authentication'],
                    'affected_services': list(services),
                    'recommendation': '중앙화된 인증 서비스 또는 공통 미들웨어 사용'
                })
        
        return duplicates
    
    def _find_data_access_duplicates(self) -> List[Dict[str, Any]]:
        """데이터 접근 중복 찾기"""
        duplicates = []
        
        for operation_type in ['data_creation', 'data_retrieval', 'data_modification', 'data_deletion']:
            if len(self.database_patterns[operation_type]) > 1:
                # 같은 비즈니스 도메인에서 중복되는지 확인
                domain_groups = defaultdict(list)
                for func in self.database_patterns[operation_type]:
                    domain_groups[func['business_domain']].append(func)
                
                for domain, funcs in domain_groups.items():
                    if len(funcs) > 1:
                        services = set(func['service_type'] for func in funcs)
                        if len(services) > 1:
                            duplicates.append({
                                'type': f'{operation_type}_duplication',
                                'description': f'{domain} 도메인의 {operation_type} 로직이 여러 서비스에서 구현됨',
                                'severity': 'medium',
                                'functions': funcs,
                                'business_domain': domain,
                                'affected_services': list(services),
                                'recommendation': f'{domain} 전용 레포지토리 또는 서비스 레이어 생성'
                            })
        
        return duplicates
    
    def _find_validation_duplicates(self) -> List[Dict[str, Any]]:
        """검증 로직 중복 찾기"""
        duplicates = []
        
        for domain, validators in self.validation_patterns.items():
            if len(validators) > 1:
                services = set(validator['service_type'] for validator in validators)
                if len(services) > 1:
                    duplicates.append({
                        'type': 'validation_logic_duplication',
                        'description': f'{domain} 도메인의 검증 로직이 여러 서비스에서 중복됨',
                        'severity': 'medium',
                        'functions': validators,
                        'business_domain': domain,
                        'affected_services': list(services),
                        'recommendation': f'arrakis-common에 {domain} 검증 모듈 추가'
                    })
        
        return duplicates
    
    def _find_business_logic_duplicates(self) -> List[Dict[str, Any]]:
        """비즈니스 로직 중복 찾기"""
        duplicates = []
        
        for domain, logic_funcs in self.business_logic_patterns.items():
            if len(logic_funcs) > 1:
                # 함수명 유사성 체크
                name_groups = defaultdict(list)
                for func in logic_funcs:
                    # 함수명의 핵심 키워드 추출
                    name_keywords = set(re.findall(r'[a-z]+', func['name'].lower()))
                    key = frozenset(name_keywords)
                    name_groups[key].append(func)
                
                for keyword_set, funcs in name_groups.items():
                    if len(funcs) > 1:
                        services = set(func['service_type'] for func in funcs)
                        if len(services) > 1:
                            duplicates.append({
                                'type': 'business_logic_duplication',
                                'description': f'{domain} 도메인의 비즈니스 로직이 여러 서비스에서 중복됨',
                                'severity': 'high',
                                'functions': funcs,
                                'business_domain': domain,
                                'similar_function_names': [func['name'] for func in funcs],
                                'affected_services': list(services),
                                'recommendation': f'{domain} 도메인 서비스 레이어 통합 또는 공통 라이브러리화'
                            })
        
        return duplicates
    
    def _find_config_duplicates(self) -> List[Dict[str, Any]]:
        """설정 관련 중복 찾기"""
        duplicates = []
        
        for config_type, configs in self.config_patterns.items():
            if len(configs) > 1:
                services = set(config['service_type'] for config in configs)
                if len(services) > 1:
                    duplicates.append({
                        'type': 'configuration_duplication',
                        'description': f'{config_type} 설정이 여러 서비스에서 중복됨',
                        'severity': 'low',
                        'configurations': configs,
                        'config_type': config_type,
                        'affected_services': list(services),
                        'recommendation': 'arrakis-common에 통합 설정 관리자 생성'
                    })
        
        return duplicates
    
    def _find_integration_duplicates(self) -> List[Dict[str, Any]]:
        """외부 연동 중복 찾기"""
        duplicates = []
        
        for domain, integrations in self.integration_patterns.items():
            if len(integrations) > 1:
                services = set(integ['service_type'] for integ in integrations)
                if len(services) > 1:
                    duplicates.append({
                        'type': 'external_integration_duplication',
                        'description': f'{domain} 도메인의 외부 연동 로직이 여러 서비스에서 중복됨',
                        'severity': 'medium',
                        'functions': integrations,
                        'business_domain': domain,
                        'affected_services': list(services),
                        'recommendation': f'{domain} 전용 클라이언트 라이브러리 생성'
                    })
        
        return duplicates
    
    def _find_error_handling_duplicates(self) -> List[Dict[str, Any]]:
        """에러 처리 중복 찾기"""
        duplicates = []
        
        for domain, error_handlers in self.error_handling_patterns.items():
            if len(error_handlers) > 1:
                services = set(handler['service_type'] for handler in error_handlers)
                if len(services) > 1:
                    duplicates.append({
                        'type': 'error_handling_duplication',
                        'description': f'{domain} 도메인의 에러 처리 로직이 여러 서비스에서 중복됨',
                        'severity': 'medium',
                        'functions': error_handlers,
                        'business_domain': domain,
                        'affected_services': list(services),
                        'recommendation': 'arrakis-common에 표준화된 에러 처리 모듈 추가'
                    })
        
        return duplicates
    
    def _find_service_layer_duplicates(self) -> List[Dict[str, Any]]:
        """서비스 레이어 중복 찾기"""
        duplicates = []
        
        for domain, services in self.service_patterns.items():
            if len(services) > 1:
                service_types = set(service['service_type'] for service in services)
                if len(service_types) > 1:
                    duplicates.append({
                        'type': 'service_layer_duplication',
                        'description': f'{domain} 도메인의 서비스 레이어가 여러 서비스에서 중복됨',
                        'severity': 'high',
                        'classes': services,
                        'business_domain': domain,
                        'affected_services': list(service_types),
                        'recommendation': f'{domain} 도메인 전용 마이크로서비스로 분리 또는 통합'
                    })
        
        return duplicates
    
    def _find_model_duplicates(self) -> List[Dict[str, Any]]:
        """모델 중복 찾기"""
        duplicates = []
        
        for domain, models in self.model_patterns.items():
            if len(models) > 1:
                # 모델명 유사성 체크
                model_names = [model['name'].lower() for model in models]
                name_similarities = defaultdict(list)
                
                for model in models:
                    base_name = re.sub(r'(model|schema|entity|dto)$', '', model['name'].lower())
                    name_similarities[base_name].append(model)
                
                for base_name, similar_models in name_similarities.items():
                    if len(similar_models) > 1:
                        services = set(model['service_type'] for model in similar_models)
                        if len(services) > 1:
                            duplicates.append({
                                'type': 'model_duplication',
                                'description': f'{domain} 도메인의 {base_name} 모델이 여러 서비스에서 중복됨',
                                'severity': 'medium',
                                'classes': similar_models,
                                'business_domain': domain,
                                'base_model_name': base_name,
                                'affected_services': list(services),
                                'recommendation': f'arrakis-common에 {base_name} 공통 모델 정의'
                            })
        
        return duplicates
    
    def _find_transformation_duplicates(self) -> List[Dict[str, Any]]:
        """데이터 변환 중복 찾기"""
        duplicates = []
        
        for domain, transformations in self.transformation_patterns.items():
            if len(transformations) > 1:
                services = set(trans['service_type'] for trans in transformations)
                if len(services) > 1:
                    duplicates.append({
                        'type': 'data_transformation_duplication',
                        'description': f'{domain} 도메인의 데이터 변환 로직이 여러 서비스에서 중복됨',
                        'severity': 'medium',
                        'functions': transformations,
                        'business_domain': domain,
                        'affected_services': list(services),
                        'recommendation': f'arrakis-common에 {domain} 데이터 변환 유틸리티 추가'
                    })
        
        return duplicates
    
    def generate_comprehensive_report(self, semantic_duplicates: Dict[str, Any]) -> Dict[str, Any]:
        """포괄적 분석 보고서 생성"""
        total_duplicates = sum(len(category) for category in semantic_duplicates.values())
        
        # 심각도별 분류
        high_severity = []
        medium_severity = []
        low_severity = []
        
        for category_name, duplicates in semantic_duplicates.items():
            for duplicate in duplicates:
                if duplicate.get('severity') == 'high':
                    high_severity.append(duplicate)
                elif duplicate.get('severity') == 'medium':
                    medium_severity.append(duplicate)
                else:
                    low_severity.append(duplicate)
        
        # 영향받는 서비스 분석
        affected_services = set()
        for category in semantic_duplicates.values():
            for duplicate in category:
                if 'affected_services' in duplicate:
                    affected_services.update(duplicate['affected_services'])
        
        report = {
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'analysis_type': 'semantic_duplicate_detection',
            'summary': {
                'total_semantic_duplicates': total_duplicates,
                'high_severity_issues': len(high_severity),
                'medium_severity_issues': len(medium_severity),
                'low_severity_issues': len(low_severity),
                'affected_services': list(affected_services),
                'most_problematic_areas': self._identify_problematic_areas(semantic_duplicates)
            },
            'detailed_analysis': semantic_duplicates,
            'priority_recommendations': self._generate_priority_recommendations(high_severity, medium_severity),
            'architectural_insights': self._generate_architectural_insights(semantic_duplicates),
            'refactoring_roadmap': self._generate_refactoring_roadmap(semantic_duplicates)
        }
        
        return report
    
    def _identify_problematic_areas(self, semantic_duplicates: Dict[str, Any]) -> List[Dict[str, Any]]:
        """가장 문제가 되는 영역 식별"""
        problem_areas = []
        
        for category_name, duplicates in semantic_duplicates.items():
            if duplicates:
                high_severity_count = sum(1 for dup in duplicates if dup.get('severity') == 'high')
                if high_severity_count > 0:
                    problem_areas.append({
                        'area': category_name,
                        'high_severity_count': high_severity_count,
                        'total_duplicates': len(duplicates)
                    })
        
        # 심각도 순으로 정렬
        problem_areas.sort(key=lambda x: x['high_severity_count'], reverse=True)
        return problem_areas[:5]  # 상위 5개
    
    def _generate_priority_recommendations(self, high_severity: List, medium_severity: List) -> List[str]:
        """우선순위 권장사항 생성"""
        recommendations = []
        
        # 고심각도 이슈 기반 권장사항
        auth_issues = [issue for issue in high_severity if 'auth' in issue['type']]
        if auth_issues:
            recommendations.append("🔴 [최우선] 인증/권한 로직을 arrakis-common으로 통합하여 보안 일관성 확보")
        
        business_logic_issues = [issue for issue in high_severity if 'business_logic' in issue['type']]
        if business_logic_issues:
            recommendations.append("🔴 [최우선] 중복된 비즈니스 로직을 도메인별 서비스로 분리 또는 통합")
        
        service_layer_issues = [issue for issue in high_severity if 'service_layer' in issue['type']]
        if service_layer_issues:
            recommendations.append("🔴 [최우선] 서비스 레이어 아키텍처 재설계 - 도메인 경계 명확화")
        
        # 중간심각도 이슈 기반 권장사항
        data_issues = [issue for issue in medium_severity if 'data' in issue['type']]
        if data_issues:
            recommendations.append("🟡 [중간] 데이터 접근 레이어 표준화 - Repository 패턴 적용")
        
        validation_issues = [issue for issue in medium_severity if 'validation' in issue['type']]
        if validation_issues:
            recommendations.append("🟡 [중간] 검증 로직을 arrakis-common 유틸리티로 표준화")
        
        return recommendations
    
    def _generate_architectural_insights(self, semantic_duplicates: Dict[str, Any]) -> List[str]:
        """아키텍처 인사이트 생성"""
        insights = []
        
        # 서비스 경계 문제
        service_boundary_issues = []
        for category in semantic_duplicates.values():
            for duplicate in category:
                if duplicate.get('severity') == 'high' and len(duplicate.get('affected_services', [])) > 1:
                    service_boundary_issues.append(duplicate)
        
        if service_boundary_issues:
            insights.append("⚠️ 서비스 경계가 불분명하여 비즈니스 로직이 여러 서비스에 분산됨")
        
        # 공통 라이브러리 부족
        common_lib_needs = []
        for category in semantic_duplicates.values():
            for duplicate in category:
                if 'arrakis-common' in duplicate.get('recommendation', ''):
                    common_lib_needs.append(duplicate)
        
        if len(common_lib_needs) > 3:
            insights.append("📚 arrakis-common 라이브러리가 충분히 활용되지 않아 중복 코드 발생")
        
        # 도메인 분리 필요성
        domain_separation_needs = set()
        for category in semantic_duplicates.values():
            for duplicate in category:
                if duplicate.get('business_domain') and duplicate.get('business_domain') != 'general':
                    domain_separation_needs.add(duplicate['business_domain'])
        
        if len(domain_separation_needs) > 2:
            insights.append(f"🏗️ {', '.join(domain_separation_needs)} 도메인들의 명확한 분리가 필요")
        
        return insights
    
    def _generate_refactoring_roadmap(self, semantic_duplicates: Dict[str, Any]) -> List[Dict[str, Any]]:
        """리팩토링 로드맵 생성"""
        roadmap = []
        
        # Phase 1: 보안 및 인증 통합
        auth_duplicates = semantic_duplicates.get('authentication_duplicates', [])
        if auth_duplicates:
            roadmap.append({
                'phase': 1,
                'title': '인증/보안 시스템 통합',
                'priority': 'high',
                'estimated_effort': 'high',
                'tasks': [
                    'arrakis-common JWT 핸들러 확장',
                    '모든 서비스의 인증 미들웨어 표준화',
                    '중앙화된 권한 관리 시스템 구축'
                ],
                'affected_duplicates': len(auth_duplicates)
            })
        
        # Phase 2: 데이터 접근 레이어 표준화
        data_duplicates = semantic_duplicates.get('data_access_duplicates', [])
        if data_duplicates:
            roadmap.append({
                'phase': 2,
                'title': '데이터 접근 레이어 표준화',
                'priority': 'medium',
                'estimated_effort': 'medium',
                'tasks': [
                    'Repository 패턴 표준화',
                    '공통 데이터 접근 인터페이스 정의',
                    'ORM 사용 패턴 통일'
                ],
                'affected_duplicates': len(data_duplicates)
            })
        
        # Phase 3: 비즈니스 로직 도메인별 분리
        business_duplicates = semantic_duplicates.get('business_logic_duplicates', [])
        if business_duplicates:
            roadmap.append({
                'phase': 3,
                'title': '비즈니스 로직 도메인 분리',
                'priority': 'high',
                'estimated_effort': 'high',
                'tasks': [
                    '도메인별 서비스 경계 재정의',
                    '중복 비즈니스 로직 통합',
                    '도메인 이벤트 기반 통신 구현'
                ],
                'affected_duplicates': len(business_duplicates)
            })
        
        return roadmap


def main():
    """메인 실행 함수"""
    analyzer = SemanticDuplicateAnalyzer("/Users/isihyeon/Desktop/Arrakis-Project")
    
    logger.info("🧠 의미적 중복 분석 시작 - Ultra Deep Analysis")
    logger.info("=" * 80)
    
    semantic_duplicates = analyzer.analyze_codebase()
    report = analyzer.generate_comprehensive_report(semantic_duplicates)
    
    # 결과 요약 출력
    logger.info(f"📊 의미적 중복 분석 완료")
    logger.info(f"🔍 총 {report['summary']['total_semantic_duplicates']}개 의미적 중복 발견")
    logger.info(f"🔴 고심각도: {report['summary']['high_severity_issues']}개")
    logger.info(f"🟡 중간심각도: {report['summary']['medium_severity_issues']}개")
    logger.info(f"🟢 저심각도: {report['summary']['low_severity_issues']}개")
    
    if report['summary']['most_problematic_areas']:
        logger.warning("⚠️  가장 문제가 되는 영역들:")
        for area in report['summary']['most_problematic_areas']:
            logger.warning(f"  - {area['area']}: 고심각도 {area['high_severity_count']}개")
    
    if report['priority_recommendations']:
        logger.info("💡 우선순위 권장사항:")
        for rec in report['priority_recommendations']:
            logger.info(f"  {rec}")
    
    # 상세 보고서 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"semantic_duplicate_analysis_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 상세 의미적 분석 보고서 저장: {report_file}")
    
    if report['summary']['total_semantic_duplicates'] == 0:
        logger.info("🎉 의미적 중복 없음! 아키텍처가 최적화되어 있습니다.")
    else:
        logger.warning(f"🔧 {report['summary']['total_semantic_duplicates']}개 의미적 중복 해결 필요")
    
    return report


if __name__ == "__main__":
    main()