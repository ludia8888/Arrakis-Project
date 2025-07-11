#!/usr/bin/env python3
"""
포괄적 중복 코드 탐지기 - 새로 생성된 코드 포함
MSA 전체 시스템의 모든 중복을 찾아내는 강화된 분석 도구
"""

import os
import sys
import ast
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdvancedDuplicateDetector:
    """고급 중복 코드 탐지기"""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.services = [
            "user-service",
            "audit-service", 
            "ontology-management-service",
            "arrakis-common"
        ]
        
        # 중복 저장소들
        self.function_hashes = defaultdict(list)  # 함수 시그니처 해시
        self.code_blocks = defaultdict(list)      # 코드 블록 해시
        self.import_patterns = defaultdict(list)  # import 패턴
        self.class_signatures = defaultdict(list) # 클래스 시그니처
        self.variable_patterns = defaultdict(list) # 변수 패턴
        self.decorator_patterns = defaultdict(list) # 데코레이터 패턴
        self.config_patterns = defaultdict(list)   # 설정 패턴
        self.api_endpoint_patterns = defaultdict(list) # API 엔드포인트 패턴
        self.database_patterns = defaultdict(list) # 데이터베이스 패턴
        self.auth_patterns = defaultdict(list)     # 인증 관련 패턴
        self.validation_patterns = defaultdict(list) # 검증 로직 패턴
        self.utility_patterns = defaultdict(list)  # 유틸리티 함수 패턴
        
        # 새로 생성된 파일들도 포함
        self.additional_files = []
        self._find_all_python_files()
        
    def _find_all_python_files(self):
        """모든 Python 파일 찾기"""
        logger.info("🔍 모든 Python 파일 검색 중...")
        
        # 서비스 디렉토리 외의 Python 파일들
        for file_path in self.root_dir.rglob("*.py"):
            if not any(service in str(file_path) for service in self.services):
                # 숨김 파일이나 __pycache__ 제외
                if not any(part.startswith('.') or part == '__pycache__' for part in file_path.parts):
                    self.additional_files.append(file_path)
        
        logger.info(f"📁 추가 Python 파일 {len(self.additional_files)}개 발견")
        
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """파일 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analysis = {
                'file_path': str(file_path),
                'functions': [],
                'classes': [],
                'imports': [],
                'decorators': [],
                'api_endpoints': [],
                'config_vars': [],
                'auth_patterns': [],
                'validation_patterns': [],
                'utility_patterns': []
            }
            
            for node in ast.walk(tree):
                self._analyze_node(node, analysis, content)
                
            return analysis
            
        except Exception as e:
            logger.warning(f"파일 분석 실패 {file_path}: {e}")
            return {'file_path': str(file_path), 'error': str(e)}
    
    def _analyze_node(self, node: ast.AST, analysis: Dict, content: str):
        """AST 노드 분석"""
        
        # 함수 분석
        if isinstance(node, ast.FunctionDef):
            func_info = self._analyze_function(node, content)
            analysis['functions'].append(func_info)
            
            # 특별한 패턴 탐지
            if self._is_auth_function(node):
                analysis['auth_patterns'].append(func_info)
            if self._is_validation_function(node):
                analysis['validation_patterns'].append(func_info)
            if self._is_utility_function(node):
                analysis['utility_patterns'].append(func_info)
                
        # 클래스 분석
        elif isinstance(node, ast.ClassDef):
            class_info = self._analyze_class(node, content)
            analysis['classes'].append(class_info)
            
        # Import 분석
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            import_info = self._analyze_import(node)
            analysis['imports'].append(import_info)
            
        # 데코레이터 분석
        elif isinstance(node, ast.FunctionDef) and node.decorator_list:
            for decorator in node.decorator_list:
                decorator_info = self._analyze_decorator(decorator)
                analysis['decorators'].append(decorator_info)
                
                # API 엔드포인트 탐지
                if self._is_api_decorator(decorator):
                    endpoint_info = self._extract_api_endpoint(node, decorator)
                    analysis['api_endpoints'].append(endpoint_info)
        
        # 변수 할당 (설정 패턴)
        elif isinstance(node, ast.Assign):
            if self._is_config_assignment(node):
                config_info = self._analyze_config(node, content)
                analysis['config_vars'].append(config_info)
    
    def _analyze_function(self, node: ast.FunctionDef, content: str) -> Dict:
        """함수 분석"""
        # 함수 시그니처 생성
        args = [arg.arg for arg in node.args.args]
        defaults = len(node.args.defaults)
        
        signature = {
            'name': node.name,
            'args': args,
            'arg_count': len(args),
            'has_defaults': defaults > 0,
            'default_count': defaults,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'has_decorators': bool(node.decorator_list),
            'decorator_count': len(node.decorator_list),
            'line_start': node.lineno,
            'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
        }
        
        # 함수 본문 해시
        func_lines = content.split('\n')[node.lineno-1:signature['line_end']]
        func_body = '\n'.join(func_lines)
        
        # 변수명을 제거한 정규화된 버전
        normalized_body = self._normalize_code(func_body)
        signature['body_hash'] = hashlib.md5(normalized_body.encode()).hexdigest()
        signature['full_hash'] = hashlib.md5(func_body.encode()).hexdigest()
        
        return signature
    
    def _analyze_class(self, node: ast.ClassDef, content: str) -> Dict:
        """클래스 분석"""
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        signature = {
            'name': node.name,
            'bases': [self._get_base_name(base) for base in node.bases],
            'methods': methods,
            'method_count': len(methods),
            'has_decorators': bool(node.decorator_list),
            'line_start': node.lineno,
            'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
        }
        
        return signature
    
    def _analyze_import(self, node: ast.AST) -> Dict:
        """Import 분석"""
        if isinstance(node, ast.Import):
            return {
                'type': 'import',
                'modules': [alias.name for alias in node.names],
                'aliases': [(alias.name, alias.asname) for alias in node.names if alias.asname]
            }
        elif isinstance(node, ast.ImportFrom):
            return {
                'type': 'from_import',
                'module': node.module,
                'names': [alias.name for alias in node.names],
                'level': node.level,
                'aliases': [(alias.name, alias.asname) for alias in node.names if alias.asname]
            }
    
    def _analyze_decorator(self, node: ast.AST) -> Dict:
        """데코레이터 분석"""
        if isinstance(node, ast.Name):
            return {'type': 'simple', 'name': node.id}
        elif isinstance(node, ast.Call):
            func_name = self._get_name_from_node(node.func)
            return {
                'type': 'call',
                'name': func_name,
                'args': len(node.args),
                'keywords': len(node.keywords)
            }
        else:
            return {'type': 'complex', 'pattern': ast.dump(node)[:100]}
    
    def _analyze_config(self, node: ast.Assign, content: str) -> Dict:
        """설정 변수 분석"""
        targets = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                targets.append(target.id)
        
        value_type = type(node.value).__name__
        
        return {
            'variables': targets,
            'value_type': value_type,
            'line': node.lineno
        }
    
    def _is_auth_function(self, node: ast.FunctionDef) -> bool:
        """인증 관련 함수 판별"""
        auth_keywords = ['auth', 'login', 'token', 'jwt', 'verify', 'validate', 'authenticate']
        return any(keyword in node.name.lower() for keyword in auth_keywords)
    
    def _is_validation_function(self, node: ast.FunctionDef) -> bool:
        """검증 함수 판별"""
        validation_keywords = ['validate', 'check', 'verify', 'ensure', 'assert']
        return any(keyword in node.name.lower() for keyword in validation_keywords)
    
    def _is_utility_function(self, node: ast.FunctionDef) -> bool:
        """유틸리티 함수 판별"""
        utility_keywords = ['helper', 'util', 'format', 'parse', 'convert', 'transform']
        return any(keyword in node.name.lower() for keyword in utility_keywords)
    
    def _is_api_decorator(self, decorator: ast.AST) -> bool:
        """API 데코레이터 판별"""
        if isinstance(decorator, ast.Call):
            func_name = self._get_name_from_node(decorator.func)
            api_decorators = ['app.get', 'app.post', 'app.put', 'app.delete', 'router.get', 'router.post']
            return any(api_dec in func_name for api_dec in api_decorators)
        return False
    
    def _is_config_assignment(self, node: ast.Assign) -> bool:
        """설정 변수 할당 판별"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                config_patterns = ['URL', 'HOST', 'PORT', 'KEY', 'SECRET', 'CONFIG', 'SETTING']
                if any(pattern in var_name.upper() for pattern in config_patterns):
                    return True
        return False
    
    def _extract_api_endpoint(self, func_node: ast.FunctionDef, decorator: ast.AST) -> Dict:
        """API 엔드포인트 정보 추출"""
        endpoint_info = {
            'function_name': func_node.name,
            'method': 'unknown',
            'path': 'unknown'
        }
        
        if isinstance(decorator, ast.Call):
            func_name = self._get_name_from_node(decorator.func)
            if '.' in func_name:
                endpoint_info['method'] = func_name.split('.')[-1].upper()
            
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                endpoint_info['path'] = decorator.args[0].value
        
        return endpoint_info
    
    def _normalize_code(self, code: str) -> str:
        """코드 정규화 (변수명 제거, 공백 정리)"""
        # 간단한 정규화 - 실제로는 더 정교해야 함
        import re
        # 문자열 리터럴 제거
        code = re.sub(r'["\'].*?["\']', '""', code)
        # 숫자 제거
        code = re.sub(r'\b\d+\b', '0', code)
        # 공백 정리
        code = re.sub(r'\s+', ' ', code)
        return code.strip()
    
    def _get_name_from_node(self, node: ast.AST) -> str:
        """AST 노드에서 이름 추출"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name_from_node(node.value)}.{node.attr}"
        return str(type(node).__name__)
    
    def _get_base_name(self, node: ast.AST) -> str:
        """기본 클래스 이름 추출"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name_from_node(node.value)}.{node.attr}"
        return "unknown"
    
    def find_duplicates(self) -> Dict[str, List]:
        """모든 중복 찾기"""
        logger.info("🔍 포괄적 중복 분석 시작...")
        
        all_files = []
        
        # 서비스 파일들
        for service in self.services:
            service_path = self.root_dir / service
            if service_path.exists():
                for py_file in service_path.rglob("*.py"):
                    if '__pycache__' not in str(py_file):
                        all_files.append(py_file)
        
        # 추가 파일들
        all_files.extend(self.additional_files)
        
        logger.info(f"📁 총 {len(all_files)}개 파일 분석")
        
        # 각 파일 분석
        for file_path in all_files:
            analysis = self.analyze_file(file_path)
            if 'error' in analysis:
                continue
                
            self._collect_patterns(analysis)
        
        # 중복 찾기
        duplicates = self._identify_duplicates()
        
        return duplicates
    
    def _collect_patterns(self, analysis: Dict[str, Any]):
        """패턴 수집"""
        file_path = analysis['file_path']
        
        # 함수 패턴
        for func in analysis['functions']:
            key = f"{func['name']}_args{func['arg_count']}"
            self.function_hashes[key].append({
                'file': file_path,
                'function': func
            })
            
            # 본문 해시별로도 수집
            self.code_blocks[func['body_hash']].append({
                'file': file_path,
                'type': 'function',
                'name': func['name'],
                'details': func
            })
        
        # 클래스 패턴
        for cls in analysis['classes']:
            key = f"{cls['name']}_methods{cls['method_count']}"
            self.class_signatures[key].append({
                'file': file_path,
                'class': cls
            })
        
        # Import 패턴
        for imp in analysis['imports']:
            if imp['type'] == 'from_import' and imp['module']:
                key = f"{imp['module']}_{'_'.join(imp['names'])}"
                self.import_patterns[key].append({
                    'file': file_path,
                    'import': imp
                })
        
        # API 엔드포인트 패턴
        for endpoint in analysis['api_endpoints']:
            key = f"{endpoint['method']}_{endpoint['path']}"
            self.api_endpoint_patterns[key].append({
                'file': file_path,
                'endpoint': endpoint
            })
        
        # 인증 패턴
        for auth in analysis['auth_patterns']:
            key = f"auth_{auth['name']}"
            self.auth_patterns[key].append({
                'file': file_path,
                'function': auth
            })
        
        # 검증 패턴
        for validation in analysis['validation_patterns']:
            key = f"validation_{validation['name']}"
            self.validation_patterns[key].append({
                'file': file_path,
                'function': validation
            })
        
        # 유틸리티 패턴
        for utility in analysis['utility_patterns']:
            key = f"utility_{utility['name']}"
            self.utility_patterns[key].append({
                'file': file_path,
                'function': utility
            })
    
    def _identify_duplicates(self) -> Dict[str, List]:
        """중복 식별"""
        duplicates = {
            'identical_functions': [],      # 완전히 동일한 함수
            'similar_functions': [],        # 유사한 함수
            'duplicate_classes': [],        # 중복 클래스
            'redundant_imports': [],        # 중복 import
            'duplicate_endpoints': [],      # 중복 API 엔드포인트
            'auth_duplicates': [],         # 인증 로직 중복
            'validation_duplicates': [],   # 검증 로직 중복
            'utility_duplicates': [],      # 유틸리티 함수 중복
            'code_block_duplicates': []    # 코드 블록 중복
        }
        
        # 완전히 동일한 코드 블록
        for hash_key, items in self.code_blocks.items():
            if len(items) > 1:
                duplicates['code_block_duplicates'].append({
                    'hash': hash_key,
                    'count': len(items),
                    'locations': items
                })
        
        # 함수명과 인자 수가 같은 것들
        for func_key, items in self.function_hashes.items():
            if len(items) > 1:
                duplicates['similar_functions'].append({
                    'pattern': func_key,
                    'count': len(items),
                    'locations': items
                })
        
        # 클래스 중복
        for class_key, items in self.class_signatures.items():
            if len(items) > 1:
                duplicates['duplicate_classes'].append({
                    'pattern': class_key,
                    'count': len(items),
                    'locations': items
                })
        
        # Import 중복
        for import_key, items in self.import_patterns.items():
            if len(items) > 1:
                duplicates['redundant_imports'].append({
                    'pattern': import_key,
                    'count': len(items),
                    'locations': items
                })
        
        # API 엔드포인트 중복
        for endpoint_key, items in self.api_endpoint_patterns.items():
            if len(items) > 1:
                duplicates['duplicate_endpoints'].append({
                    'pattern': endpoint_key,
                    'count': len(items),
                    'locations': items
                })
        
        # 인증 로직 중복
        for auth_key, items in self.auth_patterns.items():
            if len(items) > 1:
                duplicates['auth_duplicates'].append({
                    'pattern': auth_key,
                    'count': len(items),
                    'locations': items
                })
        
        # 검증 로직 중복
        for validation_key, items in self.validation_patterns.items():
            if len(items) > 1:
                duplicates['validation_duplicates'].append({
                    'pattern': validation_key,
                    'count': len(items),
                    'locations': items
                })
        
        # 유틸리티 함수 중복
        for utility_key, items in self.utility_patterns.items():
            if len(items) > 1:
                duplicates['utility_duplicates'].append({
                    'pattern': utility_key,
                    'count': len(items),
                    'locations': items
                })
        
        return duplicates
    
    def generate_report(self, duplicates: Dict[str, List]) -> Dict[str, Any]:
        """상세 보고서 생성"""
        total_duplicates = sum(len(category) for category in duplicates.values())
        
        report = {
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'total_files_analyzed': len(self.additional_files) + sum(
                len(list((self.root_dir / service).rglob("*.py"))) 
                for service in self.services 
                if (self.root_dir / service).exists()
            ),
            'summary': {
                'total_duplicate_patterns': total_duplicates,
                'categories': {category: len(items) for category, items in duplicates.items()},
                'high_priority_issues': []
            },
            'detailed_duplicates': duplicates,
            'recommendations': []
        }
        
        # 우선순위 이슈 식별
        if duplicates['identical_functions']:
            report['summary']['high_priority_issues'].append("완전히 동일한 함수들이 발견됨")
        if duplicates['duplicate_endpoints']:
            report['summary']['high_priority_issues'].append("중복된 API 엔드포인트 발견")
        if duplicates['auth_duplicates']:
            report['summary']['high_priority_issues'].append("인증 로직이 중복됨")
        
        # 권장사항
        if total_duplicates > 0:
            report['recommendations'].extend([
                "arrakis-common 라이브러리 확장으로 중복 제거",
                "공통 유틸리티 모듈 생성",
                "API 라우터 통합",
                "인증/검증 미들웨어 표준화"
            ])
        
        return report


