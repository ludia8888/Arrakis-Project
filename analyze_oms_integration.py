#!/usr/bin/env python3
"""
OMS 전체 통합성 분석 스크립트
Core 모듈, 미들웨어, API, MSA 연동을 종합적으로 검증
"""

import os
import sys
import re
import json
import ast
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ontology-management-service'))


class OMSIntegrationAnalyzer:
    """OMS 통합성 분석기"""
    
    def __init__(self):
        self.oms_path = Path("ontology-management-service")
        self.user_service_path = Path("user-service")
        self.audit_service_path = Path("audit-service")
        
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "architecture": {},
            "integration_flows": {},
            "duplications": [],
            "issues": [],
            "recommendations": []
        }
        
    def analyze_oms_structure(self):
        """OMS 내부 구조 분석"""
        print("\n🔍 OMS 내부 구조 분석 중...")
        print("="*80)
        
        # 1. API 라우트 분석
        api_routes = self._analyze_api_routes()
        
        # 2. Core 서비스 분석
        core_services = self._analyze_core_services()
        
        # 3. 미들웨어 체인 분석
        middleware_chain = self._analyze_middleware_chain()
        
        # 4. 의존성 주입 분석
        di_structure = self._analyze_dependency_injection()
        
        self.report["architecture"]["oms"] = {
            "api_routes": api_routes,
            "core_services": core_services,
            "middleware_chain": middleware_chain,
            "dependency_injection": di_structure
        }
        
        # API -> Service 매핑 검증
        self._verify_api_service_mapping(api_routes, core_services)
        
    def _analyze_api_routes(self) -> Dict:
        """API 라우트 구조 분석"""
        print("\n📡 API 라우트 분석...")
        
        routes = {}
        api_path = self.oms_path / "api" / "v1"
        
        if not api_path.exists():
            self.report["issues"].append("API v1 디렉토리를 찾을 수 없음")
            return routes
            
        for route_file in api_path.glob("*_routes.py"):
            if route_file.name == "__init__.py":
                continue
                
            module_name = route_file.stem
            routes[module_name] = {
                "file": str(route_file),
                "endpoints": [],
                "dependencies": []
            }
            
            try:
                with open(route_file, 'r') as f:
                    content = f.read()
                    
                # 엔드포인트 추출
                endpoint_pattern = r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
                endpoints = re.findall(endpoint_pattern, content)
                routes[module_name]["endpoints"] = [{"method": m, "path": p} for m, p in endpoints]
                
                # 의존성 추출
                depends_pattern = r'Depends\(([^)]+)\)'
                dependencies = re.findall(depends_pattern, content)
                routes[module_name]["dependencies"] = list(set(dependencies))
                
                # 사용하는 서비스 추출
                service_imports = re.findall(r'from core\.(\w+)\.service import', content)
                routes[module_name]["services"] = service_imports
                
            except Exception as e:
                self.report["issues"].append(f"라우트 파일 분석 실패 {route_file}: {e}")
                
        print(f"  ✅ {len(routes)}개의 라우트 모듈 발견")
        return routes
        
    def _analyze_core_services(self) -> Dict:
        """Core 서비스 구조 분석"""
        print("\n⚙️  Core 서비스 분석...")
        
        services = {}
        core_path = self.oms_path / "core"
        
        # 주요 서비스 디렉토리들
        service_dirs = ["schema", "document", "branch", "property", "validation", 
                       "iam", "audit", "time_travel", "versioning"]
        
        for service_name in service_dirs:
            service_path = core_path / service_name
            if not service_path.exists():
                continue
                
            service_file = service_path / "service.py"
            if service_file.exists():
                services[service_name] = self._analyze_service_file(service_file)
                
        print(f"  ✅ {len(services)}개의 Core 서비스 발견")
        return services
        
    def _analyze_service_file(self, service_file: Path) -> Dict:
        """서비스 파일 분석"""
        service_info = {
            "file": str(service_file),
            "classes": [],
            "methods": [],
            "dependencies": [],
            "repositories": [],
            "external_calls": []
        }
        
        try:
            with open(service_file, 'r') as f:
                content = f.read()
                
            # 클래스 추출
            class_pattern = r'class\s+(\w+Service\w*)'
            service_info["classes"] = re.findall(class_pattern, content)
            
            # 주요 메서드 추출
            method_pattern = r'async\s+def\s+(\w+)\s*\('
            service_info["methods"] = re.findall(method_pattern, content)
            
            # Repository 의존성
            repo_pattern = r'(\w+Repository)'
            service_info["repositories"] = list(set(re.findall(repo_pattern, content)))
            
            # 외부 서비스 호출
            if "httpx" in content or "requests" in content:
                http_calls = re.findall(r'(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']', content)
                service_info["external_calls"] = [{"method": m, "url": u} for m, u in http_calls]
                
            # 다른 서비스 의존성
            service_imports = re.findall(r'from\s+core\.(\w+)\.(\w+)\s+import', content)
            service_info["dependencies"] = list(set([f"{m}.{s}" for m, s in service_imports]))
            
        except Exception as e:
            self.report["issues"].append(f"서비스 파일 분석 실패 {service_file}: {e}")
            
        return service_info
        
    def _analyze_middleware_chain(self) -> List[Dict]:
        """미들웨어 체인 분석"""
        print("\n🔗 미들웨어 체인 분석...")
        
        app_file = self.oms_path / "bootstrap" / "app.py"
        middleware_chain = []
        
        try:
            with open(app_file, 'r') as f:
                content = f.read()
                
            # 미들웨어 추가 순서 추출
            middleware_pattern = r'app\.add_middleware\((\w+)(?:,\s*([^)]+))?\)'
            middlewares = re.findall(middleware_pattern, content)
            
            for i, (mw_name, mw_args) in enumerate(middlewares):
                middleware_info = {
                    "name": mw_name,
                    "order": i,
                    "args": mw_args.strip() if mw_args else None
                }
                
                # 미들웨어 파일 찾기
                mw_file = self._find_middleware_file(mw_name)
                if mw_file:
                    middleware_info["file"] = str(mw_file)
                    middleware_info["details"] = self._analyze_middleware_file(mw_file)
                    
                middleware_chain.append(middleware_info)
                
        except Exception as e:
            self.report["issues"].append(f"미들웨어 체인 분석 실패: {e}")
            
        print(f"  ✅ {len(middleware_chain)}개의 미들웨어 발견")
        return middleware_chain
        
    def _find_middleware_file(self, middleware_name: str) -> Optional[Path]:
        """미들웨어 파일 찾기"""
        # 일반적인 미들웨어 위치들
        search_paths = [
            self.oms_path / "middleware",
            self.oms_path / "core" / "iam",
            self.oms_path / "core" / "auth_utils"
        ]
        
        # 파일명 변환 (CamelCase -> snake_case)
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', middleware_name).lower()
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
                
            # 직접 파일 찾기
            possible_files = [
                search_path / f"{snake_case}.py",
                search_path / f"{snake_case.replace('_middleware', '')}.py",
                search_path / f"{snake_case.replace('middleware', 'middleware')}.py"
            ]
            
            for possible_file in possible_files:
                if possible_file.exists():
                    return possible_file
                    
        return None
        
    def _analyze_middleware_file(self, mw_file: Path) -> Dict:
        """미들웨어 파일 분석"""
        mw_info = {
            "intercepts": [],
            "modifies_request": False,
            "modifies_response": False,
            "dependencies": []
        }
        
        try:
            with open(mw_file, 'r') as f:
                content = f.read()
                
            # request.state 접근 패턴
            if "request.state" in content:
                state_patterns = re.findall(r'request\.state\.(\w+)', content)
                mw_info["intercepts"] = list(set(state_patterns))
                
            # 요청/응답 수정 여부
            mw_info["modifies_request"] = "request." in content and "=" in content
            mw_info["modifies_response"] = "response" in content and ("headers" in content or "status_code" in content)
            
            # 의존성
            imports = re.findall(r'from\s+([\w.]+)\s+import', content)
            mw_info["dependencies"] = [imp for imp in imports if "core" in imp or "shared" in imp]
            
        except Exception as e:
            pass
            
        return mw_info
        
    def _analyze_dependency_injection(self) -> Dict:
        """의존성 주입 구조 분석"""
        print("\n💉 의존성 주입 구조 분석...")
        
        di_info = {
            "container_type": None,
            "providers": [],
            "injections": []
        }
        
        # containers.py 분석
        container_file = self.oms_path / "bootstrap" / "containers.py"
        if container_file.exists():
            try:
                with open(container_file, 'r') as f:
                    content = f.read()
                    
                # Container 타입 확인
                if "dependency_injector" in content:
                    di_info["container_type"] = "dependency_injector"
                elif "punq" in content:
                    di_info["container_type"] = "punq"
                    
                # Provider 패턴 찾기
                provider_pattern = r'(\w+)\s*=\s*providers\.(\w+)\('
                providers = re.findall(provider_pattern, content)
                di_info["providers"] = [{"name": name, "type": ptype} for name, ptype in providers]
                
            except Exception as e:
                self.report["issues"].append(f"DI 컨테이너 분석 실패: {e}")
                
        print(f"  ✅ DI 타입: {di_info['container_type']}, {len(di_info['providers'])}개 프로바이더")
        return di_info
        
    def _verify_api_service_mapping(self, api_routes: Dict, core_services: Dict):
        """API와 서비스 매핑 검증"""
        print("\n🔍 API-Service 매핑 검증...")
        
        # API가 사용하는 서비스와 실제 서비스 비교
        for route_name, route_info in api_routes.items():
            used_services = route_info.get("services", [])
            for service in used_services:
                if service not in core_services:
                    self.report["issues"].append(
                        f"API {route_name}이 존재하지 않는 서비스 {service}를 참조"
                    )
                    
        print("  ✅ API-Service 매핑 검증 완료")
        
    def analyze_msa_integration(self):
        """MSA 간 통합 분석"""
        print("\n🌐 MSA 통합 분석 중...")
        print("="*80)
        
        # 1. 서비스 간 통신 패턴 분석
        communication = self._analyze_service_communication()
        
        # 2. 인증/인가 흐름 분석
        auth_flow = self._analyze_auth_flow()
        
        # 3. 이벤트 기반 통신 분석
        event_flow = self._analyze_event_flow()
        
        # 4. 데이터 일관성 분석
        data_consistency = self._analyze_data_consistency()
        
        self.report["integration_flows"]["msa"] = {
            "communication": communication,
            "auth_flow": auth_flow,
            "event_flow": event_flow,
            "data_consistency": data_consistency
        }
        
    def _analyze_service_communication(self) -> Dict:
        """서비스 간 통신 분석"""
        print("\n📡 서비스 간 통신 분석...")
        
        communication = {
            "oms_to_user": [],
            "oms_to_audit": [],
            "user_to_oms": [],
            "audit_to_oms": []
        }
        
        # OMS에서 다른 서비스 호출 찾기
        integration_path = self.oms_path / "core" / "integrations"
        if integration_path.exists():
            for client_file in integration_path.glob("*_client.py"):
                client_info = self._analyze_service_client(client_file)
                
                if "user" in client_file.name:
                    communication["oms_to_user"].extend(client_info["endpoints"])
                elif "audit" in client_file.name:
                    communication["oms_to_audit"].extend(client_info["endpoints"])
                    
        # Shared 클라이언트 분석
        shared_path = self.oms_path / "shared"
        if shared_path.exists():
            audit_client = shared_path / "audit_client.py"
            if audit_client.exists():
                client_info = self._analyze_service_client(audit_client)
                communication["oms_to_audit"].extend(client_info["endpoints"])
                
        print(f"  ✅ OMS→User: {len(communication['oms_to_user'])}개 엔드포인트")
        print(f"  ✅ OMS→Audit: {len(communication['oms_to_audit'])}개 엔드포인트")
        
        return communication
        
    def _analyze_service_client(self, client_file: Path) -> Dict:
        """서비스 클라이언트 분석"""
        client_info = {
            "file": str(client_file),
            "endpoints": [],
            "methods": []
        }
        
        try:
            with open(client_file, 'r') as f:
                content = f.read()
                
            # HTTP 호출 패턴 찾기
            http_patterns = [
                r'self\._?(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']',
                r'httpx\.(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']',
                r'requests\.(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']'
            ]
            
            endpoints = []
            for pattern in http_patterns:
                found = re.findall(pattern, content)
                endpoints.extend(found)
                
            client_info["endpoints"] = list(set(endpoints))
            
            # 메서드 찾기
            method_pattern = r'async\s+def\s+(\w+)\s*\('
            client_info["methods"] = re.findall(method_pattern, content)
            
        except Exception as e:
            self.report["issues"].append(f"클라이언트 분석 실패 {client_file}: {e}")
            
        return client_info
        
    def _analyze_auth_flow(self) -> Dict:
        """인증/인가 흐름 분석"""
        print("\n🔐 인증/인가 흐름 분석...")
        
        auth_flow = {
            "auth_middleware": None,
            "jwt_validation": None,
            "user_service_integration": None,
            "iam_integration": None,
            "flow_diagram": []
        }
        
        # AuthMiddleware 분석
        auth_mw = self.oms_path / "middleware" / "auth_middleware.py"
        if auth_mw.exists():
            with open(auth_mw, 'r') as f:
                content = f.read()
                
            # JWT 검증 방식
            if "PyJWKClient" in content:
                auth_flow["jwt_validation"] = "JWKS"
            elif "jwt.decode" in content:
                auth_flow["jwt_validation"] = "Local Secret"
                
            # User Service 통합
            if "user_service" in content.lower():
                auth_flow["user_service_integration"] = True
                
            # 인증 흐름
            auth_flow["flow_diagram"] = [
                "1. 클라이언트 → OMS (Bearer Token)",
                "2. AuthMiddleware가 토큰 검증",
                "3. JWKS를 통한 User Service 검증" if auth_flow["jwt_validation"] == "JWKS" else "3. 로컬 시크릿으로 검증",
                "4. request.state.user 설정",
                "5. ScopeRBACMiddleware가 권한 검사",
                "6. IAM Service에서 권한 조회" if "iam_integration" in content else "6. 로컬 권한 검사"
            ]
            
        print("  ✅ 인증 흐름 분석 완료")
        return auth_flow
        
    def _analyze_event_flow(self) -> Dict:
        """이벤트 기반 통신 분석"""
        print("\n📨 이벤트 기반 통신 분석...")
        
        event_flow = {
            "publishers": [],
            "consumers": [],
            "event_types": [],
            "messaging_system": None
        }
        
        # Event Publisher 찾기
        events_path = self.oms_path / "core" / "events"
        if events_path.exists():
            for pub_file in events_path.glob("*_publisher.py"):
                with open(pub_file, 'r') as f:
                    content = f.read()
                    
                # 이벤트 타입 추출
                event_types = re.findall(r'event_type["\']?\s*[:=]\s*["\']([^"\']+)["\']', content)
                event_flow["event_types"].extend(event_types)
                
                # Publisher 정보
                event_flow["publishers"].append({
                    "file": str(pub_file),
                    "events": event_types
                })
                
        # Event Consumer 찾기
        consumer_path = self.oms_path / "core" / "event_consumer"
        if consumer_path.exists():
            for consumer_file in consumer_path.glob("*_handler.py"):
                event_flow["consumers"].append(str(consumer_file))
                
        # Messaging System 확인
        if any("nats" in str(f).lower() for f in [events_path, consumer_path] if f.exists()):
            event_flow["messaging_system"] = "NATS"
        elif any("kafka" in str(f).lower() for f in [events_path, consumer_path] if f.exists()):
            event_flow["messaging_system"] = "Kafka"
        elif any("rabbit" in str(f).lower() for f in [events_path, consumer_path] if f.exists()):
            event_flow["messaging_system"] = "RabbitMQ"
            
        print(f"  ✅ {len(event_flow['publishers'])}개 Publisher, {len(event_flow['consumers'])}개 Consumer")
        return event_flow
        
    def _analyze_data_consistency(self) -> Dict:
        """데이터 일관성 분석"""
        print("\n🗂️  데이터 일관성 분석...")
        
        consistency = {
            "shared_models": [],
            "data_boundaries": {},
            "consistency_patterns": []
        }
        
        # 각 서비스의 모델 분석
        services = {
            "oms": self.oms_path / "models",
            "user": self.user_service_path / "app" / "models",
            "audit": self.audit_service_path / "models"
        }
        
        service_models = {}
        for service_name, models_path in services.items():
            if models_path.exists():
                models = []
                for model_file in models_path.glob("*.py"):
                    if model_file.name != "__init__.py":
                        models.append(model_file.stem)
                service_models[service_name] = models
                
        # 공통 모델 찾기
        if len(service_models) > 1:
            all_models = [set(models) for models in service_models.values()]
            shared = all_models[0]
            for model_set in all_models[1:]:
                shared = shared.intersection(model_set)
            consistency["shared_models"] = list(shared)
            
        # 데이터 경계 정의
        consistency["data_boundaries"] = {
            "oms": "Schema, Document, Branch 관리",
            "user": "사용자 인증, 프로필, 권한",
            "audit": "감사 로그, 이벤트 추적"
        }
        
        # 일관성 패턴
        # event_flow는 이전 분석 결과 참조
        messaging_system = self.report.get("integration_flows", {}).get("msa", {}).get("event_flow", {}).get("messaging_system")
        consistency["consistency_patterns"] = [
            "Event Sourcing을 통한 최종 일관성" if messaging_system else "동기식 API 호출",
            "각 서비스별 독립적인 데이터베이스",
            "ID 참조를 통한 느슨한 결합"
        ]
        
        print("  ✅ 데이터 일관성 분석 완료")
        return consistency
        
    def check_duplications(self):
        """중복 구현 검사"""
        print("\n🔍 중복 구현 검사 중...")
        print("="*80)
        
        duplications = []
        
        # 1. 인증 관련 중복
        auth_duplication = self._check_auth_duplication()
        if auth_duplication:
            duplications.extend(auth_duplication)
            
        # 2. 로깅/감사 중복
        audit_duplication = self._check_audit_duplication()
        if audit_duplication:
            duplications.extend(audit_duplication)
            
        # 3. 유틸리티 중복
        util_duplication = self._check_utility_duplication()
        if util_duplication:
            duplications.extend(util_duplication)
            
        self.report["duplications"] = duplications
        
        if duplications:
            print(f"  ⚠️  {len(duplications)}개의 중복 구현 발견")
        else:
            print("  ✅ 중복 구현 없음")
            
    def _check_auth_duplication(self) -> List[Dict]:
        """인증 관련 중복 검사"""
        duplications = []
        
        # JWT 검증 로직 찾기
        jwt_implementations = []
        
        # OMS에서 JWT 구현 찾기
        for root, dirs, files in os.walk(self.oms_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            if "jwt.decode" in content or "PyJWT" in content:
                                jwt_implementations.append({
                                    "service": "oms",
                                    "file": str(file_path.relative_to(self.oms_path))
                                })
                    except:
                        pass
                        
        # 중복 검사
        if len(jwt_implementations) > 1:
            duplications.append({
                "type": "JWT Validation",
                "description": "여러 곳에서 JWT 검증 로직 구현",
                "locations": jwt_implementations,
                "recommendation": "공통 라이브러리로 통합 또는 User Service에 위임"
            })
            
        return duplications
        
    def _check_audit_duplication(self) -> List[Dict]:
        """감사 로깅 중복 검사"""
        duplications = []
        
        audit_implementations = {
            "oms_middleware": [],
            "oms_service": [],
            "audit_service": []
        }
        
        # OMS의 감사 구현 찾기
        # 1. AuditLogMiddleware
        audit_mw = self.oms_path / "middleware" / "audit_log.py"
        if audit_mw.exists():
            audit_implementations["oms_middleware"].append(str(audit_mw))
            
        # 2. Audit Service (core)
        audit_service = self.oms_path / "core" / "audit" / "audit_service.py"
        if audit_service.exists():
            audit_implementations["oms_service"].append(str(audit_service))
            
        # 3. Audit Client
        audit_client = self.oms_path / "shared" / "audit_client.py"
        if audit_client.exists():
            audit_implementations["oms_service"].append(str(audit_client))
            
        # 중복 여부 확인
        impl_count = sum(1 for v in audit_implementations.values() if v)
        if impl_count > 1:
            duplications.append({
                "type": "Audit Logging",
                "description": "감사 로깅이 여러 레이어에서 구현됨",
                "locations": audit_implementations,
                "recommendation": "Audit Service로 통합하고 OMS는 클라이언트만 사용"
            })
            
        return duplications
        
    def _check_utility_duplication(self) -> List[Dict]:
        """유틸리티 함수 중복 검사"""
        duplications = []
        
        # 공통 유틸리티 패턴
        utility_patterns = {
            "datetime_utils": r'def\s+(\w*format_date\w*|parse_date\w*|to_iso\w*)',
            "string_utils": r'def\s+(\w*snake_case\w*|camel_case\w*|slugify\w*)',
            "validation_utils": r'def\s+(\w*validate_email\w*|validate_url\w*|validate_uuid\w*)'
        }
        
        found_utils = defaultdict(list)
        
        # 각 서비스에서 유틸리티 찾기
        for service_name, service_path in [("oms", self.oms_path), 
                                          ("user", self.user_service_path),
                                          ("audit", self.audit_service_path)]:
            if not service_path.exists():
                continue
                
            for root, dirs, files in os.walk(service_path):
                # node_modules, venv 등 제외
                if any(skip in root for skip in ['node_modules', 'venv', '__pycache__', '.git']):
                    continue
                    
                for file in files:
                    if file.endswith('.py'):
                        file_path = Path(root) / file
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read()
                                
                            for util_type, pattern in utility_patterns.items():
                                matches = re.findall(pattern, content)
                                if matches:
                                    found_utils[util_type].append({
                                        "service": service_name,
                                        "file": str(file_path),
                                        "functions": matches
                                    })
                        except:
                            pass
                            
        # 중복 검사
        for util_type, locations in found_utils.items():
            if len(locations) > 1:
                services = set(loc["service"] for loc in locations)
                if len(services) > 1:
                    duplications.append({
                        "type": f"Utility Functions ({util_type})",
                        "description": f"{util_type} 유틸리티가 여러 서비스에서 구현됨",
                        "locations": locations,
                        "recommendation": "공통 라이브러리 패키지로 추출"
                    })
                    
        return duplications
        
    def generate_integration_test(self):
        """통합 테스트 시나리오 생성"""
        print("\n🧪 통합 테스트 시나리오 생성 중...")
        print("="*80)
        
        test_scenarios = []
        
        # 1. 인증 플로우 테스트
        test_scenarios.append({
            "name": "End-to-End Authentication Flow",
            "steps": [
                "1. User Service에서 사용자 생성",
                "2. 로그인하여 JWT 토큰 획득",
                "3. OMS API 호출 시 토큰 사용",
                "4. AuthMiddleware가 토큰 검증",
                "5. ScopeRBACMiddleware가 권한 확인",
                "6. API 응답 확인"
            ],
            "validation": [
                "JWT 토큰이 올바르게 생성되는가",
                "OMS가 User Service의 JWKS로 토큰을 검증하는가",
                "권한이 올바르게 적용되는가"
            ]
        })
        
        # 2. 데이터 생성 및 감사 플로우
        test_scenarios.append({
            "name": "Schema Creation with Audit Trail",
            "steps": [
                "1. 인증된 사용자로 스키마 생성 API 호출",
                "2. OMS가 스키마를 TerminusDB에 저장",
                "3. 성공 이벤트 발행",
                "4. Audit Service가 이벤트 수신 및 로그 저장",
                "5. 감사 로그 조회 API로 확인"
            ],
            "validation": [
                "스키마가 정상적으로 생성되는가",
                "감사 로그가 Audit Service에 기록되는가",
                "이벤트가 올바르게 전달되는가"
            ]
        })
        
        # 3. 서비스 장애 복원력 테스트
        test_scenarios.append({
            "name": "Service Resilience Test",
            "steps": [
                "1. User Service 중단",
                "2. OMS API 호출 (캐시된 인증 사용)",
                "3. Audit Service 중단",
                "4. OMS 작업 수행 (로컬 큐잉)",
                "5. 서비스 복구 후 데이터 동기화 확인"
            ],
            "validation": [
                "User Service 중단 시에도 캐시로 동작하는가",
                "Audit 로그가 큐에 저장되고 나중에 전송되는가",
                "Circuit Breaker가 정상 작동하는가"
            ]
        })
        
        self.report["integration_tests"] = test_scenarios
        print(f"  ✅ {len(test_scenarios)}개의 통합 테스트 시나리오 생성")
        
    def analyze_issues_and_recommendations(self):
        """문제점 분석 및 권장사항 도출"""
        print("\n📋 종합 분석 및 권장사항...")
        print("="*80)
        
        # 주요 문제점 정리
        critical_issues = []
        
        # 1. 의존성 문제
        if any("prometheus_client" in issue for issue in self.report["issues"]):
            critical_issues.append({
                "category": "Dependencies",
                "issue": "필수 패키지들이 설치되지 않아 Core 모듈 로드 실패",
                "impact": "HIGH",
                "solution": "requirements.txt 재설치 및 환경 설정"
            })
            
        # 2. 중복 구현
        if self.report["duplications"]:
            critical_issues.append({
                "category": "Architecture",
                "issue": "여러 서비스에서 동일 기능 중복 구현",
                "impact": "MEDIUM",
                "solution": "공통 라이브러리 추출 및 책임 경계 명확화"
            })
            
        # 3. 서비스 간 강한 결합
        auth_flow = self.report.get("integration_flows", {}).get("msa", {}).get("auth_flow", {})
        if auth_flow.get("jwt_validation") == "Local Secret":
            critical_issues.append({
                "category": "Security",
                "issue": "로컬 시크릿 사용으로 인한 보안 취약점",
                "impact": "HIGH",
                "solution": "JWKS 기반 검증으로 전환"
            })
            
        # 권장사항 생성
        recommendations = [
            {
                "priority": "IMMEDIATE",
                "action": "Core 모듈 의존성 해결",
                "steps": [
                    "pip install -r requirements.txt 실행",
                    "환경 변수 설정 (.env 파일)",
                    "common_security 패키지 경로 수정"
                ]
            },
            {
                "priority": "HIGH",
                "action": "중복 코드 제거 및 공통화",
                "steps": [
                    "공통 유틸리티 라이브러리 생성",
                    "감사 로깅을 Audit Service로 통합",
                    "JWT 검증을 User Service JWKS로 통합"
                ]
            },
            {
                "priority": "MEDIUM",
                "action": "서비스 간 계약 명확화",
                "steps": [
                    "OpenAPI 스펙 문서화",
                    "이벤트 스키마 정의",
                    "서비스 간 인터페이스 버전 관리"
                ]
            },
            {
                "priority": "MEDIUM",
                "action": "통합 테스트 자동화",
                "steps": [
                    "Docker Compose로 전체 환경 구성",
                    "E2E 테스트 시나리오 구현",
                    "CI/CD 파이프라인 통합"
                ]
            }
        ]
        
        self.report["critical_issues"] = critical_issues
        self.report["recommendations"] = recommendations
        
        # 요약 출력
        print(f"\n🚨 심각한 문제: {len(critical_issues)}개")
        for issue in critical_issues:
            print(f"  - [{issue['impact']}] {issue['issue']}")
            
        print(f"\n💡 권장사항: {len(recommendations)}개")
        for rec in recommendations:
            print(f"  - [{rec['priority']}] {rec['action']}")
            
    def generate_report(self):
        """최종 보고서 생성"""
        print("\n" + "="*80)
        print("📊 최종 통합성 분석 보고서")
        print("="*80)
        
        # 전체 건강도 점수 계산
        total_score = 100
        
        # 의존성 문제 (-30점)
        dependency_issues = sum(1 for issue in self.report["issues"] if "import" in issue.lower())
        if dependency_issues > 0:
            total_score -= min(30, dependency_issues * 5)
            
        # 중복 구현 (-20점)
        duplication_score = len(self.report["duplications"]) * 5
        total_score -= min(20, duplication_score)
        
        # 보안 문제 (-20점)
        auth_flow = self.report.get("integration_flows", {}).get("msa", {}).get("auth_flow", {})
        if auth_flow.get("jwt_validation") != "JWKS":
            total_score -= 20
            
        # 아키텍처 문제 (-10점)
        if not self.report.get("architecture", {}).get("oms", {}).get("dependency_injection", {}).get("container_type"):
            total_score -= 10
            
        print(f"\n🏆 전체 통합성 점수: {total_score}/100")
        
        if total_score >= 80:
            print("  ✅ 상태: 양호 - 마이너한 개선사항만 필요")
        elif total_score >= 60:
            print("  ⚠️  상태: 주의 필요 - 중요한 문제들을 해결해야 함")
        else:
            print("  ❌ 상태: 심각 - 즉시 조치가 필요함")
            
        # 상세 점수
        print(f"\n📈 세부 평가:")
        print(f"  - 의존성 관리: {30 - (total_score - (100 - 30))}/30")
        print(f"  - 코드 중복: {20 - min(20, len(self.report['duplications']) * 5)}/20")
        print(f"  - 보안: {'20/20' if auth_flow.get('jwt_validation') == 'JWKS' else '0/20'}")
        print(f"  - 아키텍처: {'10/10' if self.report.get('architecture', {}).get('oms', {}).get('dependency_injection', {}).get('container_type') else '0/10'}")
        
        # 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"oms_integration_analysis_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 상세 분석 보고서 저장됨: {filename}")
        
        return total_score
        
    def run(self):
        """전체 분석 실행"""
        print("🚀 OMS 통합성 분석 시작")
        print("="*80)
        
        # 1. OMS 내부 구조 분석
        self.analyze_oms_structure()
        
        # 2. MSA 통합 분석
        self.analyze_msa_integration()
        
        # 3. 중복 구현 검사
        self.check_duplications()
        
        # 4. 통합 테스트 시나리오 생성
        self.generate_integration_test()
        
        # 5. 문제점 분석 및 권장사항
        self.analyze_issues_and_recommendations()
        
        # 6. 최종 보고서
        score = self.generate_report()
        
        return score >= 60  # 60점 이상이면 기본적으로 작동 가능


def main():
    """메인 함수"""
    analyzer = OMSIntegrationAnalyzer()
    success = analyzer.run()
    
    if not success:
        print("\n⚠️  시스템 통합성에 심각한 문제가 있습니다!")
        print("   위의 권장사항을 참고하여 문제를 해결하세요.")
        sys.exit(1)
    else:
        print("\n✅ 시스템이 기본적으로 작동 가능한 상태입니다.")
        print("   권장사항을 적용하면 더욱 안정적인 시스템이 됩니다.")


if __name__ == "__main__":
    main()