def main():
    """메인 실행 함수"""
    detector = AdvancedDuplicateDetector("/Users/isihyeon/Desktop/Arrakis-Project")
    
    logger.info("🚀 고급 중복 코드 분석 시작")
    logger.info("=" * 60)
    
    duplicates = detector.find_duplicates()
    report = detector.generate_report(duplicates)
    
    # 콘솔 출력
    logger.info(f"📊 총 {report['total_files_analyzed']}개 파일 분석 완료")
    logger.info(f"🔍 중복 패턴 {report['summary']['total_duplicate_patterns']}개 발견")
    
    for category, count in report['summary']['categories'].items():
        if count > 0:
            logger.info(f"  - {category}: {count}개")
    
    if report['summary']['high_priority_issues']:
        logger.warning("⚠️  우선순위 이슈:")
        for issue in report['summary']['high_priority_issues']:
            logger.warning(f"  - {issue}")
    
    # 상세 보고서 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"comprehensive_duplicate_analysis_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 상세 분석 보고서 저장: {report_file}")
    
    if report['summary']['total_duplicate_patterns'] == 0:
        logger.info("🎉 중복 코드 없음! 코드베이스가 최적화되어 있습니다.")
    else:
        logger.warning(f"🔧 {report['summary']['total_duplicate_patterns']}개 중복 패턴 해결 필요")
    
    return report


if __name__ == "__main__":
    main()